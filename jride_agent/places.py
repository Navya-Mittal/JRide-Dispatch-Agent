"""Dublin gazetteer. The LLM never invents coordinates: tools resolve place names here."""

from __future__ import annotations

import difflib
import re

# Approximate coordinates (good to ~100 m), enough for ring-based dispatch.
PLACES: dict[str, tuple[float, float]] = {
    "trinity college": (53.3438, -6.2546),
    "grafton street": (53.3419, -6.2625),
    "temple bar": (53.3453, -6.2635),
    "o'connell street": (53.3498, -6.2603),
    "st stephen's green": (53.3382, -6.2591),
    "ifsc": (53.3478, -6.2485),
    "point village": (53.3474, -6.2288),
    "3arena": (53.3474, -6.2288),
    "croke park": (53.3607, -6.2512),
    "phoenix park": (53.3556, -6.3298),
    "dublin airport": (53.4213, -6.2701),
    "dun laoghaire": (53.2938, -6.1344),
    "blanchardstown": (53.3856, -6.3808),
    "heuston station": (53.3464, -6.2924),
    "connolly station": (53.3510, -6.2504),
    "guinness storehouse": (53.3419, -6.2867),
    "dublin castle": (53.3429, -6.2674),
    "christ church cathedral": (53.3434, -6.2711),
    "aviva stadium": (53.3352, -6.2285),
    "ucd belfield": (53.3065, -6.2208),
    "dcu glasnevin": (53.3857, -6.2575),
    "st james's hospital": (53.3393, -6.2955),
    "mater hospital": (53.3589, -6.2644),
    "beaumont hospital": (53.3926, -6.2224),
    "dundrum town centre": (53.2916, -6.2455),
    "smithfield": (53.3489, -6.2780),
    "rathmines": (53.3225, -6.2655),
    "tallaght": (53.2875, -6.3733),
    "howth harbour": (53.3917, -6.0654),
}

ALIASES: dict[str, str] = {
    "trinity": "trinity college", "tcd": "trinity college", "grafton st": "grafton street",
    "oconnell street": "o'connell street", "o connell street": "o'connell street",
    "oconnell st": "o'connell street", "the spire": "o'connell street",
    "stephens green": "st stephen's green", "st stephens green": "st stephen's green",
    "the green": "st stephen's green", "airport": "dublin airport", "dub": "dublin airport",
    "dublin airport terminal 1": "dublin airport", "dublin airport terminal 2": "dublin airport",
    "heuston": "heuston station", "connolly": "connolly station", "guinness": "guinness storehouse",
    "aviva": "aviva stadium", "lansdowne road": "aviva stadium", "ucd": "ucd belfield",
    "dcu": "dcu glasnevin", "st james hospital": "st james's hospital", "st james's": "st james's hospital",
    "mater": "mater hospital", "beaumont": "beaumont hospital", "dundrum": "dundrum town centre",
    "dun laoghaire harbour": "dun laoghaire", "dlr": "dun laoghaire", "howth": "howth harbour",
    "the point": "point village", "ifsc dublin": "ifsc", "croker": "croke park",
}

# Service area (greater Dublin, a little wider than the engine demo box so Howth fits).
LAT_MIN, LAT_MAX = 53.25, 53.45
LON_MIN, LON_MAX = -6.45, -6.05

_COORD = re.compile(r"^\s*(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s*$")


class PlaceError(ValueError):
    """The name could not be resolved to a location inside the service area."""


def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").strip()
    s = re.sub(r"[^a-z0-9' ,.\-]", " ", s)
    return re.sub(r"\s+", " ", s).strip(" ,.")


def in_service_area(lat: float, lon: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def resolve(query: str) -> tuple[str, float, float]:
    """Resolve a place name (or an explicit 'lat, lon') to (display_name, lat, lon)."""
    q = _norm(query)
    if not q:
        raise PlaceError("empty place name")

    m = _COORD.match(q)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if not in_service_area(lat, lon):
            raise PlaceError(f"{lat}, {lon} is outside the Dublin service area")
        return f"{lat:.4f}, {lon:.4f}", lat, lon

    key = ALIASES.get(q, q)
    if key in PLACES:
        lat, lon = PLACES[key]
        return key.title().replace("'S", "'s"), lat, lon

    close = difflib.get_close_matches(key, list(PLACES) + list(ALIASES), n=3, cutoff=0.75)
    if len(close) == 1 or (close and close[0] == key):
        k = ALIASES.get(close[0], close[0])
        lat, lon = PLACES[k]
        return k.title().replace("'S", "'s"), lat, lon
    hint = f" Did you mean: {', '.join(sorted({ALIASES.get(c, c).title() for c in close}))}?" if close else ""
    raise PlaceError(f"I don't know a place called '{query}' in Dublin.{hint}")


def search(query: str, limit: int = 5) -> list[str]:
    q = _norm(query)
    names = sorted(PLACES)
    hits = [n for n in names if q and (q in n or n in q)]
    hits += [ALIASES[a] for a in ALIASES if q and (q in a or a in q)]
    hits += difflib.get_close_matches(q, names, n=limit, cutoff=0.5)
    seen: list[str] = []
    for h in hits:
        if h not in seen:
            seen.append(h)
    return [s.title().replace("'S", "'s") for s in seen[:limit]]
