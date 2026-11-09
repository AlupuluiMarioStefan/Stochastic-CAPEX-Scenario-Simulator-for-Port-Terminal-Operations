"""A SimPy resource that also records utilisation and queueing statistics."""

from __future__ import annotations

from dataclasses import dataclass

import simpy


@dataclass
class StationStats:
    name: str
    capacity: int
    requests: int
    utilization: float  # time-averaged fraction of capacity in use
    mean_queue_length: float
    max_queue_length: int
    mean_wait: float  # hours spent queueing, per request
    max_wait: float


class Station:
    """``simpy.Resource`` wrapper. Use ``req, wait = yield from station.acquire()``."""

    def __init__(self, env: simpy.Environment, name: str, capacity: int):
        self.env, self.name, self.capacity = env, name, capacity
        self._res = simpy.Resource(env, capacity=capacity)
        self._last = 0.0
        self._busy_area = 0.0
        self._queue_area = 0.0
        self._waits = []
        self._max_queue = 0

    def _tick(self) -> None:
        now = self.env.now
        dt = now - self._last
        self._busy_area += self._res.count * dt
        self._queue_area += len(self._res.queue) * dt
        self._last = now

    def acquire(self):
        t0 = self.env.now
        self._tick()
        req = self._res.request()
        self._max_queue = max(self._max_queue, len(self._res.queue))
        yield req
        wait = self.env.now - t0
        self._waits.append(wait)
        return req, wait

    def release(self, req) -> None:
        self._tick()
        self._res.release(req)

    def stats(self) -> StationStats:
        self._tick()
        horizon = self.env.now
        n = len(self._waits)
        return StationStats(
            name=self.name,
            capacity=self.capacity,
            requests=n,
            utilization=self._busy_area / (self.capacity * horizon) if horizon else 0.0,
            mean_queue_length=self._queue_area / horizon if horizon else 0.0,
            max_queue_length=self._max_queue,
            mean_wait=sum(self._waits) / n if n else 0.0,
            max_wait=max(self._waits, default=0.0),
        )
