"""Channel adapters: normalize a raw provider payload into a ChannelMessage."""

from __future__ import annotations

from app.channels.adapters.base import ChannelAdapter, ChannelMessage
from app.channels.adapters.generic import GenericWebhookAdapter

# Registry keyed by channel_configs.channel_type. TD-09-T2 fills in the
# wechat / email / web_widget adapters; the generic one is enough for T1 and
# for any system that can POST JSON.
_ADAPTERS: dict[str, ChannelAdapter] = {
    "generic_webhook": GenericWebhookAdapter(),
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
    "GenericWebhookAdapter",
    "UnsupportedChannelError",
    "get_adapter",
]
