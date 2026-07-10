"""Channel adapters: normalize a raw provider payload into a ChannelMessage."""

from __future__ import annotations

from app.channels.adapters.base import ChannelAdapter, ChannelMessage
from app.channels.adapters.email import EmailAdapter
from app.channels.adapters.generic import GenericWebhookAdapter

# Registry keyed by channel_configs.channel_type. wechat (XML + crypto) and
# web_widget (SSE session) inbound parsing land in a later slice; generic +
# email cover any system that can POST JSON.
_ADAPTERS: dict[str, ChannelAdapter] = {
    "generic_webhook": GenericWebhookAdapter(),
    "email": EmailAdapter(),
}


class UnsupportedChannelError(ValueError):
    """Raised when no adapter is registered for a channel type."""


def get_adapter(channel_type: str) -> ChannelAdapter:
    adapter = _ADAPTERS.get(channel_type)
    if adapter is None:
        raise UnsupportedChannelError(
            f"no adapter registered for channel type: {channel_type}"
        )
    return adapter


__all__ = [
    "ChannelAdapter",
    "ChannelMessage",
    "EmailAdapter",
    "GenericWebhookAdapter",
    "UnsupportedChannelError",
    "get_adapter",
]
