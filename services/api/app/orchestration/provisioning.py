"""Provisioning orchestration: role_spec drafting + SOUL.md generation (TD-04-T3).

Two core functions:
- draft_role_spec: LLM drafts responsibilities + capability keys, with hard validation
- draft_soul_md: LLM generates SOUL.md from role spec

Security rules (hardcoded, not up to LLM):
- Unknown capability keys are silently stripped
- risk_gate is always taken from catalog, never from LLM output
- domain_register is always prohibited_auto
"""

from __future__ import annotations

import json
from typing import Any

from app.orchestration.capability_catalog import (
    CATALOG,
    CapabilityDef,
    get_capability,
    resolve_bundle,
    validate_capability_keys,
)

# Prompts for LLM drafting
_ROLE_SPEC_SYSTEM_PROMPT = """你是一个 AI 员工配置助手。根据用户描述，输出该员工的职责和能力需求。

输出格式（严格 JSON，不要多余文字）：
{{
  "responsibilities": ["职责1", "职责2", ...],
  "suggested_capability_keys": ["key1", "key2", ...]
}}

可用能力 key（只从以下选取）：
{available_keys}

规则：
1. responsibilities 不超过 12 条，每条不超过 200 字
2. suggested_capability_keys 只从上面的可用 key 中选取
3. 根据用户描述合理推断需要的能力，宁多勿少
"""

_SOUL_MD_SYSTEM_PROMPT = """你是一个 AI 人格设计专家。根据员工角色信息，生成 SOUL.md 文件内容。

SOUL.md 是 Hermes Agent 的人格文件，定义了 AI 员工的行为准则。

格式要求：
- 以 Markdown 格式输出
- 第一行是 # 角色名
- 包含以下章节：## 角色定位、## 核心职责、## 行为准则、## 沟通风格
- 行为准则必须包含：背景不清楚时先提问，不盲目执行
- 语气专业但友好
- 不超过 500 字

公司名：{company_name}
产品：AI 公司工作台（AgentPulse）

员工职责：
{responsibilities_text}

员工能力：
{capabilities_text}
"""


class RoleSpecDraft:
    """Result of drafting a role spec."""

    def __init__(
        self,
        role_name: str,
        source_request: str,
        responsibilities: list[str],
        capability_keys: list[str],
        invalid_keys_stripped: list[str],
    ) -> None:
        self.role_name = role_name
        self.source_request = source_request
        self.responsibilities = responsibilities
        self.capability_keys = capability_keys
        self.invalid_keys_stripped = invalid_keys_stripped


def draft_role_spec(
    role_name: str,
    source_request: str,
    user_capability_keys: list[str] | None = None,
    llm_output: dict[str, Any] | None = None,
) -> RoleSpecDraft:
    """Draft a role specification for an agent.

    This function combines LLM-suggested capabilities with user-selected ones,
    applying hard validation rules:
    - Unknown capability keys are stripped (not an error)
    - risk_gate is always from catalog, never from LLM
    - User keys and LLM keys are unioned

    Args:
        role_name: Role name (e.g. "前端工程师")
        source_request: User's natural language description
        user_capability_keys: Keys explicitly selected by user
        llm_output: Pre-parsed LLM output dict with
            'responsibilities' and 'suggested_capability_keys'.
            If None, only user keys are used (no LLM call here).

    Returns:
        RoleSpecDraft with validated keys and stripped invalid keys listed
    """
    user_keys = set(user_capability_keys or [])
    llm_keys: set[str] = set()

    if llm_output:
        llm_keys = set(llm_output.get("suggested_capability_keys", []))

    # Union of user and LLM keys
    all_keys = user_keys | llm_keys

    # Validate: separate known from unknown
    valid_keys: list[str] = []
    invalid_keys: list[str] = []
    for key in sorted(all_keys):
        if key in CATALOG:
            valid_keys.append(key)
        else:
            invalid_keys.append(key)

    # Get responsibilities from LLM output, or empty
    responsibilities: list[str] = []
    if llm_output:
        raw_resp = llm_output.get("responsibilities", [])
        if isinstance(raw_resp, list):
            # Limit to 12 items, each <= 200 chars
            responsibilities = [
                str(r)[:200] for r in raw_resp[:12]
            ]

    return RoleSpecDraft(
        role_name=role_name,
        source_request=source_request,
        responsibilities=responsibilities,
        capability_keys=valid_keys,
        invalid_keys_stripped=invalid_keys,
    )


def build_role_spec_prompt(source_request: str) -> str:
    """Build the system prompt for LLM role_spec drafting.

    This is called by the API layer before making the LLM call.
    The LLM output is then passed to draft_role_spec().
    """
    available_keys = "\n".join(
        f"- {key}: {cap.description}" for key, cap in sorted(CATALOG.items())
    )
    return _ROLE_SPEC_SYSTEM_PROMPT.format(available_keys=available_keys)


def build_soul_md_prompt(
    role_name: str,
    responsibilities: list[str],
    capability_keys: list[str],
    company_name: str = "我的公司",
) -> str:
    """Build the system prompt for SOUL.md generation.

    Args:
        role_name: Role name
        responsibilities: List of responsibilities
        capability_keys: Validated capability keys
        company_name: Company name for personalization

    Returns:
        System prompt string for LLM call
    """
    cap_descriptions = []
    for key in capability_keys:
        cap = get_capability(key)
        cap_descriptions.append(f"- {key}: {cap.description}")

    caps_text = "\n".join(cap_descriptions) if cap_descriptions else "无特定能力要求"
    resp_text = "\n".join(f"- {r}" for r in responsibilities) if responsibilities else "待补充"

    return _SOUL_MD_SYSTEM_PROMPT.format(
        company_name=company_name,
        responsibilities_text=resp_text,
        capabilities_text=caps_text,
    )


def draft_soul_md(
    role_name: str,
    responsibilities: list[str],
    capability_keys: list[str],
    company_name: str = "我的公司",
    llm_soul_text: str | None = None,
) -> str:
    """Generate a SOUL.md string for an agent.

    If llm_soul_text is provided (from LLM call), it's used as-is
    (the prompt already constrains format).
    If not, a template-based fallback is generated.

    Args:
        role_name: Role name
        responsibilities: List of responsibilities
        capability_keys: Validated capability keys
        company_name: Company name
        llm_soul_text: LLM-generated SOUL.md text (optional)

    Returns:
        SOUL.md content string
    """
    if llm_soul_text:
        return llm_soul_text

    # Fallback template (when no LLM available)
    cap_descriptions = []
    for key in capability_keys:
        cap = get_capability(key)
        cap_descriptions.append(f"- {cap.description}")

    caps_section = "\n".join(cap_descriptions) if cap_descriptions else "暂无"
    resp_section = "\n".join(f"- {r}" for r in responsibilities) if responsibilities else "- 待确认"

    return f"""# {role_name}

## 角色定位
你是{company_name}的{role_name}，负责以下职责：
{resp_section}

## 核心职责
{resp_section}

## 行为准则
- 背景不清楚时先提问，不盲目执行
- 涉及高风险操作（部署生产、花钱、不可逆操作）必须请示老板
- 主动汇报工作进展
- 遇到问题及时沟通，不隐瞒

## 沟通风格
- 专业、简洁、友好
- 用中文沟通
- 关键信息用列表呈现

## 能力范围
{caps_section}
"""
