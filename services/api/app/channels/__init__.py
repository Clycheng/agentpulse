"""External channel adapters (TD-09).

Inbound external messages (WeChat / email / web widget / generic webhook) are
normalized into a standard ChannelMessage and routed into the ordinary
conversation/message flow — agents never learn which channel a message came
from. TD-09-T1 provides the data model, the generic adapter, and the router
core (normalize -> find-or-create conversation -> dedup -> persist). The public
webhook endpoints, per-channel adapters and reply-back path are TD-09-T2/T3.
"""
