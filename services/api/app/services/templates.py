from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
import json


TALENT_CATEGORIES = [
    {
        "id": "business-ops",
        "name": "经营管理",
        "description": "目标拆解、经营复盘、流程优化、项目推进与跨岗位协同类官方人才",
        "sort_order": 10,
    },
    {
        "id": "content-growth",
        "name": "内容增长",
        "description": "选题、文案、脚本、品牌叙事、SEO 与内容分发类官方人才",
        "sort_order": 20,
    },
    {
        "id": "sales-success",
        "name": "销售客户",
        "description": "线索跟进、客户响应、报价、FAQ、成交支持与客户成功类官方人才",
        "sort_order": 30,
    },
    {
        "id": "finance-office",
        "name": "财务行政",
        "description": "记账、对账、报表、行政支持、合规检查与异常提醒类官方人才",
        "sort_order": 40,
    },
]


AGENT_TEMPLATES = [
    {
        "id": "ops-lead",
        "name": "运营负责人",
        "category_id": "business-ops",
        "category": "经营管理",
        "department": "运营部",
        "description": "渠道、预算、节奏",
        "prompt": "你是一名资深运营负责人。负责渠道盘点、预算分配与节奏把控，输出可直接执行的运营方案，并统筹团队成员分工。",
        "skills": ["数据报表", "竞品分析", "投放策略"],
        "mcps": ["飞书文档", "Notion"],
        "publisher": "AgentPulse 官方",
        "version": "v0.1.0",
        "status": "published",
    },
    {
        "id": "content-writer",
        "name": "内容主笔",
        "category_id": "content-growth",
        "category": "内容增长",
        "department": "内容部",
        "description": "文案、品牌叙事",
        "prompt": "你是一名内容主笔。擅长品牌叙事与转化型文案，为官网、公众号与销售物料产出高质量内容。",
        "skills": ["公众号文案", "SEO 优化"],
        "mcps": ["飞书文档", "微信公众号"],
        "publisher": "AgentPulse 官方",
        "version": "v0.1.0",
        "status": "published",
    },
    {
        "id": "video-planner",
        "name": "短视频策划",
        "category_id": "content-growth",
        "category": "内容增长",
        "department": "内容部",
        "description": "选题、脚本、分发",
        "prompt": "你是一名短视频策划。负责选题、脚本与分发节奏，选题要能挂钩获客目标。",
        "skills": ["公众号文案"],
        "mcps": ["飞书文档"],
        "publisher": "AgentPulse 官方",
        "version": "v0.1.0",
        "status": "published",
    },
    {
        "id": "sales-consultant",
        "name": "销售顾问",
        "category_id": "sales-success",
        "category": "销售客户",
        "department": "增长与客户",
        "description": "线索、报价、周报",
        "prompt": "你是一名销售顾问。负责线索跟进、报价与周报，成交卡点要及时上报老板拍板。",
        "skills": ["客服话术", "数据报表"],
        "mcps": ["企业邮箱", "Notion"],
        "publisher": "AgentPulse 官方",
        "version": "v0.1.0",
        "status": "published",
    },
    {
        "id": "support-agent",
        "name": "客服专员",
        "category_id": "sales-success",
        "category": "销售客户",
        "department": "增长与客户",
        "description": "FAQ、话术、响应",
        "prompt": "你是一名客服专员。基于公司 FAQ 与话术库回复客户，超出权限的承诺必须请老板拍板。",
        "skills": ["客服话术"],
        "mcps": ["企业邮箱"],
        "publisher": "AgentPulse 官方",
        "version": "v0.1.0",
        "status": "published",
    },
    {
        "id": "finance-assistant",
        "name": "财务助理",
        "category_id": "finance-office",
        "category": "财务行政",
        "department": "财务行政",
        "description": "记账、对账、报表",
        "prompt": "你是一名财务助理。负责记账、对账与月度报表，任何异常支出立即标红上报。",
        "skills": ["数据报表"],
        "mcps": ["Stripe", "飞书文档"],
        "publisher": "AgentPulse 官方",
        "version": "v0.1.0",
        "status": "published",
    },
]


