"""Email inbound adapter (SendGrid / Mailgun inbound-parse style JSON).

Providers post the parsed inbound email as JSON. We thread by sender address and
dedup on the RFC Message-Id. Field locations are configurable (config_json) but
default to the common inbound-parse shape.
"""

from __future__ import annotations

from app.channels.adapters.base import ChannelMessage
from app.channels.adapters.generic import _dig


class EmailAdapter:
    def normalize(self, config: dict, raw_payload: dict) -> ChannelMessage:
        sender = _dig(raw_payload, config.get("user_id_path", "from"))
        text = _dig(raw_payload, config.get("message_path", "text"))
        if text is None:
            text = _dig(raw_payload, "subject")
        message_id = _dig(raw_payload, config.get("message_id_path", "message_id"))

        if sender is None or not str(sender).strip():
            raise ValueError("email payload has no sender address")
        if text is None or not str(text).strip():
            raise ValueError("email payload has no body")

        return ChannelMessage(
            external_user_id=str(sender),
            content=str(text),
            external_message_id=str(message_id) if message_id is not None else None,
        )
