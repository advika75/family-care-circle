"""In-memory sliding-window throttle for logins, sign-ups, password changes and invitation-code attempts.

Documented limitation: state lives in this process only. It resets on restart and is not shared between worker
processes, so it is NOT distributed rate limiting.

Memory (F-06): the number of tracked keys is bounded. Expired keys are dropped as they age out, a periodic full sweep
removes the rest, and ``max_keys`` is a hard cap (least recently written keys go first). A key that is being actively
attacked is kept "recent" every time it is checked, so flooding the table with junk cannot flush it and unblock it.
"""

from __future__ import annotations

import threading
from collections import OrderedDict, deque
from typing import Callable


class Throttle:
    def __init__(self, clock: Callable[[], float], window_seconds: int = 900, max_keys: int = 20_000) -> None:
        self._clock = clock
        self.window = window_seconds
        self.max_keys = max_keys
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._writes = 0

    def _fresh(self, q: deque[float], now: float) -> bool:
        while q and now - q[0] > self.window:
            q.popleft()
        return bool(q)

    def _evict(self, now: float) -> None:
        # cheap, amortised: expired keys are mostly at the front (oldest write first)
        while self._events:
            key, q = next(iter(self._events.items()))
            if self._fresh(q, now):
                break
            del self._events[key]
        if self._writes % 1024 == 0:                                  # periodic full sweep for expired keys elsewhere
            for key in [k for k, q in self._events.items() if not self._fresh(q, now)]:
                del self._events[key]
        while len(self._events) > self.max_keys:                      # hard cap: drop the least recently written
            self._events.popitem(last=False)

    def blocked(self, key: str, limit: int) -> bool:
        """True once ``limit`` events were recorded for ``key`` inside the window."""
        now = self._clock()
        with self._lock:
            q = self._events.get(key)
            if q is None or not self._fresh(q, now):
                return False
            if len(q) >= limit:
                self._events.move_to_end(key)                         # being attacked: keep it from being evicted
                return True
            return False

    def record_failure(self, *keys: str) -> None:
        now = self._clock()
        with self._lock:
            for key in keys:
                q = self._events.get(key)
                if q is None:
                    q = self._events[key] = deque()
                else:
                    self._events.move_to_end(key)
                self._fresh(q, now)
                q.append(now)
                self._writes += 1
            self._evict(now)

    def reset(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._events.pop(key, None)