def seed_official_talent_market(conn: Any) -> None:
    now = datetime.now(UTC).isoformat()
    for category in TALENT_CATEGORIES:
        existing = conn.execute(
            "SELECT id FROM official_talent_categories WHERE id = ?",
            (category["id"],),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO official_talent_categories (
                  id, name, description, sort_order, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'published', ?, ?)
                """,
                (
                    category["id"],
                    category["name"],
                    category["description"],
                    category["sort_order"],
                    now,
                    now,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE official_talent_categories
                SET name = ?, description = ?, sort_order = ?, status = 'published',
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    category["name"],
                    category["description"],
                    category["sort_order"],
                    now,
                    category["id"],
                ),
            )

    for template in AGENT_TEMPLATES:
        existing = conn.execute(
            "SELECT id FROM official_agent_templates WHERE id = ?",
            (template["id"],),
        ).fetchone()
        values = (
            template["category_id"],
            template["name"],
            template["department"],
            template["description"],
            template["prompt"],
            json.dumps(template["skills"], ensure_ascii=False),
            json.dumps(template["mcps"], ensure_ascii=False),
            template["publisher"],
            template["version"],
            template["status"],
            now,
            template["id"],
        )
        if existing is None:
            conn.execute(
                """
                INSERT INTO official_agent_templates (
                  id, category_id, name, department, description, prompt,
                  skills_json, mcps_json, publisher, version, status,
                  created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template["id"],
                    template["category_id"],
                    template["name"],
                    template["department"],
                    template["description"],
                    template["prompt"],
                    json.dumps(template["skills"], ensure_ascii=False),
                    json.dumps(template["mcps"], ensure_ascii=False),
                    template["publisher"],
                    template["version"],
                    template["status"],
                    now,
                    now,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE official_agent_templates
                SET category_id = ?, name = ?, department = ?, description = ?,
                    prompt = ?, skills_json = ?, mcps_json = ?, publisher = ?,
                    version = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                values,
            )


def list_talent_categories(conn: Any) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, name, description, sort_order
        FROM official_talent_categories
        WHERE status = 'published'
        ORDER BY sort_order, name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def list_agent_templates(conn: Any) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
          templates.id,
          templates.category_id,
          categories.name AS category,
          templates.name,
          templates.department,
          templates.description,
          templates.prompt,
          templates.skills_json,
          templates.mcps_json,
          templates.publisher,
          templates.version,
          templates.status
        FROM official_agent_templates AS templates
        JOIN official_talent_categories AS categories
          ON categories.id = templates.category_id
        WHERE templates.status = 'published'
          AND categories.status = 'published'
        ORDER BY categories.sort_order, templates.updated_at DESC, templates.name
        """
    ).fetchall()
    return [serialize_template(row) for row in rows]


def get_template(conn: Any, template_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT
          templates.id,
          templates.category_id,
          categories.name AS category,
          templates.name,
          templates.department,
          templates.description,
          templates.prompt,
          templates.skills_json,
          templates.mcps_json,
          templates.publisher,
          templates.version,
          templates.status
        FROM official_agent_templates AS templates
        JOIN official_talent_categories AS categories
          ON categories.id = templates.category_id
        WHERE templates.id = ?
          AND templates.status = 'published'
          AND categories.status = 'published'
        """,
        (template_id,),
    ).fetchone()
    return serialize_template(row) if row is not None else None


def serialize_template(row: Sequence[Any] | dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "category_id": row["category_id"],
        "category": row["category"],
        "department": row["department"],
        "description": row["description"],
        "prompt": row["prompt"],
        "skills": json.loads(row["skills_json"]),
        "mcps": json.loads(row["mcps_json"]),
        "publisher": row["publisher"],
        "version": row["version"],
        "status": row["status"],
    }
