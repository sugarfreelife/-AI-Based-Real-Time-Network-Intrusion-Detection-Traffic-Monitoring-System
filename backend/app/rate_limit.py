"""Bounded in-process fixed-window throttling for login failures."""

from __future__ import annotations

import ipaddress
import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable

from fastapi import Request

LoginKey = tuple[str, str]
_OVERFLOW_KEY: LoginKey = ("__overflow__", "__overflow__")


@dataclass(slots=True)
class _FailureWindow:
    started_at: float
    failures: int = 0
    blocked_until: float = 0.0
    rate_limited_audited: bool = False


class LoginRateLimiter:
    """Limit failed logins per socket peer and normalized username.

    When the bounded key store is nearly full, new keys share one conservative
    overflow bucket instead of evicting active lockouts and allowing retries.
    """

    def __init__(
        self,
        *,
        attempts: int,
        window_seconds: int,
        block_seconds: int,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not 1 <= attempts <= 100:
            raise ValueError("attempts must be between 1 and 100")
        if not 1 <= window_seconds <= 86_400 or not 1 <= block_seconds <= 86_400:
            raise ValueError("login rate-limit durations must be between 1 and 86400 seconds")
        if not 2 <= max_entries <= 100_000:
            raise ValueError("max_entries must be between 2 and 100000")
        self.attempts = attempts
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: OrderedDict[LoginKey, _FailureWindow] = OrderedDict()

    def _prune(self, now: float) -> None:
        expired = [
            key for key, entry in self._entries.items()
            if now >= entry.blocked_until and now - entry.started_at >= self.window_seconds
        ]
        for key in expired:
            self._entries.pop(key, None)

    def _resolve_key(self, key: LoginKey) -> LoginKey:
        if key in self._entries:
            self._entries.move_to_end(key)
            return key
        if len(self._entries) >= self.max_entries - 1:
            return _OVERFLOW_KEY
        return key

    def check(self, key: LoginKey) -> tuple[int | None, bool]:
        """Return retry seconds and whether this block should be audited."""
        now = self._clock()
        with self._lock:
            self._prune(now)
            entry = self._entries.get(self._resolve_key(key))
            if entry is None:
                return None, False
            if entry.blocked_until and entry.blocked_until <= now:
                entry.started_at = now
                entry.failures = 0
                entry.blocked_until = 0.0
                entry.rate_limited_audited = False
            elif now - entry.started_at >= self.window_seconds:
                entry.started_at = now
                entry.failures = 0
                entry.blocked_until = 0.0
                entry.rate_limited_audited = False
            if entry.blocked_until > now:
                retry_after = max(1, math.ceil(entry.blocked_until - now))
                should_audit = not entry.rate_limited_audited
                entry.rate_limited_audited = True
                return retry_after, should_audit
            return None, False

    def record_failure(self, key: LoginKey) -> None:
        now = self._clock()
        with self._lock:
            self._prune(now)
            resolved_key = self._resolve_key(key)
            entry = self._entries.get(resolved_key)
            if entry is None:
                entry = _FailureWindow(started_at=now)
                self._entries[resolved_key] = entry
            elif entry.blocked_until > now:
                # Parallel requests that passed `check` just before the threshold
                # must not prolong a lockout after it has already started.
                return
            elif entry.blocked_until or now - entry.started_at >= self.window_seconds:
                entry.started_at = now
                entry.failures = 0
                entry.blocked_until = 0.0
                entry.rate_limited_audited = False
            entry.failures += 1
            if entry.failures >= self.attempts:
                entry.blocked_until = now + self.block_seconds
                entry.rate_limited_audited = False
            self._entries.move_to_end(resolved_key)

    def clear(self, key: LoginKey) -> None:
        """Clear the exact key after a successful login, never the shared overflow bucket."""
        with self._lock:
            self._entries.pop(key, None)


def client_address(request: Request) -> str:
    """Return the socket peer only; X-Forwarded-For is deliberately ignored."""
    if request.client is None or not request.client.host:
        return "unknown"
    host = request.client.host.strip()
    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        return host.casefold()[:128] or "unknown"
