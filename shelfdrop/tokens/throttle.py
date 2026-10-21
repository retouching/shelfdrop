"""TokenThrottle: the requests allowed to an access token, in memory (one process): 60 a minute
for each token. A container singleton."""

from collections import deque
from dataclasses import dataclass, field
from typing import Final

TOKEN_LIMIT: Final = 60
TOKEN_SECONDS: Final = 60.0


@dataclass
class TokenThrottle:
    by_token: dict[int, deque[float]] = field(default_factory=dict)

    def allow(self, token_id: int, now: float) -> bool:
        """Whether a request of this token may go now; a request allowed is counted."""
        recent = self.by_token.setdefault(token_id, deque())
        while recent and recent[0] <= now - TOKEN_SECONDS:
            recent.popleft()
        if len(recent) >= TOKEN_LIMIT:
            return False
        recent.append(now)
        return True
