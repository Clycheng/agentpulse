from typing import Any

import httpx

from app.core.config import settings
from app.schemas.run import LlmChatMessage, LlmChatRequest, LlmChatResponse


class DeepSeekNotConfigured(RuntimeError):
    pass


class DeepSeekAPIError(RuntimeError):
    pass


class DeepSeekChatClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.deepseek_api_key
        self.base_url = (
            base_url if base_url is not None else settings.deepseek_base_url
        ).rstrip("/")
        self.model = model if model is not None else settings.deepseek_model
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.deepseek_timeout_seconds
        )

    async def complete(self, request: LlmChatRequest) -> LlmChatResponse:
        if not self.api_key:
            raise DeepSeekNotConfigured(
                "DeepSeek API Key 未配置，请设置 AGENTPULSE_DEEPSEEK_API_KEY"
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": build_system_prompt(request)},
                *[message_to_deepseek(message) for message in request.messages],
            ],
            "stream": False,
            "thinking": {
                "type": "enabled" if settings.deepseek_thinking_enabled else "disabled"
            },
        }
        if not settings.deepseek_thinking_enabled:
            payload["temperature"] = settings.deepseek_temperature

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise DeepSeekAPIError("DeepSeek 请求超时，请稍后重试") from exc
        except httpx.HTTPError as exc:
            raise DeepSeekAPIError(f"DeepSeek 请求失败：{exc}") from exc

        if response.status_code >= 400:
            raise DeepSeekAPIError(
                f"DeepSeek API 返回 {response.status_code}：{extract_error(response)}"
            )

        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise DeepSeekAPIError("DeepSeek 返回了无法解析的响应") from exc

        content = extract_reply(data)
        if not content:
            raise DeepSeekAPIError("DeepSeek 没有返回有效回复")

        return LlmChatResponse(
            reply=clean_agent_prefix(content, request.agent.name),
            provider="deepseek",
            model=str(data.get("model") or self.model),
            usage=data.get("usage"),
        )


def build_system_prompt(request: LlmChatRequest) -> str:
    agent = request.agent
    skills = "、".join(agent.skills) if agent.skills else "暂无绑定技能"
    conversation = request.conversation_title or "当前会话"
    related_tasks = format_related_tasks(request)

    return f"""你是 AgentPulse 里的 AI 员工，需要像真实团队成员一样帮助老板推进一人公司的工作。

公司：{request.company_name}
当前会话：{conversation}
{related_tasks}

你的员工档案：
- 姓名：{agent.name}
- 岗位：{agent.role or "未填写"}
- 部门：{agent.department or "未分配"}
- 技能：{skills}

你的工作职责 Prompt：
{agent.prompt}

回复规则：
1. 使用中文，语气专业、直接、可靠。
2. 如果老板给的是模糊想法，先帮助拆解成下一步，而不是空泛鼓励。
3. 不要声称已经发送邮件、创建外部文档、发布内容或操作第三方系统；第一版你只能回复消息和提出计划。
4. 如果需要老板确认，明确列出需要拍板的问题和可选方案。
5. 如果需要其他员工协作，可以在回复里写出建议 @谁，但不要假装他们已经执行。
6. 输出尽量结构化，优先给老板可直接推进的下一步。"""


def format_related_tasks(request: LlmChatRequest) -> str:
    if not request.related_tasks:
        return "\n当前关联任务：无"

    lines = ["\n当前关联任务："]
    for index, task in enumerate(request.related_tasks, start=1):
        owner = f"，负责人：{task.owner_name}" if task.owner_name else ""
        description = f"\n   说明：{task.description}" if task.description else ""
        lines.append(
            f"{index}. [{task.priority}] {task.title} "
            f"({task.status}，进度 {task.progress}%{owner}){description}"
        )
    return "\n".join(lines)


def message_to_deepseek(message: LlmChatMessage) -> dict[str, str]:
    speaker = f"{message.name}：" if message.name else ""
    return {"role": message.role, "content": f"{speaker}{message.content}"}


def extract_reply(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""

    message = first_choice.get("message")
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def clean_agent_prefix(content: str, agent_name: str) -> str:
    cleaned = content.strip()
    prefixes = [
        f"{agent_name}：",
        f"{agent_name}:",
        f"{agent_name}：{agent_name}：",
        f"{agent_name}:{agent_name}:",
    ]
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :].lstrip()
                changed = True
    return cleaned


def extract_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:500]

    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
        message = data.get("message")
        if isinstance(message, str):
            return message

    return str(data)[:500]
