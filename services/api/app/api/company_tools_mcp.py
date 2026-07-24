"""Streamable HTTP MCP surface for per-run AgentPulse company tools."""

from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.core.config import settings
from app.core.database import connect
from app.runtime.company_tools_auth import decode_company_tool_token
from app.services import company_tools


class CompanyTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            payload = decode_company_tool_token(token)
        except ValueError:
            return None
        return AccessToken(
            token=token,
            client_id=payload["agent_id"],
            scopes=["company-tools"],
            expires_at=int(payload["exp"]),
        )


company_mcp = FastMCP(
    "AgentPulse Company Tools",
    instructions="Use these tools to read company context and report durable task state.",
    token_verifier=CompanyTokenVerifier(),
    auth=AuthSettings(
        issuer_url="http://agentpulse.local",
        resource_server_url="http://agentpulse.local/mcp/company-tools",
        required_scopes=["company-tools"],
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
    access_token = get_access_token()
    if access_token is None:
        raise company_tools.CompanyToolError("missing company tool token")
    return decode_company_tool_token(access_token.token)


def _call(operation, **kwargs):
    conn = connect()
    try:
        result = operation(conn, _claims(), **kwargs)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@company_mcp.tool(description="Search the current workspace knowledge base first.")
async def search_company_knowledge(query: str, limit: int = 5) -> list[dict]:
    return _call(company_tools.search_company_knowledge, query=query, limit=limit)


@company_mcp.tool(description="Persist task progress and a short factual summary.")
async def report_progress(progress: int, summary: str) -> dict:
    return _call(company_tools.report_progress, progress=progress, summary=summary)


@company_mcp.tool(description="Submit the task's contracted Markdown or content_package_v1 output.")
async def submit_output(
    title: str, output_type: str, content: str | dict
) -> dict:
    return _call(
        company_tools.submit_output,
        title=title,
        output_type=output_type,
        content=content,
    )


@company_mcp.tool(description="Add a subtask within the confirmed brief scope.")
async def create_subtask(
    title: str,
    description: str,
    owner_agent_id: str,
    expected_output: str,
    output_type: str = "markdown",
    depends_on_task_ids: list[str] | None = None,
) -> dict:
    return _call(
        company_tools.create_subtask,
        title=title,
        description=description,
        owner_agent_id=owner_agent_id,
        expected_output=expected_output,
        output_type=output_type,
        depends_on_task_ids=depends_on_task_ids,
    )


@company_mcp.tool(description="Request a brief participant to produce supporting work.")
async def request_support(
    agent_id: str, request: str, expected_output: str
) -> dict:
    return _call(
        company_tools.request_support,
        agent_id=agent_id,
        request=request,
        expected_output=expected_output,
    )


@company_mcp.tool(description="Block the task with the exact missing information or failure reason.")
async def block_task(reason: str) -> dict:
    return _call(company_tools.block_task, reason=reason)


company_tools_app = company_mcp.streamable_http_app()


@asynccontextmanager
async def company_tools_lifespan():
    async with company_mcp.session_manager.run():
        yield
