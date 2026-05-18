"""Simple in-memory rate limiter (per client IP)."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

_lock = Lock()
_buckets: dict[str, list[float]] = defaultdict(list)


def allow_request(
    client_ip: str,
    *,
    max_requests: int = 5,
    window_seconds: int = 60,
) -> tuple[bool, str]:
    """Return (allowed, message)."""
    now = time.time()
    cutoff = now - window_seconds

    with _lock:
        hits = [t for t in _buckets[client_ip] if t > cutoff]
        if len(hits) >= max_requests:
            return False, f"Rate limit exceeded: max {max_requests} requests per {window_seconds}s"
        hits.append(now)
        _buckets[client_ip] = hits

    return True, ""
