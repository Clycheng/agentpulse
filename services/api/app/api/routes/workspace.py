import json
import os
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Body, Depends, HTTPException
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import Database, Row, get_db
from app.runtime.deepseek import DeepSeekAPIError, DeepSeekChatClient, DeepSeekNotConfigured
from app.runtime.hermes_client import HermesBackend, RunContext
from app.runtime.runner import (
    make_bridge_resolver,
    resolve_hermes_profile,
    stream_agent_run,
)
from app.runtime.profile_provisioner import build_provisioner_from_settings
from app.runtime.reflection import run_reflection
from app.runtime import approval_bridge
from app.runtime.runs import RunStatus, RunStateError, transition_run
from app.schemas.run import (
    LlmAgentExperience,
    LlmChatAgent,
    LlmChatMessage,
    LlmChatRequest,
    LlmKnowledgeSource,
)
from app.schemas.workspace import (
    AddConversationMembersRequest,
    BootstrapResponse,
    ClaimTaskRequest,
    CreateAgentRequest,
    CreateGroupRequest,
    CreateKnowledgeSourceRequest,
    CreateTaskRequest,
    RecruitAgentRequest,
    ResolveApprovalRequest,
    SendMessageRequest,
    SendMessageResponse,
    TaskOut,
    UpdateTaskRequest,
)
from app.schemas.agent_spec import AgentSpecOut, CredentialRequest
from app.services.workspace import (
    add_agent_experience,
    add_message,
    add_task_event,
    add_task_output,
    claim_task,
    create_agent,
    create_dm_conversation,
    create_knowledge_source,
    create_task,
    ensure_department,
    extract_recruit_intent,
    get_bootstrap,
    get_workspace_for_user,
    load_knowledge_context,
    new_id,
    now_iso,
    recruit_from_template,
    serialize_agent,
    serialize_approval,
    serialize_knowledge_source,
    serialize_message,
    serialize_task,
    update_task,
)
from app.orchestration.supply import create_agent_spec, provision, ProvisioningError
from app.orchestration.discussion import (
    run_discussion_round,
    build_discussion_context,
)

router = APIRouter(tags=["workspace"])


