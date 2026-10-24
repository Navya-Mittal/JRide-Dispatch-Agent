"""Strands tools that wrap the JRide dispatch engine for ONE rider session."""

from __future__ import annotations

from strands import tool

from . import places
from .engine_client import EngineClient, EngineError

CITY_SPEED_KMH = 25.0  # used only for a rough, clearly-labelled pickup estimate


def build_tools(engine: EngineClient, rider_id: str):
    """Return the tool list, bound to a rider id so the model can't act as someone else."""
    my_requests: list[int] = []

    @tool
    def find_place(query: str) -> str:
        """Look up a Dublin place by name and return its canonical name, or suggestions.

        Args:
            query: A landmark, station, hospital or area name, e.g. "Heuston" or "Trinity".
        """
        try:
            name, lat, lon = places.resolve(query)
            return f"{name} ({lat:.4f}, {lon:.4f})"
        except places.PlaceError as exc:
            sugg = places.search(query)
            return f"{exc}" + (f" Known places that look close: {', '.join(sugg)}." if sugg else "")

    @tool
    def request_ride(pickup: str, destination: str) -> str:
        """Request a ride for the current rider. Both places must be names the rider actually gave.

        Args:
            pickup: Pickup place name exactly as the rider said it (e.g. "Temple Bar").
            destination: Destination place name exactly as the rider said it.
        """
        try:
            p_name, p_lat, p_lon = places.resolve(pickup)
            d_name, d_lat, d_lon = places.resolve(destination)
        except places.PlaceError as exc:
            return f"NOT REQUESTED: {exc} Ask the rider to clarify."
        if (p_lat, p_lon) == (d_lat, d_lon):
            return "NOT REQUESTED: pickup and destination are the same place. Ask the rider to clarify."
        try:
            res = engine.request_ride(rider_id, (p_lat, p_lon), (d_lat, d_lon))
        except EngineError as exc:
            return f"ENGINE ERROR: {exc}"
        my_requests.append(int(res["requestId"]))
        base = f"request_id={res['requestId']} pickup={p_name} destination={d_name}"
        if res["status"] == "MATCHED" and res.get("match"):
            m = res["match"]
            eta = max(1, round(m["distanceKm"] / CITY_SPEED_KMH * 60))
            return (f"MATCHED {base} driver={m['driverId']} driver_distance_km={m['distanceKm']} "
                    f"rough_eta_minutes~{eta} (straight-line estimate, not live traffic)")
        return (f"QUEUED {base}: no driver in range right now. The request stays open and will be matched "
                f"automatically when a driver comes online nearby.")

    @tool
    def cancel_ride(request_id: int) -> str:
        """Cancel one of THIS rider's open ride requests.

        Args:
            request_id: The numeric request id returned when the ride was requested.
        """
        if request_id not in my_requests:
            known = ", ".join(map(str, my_requests)) or "none"
            return f"NOT CANCELLED: request {request_id} doesn't belong to this rider. This rider's requests: {known}."
        try:
            ok = engine.cancel(request_id)
        except EngineError as exc:
            return f"ENGINE ERROR: {exc}"
        return (f"CANCELLED request {request_id}." if ok else
                f"Request {request_id} could not be cancelled (it may already be matched or closed).")

    @tool
    def zone_status() -> str:
        """Current supply and demand in the Dublin dispatch zone (drivers available, pending requests)."""
        try:
            s = engine.zone_status()
        except EngineError as exc:
            return f"ENGINE ERROR: {exc}"
        return (f"Dublin: {s['availableDrivers']} drivers available, {s['enRouteDrivers']} en route, "
                f"{s['totalDrivers']} online, {s['pendingRequests']} requests waiting.")

    @tool
    def my_open_requests() -> str:
        """List the request ids this rider has made in this session."""
        return ", ".join(map(str, my_requests)) if my_requests else "No requests made yet."

    return [find_place, request_ride, cancel_ride, zone_status, my_open_requests]
