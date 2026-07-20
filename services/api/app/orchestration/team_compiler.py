"""Team compiler — turn one free-text org description into N role drafts.

The "last mile" gap this closes: a boss who can describe a whole custom team
in one paragraph (see the CEO/CTO/COO/CFO/CMO/CCO/HR elder-care + Douyin
example that motivated this) had no way to turn that into real employees
without manually filling in a "create employee" form once per role and
guessing at capability keys.

This module only extracts *which roles exist* and *what each one roughly
does* from the paragraph — the actual per-role validation (stripping unknown
capability keys, capping responsibilities) reuses the already-built, already-
tested `orchestration.provisioning.draft_role_spec` (TD-04-T3), which existed
but had never been wired to anything that calls an LLM and creates a real
agent from it. Turning a role name into a real, provisioned Hermes employee
reuses `services.workspace.provision_new_agent` — the same function every
other hiring path (Talent Market, the create_employee tool) goes through.

No new provisioning logic here — this module is purely "parse the paragraph
into role drafts."
"""

from __future__ import annotations

import json

from app.orchestration.capability_catalog import CATALOG
from app.orchestration.provisioning import draft_role_spec

_TEAM_DRAFT_SYSTEM_PROMPT = """你是团队编译器：把老板用一段话描述的团队，拆解成一份可以直接建成真实 AI 员工的团队草稿。

输出格式（严格 JSON，不要多余文字、不要 markdown 代码块标记）：
{{
  "members": [
    {{
      "name": "员工名字",
      "role": "岗位名称",
      "department": "所属部门",
      "description": "这个岗位一句话职责概述",
      "responsibilities": ["具体职责1", "具体职责2", ...],
      "suggested_capability_keys": ["key1", "key2", ...]
    }},
    ...
  ]
}}

可选的能力 key（只从以下选取，找不到贴切的就不填，不要编造不存在的 key）：
{available_keys}

规则：
1. 老板描述里提到几个岗位就拆几个 member，不要合并也不要凭空多加。
2. responsibilities 要贴着老板原话拆，不超过 8 条，每条不超过 150 字；老板没说清楚的部分不要替他编造细节。
3. 有些岗位天生是"随时支援、没有固定清单"的（比如"机动备援""哪里需要去哪里"），这种岗位 responsibilities 可以写成一段判断性的指引而不是清单，照实反映，不要硬凑成看起来标准的条目。
4. suggested_capability_keys 只从上面的目录里选，宁缺勿滥；纯判断/协调类的岗位（不碰文件、不跑代码、不查数据）可以完全不选。
5. department 尽量沿用老板原话里出现的部门/业务线名字，没提到就按岗位性质合理归类。
"""


class TeamDraftError(ValueError):
    """Raised when the LLM output can't be parsed into a team draft."""


def build_team_draft_prompt() -> str:
    """System prompt instructing the LLM to extract role drafts from a
    free-text org description. The description itself goes in the user
    message, not here, so the same prompt is reusable for any description."""
    available_keys = "\n".join(
        f"- {key}: {cap.description}" for key, cap in sorted(CATALOG.items())
    )
    return _TEAM_DRAFT_SYSTEM_PROMPT.format(available_keys=available_keys)


def parse_team_draft(raw_text: str, *, source_request: str) -> list[dict]:
    """Parse + validate the LLM's raw JSON response into a list of member
    drafts, each already run through draft_role_spec (so capability keys
    are guaranteed real, responsibilities are capped).

    Raises TeamDraftError if the shape is unusable (missing name/role, not
    valid JSON) — the caller should surface this as "didn't understand,
    please clarify" rather than silently fabricating a team.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise TeamDraftError(f"团队草稿解析失败：{exc}") from exc

    raw_members = data.get("members") if isinstance(data, dict) else None
    if not isinstance(raw_members, list) or not raw_members:
        raise TeamDraftError("团队草稿里没有解析出任何角色")

    members: list[dict] = []
    for raw in raw_members:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        role = str(raw.get("role") or "").strip()
        if not name or not role:
            continue  # skip malformed entries rather than fail the whole batch

        draft = draft_role_spec(
            role_name=role,
            source_request=source_request,
            llm_output={
                "responsibilities": raw.get("responsibilities", []),
                "suggested_capability_keys": raw.get("suggested_capability_keys", []),
            },
        )
        members.append(
            {
                "name": name[:24],
                "role": role[:24],
                "department": str(raw.get("department") or "").strip()[:40] or role[:40],
                "description": str(raw.get("description") or "").strip()[:400],
                "responsibilities": draft.responsibilities,
                "capability_keys": draft.capability_keys,
            }
        )

    if not members:
        raise TeamDraftError("团队草稿里没有解析出任何有效角色")
    return members
