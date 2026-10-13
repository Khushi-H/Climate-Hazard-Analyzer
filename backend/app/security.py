"""Rate limiting (sliding window, per client IP) and security headers."""
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from .config import settings


class SlidingWindowLimiter:
    def __init__(self, limit: int, window: float = 60.0):
        self.limit = limit
        self.window = window
        self._hits: dict = {}
        self._lock = threading.Lock()
        self._last_gc = time.monotonic()

    def check(self, key: str):
        now = time.monotonic()
        with self._lock:
            if now - self._last_gc > self.window:
                self._gc(now)
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False, max(1, int(self.window - (now - q[0])) + 1)
            q.append(now)
            return True, 0

    def _gc(self, now: float) -> None:
        for k in list(self._hits):
            q = self._hits[k]
            while q and now - q[0] > self.window:
                q.popleft()
            if not q:
                del self._hits[k]
        self._last_gc = now

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


general_limiter = SlidingWindowLimiter(settings.rate_limit_general)
heavy_limiter = SlidingWindowLimiter(settings.rate_limit_heavy)
geocode_limiter = SlidingWindowLimiter(settings.rate_limit_geocode)


def client_ip(request: Request) -> str:
    if settings.trust_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(limiter: SlidingWindowLimiter, scope: str):
    def dependency(request: Request):
        ok, retry = limiter.check(f"{scope}:{client_ip(request)}")
        if not ok:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Please retry in {retry}s.",
                headers={"Retry-After": str(retry)},
            )

    return dependency


def reset_limiters() -> None:
    for lim in (general_limiter, heavy_limiter, geocode_limiter):
        lim.reset()


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}
