"""Which address is the client? (F-05)

The socket peer is the real client only when nothing sits in front of the app. Behind a reverse proxy the peer is the
proxy itself, so every user would share one address and one person's failed logins could lock everybody out.

``X-Forwarded-For`` is a header any client can forge, so it is used ONLY when the immediate peer is a proxy you have
listed in ``APP_TRUSTED_PROXIES``, and then we take the right-most address in the chain that is not itself a trusted
proxy (anything a client prepends to the header sits to the left of it and is ignored). Malformed values give "" (unknown
client), never a guess. Exact addresses only; CIDR ranges are not supported.
"""

from __future__ import annotations

import ipaddress
from typing import Iterable


def _normal(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return value.strip()


def resolve_client_ip(peer: str | None, forwarded_for: str | None, trusted: Iterable[str]) -> str:
    peer = _normal(peer or "")
    if not peer:
        return ""
    trusted_set = {_normal(t) for t in trusted if t.strip()}
    if peer not in trusted_set:
        return peer                                   # nothing trustworthy in front: the peer is the client
    hops = [h.strip() for h in (forwarded_for or "").split(",") if h.strip()]
    for hop in reversed(hops):
        try:
            address = str(ipaddress.ip_address(hop))
        except ValueError:
            return ""                                 # malformed hop: do not trust anything to its left
        if address in trusted_set:
            continue                                  # another of our own proxies: keep walking left
        return address
    return ""