@router.get("/me/bootstrap", response_model=BootstrapResponse)
def bootstrap(
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    return get_bootstrap(conn, workspace["id"])


@router.post("/me/onboarding/complete")
def complete_onboarding(
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    conn.execute(
        "UPDATE workspaces SET onboarding_completed = ? WHERE id = ?",
        (True, workspace["id"]),
    )
    return {"ok": True}


@router.post("/agents")
def create_custom_agent(
    payload: CreateAgentRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    department = ensure_department(conn, workspace["id"], payload.department_name)

    # "Hire by role" (TD-07-T2): a role_bundle_key expands into its preset
    # capability list, merged (dedup, bundle-first) with any explicit keys.
    if payload.role_spec and payload.role_spec.role_bundle_key:
        from app.orchestration.capability_catalog import get_role_bundle
        try:
            bundle_keys = get_role_bundle(payload.role_spec.role_bundle_key)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload.role_spec.capability_keys = list(
            dict.fromkeys(bundle_keys + payload.role_spec.capability_keys)
        )

    # Collect skills from role_spec capability keys if provided
    skills: list[str] = []
    if payload.role_spec and payload.role_spec.capability_keys:
        from app.orchestration.capability_catalog import get_capability
        for key in payload.role_spec.capability_keys:
            try:
                cap = get_capability(key)
                skills.extend(cap.skills)
            except ValueError:
                pass  # unknown keys silently stripped
        skills = list(dict.fromkeys(skills))  # deduplicate preserving order

    agent_id = create_agent(
        conn,
        workspace_id=workspace["id"],
        department_id=department["id"],
        name=payload.name,
        role=payload.role_spec.role_name if payload.role_spec else (payload.description or "自定义员工"),
        description=payload.description,
        prompt=payload.prompt,
        skills=skills,
        mcps=[],
        source="custom",
    )
    create_dm_conversation(conn, workspace["id"], agent_id)
    agent = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()

    result = serialize_agent(agent)

    # If role_spec provided, create agent_spec + provision
    if payload.role_spec:
        try:
            spec = create_agent_spec(
                conn,
                agent_id=agent_id,
                workspace_id=workspace["id"],
                role_name=payload.role_spec.role_name,
                source_request=payload.role_spec.source_request,
                responsibilities=payload.role_spec.responsibilities,
                capability_keys=payload.role_spec.capability_keys,
            )
            spec = provision(conn, agent_id)
            result["spec"] = spec
        except (ValueError, ProvisioningError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


@router.post("/agents/recruit")
def recruit_agent(
    payload: RecruitAgentRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    try:
        agent = recruit_from_template(
            conn,
            workspace_id=workspace["id"],
            template_id=payload.template_id,
            department_name=payload.department_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serialize_agent(agent)


@router.get("/agents/{agent_id}/spec", response_model=AgentSpecOut)
def get_agent_spec(
    agent_id: str,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    # Verify agent belongs to workspace
    agent = conn.execute(
        "SELECT id FROM agents WHERE id = ? AND workspace_id = ?",
        (agent_id, workspace["id"]),
    ).fetchone()
    if agent is None:
        raise HTTPException(status_code=404, detail="员工不存在")
    spec = conn.execute(
        "SELECT * FROM agent_specs WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    if spec is None:
        raise HTTPException(status_code=404, detail="该员工尚未配置角色规格")
    return _serialize_spec_from_row(conn, spec)


def _verify_agent_in_workspace(conn: Database, current_user: Row, agent_id: str) -> Row:
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    agent = conn.execute(
        "SELECT id FROM agents WHERE id = ? AND workspace_id = ?",
        (agent_id, workspace["id"]),
    ).fetchone()
    if agent is None:
        raise HTTPException(status_code=404, detail="员工不存在")
    return agent


@router.get("/agents/{agent_id}/skills")
def list_agent_skills(
    agent_id: str,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    """TD-06-T1: auto-sedimented skills for an employee (growth trajectory)."""
    _verify_agent_in_workspace(conn, current_user, agent_id)
    spec = conn.execute(
        "SELECT hermes_profile FROM agent_specs WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    if spec is None or not spec["hermes_profile"]:
        return {"skills": []}
    provisioner = build_provisioner_from_settings()
    try:
        skills = provisioner.list_skills(spec["hermes_profile"])
    except Exception:
        skills = []
    return {"skills": skills}


@router.post("/agents/{agent_id}/reflect")
async def reflect_agent(
    agent_id: str,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    """TD-06-T1: manually trigger one skill-reflection pass (debug/demo)."""
    _verify_agent_in_workspace(conn, current_user, agent_id)
    spec = conn.execute(
        "SELECT status, hermes_profile FROM agent_specs WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()
    if spec is None or spec["status"] != "ready" or not spec["hermes_profile"]:
        raise HTTPException(status_code=400, detail="该员工尚无可运行的 Hermes profile")
    names = await run_reflection(
        conn,
        agent_id=agent_id,
        backend=HermesBackend(hermes_bin=settings.hermes_bin),
        provisioner=build_provisioner_from_settings(),
        hermes_work_root=settings.hermes_work_root,
    )
    return {"skills_learned": names}


@router.post("/agents/{agent_id}/credentials", response_model=AgentSpecOut)
def provide_credential(
    agent_id: str,
    payload: CredentialRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    agent = conn.execute(
        "SELECT id FROM agents WHERE id = ? AND workspace_id = ?",
        (agent_id, workspace["id"]),
    ).fetchone()
    if agent is None:
        raise HTTPException(status_code=404, detail="员工不存在")

    spec = conn.execute(
        "SELECT * FROM agent_specs WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    if spec is None:
        raise HTTPException(status_code=404, detail="该员工尚未配置角色规格")

    # Find capability that requires this credential
    caps = conn.execute(
        "SELECT * FROM agent_capabilities WHERE agent_id = ?",
        (agent_id,),
    ).fetchall()
    matching_cap = None
    for cap in caps:
        import json as _json
        required = _json.loads(cap["required_credentials_json"] or "[]")
        if payload.credential_name in required:
            matching_cap = cap
            break
    if matching_cap is None:
        raise HTTPException(
            status_code=400,
            detail=f"该员工不需要凭证 {payload.credential_name}",
        )

    # Security: credential value is NOT stored in DB.
    # It would go to ProfileProvisioner.write_credentials in production.
    # For v1 (RecordOnlyProvisioner), we just mark the capability as enabled.
    now = now_iso()

    # If this capability was credential_missing, mark as enabled
    if matching_cap["status"] == "credential_missing":
        conn.execute(
            "UPDATE agent_capabilities SET status = 'enabled', updated_at = ? WHERE id = ?",
            (now, matching_cap["id"]),
        )

    # Check if all capabilities are now enabled → update spec status
    _refresh_spec_status(conn, spec["id"])

    updated_spec = conn.execute(
        "SELECT * FROM agent_specs WHERE id = ?", (spec["id"],)
    ).fetchone()
    return _serialize_spec_from_row(conn, updated_spec)


@router.post("/agents/{agent_id}/provision", response_model=AgentSpecOut)
def provision_agent(
    agent_id: str,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    agent = conn.execute(
        "SELECT id FROM agents WHERE id = ? AND workspace_id = ?",
        (agent_id, workspace["id"]),
    ).fetchone()
    if agent is None:
        raise HTTPException(status_code=404, detail="员工不存在")
    try:
        spec = provision(conn, agent_id)
    except ProvisioningError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return spec


def _serialize_spec_from_row(conn: Database, spec: Row) -> dict:
    """Serialize an agent_spec row with its capabilities."""
    import json as _json
    capabilities = conn.execute(
        "SELECT * FROM agent_capabilities WHERE agent_id = ? ORDER BY created_at",
        (spec["agent_id"],),
    ).fetchall()
    return {
        "id": spec["id"],
        "agent_id": spec["agent_id"],
        "workspace_id": spec["workspace_id"],
        "role_name": spec["role_name"],
        "source_request": spec["source_request"],
        "responsibilities": _json.loads(spec["responsibilities_json"] or "[]"),
        "hermes_profile": spec["hermes_profile"],
        "status": spec["status"],
        "capabilities": [
            {
                "id": cap["id"],
                "agent_id": cap["agent_id"],
                "capability_key": cap["capability_key"],
                "skill_refs": _json.loads(cap["skill_refs_json"] or "[]"),
                "toolset_refs": _json.loads(cap["toolset_refs_json"] or "[]"),
                "mcp_refs": _json.loads(cap["mcp_refs_json"] or "[]"),
                "required_credentials": _json.loads(cap["required_credentials_json"] or "[]"),
                "risk_gate": cap["risk_gate"],
                "status": cap["status"],
                "created_at": cap["created_at"],
                "updated_at": cap["updated_at"],
            }
            for cap in capabilities
        ],
        "created_at": spec["created_at"],
        "updated_at": spec["updated_at"],
    }


def _refresh_spec_status(conn: Database, spec_id: str) -> None:
    """Check capabilities and update spec status if all enabled."""
    spec = conn.execute(
        "SELECT * FROM agent_specs WHERE id = ?", (spec_id,)
    ).fetchone()
    if spec is None:
        return
    caps = conn.execute(
        "SELECT status FROM agent_capabilities WHERE agent_id = ?",
        (spec["agent_id"],),
    ).fetchall()
    if not caps:
        return
    all_enabled = all(cap["status"] == "enabled" for cap in caps)
    if all_enabled and spec["status"] == "blocked_on_credentials":
        # All capabilities enabled → provision to ready
        from app.orchestration.supply import provision as _provision
        _provision(conn, spec["agent_id"])


@router.post("/knowledge-sources")
def create_workspace_knowledge_source(
    payload: CreateKnowledgeSourceRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    source = create_knowledge_source(
        conn,
        workspace_id=workspace["id"],
        title=payload.title,
        category=payload.category,
        content=payload.content,
        created_by=current_user["id"],
    )
    return serialize_knowledge_source(source)


@router.post("/conversations/group")
def create_group(
    payload: CreateGroupRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")

    found = conn.execute(
        f"""
        SELECT id, name FROM agents
        WHERE workspace_id = ? AND id IN ({",".join("?" for _ in payload.member_ids)})
        """,
        (workspace["id"], *payload.member_ids),
    ).fetchall()
    if len(found) != len(set(payload.member_ids)):
        raise HTTPException(status_code=400, detail="群成员不存在")

    conversation_id = new_id("conv")
    created_at = now_iso()
    conn.execute(
        """
        INSERT INTO conversations (id, workspace_id, kind, name, unread, created_at, updated_at)
        VALUES (?, ?, 'group', ?, 0, ?, ?)
        """,
        (conversation_id, workspace["id"], payload.name, created_at, created_at),
    )
    for agent_id in payload.member_ids:
        conn.execute(
            """
            INSERT INTO conversation_members (conversation_id, agent_id)
            VALUES (?, ?)
            """,
            (conversation_id, agent_id),
        )
    names = "、".join(row["name"] for row in found)
    add_message(
        conn,
        conversation_id=conversation_id,
        sender_type="system",
        sender_id="",
        content=f"你创建了群聊，拉入了 {names}",
    )
    if payload.related_task_ids:
        unique_task_ids = list(dict.fromkeys(payload.related_task_ids))
        tasks = conn.execute(
            f"""
            SELECT id, title FROM tasks
            WHERE workspace_id = ? AND id IN ({",".join("?" for _ in unique_task_ids)})
            """,
            (workspace["id"], *unique_task_ids),
        ).fetchall()
        if len(tasks) != len(unique_task_ids):
            raise HTTPException(status_code=400, detail="关联任务不存在")
        for task in tasks:
            conn.execute(
                """
                UPDATE tasks
                SET conversation_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (conversation_id, now_iso(), task["id"]),
            )
            add_task_event(
                conn,
                workspace_id=workspace["id"],
                task_id=task["id"],
                kind="conversation_linked",
                title="任务已关联群聊",
                content=f"已关联到 #{payload.name}，群聊内员工回复会沉淀为任务产出。",
                conversation_id=conversation_id,
            )
        task_names = "、".join(task["title"] for task in tasks)
        add_message(
            conn,
            conversation_id=conversation_id,
            sender_type="system",
            sender_id="",
            content=f"已关联任务：{task_names}",
        )
    return {"id": conversation_id}


@router.post("/conversations/{conversation_id}/members")
def add_group_members(
    conversation_id: str,
    payload: AddConversationMembersRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")

    conversation = conn.execute(
        """
        SELECT * FROM conversations
        WHERE id = ? AND workspace_id = ? AND kind = 'group'
        """,
        (conversation_id, workspace["id"]),
    ).fetchone()
    if conversation is None:
        raise HTTPException(status_code=404, detail="群聊不存在")

    unique_member_ids = list(dict.fromkeys(payload.member_ids))
    found = conn.execute(
        f"""
        SELECT id, name FROM agents
        WHERE workspace_id = ? AND id IN ({",".join("?" for _ in unique_member_ids)})
        """,
        (workspace["id"], *unique_member_ids),
    ).fetchall()
    if len(found) != len(unique_member_ids):
        raise HTTPException(status_code=400, detail="员工不存在")

    existing = conn.execute(
        """
        SELECT agent_id FROM conversation_members
        WHERE conversation_id = ?
        """,
        (conversation_id,),
    ).fetchall()
    existing_ids = {row["agent_id"] for row in existing}
    new_members = [row for row in found if row["id"] not in existing_ids]
    if not new_members:
        raise HTTPException(status_code=409, detail="这些员工已经在群聊里")

    for member in new_members:
        conn.execute(
            """
            INSERT INTO conversation_members (conversation_id, agent_id)
            VALUES (?, ?)
            """,
            (conversation_id, member["id"]),
        )

    names = "、".join(member["name"] for member in new_members)
    add_message(
        conn,
        conversation_id=conversation_id,
        sender_type="system",
        sender_id="",
        content=f"你拉入了 {names}",
    )
    return {"ok": True, "added_member_ids": [member["id"] for member in new_members]}


@router.post("/tasks", response_model=TaskOut)
def create_workspace_task(
    payload: CreateTaskRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    try:
        task = create_task(
            conn,
            workspace_id=workspace["id"],
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            owner_agent_id=payload.owner_agent_id,
            status=payload.status,
            progress=payload.progress,
            conversation_id=payload.conversation_id,
            due_date=payload.due_date,
            parent_task_id=payload.parent_task_id,
            consensus_brief_id=payload.consensus_brief_id,  # Gate condition
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_task(task)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_workspace_task(
    task_id: str,
    payload: UpdateTaskRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    try:
        task = update_task(
            conn,
            workspace_id=workspace["id"],
            task_id=task_id,
            changes=payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "task not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return serialize_task(task)


@router.post("/tasks/{task_id}/claim", response_model=TaskOut)
def claim_workspace_task(
    task_id: str,
    payload: ClaimTaskRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    try:
        task = claim_task(
            conn,
            workspace_id=workspace["id"],
            task_id=task_id,
            agent_id=payload.agent_id,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "task not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return serialize_task(task)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
)
async def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    conversation = conn.execute(
        """
        SELECT * FROM conversations
        WHERE id = ? AND workspace_id = ?
        """,
        (conversation_id, workspace["id"]),
    ).fetchone()
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    reply_agents = resolve_reply_agents(conn, workspace["id"], conversation, payload)
    if not reply_agents:
        raise HTTPException(status_code=400, detail="没有可回复的智能体")
    task_owner = reply_agents[0]

    user_message = add_message(
        conn,
        conversation_id=conversation_id,
        sender_type="user",
        sender_id=current_user["id"],
        content=payload.content,
    )
    created_task = None
    created_agent = None
    recruit_intent = extract_recruit_intent(payload.content)
    if recruit_intent is not None:
        department = ensure_department(
            conn, workspace["id"], recruit_intent["department_name"]
        )
        created_agent_id = create_agent(
            conn,
            workspace_id=workspace["id"],
            department_id=department["id"],
            name=recruit_intent["name"],
            role=recruit_intent["role"],
            description=recruit_intent["description"],
            prompt=recruit_intent["prompt"],
            skills=recruit_intent["skills"],
            mcps=recruit_intent["mcps"],
            source="chat_factory",
        )
        create_dm_conversation(conn, workspace["id"], created_agent_id)
        created_agent = conn.execute(
            "SELECT * FROM agents WHERE id = ?", (created_agent_id,)
        ).fetchone()
        add_message(
            conn,
            conversation_id=conversation_id,
            sender_type="system",
            sender_id="",
            content=(
                f"已创建员工：{created_agent['name']}，加入"
                f"{recruit_intent['department_name']}。你可以在员工列表或私聊里继续配置他。"
            ),
        )
    # NOTE: Auto-task creation from chat intent has been removed.
    # Task creation now requires a confirmed consensus_brief (see ADR 0006).
    created_task = None
    agent_messages = []

    # Group discussion orchestration: if group chat in 'discussing' state,
    # use multi-agent discussion round instead of replying to each agent individually.
    is_group_discussing = (
        conversation["kind"] == "group"
        and (conversation.get("discussion_status") or "discussing") == "discussing"
    )

    if is_group_discussing and len(reply_agents) > 1:
        # Multi-agent discussion round (TD-02) — orchestrated by the
        # discussion layer. The route only injects how a turn executes and
        # how the moderator LLM is called, then collects the yielded messages.
        async def turn_executor(conn, agent_id):
            next_agent = next(
                (a for a in reply_agents if a["id"] == agent_id), None
            )
            if next_agent is None:
                return
            discussion_ctx = build_discussion_context(
                conn, conversation_id, next_agent, reply_agents
            )
            msg = await complete_agent_reply(
                conn,
                workspace=workspace,
                conversation=conversation,
                conversation_id=conversation_id,
                agent=next_agent,
                user_message=user_message,
                discussion_context=discussion_ctx,
            )
            # Commit so the next speaker selection can see this reply.
            conn.commit()
            if msg is not None:
                yield {"type": "message", "message": msg}

        error_exc: Exception | None = None
        async for event in run_discussion_round(
            conn,
            workspace_id=workspace["id"],
            conversation_id=conversation_id,
            member_agents=reply_agents,
            turn_executor=turn_executor,
            llm_complete=make_speaker_selector(),
        ):
            if event["type"] == "message":
                agent_messages.append(event["message"])
            elif event["type"] == "error":
                error_exc = event.get("exc")

        if isinstance(error_exc, DeepSeekNotConfigured):
            raise HTTPException(status_code=503, detail=str(error_exc))
        if isinstance(error_exc, DeepSeekAPIError):
            raise HTTPException(status_code=502, detail=str(error_exc))
    else:
        # DM or single-agent group: original behavior
        for agent in reply_agents:
            try:
                agent_messages.append(
                    await complete_agent_reply(
                        conn,
                        workspace=workspace,
                        conversation=conversation,
                        conversation_id=conversation_id,
                        agent=agent,
                        user_message=user_message,
                    )
                )
            except DeepSeekNotConfigured as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except DeepSeekAPIError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

    serialized_agent_messages = [
        serialize_message(message) for message in agent_messages
    ]
    return {
        "user_message": serialize_message(user_message),
        "agent_message": serialized_agent_messages[0],
        "agent_messages": serialized_agent_messages,
        "created_task": serialize_task(created_task) if created_task else None,
        "created_agent": serialize_agent(created_agent) if created_agent else None,
    }


@router.post("/conversations/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: str,
    payload: SendMessageRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    """SSE streaming version of send_message.

    Events emitted:
    - event: user_message  data: {message}
    - event: speaking      data: {agent_id, agent_name, agent_role}
    - event: chunk         data: {content}
    - event: done          data: {message}
    - event: system        data: {content}
    - event: end           data: {}
    - event: error         data: {detail}
    """
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    conversation = conn.execute(
        "SELECT * FROM conversations WHERE id = ? AND workspace_id = ?",
        (conversation_id, workspace["id"]),
    ).fetchone()
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    reply_agents = resolve_reply_agents(conn, workspace["id"], conversation, payload)
    if not reply_agents:
        raise HTTPException(status_code=400, detail="没有可回复的智能体")

    user_message = add_message(
        conn,
        conversation_id=conversation_id,
        sender_type="user",
        sender_id=current_user["id"],
        content=payload.content,
    )
    conn.commit()

    # Handle recruit intent (same as non-streaming)
    recruit_intent = extract_recruit_intent(payload.content)
    if recruit_intent is not None:
        department = ensure_department(
            conn, workspace["id"], recruit_intent["department_name"]
        )
        create_agent(
            conn,
            workspace_id=workspace["id"],
            department_id=department["id"],
            name=recruit_intent["name"],
            role=recruit_intent["role"],
            description=recruit_intent["description"],
            prompt=recruit_intent["prompt"],
            skills=recruit_intent["skills"],
            mcps=recruit_intent["mcps"],
            source="chat_factory",
        )
        conn.commit()

    async def event_generator():
        # Emit user message
        yield f"event: user_message\ndata: {json.dumps(serialize_message(user_message), ensure_ascii=False)}\n\n"

        is_group_discussing = (
            conversation["kind"] == "group"
            and (conversation.get("discussion_status") or "discussing") == "discussing"
        )

        if is_group_discussing and len(reply_agents) > 1:
            # Multi-agent discussion with streaming — orchestrated by the
            # discussion layer. The route injects a streaming turn executor
            # and translates the yielded events into SSE frames.
            async def turn_executor(conn, agent_id):
                next_agent = next(
                    (a for a in reply_agents if a["id"] == agent_id), None
                )
                if next_agent is None:
                    return
                discussion_ctx = build_discussion_context(
                    conn, conversation_id, next_agent, reply_agents
                )
                async for event in _stream_reply_events(
                    conn,
                    workspace=workspace,
                    conversation=conversation,
                    agent=next_agent,
                    user_message=user_message,
                    discussion_context=discussion_ctx,
                ):
                    yield event

            async for event in run_discussion_round(
                conn,
                workspace_id=workspace["id"],
                conversation_id=conversation_id,
                member_agents=reply_agents,
                turn_executor=turn_executor,
                llm_complete=make_speaker_selector(),
            ):
                etype = event["type"]
                if etype == "speaker":
                    speaker = next(
                        (a for a in reply_agents if a["id"] == event["agent_id"]),
                        None,
                    )
                    if speaker is not None:
                        yield f"event: speaking\ndata: {json.dumps({'agent_id': speaker['id'], 'agent_name': speaker['name'], 'agent_role': speaker['role']}, ensure_ascii=False)}\n\n"
                elif etype == "chunk":
                    yield f"event: chunk\ndata: {json.dumps({'content': event['content']}, ensure_ascii=False)}\n\n"
                elif etype == "message" and event.get("message"):
                    yield f"event: done\ndata: {json.dumps(serialize_message(event['message']), ensure_ascii=False)}\n\n"
                elif etype == "approval_required":
                    yield f"event: approval\ndata: {json.dumps(event.get('payload', {}), ensure_ascii=False)}\n\n"
                elif etype == "error":
                    yield f"event: error\ndata: {json.dumps({'detail': event['detail']}, ensure_ascii=False)}\n\n"
        else:
            # DM or single-agent: stream the reply (Hermes or DeepSeek fallback).
            for agent in reply_agents:
                yield f"event: speaking\ndata: {json.dumps({'agent_id': agent['id'], 'agent_name': agent['name'], 'agent_role': agent['role']}, ensure_ascii=False)}\n\n"
                try:
                    async for event in _stream_reply_events(
                        conn,
                        workspace=workspace,
                        conversation=conversation,
                        agent=agent,
                        user_message=user_message,
                    ):
                        etype = event["type"]
                        if etype == "chunk":
                            yield f"event: chunk\ndata: {json.dumps({'content': event['content']}, ensure_ascii=False)}\n\n"
                        elif etype == "message" and event.get("message"):
                            yield f"event: done\ndata: {json.dumps(serialize_message(event['message']), ensure_ascii=False)}\n\n"
                        elif etype == "approval_required":
                            yield f"event: approval\ndata: {json.dumps(event.get('payload', {}), ensure_ascii=False)}\n\n"
                except (DeepSeekNotConfigured, DeepSeekAPIError) as exc:
                    yield f"event: error\ndata: {json.dumps({'detail': str(exc)}, ensure_ascii=False)}\n\n"
                    break

        yield f"event: end\ndata: {{}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/approvals/{approval_id}/resolve")
def resolve_approval(
    approval_id: str,
    payload: ResolveApprovalRequest,
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    approval = conn.execute(
        """
        SELECT * FROM approvals
        WHERE id = ? AND workspace_id = ?
        """,
        (approval_id, workspace["id"]),
    ).fetchone()
    if approval is None:
        raise HTTPException(status_code=404, detail="确认请求不存在")
    if approval["status"] != "pending":
        raise HTTPException(status_code=409, detail="确认请求已处理")

    resolved_at = now_iso()
    decision = payload.status
    conn.execute(
        """
        UPDATE approvals
        SET status = ?, resolved_by = ?, resolved_at = ?
        WHERE id = ? AND workspace_id = ?
        """,
        (decision, current_user["id"], resolved_at, approval_id, workspace["id"]),
    )

    # TD-03-T4: wake a suspended run (high_risk approvals created by the Hermes
    # approval_resolver). The in-process permission_resolver callback is blocked
    # on an approval_bridge Future; waking it lets the ACP stream continue.
    run_id = approval.get("run_id")
    if run_id and approval.get("type") == "high_risk":
        from app.runtime.approval_bridge import resolve_pending
        from app.runtime.runs import RunStatus, transition_run

        # Transition the run (in case no resolver is waiting — detached wake).
        try:
            transition_run(
                conn, run_id,
                RunStatus.RUNNING if decision == "approved" else RunStatus.COMPLETED,
            )
        except Exception:
            pass  # run may have already moved on; bridge wake is still needed.

        resolve_pending(approval_id, decision)
        # Log a task event if the approval has a task_id.
        task_id = approval.get("task_id")
        if task_id:
            add_task_event(
                conn,
                workspace_id=workspace["id"],
                task_id=task_id,
                kind="approval_resolved",
                title="老板已确认通过" if decision == "approved" else "老板已驳回",
                content=approval["title"],
                conversation_id=approval["conversation_id"],
                agent_id=approval["agent_id"],
            )
    else:
        # Legacy approval (attached to a task, not a run): update task + capture
        # agent experience as before.
        task_id = approval["task_id"]
        if task_id:
            add_task_event(
                conn,
                workspace_id=workspace["id"],
                task_id=task_id,
                kind="approval_resolved",
                title="老板已确认" if decision == "approved" else "老板已驳回",
                content=approval["title"],
                conversation_id=approval["conversation_id"],
                agent_id=approval["agent_id"],
            )
            capture_agent_experience_from_approval(
                conn,
                workspace_id=workspace["id"],
                approval=approval,
                resolution=decision,
            )
            if decision == "approved":
                update_task(
                    conn,
                    workspace_id=workspace["id"],
                    task_id=task_id,
                    changes={"status": "已完成", "progress": 100},
                )
            else:
                update_task(
                    conn,
                    workspace_id=workspace["id"],
                    task_id=task_id,
                    changes={"status": "阻塞", "progress": 80},
                )

    updated = conn.execute(
        "SELECT * FROM approvals WHERE id = ?", (approval_id,)
    ).fetchone()
    return serialize_approval(updated)


@router.post("/approvals/{approval_id}/answer")
def answer_clarification(
    approval_id: str,
    answer: str = Body(..., embed=True),
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
):
    """TD-03-T4: answer an employee's clarification request and resume its run.

    The answer is recorded as a chat message (so it enters conversation history)
    and the suspended run is woken to continue. NOTE: ACP permission responses
    carry only allow/deny, so the paused run resumes as "proceed" rather than
    receiving the answer text inline — the employee picks the answer up from
    conversation history on its next turn. Full inline injection needs a Hermes
    resume API and is tracked as a follow-up.
    """
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    approval = conn.execute(
        "SELECT * FROM approvals WHERE id = ? AND workspace_id = ? AND type = 'clarification'",
        (approval_id, workspace["id"]),
    ).fetchone()
    if approval is None:
        raise HTTPException(status_code=404, detail="澄清请求不存在")
    if approval["status"] != "pending":
        raise HTTPException(status_code=409, detail="澄清请求已处理")

    conn.execute(
        "UPDATE approvals SET status = 'answered', resolved_by = ?, resolved_at = ? "
        "WHERE id = ?",
        (current_user["id"], now_iso(), approval_id),
    )
    if approval["conversation_id"]:
        add_message(
            conn,
            conversation_id=approval["conversation_id"],
            sender_type="user",
            sender_id=current_user["id"],
            content=answer,
        )
    run_id = approval["run_id"]
    if run_id:
        try:
            transition_run(conn, run_id, RunStatus.RUNNING)
        except RunStateError:
            pass
        conn.commit()
        approval_bridge.resolve_pending(approval_id, "allow_once")
    else:
        conn.commit()
    updated = conn.execute(
        "SELECT * FROM approvals WHERE id = ?", (approval_id,)
    ).fetchone()
    return serialize_approval(updated)


def capture_agent_experience_from_approval(
    conn: Database,
    *,
    workspace_id: str,
    approval: Row,
    resolution: str,
) -> None:
    agent_id = approval["agent_id"]
    task_id = approval["task_id"]
    if not agent_id or not task_id:
        return

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND workspace_id = ?",
        (task_id, workspace_id),
    ).fetchone()
    if task is None:
        return

    latest_output = conn.execute(
        """
        SELECT * FROM task_outputs
        WHERE workspace_id = ? AND task_id = ? AND agent_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (workspace_id, task_id, agent_id),
    ).fetchone()
    output_excerpt = latest_output["content"][:180] if latest_output else ""
    if resolution == "approved":
        outcome = "success"
        summary = f"完成任务《{task['title']}》，老板已确认通过。"
        lessons = (
            f"可复用经验：围绕「{task['title']}」的输出已通过验收。"
            + (f" 关键产出：{output_excerpt}" if output_excerpt else "")
        )
    else:
        outcome = "lesson"
        summary = f"任务《{task['title']}》被老板驳回，需要重新推进。"
        lessons = (
            f"改进提醒：下次处理「{task['title']}」前先补充确认标准、风险和老板要拍板的问题。"
            + (f" 本次产出片段：{output_excerpt}" if output_excerpt else "")
        )

    add_agent_experience(
        conn,
        workspace_id=workspace_id,
        agent_id=agent_id,
        task_id=task_id,
        outcome=outcome,
        summary=summary,
        lessons=lessons,
    )


def _build_hermes_prompt(user_message: Row, discussion_context: str) -> str:
    """Prompt fed to a Hermes employee. Persona comes from the profile's SOUL;
    this carries the situational context + the boss's message."""
    latest = user_message["content"]
    if discussion_context:
        return f"{discussion_context}\n\n老板刚说：{latest}\n\n请以你的角色简洁发言。"
    return latest


async def _stream_reply_events(
    conn: Database,
    *,
    workspace: Row,
    conversation: Row,
    agent: Row,
    user_message: Row,
    discussion_context: str = "",
) -> AsyncGenerator:
    """Produce an agent's reply as {type: chunk|message|...} events.

    Routes execution to Hermes when the employee has a ready profile
    (TD-03-T3), else falls back to the temporary DeepSeek path. Both persist an
    agent message and end with a single {"type": "message", "message": row|None}.
    """
    profile = resolve_hermes_profile(conn, agent["id"])
    if profile:
        work_root = os.path.abspath(settings.hermes_work_root or ".hermes-data")
        ctx = RunContext(
            run_id="",
            prompt=_build_hermes_prompt(user_message, discussion_context),
            workdir=os.path.join(work_root, profile, "work", "runs", new_id("run")),
            profile=profile,
            agent_id=agent["id"],
            workspace_id=workspace["id"],
            conversation_id=conversation["id"],
        )
        async for event in stream_agent_run(
            conn,
            ctx=ctx,
            backend=HermesBackend(hermes_bin=settings.hermes_bin),
            input_message_id=user_message["id"],
            permission_resolver=make_bridge_resolver(),  # TD-03-T4: suspend/resume
        ):
            yield event
        return

    # Temporary DeepSeek execution layer (employees without a Hermes profile).
    full_reply = ""
    async for chunk_text in await _stream_agent_reply(
        conn,
        workspace=workspace,
        conversation=conversation,
        conversation_id=conversation["id"],
        agent=agent,
        user_message=user_message,
        discussion_context=discussion_context,
    ):
        full_reply += chunk_text
        yield {"type": "chunk", "content": chunk_text}
    msg = add_message(
        conn,
        conversation_id=conversation["id"],
        sender_type="agent",
        sender_id=agent["id"],
        content=full_reply,
        provider="deepseek",
        model="deepseek-v4-flash",
    )
    conn.commit()
    yield {"type": "message", "message": msg}


async def _stream_agent_reply(
    conn: Database,
    *,
    workspace: Row,
    conversation: Row,
    conversation_id: str,
    agent: Row,
    user_message: Row,
    discussion_context: str = "",
) -> AsyncGenerator:
    """Stream agent reply using DeepSeek streaming API.

    Yields text chunks. The caller is responsible for collecting and persisting.
    """
    from collections.abc import AsyncGenerator as _AG

    history = load_llm_history(conn, conversation_id)
    related_tasks = load_related_task_context(conn, conversation_id)
    latest_user_content = next(
        (message.content for message in reversed(history) if message.role == "user"),
        "",
    )
    knowledge_sources = [
        LlmKnowledgeSource(
            id=source["id"],
            title=source["title"],
            category=source["category"],
            content=source["content"][:2000],
        )
        for source in load_knowledge_context(
            conn,
            workspace_id=workspace["id"],
            query=latest_user_content,
        )
    ]
    agent_experiences = load_agent_experience_context(conn, agent["id"])

    request = LlmChatRequest(
        company_name=workspace["name"],
        conversation_title=conversation_title(conversation, agent),
        agent=LlmChatAgent(
            id=agent["id"],
            name=agent["name"],
            role=agent["role"],
            department=agent["department_name"],
            prompt=agent["prompt"],
            skills=json.loads(agent["skills_json"]),
        ),
        messages=history,
        related_tasks=related_tasks,
        knowledge_sources=knowledge_sources,
        agent_experiences=agent_experiences,
        discussion_context=discussion_context,
    )

    return DeepSeekChatClient().complete_stream(request)


def make_speaker_selector():
    """Build the moderator-LLM callback injected into run_discussion_round.

    Pure execution-layer plumbing: given a system prompt (assembled by the
    orchestration layer), return the model's raw text. All selection logic
    (@mention priority, JSON parsing/validation, round-robin fallback) lives
    in orchestration/discussion.py.
    """

    async def _complete(prompt: str) -> str:
        completion = await DeepSeekChatClient().complete(
            LlmChatRequest(
                agent=LlmChatAgent(
                    id="system",
                    name="主持人",
                    role="讨论主持人",
                    prompt=prompt,
                ),
                messages=[LlmChatMessage(role="user", content="请选择下一个发言人")],
            )
        )
        return completion.reply

    return _complete


async def complete_agent_reply(
    conn: Database,
    *,
    workspace: Row,
    conversation: Row,
    conversation_id: str,
    agent: Row,
    user_message: Row,
    discussion_context: str = "",
) -> Row:
    history = load_llm_history(conn, conversation_id)
    related_tasks = load_related_task_context(conn, conversation_id)
    latest_user_content = next(
        (message.content for message in reversed(history) if message.role == "user"),
        "",
    )
    knowledge_sources = [
        LlmKnowledgeSource(
            id=source["id"],
            title=source["title"],
            category=source["category"],
            content=source["content"][:2000],
        )
        for source in load_knowledge_context(
            conn,
            workspace_id=workspace["id"],
            query=latest_user_content,
        )
    ]
    agent_experiences = load_agent_experience_context(conn, agent["id"])
    completion = await DeepSeekChatClient().complete(
        LlmChatRequest(
            company_name=workspace["name"],
            conversation_title=conversation_title(conversation, agent),
            agent=LlmChatAgent(
                id=agent["id"],
                name=agent["name"],
                role=agent["role"],
                department=agent["department_name"],
                prompt=agent["prompt"],
                skills=json.loads(agent["skills_json"]),
            ),
            messages=history,
            related_tasks=related_tasks,
            knowledge_sources=knowledge_sources,
            agent_experiences=agent_experiences,
            discussion_context=discussion_context,
        )
    )

    agent_message = add_message(
        conn,
        conversation_id=conversation_id,
        sender_type="agent",
        sender_id=agent["id"],
        content=completion.reply,
        provider=completion.provider,
        model=completion.model,
    )
    run_id = new_id("run")
    now = now_iso()
    conn.execute(
        """
        INSERT INTO runs (
          id, workspace_id, conversation_id, agent_id, status, input_message_id,
          output_message_id, provider, model, usage_json, created_at, completed_at
        )
        VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            workspace["id"],
            conversation_id,
            agent["id"],
            user_message["id"],
            agent_message["id"],
            completion.provider,
            completion.model,
            json.dumps(completion.usage or {}),
            now,
            now,
        ),
    )
    related_task_rows = conn.execute(
        """
        SELECT id, title FROM tasks
        WHERE workspace_id = ? AND conversation_id = ?
        ORDER BY updated_at DESC
        LIMIT 12
        """,
        (workspace["id"], conversation_id),
    ).fetchall()
    for task in related_task_rows:
        add_task_event(
            conn,
            workspace_id=workspace["id"],
            task_id=task["id"],
            kind="agent_output_generated",
            title=f"{agent['name']} 生成了产出",
            content=completion.reply[:600],
            conversation_id=conversation_id,
            agent_id=agent["id"],
        )
        add_task_output(
            conn,
            workspace_id=workspace["id"],
            task_id=task["id"],
            title=f"{agent['name']} 的回复",
            content=completion.reply,
            conversation_id=conversation_id,
            agent_id=agent["id"],
        )
    return agent_message


def resolve_reply_agents(
    conn: Database,
    workspace_id: str,
    conversation: Row,
    payload: SendMessageRequest,
) -> list[Row]:
    if conversation["kind"] == "dm":
        if not conversation["agent_id"]:
            return []
        agent = load_agent_for_reply(conn, workspace_id, conversation["agent_id"])
        return [agent] if agent else []

    if payload.target_agent_id:
        agent = load_agent_for_reply(conn, workspace_id, payload.target_agent_id)
        if agent is None:
            return []
        member = conn.execute(
            """
            SELECT 1 FROM conversation_members
            WHERE conversation_id = ? AND agent_id = ?
            """,
            (conversation["id"], agent["id"]),
        ).fetchone()
        return [agent] if member else []

    rows = conn.execute(
        """
        SELECT agents.*, departments.name AS department_name
        FROM conversation_members
        JOIN agents ON agents.id = conversation_members.agent_id
        JOIN departments ON departments.id = agents.department_id
        WHERE conversation_members.conversation_id = ?
          AND agents.workspace_id = ?
        ORDER BY conversation_members.id
        LIMIT 3
        """,
        (conversation["id"], workspace_id),
    ).fetchall()
    return rows


def load_agent_for_reply(
    conn: Database, workspace_id: str, agent_id: str
) -> Row | None:
    return conn.execute(
        """
        SELECT agents.*, departments.name AS department_name
        FROM agents
        JOIN departments ON departments.id = agents.department_id
        WHERE agents.id = ? AND agents.workspace_id = ?
        """,
        (agent_id, workspace_id),
    ).fetchone()


def load_llm_history(
    conn: Database, conversation_id: str
) -> list[LlmChatMessage]:
    rows = conn.execute(
        """
        SELECT messages.*, agents.name AS agent_name
        FROM messages
        LEFT JOIN agents ON agents.id = messages.sender_id
        WHERE conversation_id = ? AND sender_type IN ('user', 'agent')
        ORDER BY created_at DESC
        LIMIT 12
        """,
        (conversation_id,),
    ).fetchall()
    messages = []
    for row in reversed(rows):
        messages.append(
            LlmChatMessage(
                role="user" if row["sender_type"] == "user" else "assistant",
                name="老板" if row["sender_type"] == "user" else row["agent_name"],
                content=row["content"],
            )
        )
    return messages


def load_related_task_context(conn: Database, conversation_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
          tasks.id, tasks.title, tasks.description, tasks.priority,
          tasks.status, tasks.progress, agents.name AS owner_name
        FROM tasks
        LEFT JOIN agents ON agents.id = tasks.owner_agent_id
        WHERE tasks.conversation_id = ?
        ORDER BY
          CASE tasks.priority
            WHEN 'P0' THEN 0
            WHEN 'P1' THEN 1
            ELSE 2
          END,
          tasks.updated_at DESC
        LIMIT 12
        """,
        (conversation_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "priority": row["priority"],
            "status": row["status"],
            "progress": row["progress"],
            "owner_name": row["owner_name"],
        }
        for row in rows
    ]


def load_agent_experience_context(
    conn: Database, agent_id: str
) -> list[LlmAgentExperience]:
    rows = conn.execute(
        """
        SELECT id, task_id, outcome, summary, lessons
        FROM agent_experiences
        WHERE agent_id = ?
        ORDER BY created_at DESC
        LIMIT 6
        """,
        (agent_id,),
    ).fetchall()
    return [
        LlmAgentExperience(
            id=row["id"],
            task_id=row["task_id"],
            outcome=row["outcome"],
            summary=row["summary"],
            lessons=row["lessons"],
        )
        for row in rows
    ]


def conversation_title(conversation: Row, agent: Row) -> str:
    if conversation["kind"] == "dm":
        return f"私聊 · {agent['name']}"
    return f"群聊 · {conversation['name']}"
