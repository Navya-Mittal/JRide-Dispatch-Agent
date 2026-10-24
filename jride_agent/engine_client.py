"""Thin client for the JRide REST gateway (the Java engine in ./engine)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class EngineError(RuntimeError):
    pass


class EngineClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8080", region: str = "Dublin", timeout: float = 10.0):
        self.base = base_url.rstrip("/")
        self.region = region
        self.timeout = timeout

    def _call(self, method: str, path: str, **params: Any) -> dict[str, Any]:
        params = {"region": self.region, **params}
        url = f"{self.base}{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                return json.loads(res.read())
        except urllib.error.HTTPError as exc:
            try:
                msg = json.loads(exc.read()).get("error", exc.reason)
            except Exception:
                msg = exc.reason
            raise EngineError(f"engine rejected the call ({exc.code}): {msg}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise EngineError(f"dispatch engine unreachable at {self.base}: {exc}") from exc

    def health(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base}/health")
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                return json.loads(res.read()).get("status") == "ok"
        except Exception:
            return False

    def request_ride(self, rider_id: str, pickup: tuple[float, float], dest: tuple[float, float]) -> dict[str, Any]:
        return self._call("POST", "/riders/request", riderId=rider_id, pickupLat=pickup[0], pickupLon=pickup[1],
                          destLat=dest[0], destLon=dest[1])

    def cancel(self, request_id: int) -> bool:
        return bool(self._call("DELETE", "/riders/request", id=request_id).get("cancelled"))

    def zone_status(self) -> dict[str, Any]:
        return self._call("GET", "/zone/status")

    def driver_online(self, driver_id: str, lat: float, lon: float) -> None:
        self._call("POST", "/drivers/online", driverId=driver_id, lat=lat, lon=lon)

    def driver_offline(self, driver_id: str) -> None:
        self._call("POST", "/drivers/offline", driverId=driver_id)
