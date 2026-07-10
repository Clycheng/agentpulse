"""Generic webhook adapter — extracts fields by configurable dot-paths.

config_json fields (all optional, with sensible defaults):
  message_path      default "message"      → message body
  user_id_path      default "user_id"      → external user id
  message_id_path   default "message_id"   → external message id (for dedup)

Paths are simple dotted paths into the JSON, with an optional leading "$."
(e.g. "$.user.id" or "data.text"). Anything a system can POST as JSON works.
"""

from __future__ import annotations

from typing import Any

from app.channels.adapters.base import ChannelMessage


def _dig(payload: Any, path: str) -> Any:
    node = payload
    for key in path.removeprefix("$.").split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


class GenericWebhookAdapter:
    def normalize(self, config: dict, raw_payload: dict) -> ChannelMessage:
        content = _dig(raw_payload, config.get("message_path", "message"))
        user_id = _dig(raw_payload, config.get("user_id_path", "user_id"))
        message_id = _dig(raw_payload, config.get("message_id_path", "message_id"))

        if content is None or not str(content).strip():
            raise ValueError("generic webhook payload has no message content")
        if user_id is None or not str(user_id).strip():
            raise ValueError("generic webhook payload has no user id")

        return ChannelMessage(
            external_user_id=str(user_id),
            content=str(content),
            external_message_id=str(message_id) if message_id is not None else None,
        )
