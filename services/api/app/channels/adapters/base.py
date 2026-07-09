"""Adapter contract + the normalized message shape."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ChannelMessage:
    """A provider payload normalized into what the router needs.

    - external_user_id: stable id of the external sender (WeChat openid, email
      address, widget session…) — used to thread messages into one conversation.
    - content: the plain-text message body.
    - external_message_id: provider's unique id for this message; used to drop
      duplicate webhook redeliveries. None when the provider gives none (then no
      dedup is possible for that message).
    """

    external_user_id: str
    content: str
    external_message_id: str | None = None


class ChannelAdapter(Protocol):
    def normalize(self, config: dict, raw_payload: dict) -> ChannelMessage:
        """Turn a raw provider payload into a ChannelMessage.

        ``config`` is the parsed channel_configs.config_json. Raises ValueError
        when the payload is missing required fields.
        """
        ...
