"""Outbound email providers used only by the controlled business worker."""

from __future__ import annotations

import httpx

from app.core.config import settings


class EmailProviderError(RuntimeError):
    pass


async def send_resend_email(
    *,
    api_key: str,
    idempotency_key: str,
    from_address: str,
    from_name: str,
    to: list[str],
    subject: str,
    body: str,
    reply_to: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict:
    payload: dict = {
        "from": f"{from_name} <{from_address}>" if from_name else from_address,
        "to": to,
        "subject": subject,
        "text": body,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=15.0)
    try:
        response = await http.post(
            f"{settings.resend_base_url.rstrip('/')}/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            json=payload,
        )
        if response.status_code >= 400:
            detail = response.text[:1000]
            raise EmailProviderError(
                f"Resend returned {response.status_code}: {detail}"
            )
        data = response.json()
        external_id = data.get("id")
        if not external_id:
            raise EmailProviderError("Resend response did not include an email id")
        return {"id": str(external_id)}
    except httpx.HTTPError as exc:
        raise EmailProviderError(f"Resend request failed: {exc}") from exc
    finally:
        if owns_client:
            await http.aclose()
