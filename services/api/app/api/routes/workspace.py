import json

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.core.database import Database, Row, get_db
from app.runtime.deepseek import DeepSeekAPIError, DeepSeekChatClient, DeepSeekNotConfigured
from app.schemas.run import (
    LlmAgentExperience,
    LlmChatAgent,
    LlmChatMessage,
    LlmChatRequest,
)
from app.schemas.workspace import (
    AddConversationMembersRequest,
    BootstrapResponse,
    CreateAgentRequest,
    CreateGroupRequest,
    CreateTaskRequest,
    RecruitAgentRequest,
    ResolveApprovalRequest,
    SendMessageRequest,
    SendMessageResponse,
    TaskOut,
    UpdateTaskRequest,
)
from app.services.workspace import (
    add_agent_experience,
    add_message,
    add_task_event,
    add_task_output,
    create_agent,
    create_dm_conversation,
    create_task,
    ensure_department,
    extract_task_intent,
    get_bootstrap,
    get_workspace_for_user,
    new_id,
    now_iso,
    recruit_from_template,
    serialize_agent,
    serialize_approval,
    serialize_message,
    serialize_task,
    update_task,
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
    agent_id = create_agent(
        conn,
        workspace_id=workspace["id"],
        department_id=department["id"],
        name=payload.name,
        role=payload.description or "自定义员工",
        description=payload.description,
        prompt=payload.prompt,
        skills=[],
        mcps=[],
        source="custom",
    )
    create_dm_conversation(conn, workspace["id"], agent_id)
    agent = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    return serialize_agent(agent)


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
    task_intent = extract_task_intent(payload.content)
    if task_intent is not None:
        created_task = create_task(
            conn,
            workspace_id=workspace["id"],
            title=task_intent["title"],
            description=task_intent["description"],
            priority=task_intent["priority"],
            owner_agent_id=task_owner["id"],
            conversation_id=conversation_id,
            status="进行中",
            progress=10,
        )
        add_task_event(
            conn,
            workspace_id=workspace["id"],
            task_id=created_task["id"],
            kind="task_created_from_chat",
            title="由聊天自动生成",
            content=payload.content,
            conversation_id=conversation_id,
            agent_id=task_owner["id"],
        )
    agent_messages = []
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
    }


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
    conn.execute(
        """
        UPDATE approvals
        SET status = ?, resolved_by = ?, resolved_at = ?
        WHERE id = ? AND workspace_id = ?
        """,
        (
            payload.status,
            current_user["id"],
            resolved_at,
            approval_id,
            workspace["id"],
        ),
    )
    task_id = approval["task_id"]
    if task_id:
        add_task_event(
            conn,
            workspace_id=workspace["id"],
            task_id=task_id,
            kind="approval_resolved",
            title="老板已确认" if payload.status == "approved" else "老板已驳回",
            content=approval["title"],
            conversation_id=approval["conversation_id"],
            agent_id=approval["agent_id"],
        )
        capture_agent_experience_from_approval(
            conn,
            workspace_id=workspace["id"],
            approval=approval,
            resolution=payload.status,
        )
        if payload.status == "approved":
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


async def complete_agent_reply(
    conn: Database,
    *,
    workspace: Row,
    conversation: Row,
    conversation_id: str,
    agent: Row,
    user_message: Row,
) -> Row:
    history = load_llm_history(conn, conversation_id)
    related_tasks = load_related_task_context(conn, conversation_id)
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
            agent_experiences=agent_experiences,
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
