"""Read-only parking availability estimates for an explicitly labeled demo.

The default is a deterministic synthetic scenario; it is not a learned
campus-traffic model. Historical forecasting is an opt-in, same-weekday/hour
baseline, and requires manually verified recording-time provenance.
Never train on timestamps of prerecorded video *replay* or call model-generated
occupancy classifications independently verified ground truth.
"""

from datetime import datetime, timedelta, timezone
import math
import re
from zoneinfo import ZoneInfo

CAMPUS_TZ_NAME = "America/New_York"
CAMPUS_TZ = ZoneInfo(CAMPUS_TZ_NAME)
MAX_FUTURE_DAYS = 14
MIN_HISTORICAL_DAYS = 3
HISTORY_LOOKBACK_DAYS = 56
_TARGET_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}$")


def parse_target(value, *, now=None):
    """Require a future, unambiguous local campus minute within 14 days.

    The browser sends a literal campus-wall-clock date and time, *not*
    JavaScript's device-local timezone or an untrusted UTC offset.
    Ambiguous fall-back hours and nonexistent spring-forward hours are
    rejected rather than silently choosing an unexpected instant.
    """
    if not isinstance(value, str) or not _TARGET_PATTERN.fullmatch(value):
        raise ValueError("Use YYYY-MM-DDTHH:MM in America/New_York")
    try:
        wall = datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError as exc:
        raise ValueError("Invalid campus date or time") from exc
    candidate = wall.replace(tzinfo=CAMPUS_TZ)
    if candidate.utcoffset() != wall.replace(tzinfo=CAMPUS_TZ, fold=1).utcoffset():
        raise ValueError("Ambiguous or nonexistent daylight-saving time; choose another hour")
    roundtrip = candidate.astimezone(timezone.utc).astimezone(CAMPUS_TZ)
    if roundtrip.replace(tzinfo=None) != wall:
        raise ValueError("Nonexistent daylight-saving time; choose another hour")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone aware")
    seconds = (candidate - now.astimezone(timezone.utc)).total_seconds()
    if seconds <= 0:
        raise ValueError("Choose a future campus date and time")
    if seconds > MAX_FUTURE_DAYS * 86400:
        raise ValueError("Choose a time within the next 14 days")
    return candidate


def _estimate(lot_id, label, total, occupied_share, *, status, days=0, snapshots=0):
    """Round to an integer space count and conserve lot capacity."""
    if type(total) is not int or total <= 0:
        raise ValueError("A positive configured lot capacity is required")
    if occupied_share is None:
        return {
            "lot_id": lot_id, "display_label": label, "total_spaces": total,
            "status": status, "estimated_available": None,
            "estimated_occupied": None, "estimated_open_percent": None,
            "historical_days": days, "historical_snapshots": snapshots,
        }
    if not math.isfinite(occupied_share) or not 0 <= occupied_share <= 1:
        raise ValueError("Invalid occupancy share")
    occupied = min(total, max(0, round(total * occupied_share)))
    available = total - occupied
    return {
        "lot_id": lot_id, "display_label": label, "total_spaces": total,
        "status": status, "estimated_available": available,
        "estimated_occupied": occupied,
        "estimated_open_percent": round(100 * available / total, 1),
        "historical_days": days, "historical_snapshots": snapshots,
    }


def demo_estimate(lot_id, label, total, target):
    """Deterministic, made-up commuter/residential demand demonstration.

    These curves are EXAMPLES, not observed or calibrated occupancy.
    They do not use stored replay timestamps or secretly seed the DB.
    """
    hour = target.hour + target.minute / 60
    weekday = target.weekday() < 5
    if lot_id == "lot3":
        evening = max(0.0, 1 - abs(hour - 21) / 9)
        occupied = 0.33 + 0.46 * evening + (0.04 if not weekday else 0.0)
    else:
        midday = max(0.0, 1 - abs(hour - 13) / 6)
        bump = 0.60 if lot_id == "lot2" else 0.52
        occupied = 0.14 + bump * midday * (1 if weekday else 0.35)
        occupied += 0.04 if 8 <= hour < 10 and weekday else 0
    # Small stable illustrative variation by calendar day and lot, no RNG.
    salt = {"lot1": 2, "lot2": 7, "lot3": 11}.get(lot_id, 0)
    occupied += (((target.toordinal() * 7 + salt) % 9) - 4) / 100
    occupied = max(0.05, min(0.95, occupied))
    return _estimate(lot_id, label, total, occupied,
                     status="illustrative")


def historical_estimate(lot_id, label, total, target, profiles):
    """Day-balanced same-weekday/hour baseline, never silently extrapolate.

    profiles: individual (calendar date, weekday 0=Monday, hour,
    mean occupied share, snapshot count) observations. Each calendar
    day weighs once; repeated video-frame writes cannot create extra
    independent days. At least three different matching weekdays are
    required before returning a number.
    """
    matched = []
    for record in profiles:
        if (record["weekday"] == target.weekday()
                and record["hour"] == target.hour):
            share = float(record["occupied_share"])
            n = record["snapshots"]
            if not math.isfinite(share) or not 0 <= share <= 1:
                raise ValueError("Invalid historical share")
            if type(n) is not int or n <= 0:
                raise ValueError("Invalid historical sample count")
            matched.append((record["local_date"], share, n))
    # A corrupt or duplicate date must not count as independent evidence.
    dates = {entry[0] for entry in matched}
    if len(dates) != len(matched):
        raise ValueError("Duplicate historical day/hour bucket")
    days = len(dates)
    samples = sum(entry[2] for entry in matched)
    if days < MIN_HISTORICAL_DAYS:
        return _estimate(lot_id, label, total, None,
                         status="insufficient_history", days=days, snapshots=samples)
    mean_occupied = sum(entry[1] for entry in matched) / days
    return _estimate(lot_id, label, total, mean_occupied,
                     status="historical_estimate", days=days, snapshots=samples)


def forecast_response(configured, target, mode, *, history_provider=None, now=None):
    """Compute all configured lots; never write to the database."""
    if mode not in ("demo", "historical"):
        raise ValueError("mode must be demo or historical")
    now = now or datetime.now(timezone.utc)
    if mode == "historical" and history_provider is None:
        raise PermissionError("Verified historical forecasting is not enabled")
    lots = []
    for lot_id, label, _camera, ids, _observed in configured:
        if not ids:
            continue
        if mode == "demo":
            lots.append(demo_estimate(lot_id, label, len(ids), target))
        else:
            profiles = history_provider.forecast_hourly_profiles(
                lot_id, as_of_utc=now, lookback_days=HISTORY_LOOKBACK_DAYS,
                required_spaces=len(ids),
            )
            lots.append(historical_estimate(lot_id, label, len(ids), target, profiles))

    if mode == "demo":
        source = "synthetic_demo"
        basis = ("Illustrative weekday/hour scenario generated in software. "
                 "NOT real campus occupancy, trained ML, or a measured prediction.")
    else:
        source = "verified_history"
        basis = ("Simple day-balanced average for the same local weekday and hour "
                 "over the preceding 56 days, requiring at least 3 matching "
                 "calendar days. Not a validated accuracy claim or guarantee.")
    return {
        "requested_at": target.isoformat(),
        "timezone": CAMPUS_TZ_NAME,
        "mode": mode,
        "source": source,
        "model": ("illustrative_schedule_v1" if mode == "demo"
                  else "weekday_hour_baseline_v1"),
        "basis": basis,
        "lots": lots,
    }
