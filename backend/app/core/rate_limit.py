from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._next_cleanup = 0.0

    def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            if now >= self._next_cleanup:
                self._events = defaultdict(deque, {
                    key: events for key, events in self._events.items() if events[-1] > cutoff
                })
                self._next_cleanup = now + self.window_seconds
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


password_reset_rate_limiter = InMemoryRateLimiter(limit=5, window_seconds=15 * 60)
password_reset_confirmation_limiter = InMemoryRateLimiter(limit=5, window_seconds=15 * 60)
patient_password_change_limiter = InMemoryRateLimiter(limit=5, window_seconds=15 * 60)
