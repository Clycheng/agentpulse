from __future__ import annotations

from datetime import UTC, datetime
import json
from uuid import uuid4

from app.core.database import Database, Row
from app.services.templates import AGENT_TEMPLATES, TALENT_CATEGORIES, get_template


DEFAULT_DEPARTMENTS = ["老板办公室"]
HUES = [262, 230, 300, 140, 55, 20, 330]
GLYPHS = ["✦", "▲", "◆", "◗", "✱", "◍", "◉"]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def create_workspace_for_user(
    conn: Database,
    user_id: str,
    workspace_name: str,
) -> Row:
    created_at = now_iso()
    workspace_id = new_id("ws")
    conn.execute(
        """
        INSERT INTO workspaces (id, owner_user_id, name, onboarding_completed, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (workspace_id, user_id, workspace_name, False, created_at),
    )

    department_ids: dict[str, str] = {}
    for index, name in enumerate(DEFAULT_DEPARTMENTS):
        department_id = new_id("dept")
        department_ids[name] = department_id
        conn.execute(
            """
            INSERT INTO departments (id, workspace_id, name, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (department_id, workspace_id, name, index, created_at),
        )

    secretary_id = create_agent(
        conn,
        workspace_id=workspace_id,
        department_id=department_ids["老板办公室"],
        name="小秘",
        role="老板秘书",
        description="负责接收老板想法、拆任务、拉群协作和提醒拍板",
        prompt="你是老板的贴身秘书兼幕僚长。接收老板的任何想法，转化为任务、招聘建议或群组讨论；跟踪全公司任务进度；需要老板拍板时，整理好决策要点再去打扰他。",
        skills=["任务拆解", "会议纪要", "信息检索"],
        mcps=[],
        hue=262,
        glyph="✦",
        source="system_secretary",
        joined="系统内置",
    )
    conversation_id = new_id("conv")
    conn.execute(
        """
        INSERT INTO conversations (id, workspace_id, kind, name, agent_id, unread, created_at, updated_at)
        VALUES (?, ?, 'dm', '', ?, 0, ?, ?)
        """,
        (conversation_id, workspace_id, secretary_id, created_at, created_at),
    )
    add_message(
        conn,
        conversation_id=conversation_id,
        sender_type="agent",
        sender_id=secretary_id,
        content="欢迎老板。我是小秘。你可以直接把想法丢给我，我会帮你拆任务、建议招募谁、或者拉群推进。",
    )
    return get_workspace_by_id(conn, workspace_id)


def create_agent(
    conn: Database,
    *,
    workspace_id: str,
    department_id: str,
    name: str,
    role: str,
    description: str,
    prompt: str,
    skills: list[str],
    mcps: list[str],
    hue: int | None = None,
    glyph: str | None = None,
    source: str = "custom",
    joined: str = "今天入职",
) -> str:
    agent_count = conn.execute(
        "SELECT COUNT(*) AS count FROM agents WHERE workspace_id = ?", (workspace_id,)
    ).fetchone()["count"]
    agent_id = new_id("agent")
    conn.execute(
        """
        INSERT INTO agents (
          id, workspace_id, department_id, name, role, description, prompt,
          hue, glyph, status_kind, status_label, joined, source,
          skills_json, mcps_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'idle', '在线待命', ?, ?, ?, ?, ?)
        """,
        (
            agent_id,
            workspace_id,
            department_id,
            name,
            role,
            description,
            prompt,
            hue if hue is not None else HUES[agent_count % len(HUES)],
            glyph if glyph is not None else GLYPHS[agent_count % len(GLYPHS)],
            joined,
            source,
            json.dumps(skills, ensure_ascii=False),
            json.dumps(mcps, ensure_ascii=False),
            now_iso(),
        ),
    )
    return agent_id


def get_workspace_for_user(conn: Database, user_id: str) -> Row | None:
    return conn.execute(
        """
        SELECT * FROM workspaces
        WHERE owner_user_id = ?
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()


def get_workspace_by_id(conn: Database, workspace_id: str) -> Row:
    row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
    if row is None:
        raise ValueError("workspace not found")
    return row


def ensure_department(
    conn: Database, workspace_id: str, department_name: str
) -> Row:
    row = conn.execute(
        "SELECT * FROM departments WHERE workspace_id = ? AND name = ?",
        (workspace_id, department_name),
    ).fetchone()
    if row is not None:
        return row

    count = conn.execute(
        "SELECT COUNT(*) AS count FROM departments WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchone()["count"]
    department_id = new_id("dept")
    conn.execute(
        """
        INSERT INTO departments (id, workspace_id, name, sort_order, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (department_id, workspace_id, department_name, count, now_iso()),
    )
    return conn.execute("SELECT * FROM departments WHERE id = ?", (department_id,)).fetchone()


def add_message(
    conn: Database,
    *,
    conversation_id: str,
    sender_type: str,
    sender_id: str,
    content: str,
    provider: str | None = None,
    model: str | None = None,
) -> Row:
    message_id = new_id("msg")
    created_at = now_iso()
    conn.execute(
        """
        INSERT INTO messages (
          id, conversation_id, sender_type, sender_id, content,
          provider, model, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            conversation_id,
            sender_type,
            sender_id,
            content,
            provider,
            model,
            created_at,
        ),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (created_at, conversation_id),
    )
    return conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()


def serialize_workspace(row: Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "onboarding_completed": bool(row["onboarding_completed"]),
    }


def serialize_user(row: Row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
    }


def serialize_department(row: Row) -> dict:
    return {"id": row["id"], "name": row["name"], "sort_order": row["sort_order"]}


def serialize_agent(row: Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "role": row["role"],
        "description": row["description"],
        "department_id": row["department_id"],
        "prompt": row["prompt"],
        "hue": row["hue"],
        "glyph": row["glyph"],
        "status_kind": row["status_kind"],
        "status_label": row["status_label"],
        "joined": row["joined"],
        "source": row["source"],
        "skills": json.loads(row["skills_json"]),
        "mcps": json.loads(row["mcps_json"]),
    }


def serialize_conversation(row: Row, member_ids: list[str]) -> dict:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "name": row["name"],
        "agent_id": row["agent_id"],
        "member_ids": member_ids,
        "unread": row["unread"],
        "updated_at": row["updated_at"],
    }


def serialize_message(row: Row) -> dict:
    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "sender_type": row["sender_type"],
        "sender_id": row["sender_id"],
        "content": row["content"],
        "provider": row["provider"],
        "model": row["model"],
        "created_at": row["created_at"],
    }


def serialize_task(row: Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "priority": row["priority"],
        "owner_agent_id": row["owner_agent_id"],
        "status": row["status"],
        "progress": row["progress"],
        "conversation_id": row["conversation_id"],
        "due_date": row["due_date"],
        "parent_task_id": row["parent_task_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_task_event(row: Row) -> dict:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "conversation_id": row["conversation_id"],
        "agent_id": row["agent_id"],
        "kind": row["kind"],
        "title": row["title"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def serialize_task_output(row: Row) -> dict:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "conversation_id": row["conversation_id"],
        "agent_id": row["agent_id"],
        "title": row["title"],
        "output_type": row["output_type"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def serialize_approval(row: Row) -> dict:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "conversation_id": row["conversation_id"],
        "agent_id": row["agent_id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "risk_level": row["risk_level"],
        "resolved_by": row["resolved_by"],
        "resolved_at": row["resolved_at"],
        "created_at": row["created_at"],
    }


def add_task_event(
    conn: Database,
    *,
    workspace_id: str,
    task_id: str,
    kind: str,
    title: str,
    content: str = "",
    conversation_id: str | None = None,
    agent_id: str | None = None,
) -> Row:
    event_id = new_id("event")
    created_at = now_iso()
    conn.execute(
        """
        INSERT INTO task_events (
          id, workspace_id, task_id, conversation_id, agent_id,
          kind, title, content, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            workspace_id,
            task_id,
            conversation_id,
            agent_id,
            kind,
            title,
            content,
            created_at,
        ),
    )
    return conn.execute("SELECT * FROM task_events WHERE id = ?", (event_id,)).fetchone()


def add_task_output(
    conn: Database,
    *,
    workspace_id: str,
    task_id: str,
    title: str,
    content: str,
    conversation_id: str | None = None,
    agent_id: str | None = None,
    output_type: str = "markdown",
) -> Row:
    output_id = new_id("output")
    created_at = now_iso()
    conn.execute(
        """
        INSERT INTO task_outputs (
          id, workspace_id, task_id, conversation_id, agent_id,
          title, output_type, content, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            output_id,
            workspace_id,
            task_id,
            conversation_id,
            agent_id,
            title,
            output_type,
            content,
            created_at,
        ),
    )
    return conn.execute("SELECT * FROM task_outputs WHERE id = ?", (output_id,)).fetchone()


def add_approval(
    conn: Database,
    *,
    workspace_id: str,
    title: str,
    description: str,
    task_id: str | None = None,
    conversation_id: str | None = None,
    agent_id: str | None = None,
    risk_level: str = "medium",
) -> Row:
    approval_id = new_id("approval")
    created_at = now_iso()
    conn.execute(
        """
        INSERT INTO approvals (
          id, workspace_id, task_id, conversation_id, agent_id,
          title, description, status, risk_level, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (
            approval_id,
            workspace_id,
            task_id,
            conversation_id,
            agent_id,
            title,
            description,
            risk_level,
            created_at,
        ),
    )
    return conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()


def create_task(
    conn: Database,
    *,
    workspace_id: str,
    title: str,
    description: str = "",
    priority: str = "P2",
    owner_agent_id: str | None = None,
    status: str = "进行中",
    progress: int = 0,
    conversation_id: str | None = None,
    due_date: str | None = None,
    parent_task_id: str | None = None,
) -> Row:
    validate_task_links(
        conn,
        workspace_id=workspace_id,
        owner_agent_id=owner_agent_id,
        conversation_id=conversation_id,
        parent_task_id=parent_task_id,
    )
    task_id = new_id("task")
    created_at = now_iso()
    conn.execute(
        """
        INSERT INTO tasks (
          id, workspace_id, title, description, priority, owner_agent_id,
          status, progress, conversation_id, due_date, parent_task_id,
          created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            workspace_id,
            title,
            description,
            normalize_priority(priority),
            owner_agent_id,
            normalize_task_status(status),
            progress_for_status(normalize_task_status(status), progress),
            conversation_id,
            due_date,
            parent_task_id,
            created_at,
            created_at,
        ),
    )
    add_task_event(
        conn,
        workspace_id=workspace_id,
        task_id=task_id,
        kind="task_created",
        title="任务已创建",
        content=description or "任务已进入执行队列。",
        conversation_id=conversation_id,
        agent_id=owner_agent_id,
    )
    if owner_agent_id:
        add_task_event(
            conn,
            workspace_id=workspace_id,
            task_id=task_id,
            kind="task_assigned",
            title="已分配负责人",
            content="任务已分配给员工处理。",
            conversation_id=conversation_id,
            agent_id=owner_agent_id,
        )
    if conversation_id:
        add_message(
            conn,
            conversation_id=conversation_id,
            sender_type="system",
            sender_id="",
            content=f"已创建任务：{title}",
        )
    return conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def update_task(
    conn: Database,
    *,
    workspace_id: str,
    task_id: str,
    changes: dict,
) -> Row:
    existing = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND workspace_id = ?",
        (task_id, workspace_id),
    ).fetchone()
    if existing is None:
        raise ValueError("task not found")

    next_values = {
        "title": changes.get("title", existing["title"]),
        "description": changes.get("description", existing["description"]),
        "priority": normalize_priority(changes.get("priority", existing["priority"])),
        "owner_agent_id": changes.get("owner_agent_id", existing["owner_agent_id"]),
        "status": normalize_task_status(changes.get("status", existing["status"])),
        "progress": changes.get("progress", existing["progress"]),
        "conversation_id": changes.get("conversation_id", existing["conversation_id"]),
        "due_date": changes.get("due_date", existing["due_date"]),
        "parent_task_id": changes.get("parent_task_id", existing["parent_task_id"]),
    }
    next_values["progress"] = progress_for_status(
        next_values["status"], int(next_values["progress"])
    )
    if next_values["parent_task_id"] == task_id:
        raise ValueError("task cannot be its own parent")
    validate_task_links(
        conn,
        workspace_id=workspace_id,
        owner_agent_id=next_values["owner_agent_id"],
        conversation_id=next_values["conversation_id"],
        parent_task_id=next_values["parent_task_id"],
    )
    updated_at = now_iso()
    conn.execute(
        """
        UPDATE tasks
        SET title = ?, description = ?, priority = ?, owner_agent_id = ?,
            status = ?, progress = ?, conversation_id = ?, due_date = ?,
            parent_task_id = ?, updated_at = ?
        WHERE id = ? AND workspace_id = ?
        """,
        (
            next_values["title"],
            next_values["description"],
            next_values["priority"],
            next_values["owner_agent_id"],
            next_values["status"],
            next_values["progress"],
            next_values["conversation_id"],
            next_values["due_date"],
            next_values["parent_task_id"],
            updated_at,
            task_id,
            workspace_id,
        ),
    )
    if next_values["conversation_id"]:
        add_message(
            conn,
            conversation_id=next_values["conversation_id"],
            sender_type="system",
            sender_id="",
            content=f"任务更新：{next_values['title']} · {next_values['status']}",
        )
    event_kind = (
        "task_status_changed"
        if next_values["status"] != existing["status"]
        else "task_updated"
    )
    add_task_event(
        conn,
        workspace_id=workspace_id,
        task_id=task_id,
        kind=event_kind,
        title=(
            f"状态更新为 {next_values['status']}"
            if event_kind == "task_status_changed"
            else "任务信息已更新"
        ),
        content=f"当前进度 {next_values['progress']}%。",
        conversation_id=next_values["conversation_id"],
        agent_id=next_values["owner_agent_id"],
    )
    if next_values["status"] == "待确认":
        existing_pending = conn.execute(
            """
            SELECT id FROM approvals
            WHERE workspace_id = ? AND task_id = ? AND status = 'pending'
            LIMIT 1
            """,
            (workspace_id, task_id),
        ).fetchone()
        if existing_pending is None:
            add_approval(
                conn,
                workspace_id=workspace_id,
                task_id=task_id,
                conversation_id=next_values["conversation_id"],
                agent_id=next_values["owner_agent_id"],
                title=f"确认任务产出：{next_values['title']}",
                description="任务已进入待确认状态，请老板确认结果是否可以归档完成。",
                risk_level="low",
            )
            add_task_event(
                conn,
                workspace_id=workspace_id,
                task_id=task_id,
                kind="approval_requested",
                title="等待老板确认",
                content="员工已提交阶段性结果，需要老板拍板。",
                conversation_id=next_values["conversation_id"],
                agent_id=next_values["owner_agent_id"],
            )
    return conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def validate_task_links(
    conn: Database,
    *,
    workspace_id: str,
    owner_agent_id: str | None,
    conversation_id: str | None,
    parent_task_id: str | None,
) -> None:
    if owner_agent_id:
        owner = conn.execute(
            "SELECT id FROM agents WHERE id = ? AND workspace_id = ?",
            (owner_agent_id, workspace_id),
        ).fetchone()
        if owner is None:
            raise ValueError("owner agent not found")

    if conversation_id:
        conversation = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND workspace_id = ?",
            (conversation_id, workspace_id),
        ).fetchone()
        if conversation is None:
            raise ValueError("conversation not found")

    if parent_task_id:
        parent = conn.execute(
            "SELECT id FROM tasks WHERE id = ? AND workspace_id = ?",
            (parent_task_id, workspace_id),
        ).fetchone()
        if parent is None:
            raise ValueError("parent task not found")


def normalize_priority(value: str) -> str:
    return value if value in {"P0", "P1", "P2"} else "P2"


def normalize_task_status(value: str) -> str:
    if value == "卡住":
        return "阻塞"
    return value if value in {"进行中", "待确认", "阻塞", "已完成"} else "进行中"


def progress_for_status(status: str, progress: int) -> int:
    bounded = max(0, min(100, progress))
    if status == "已完成":
        return 100
    if status == "进行中" and bounded == 0:
        return 10
    return bounded


def get_bootstrap(conn: Database, workspace_id: str) -> dict:
    workspace = get_workspace_by_id(conn, workspace_id)
    departments = conn.execute(
        "SELECT * FROM departments WHERE workspace_id = ? ORDER BY sort_order, created_at",
        (workspace_id,),
    ).fetchall()
    agents = conn.execute(
        "SELECT * FROM agents WHERE workspace_id = ? ORDER BY created_at", (workspace_id,)
    ).fetchall()
    conversations = conn.execute(
        "SELECT * FROM conversations WHERE workspace_id = ? ORDER BY updated_at DESC",
        (workspace_id,),
    ).fetchall()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE workspace_id = ? ORDER BY updated_at DESC",
        (workspace_id,),
    ).fetchall()
    task_ids = [task["id"] for task in tasks]
    task_events_by_task = {task_id: [] for task_id in task_ids}
    task_outputs_by_task = {task_id: [] for task_id in task_ids}
    approvals_by_task = {task_id: [] for task_id in task_ids}
    if task_ids:
        placeholders = ",".join("?" for _ in task_ids)
        events = conn.execute(
            f"""
            SELECT * FROM task_events
            WHERE workspace_id = ? AND task_id IN ({placeholders})
            ORDER BY created_at ASC
            """,
            (workspace_id, *task_ids),
        ).fetchall()
        for event in events:
            task_events_by_task.setdefault(event["task_id"], []).append(
                serialize_task_event(event)
            )

        outputs = conn.execute(
            f"""
            SELECT * FROM task_outputs
            WHERE workspace_id = ? AND task_id IN ({placeholders})
            ORDER BY created_at DESC
            """,
            (workspace_id, *task_ids),
        ).fetchall()
        for output in outputs:
            task_outputs_by_task.setdefault(output["task_id"], []).append(
                serialize_task_output(output)
            )

        approvals = conn.execute(
            f"""
            SELECT * FROM approvals
            WHERE workspace_id = ? AND task_id IN ({placeholders})
            ORDER BY created_at DESC
            """,
            (workspace_id, *task_ids),
        ).fetchall()
        for approval in approvals:
            approvals_by_task.setdefault(approval["task_id"], []).append(
                serialize_approval(approval)
            )
    messages_by_conversation = {}
    serialized_conversations = []
    for conversation in conversations:
        members = conn.execute(
            """
            SELECT agent_id FROM conversation_members
            WHERE conversation_id = ?
            ORDER BY id
            """,
            (conversation["id"],),
        ).fetchall()
        member_ids = [member["agent_id"] for member in members]
        if conversation["kind"] == "dm" and conversation["agent_id"]:
            member_ids = [conversation["agent_id"]]
        serialized_conversations.append(serialize_conversation(conversation, member_ids))
        messages = conn.execute(
            """
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
            """,
            (conversation["id"],),
        ).fetchall()
        messages_by_conversation[conversation["id"]] = [
            serialize_message(message) for message in messages
        ]

    return {
        "workspace": serialize_workspace(workspace),
        "departments": [serialize_department(dept) for dept in departments],
        "agents": [serialize_agent(agent) for agent in agents],
        "conversations": serialized_conversations,
        "messages_by_conversation": messages_by_conversation,
        "tasks": [serialize_task(task) for task in tasks],
        "task_events_by_task": task_events_by_task,
        "task_outputs_by_task": task_outputs_by_task,
        "approvals_by_task": approvals_by_task,
        "agent_template_categories": TALENT_CATEGORIES,
        "agent_templates": AGENT_TEMPLATES,
    }


def recruit_from_template(
    conn: Database,
    *,
    workspace_id: str,
    template_id: str,
    department_name: str | None,
) -> Row:
    template = get_template(template_id)
    if template is None:
        raise ValueError("template not found")

    department = ensure_department(
        conn, workspace_id, department_name or template["department"]
    )
    agent_id = create_agent(
        conn,
        workspace_id=workspace_id,
        department_id=department["id"],
        name=template["name"],
        role=template["name"],
        description=template["description"],
        prompt=template["prompt"],
        skills=template["skills"],
        mcps=template["mcps"],
        source=f"template:{template['id']}",
    )
    create_dm_conversation(conn, workspace_id, agent_id)
    return conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()


def create_dm_conversation(
    conn: Database, workspace_id: str, agent_id: str
) -> Row:
    existing = conn.execute(
        """
        SELECT * FROM conversations
        WHERE workspace_id = ? AND kind = 'dm' AND agent_id = ?
        """,
        (workspace_id, agent_id),
    ).fetchone()
    if existing is not None:
        return existing

    conversation_id = new_id("conv")
    created_at = now_iso()
    conn.execute(
        """
        INSERT INTO conversations (id, workspace_id, kind, name, agent_id, unread, created_at, updated_at)
        VALUES (?, ?, 'dm', '', ?, 0, ?, ?)
        """,
        (conversation_id, workspace_id, agent_id, created_at, created_at),
    )
    return conn.execute(
        "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
