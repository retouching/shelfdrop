"""LoginThrottle: the sign-in attempts allowed, in memory (one process): 5 a minute from one
address, 30 an hour from everywhere. A container singleton."""

from collections import deque
from dataclasses import dataclass, field
from typing import Final

ADDRESS_LIMIT: Final = 5
ADDRESS_SECONDS: Final = 60.0
OVERALL_LIMIT: Final = 30
OVERALL_SECONDS: Final = 3600.0


@dataclass
class LoginThrottle:
    by_address: dict[str, deque[float]] = field(default_factory=dict)
    overall: deque[float] = field(default_factory=deque)

    def allow(self, address: str, now: float) -> bool:
        """Whether an attempt from `address` may go now; an attempt allowed is counted."""
        self.forget(now)
        recent = self.by_address.setdefault(address, deque())
        if len(recent) >= ADDRESS_LIMIT or len(self.overall) >= OVERALL_LIMIT:
            return False
        recent.append(now)
        self.overall.append(now)
        return True

    def forget(self, now: float) -> None:
        while self.overall and self.overall[0] <= now - OVERALL_SECONDS:
            self.overall.popleft()
        for address, recent in list(self.by_address.items()):
            while recent and recent[0] <= now - ADDRESS_SECONDS:
                recent.popleft()
            if not recent:
                del self.by_address[address]
