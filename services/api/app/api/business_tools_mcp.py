"""Per-Run controlled business tools exposed to Hermes over MCP."""

from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.core.config import settings
from app.runtime.business_tools_auth import decode_business_tool_token
from app.services.business_actions import BusinessToolError, invoke_business_tool


class BusinessTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            payload = decode_business_tool_token(token)
        except ValueError:
            return None
        return AccessToken(
            token=token,
            client_id=payload["agent_id"],
            scopes=["business-tools"],
            expires_at=int(payload["exp"]),
        )


business_mcp = FastMCP(
    "AgentPulse Business Tools",
    instructions=(
        "Use these tools for real external business actions. AgentPulse validates "
        "capabilities, credentials and owner approval before execution."
    ),
    token_verifier=BusinessTokenVerifier(),
    auth=AuthSettings(
        issuer_url="http://agentpulse.local",
        resource_server_url="http://agentpulse.local/mcp/business-tools",
        required_scopes=["business-tools"],
    ),
    streamable_http_path="/",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=settings.mcp_allowed_hosts,
        allowed_origins=settings.mcp_allowed_origins,
    ),
)


def _claims() -> dict:
    token = get_access_token()
    if token is None:
        raise BusinessToolError("missing business tool token")
    return decode_business_tool_token(token.token)


async def _invoke(tool_name: str, arguments: dict) -> dict:
    try:
        return await invoke_business_tool(
            _claims(), tool_name=tool_name, arguments=arguments
        )
    except BusinessToolError as exc:
        return {"ok": False, "status": "not_configured", "message": str(exc)}


@business_mcp.tool(description="Send a real plain-text email after AgentPulse approval.")
async def send_email(
    to: list[str],
    subject: str,
    body: str,
    channel_id: str = "",
    reply_to: str = "",
) -> dict:
    return await _invoke(
        "send_email",
        {
            "to": to,
            "subject": subject,
            "body": body,
            "channel_id": channel_id,
            "reply_to": reply_to,
        },
    )


@business_mcp.tool(description="Publish social content through a configured channel.")
async def publish_social_content(platform: str, content: str, account_id: str = "") -> dict:
    return await _invoke(
        "publish_social_content",
        {"platform": platform, "content": content, "account_id": account_id},
    )


@business_mcp.tool(description="Process a refund through a configured order provider.")
async def process_refund(order_id: str, amount: float, reason: str) -> dict:
    return await _invoke(
        "process_refund", {"order_id": order_id, "amount": amount, "reason": reason}
    )


@business_mcp.tool(description="Change an advertising bid or budget.")
async def update_ad_bid(campaign_id: str, amount: float, currency: str = "CNY") -> dict:
    return await _invoke(
        "update_ad_bid",
        {"campaign_id": campaign_id, "amount": amount, "currency": currency},
    )


@business_mcp.tool(description="Submit a payroll period to a configured HR provider.")
async def submit_payroll(period: str, total: float, notes: str = "") -> dict:
    return await _invoke(
        "submit_payroll", {"period": period, "total": total, "notes": notes}
    )


@business_mcp.tool(description="Execute a payment. Every call requires one-time approval.")
async def execute_payment(
    payee: str, amount: float, currency: str, reference: str = ""
) -> dict:
    return await _invoke(
        "execute_payment",
        {
            "payee": payee,
            "amount": amount,
            "currency": currency,
            "reference": reference,
        },
    )


business_tools_app = business_mcp.streamable_http_app()


@asynccontextmanager
async def business_tools_lifespan():
    async with business_mcp.session_manager.run():
        yield
