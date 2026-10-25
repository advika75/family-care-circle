"""Per-process context shared by the service functions: settings, throttle and an injectable clock."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from app.config import Settings
from app.throttle import Throttle

#: failures allowed per window before further attempts are refused
LOGIN_FAILURES_PER_PAIR = 5          # wrong passwords for one account from one address
LOGIN_FAILURES_PER_EMAIL = 25        # wrong passwords for one account from ALL addresses together
LOGIN_FAILURES_PER_IP = 20           # wrong passwords from one address, any account
LOGIN_ATTEMPTS_PER_IP = 60           # every login attempt from one address, right or wrong (each costs ~60 ms of CPU)
SIGNUPS_PER_IP = 10                  # sign-up attempts from one address, accepted or not
JOIN_FAILURES_PER_USER = 5
JOIN_FAILURES_PER_IP = 20


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Ctx:
    settings: Settings
    clock: Callable[[], datetime] = utc_now
    throttle: Throttle = field(init=False)

    def __post_init__(self) -> None:
        self.throttle = Throttle(lambda: self.clock().timestamp())

    def now(self) -> datetime:
        return self.clock()
