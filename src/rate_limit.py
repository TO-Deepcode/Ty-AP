"""Simple token bucket rate limiter keyed by hostname."""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict

@dataclass
class TokenBucket:
    capacity: float
    tokens: float
    refill_rate: float
    updated_at: float

    def consume(self, amount: float) -> bool:
        now = time.time()
        elapsed = now - self.updated_at
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.updated_at = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class RateLimiter:
    def __init__(self, qps: float = 0.5, burst: float = 1.0) -> None:
        self.qps = qps
        self.burst = burst
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        with self._lock:
            bucket = self._buckets.get(key)
            if not bucket:
                bucket = TokenBucket(capacity=self.burst, tokens=self.burst, refill_rate=self.qps, updated_at=time.time())
                self._buckets[key] = bucket
            return bucket.consume(1.0)


_default_limiter = RateLimiter()


def allow_request(host: str) -> bool:
    return _default_limiter.allow(host)
