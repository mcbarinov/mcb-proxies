import asyncio
import time
from collections import deque


class AsyncSlidingWindowCounter:
    """Async-safe counter that tracks operations within a sliding time window.

    Useful for rate limiting or monitoring operations per time period.
    """

    def __init__(self, window_seconds: int) -> None:
        """Initialize counter with specified window size.

        Args:
            window_seconds: Size of the sliding window in seconds.
        """
        self.window = window_seconds
        self.timestamps: deque[float] = deque()
        self.lock = asyncio.Lock()

    async def record_operation(self) -> None:
        """Record an operation at the current time."""
        now = time.monotonic()
        async with self.lock:
            self.timestamps.append(now)
            self._cleanup(now)

    def _cleanup(self, current_time: float) -> None:
        """Remove timestamps older than the window."""
        while self.timestamps and self.timestamps[0] < current_time - self.window:
            self.timestamps.popleft()

    async def get_count(self) -> int:
        """Return the number of operations within the current window."""
        now = time.monotonic()
        async with self.lock:
            self._cleanup(now)
            return len(self.timestamps)
