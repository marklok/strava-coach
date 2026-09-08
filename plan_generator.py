"""Deterministic marathon-plan drafting from user-confirmed fitness and training."""

from dataclasses import dataclass
from datetime import date, timedelta
import math
import statistics

from training_metrics import RUN_TYPES, activity_date
from training_plan import load_plan


MARATHON_KM = 42.195
RACE_DISTANCES = ((5.0, "5K"), (10.0, "10K"), (21.0975, "Half marathon"), (42.195, "Marathon"))


@dataclass(frozen=True)
class Aggressiveness:
    name: str
    peak_multiplier: float
    recovery_every: int
    recovery_factor: float
    taper_weeks: int
    long_run_cap_km: float


LEVELS = {
    "conservative": Aggressiveness("Conservative", 1.20, 3, 0.82, 3, 28),
    "balanced": Aggressiveness("Balanced", 1.35, 4, 0.82, 3, 30),
    "aggressive": Aggressiveness("Aggressive", 1.50, 4, 0.88, 2, 32),
}


def vdot_from_performance(distance_km, seconds):
    if not 1 <= distance_km <= 100 or not 180 <= seconds <= 24 * 3600:
        raise ValueError("Race distance or time is outside the supported range")
    minutes = seconds / 60
    velocity = distance_km * 1000 / minutes
    oxygen_cost = -4.60 + 0.182258 * velocity + 0.000104 * velocity * velocity
    sustainable_fraction = (0.8 + 0.1894393 * math.exp(-0.012778 * minutes)
                            + 0.2989558 * math.exp(-0.1932605 * minutes))
    return round(oxygen_cost / sustainable_fraction, 1)


def _oxygen_velocity(oxygen):
    # Positive root of the Daniels/Gilbert oxygen-cost equation.
    a, b, c = 0.000104, 0.182258, -4.60 - oxygen
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)


def _pace_for_fraction(vdot, fraction):
    metres_per_minute = _oxygen_velocity(vdot * fraction)
    seconds = round(60_000 / metres_per_minute)
    return f"{seconds // 60}:{seconds % 60:02d}/km"


def equivalent_time(vdot, distance_km):
    low, high = 180.0, 24 * 3600.0
    for _ in range(80):
        middle = (low + high) / 2
        if vdot_from_performance(distance_km, middle) > vdot:
            low = middle
        else:
            high = middle
    return round((low + high) / 2)


def training_paces(vdot):
    if not 20 <= vdot <= 85:
        raise ValueError("VDOT is outside the supported range")
    return {
        "E": f"{_pace_for_fraction(vdot, .74)}–{_pace_for_fraction(vdot, .62)}",
        "M": _format_pace(equivalent_time(vdot, MARATHON_KM) / MARATHON_KM),
        "T": f"{_pace_for_fraction(vdot, .88)}–{_pace_for_fraction(vdot, .83)}",
        "I": f"{_pace_for_fraction(vdot, 1.00)}–{_pace_for_fraction(vdot, .95)}",
        "R": f"{_pace_for_fraction(vdot, 1.10)}–{_pace_for_fraction(vdot, 1.05)}",
    }


def _format_pace(seconds_per_km):
    seconds = round(seconds_per_km)
    return f"{seconds // 60}:{seconds % 60:02d}/km"


def analyse_training(runs, today, tz):
    end = today - timedelta(days=today.weekday() + 1)
    starts = [end - timedelta(days=6, weeks=offset) for offset in reversed(range(8))]
    weeks = []
    for start in starts:
        finish = start + timedelta(days=6)
        selected = [run for run in runs if start <= activity_date(run, tz) <= finish]
        weeks.append(round(sum((run.get("distance") or 0) for run in selected) / 1000, 1))
    recent_runs = [run for run in runs if end - timedelta(days=55) <= activity_date(run, tz) <= end]
    long_run = max(((run.get("distance") or 0) / 1000 for run in recent_runs), default=0)
    active_weeks = sum(km > 0 for km in weeks)
    return {
        "weekly_km": weeks,
        "median_weekly_km": round(statistics.median(weeks), 1),
        "recent_three_week_km": round(statistics.mean(weeks[-3:]), 1),
        "runs_per_week": round(len(recent_runs) / 8, 1),
        "longest_run_km": round(long_run, 1),
        "active_weeks": active_weeks,
    }


def race_candidates(runs, today, tz):
    earliest = today - timedelta(days=365)
    words = ("race", "marathon", "half", "10k", "5k", "løb", "lopp")
    likely = []
    fallback = {}
    for run in runs:
        run_date = activity_date(run, tz)
        if not earliest <= run_date <= today or run.get("sport_type", run.get("type")) not in RUN_TYPES:
            continue
        km = (run.get("distance") or 0) / 1000
        match = min(RACE_DISTANCES, key=lambda item: abs(item[0] - km))
        marked = run.get("workout_type") == 1
        named = any(word in str(run.get("name", "")).lower() for word in words)
        if abs(match[0] - km) / match[0] <= .05:
            seconds = run.get("elapsed_time") or run.get("moving_time")
            candidate = {
                "date": run_date.isoformat(), "name": str(run.get("name") or match[1]),
                "distance_km": match[0], "recorded_km": round(km, 2),
                "recorded_seconds": seconds,
                "distance_label": match[1],
                "confidence": "likely_race" if marked or named else "fastest_distance_match",
            }
            if marked or named:
                likely.append(candidate)
            elif seconds:
                score = seconds / max(km, .001)
                current = fallback.get(match[1])
                if current is None or score < current[0]:
                    fallback[match[1]] = (score, candidate)
    likely = sorted(likely, key=lambda item: item["date"], reverse=True)[:8]
    labelled_distances = {item["distance_label"] for item in likely}
    fallbacks = [fallback[label][1] for _, label in RACE_DISTANCES
                 if label in fallback and label not in labelled_distances]
    return likely + fallbacks


def readiness(baseline):
    checks = [
        (baseline["history_weeks"] >= 8, "At least eight weeks of recent training history"),
        (baseline["weekly_km"] >= 25, "Median weekly distance of at least 25 km"),
        (baseline["runs_per_week"] >= 3, "Usually at least three runs per week"),
        (baseline["long_run_km"] >= 12, "A recent long run of at least 12 km"),
    ]
    gaps = [label for passed, label in checks if not passed]
    return {"status": "Standard foundation" if not gaps else "Some foundation gaps",
            "gaps": gaps, "advisory_only": True}


def _monday_on_or_after(day):
    return day + timedelta(days=(-day.weekday()) % 7)


def _phase(index, build_weeks):
    ratio = index / max(1, build_weeks)
    if ratio < .28:
        return "Foundation"
    if ratio < .55:
        return "Early quality"
    if ratio < .78:
        return "Marathon development"
    return "Marathon-specific"


def _segments_total(segments):
    return sum(s["km"] * s.get("repeats", 1) + s.get("recovery_km", 0) * (s.get("repeats", 1) - 1)
               for s in segments)


def _draft_workouts(total_km, phase, run_days, long_day, long_km, week_index, aggressive=False):
    days = sorted(set(run_days) | {long_day})
    quality_day = max((day for day in days if day != long_day),
                      key=lambda day: min((day - long_day) % 7, (long_day - day) % 7))
    workouts = []
    if phase == "Foundation":
        quality_segments = [{"intensity": "E", "km": 5}]
        quality_label = "Easy run with relaxed strides"
    else:
        repetitions = 3 if total_km < 55 else 4
        threshold_km = 1.5 if phase == "Early quality" else 2
        quality_segments = [{"intensity": "E", "km": 2},
                            {"intensity": "T", "km": threshold_km, "repeats": repetitions, "recovery_km": .3},
                            {"intensity": "E", "km": 2}]
        quality_label = "Controlled threshold session"
    quality_km = _segments_total(quality_segments)
    long_segments = [{"intensity": "E", "km": long_km}]
    if phase in {"Marathon development", "Marathon-specific"} and long_km >= 18:
        marathon_km = min(14 if aggressive else 10, max(4, round(long_km * .35)))
        long_segments = [{"intensity": "E", "km": round(long_km - marathon_km, 1)},
                         {"intensity": "M", "km": marathon_km}]
    fixed = quality_km + long_km
    if fixed > total_km:
        long_km = min(long_km, max(6, round(total_km - 3, 1)))
        long_segments = [{"intensity": "E", "km": long_km}]
        quality_segments = [{"intensity": "E", "km": round(total_km - long_km, 1)}]
        quality_label = "Easy run"
        fixed = _segments_total(quality_segments) + long_km
    workouts.append({"day": quality_day, "label": quality_label, "segments": quality_segments})
    workouts.append({"day": long_day, "label": "Long run", "long_run": True, "segments": long_segments})
    other_days = [day for day in days if day not in {quality_day, long_day}]
    remaining = round(total_km - fixed, 1)
    for position, day in enumerate(other_days):
        km = round(remaining / (len(other_days) - position), 1) if position < len(other_days) - 1 else remaining
        if km > 0:
            if aggressive and len(days) >= 5 and phase == "Marathon-specific" and position == 0 and km >= 6:
                steady_km = round(min(5, km * .30), 1)
                segments = [{"intensity": "E", "km": round(km - steady_km, 1)},
                            {"intensity": "M", "km": steady_km}]
                label = "Steady aerobic run"
            else:
                segments = [{"intensity": "E", "km": km}]
                label = "Easy run"
            workouts.append({"day": day, "label": label, "segments": segments})
            remaining = round(remaining - km, 1)
    return sorted(workouts, key=lambda item: item["day"])


def draft_marathon_plan(data, today=None):
    today = today or date.today()
    try:
        race_date = date.fromisoformat(str(data.get("race_date", "")))
    except ValueError:
        raise ValueError("Choose your marathon and enter its race date") from None
    try:
        requested_start = date.fromisoformat(str(data.get("start_date") or today.isoformat()))
    except ValueError:
        raise ValueError("Enter a valid programme start date") from None
    if requested_start < today:
        raise ValueError("The programme start date cannot be in the past")
    first_monday = _monday_on_or_after(requested_start)
    race_monday = race_date - timedelta(days=race_date.weekday())
    weeks = (race_monday - first_monday).days // 7 + 1
    if weeks < 12:
        raise ValueError("A marathon plan requires at least 12 weeks before race week")
    if weeks > 52:
        raise ValueError("Select a marathon within the next year")
    level = LEVELS.get(data.get("aggressiveness", "balanced"))
    if not level:
        raise ValueError("Unknown plan aggressiveness")
    baseline = {
        "weekly_km": float(data["weekly_km"]), "runs_per_week": float(data["runs_per_week"]),
        "long_run_km": float(data["long_run_km"]), "history_weeks": int(data.get("history_weeks", 8)),
    }
    if not 10 <= baseline["weekly_km"] <= 200 or not 2 <= baseline["runs_per_week"] <= 7:
        raise ValueError("Training baseline is outside the supported range")
    run_days = [int(day) for day in data.get("run_days", [1, 3, 5, 6])]
    long_day = int(data.get("long_run_day", 6))
    if len(set(run_days)) < 2 or any(day < 0 or day > 6 for day in run_days) or long_day not in run_days:
        raise ValueError("Choose valid running days including the long-run day")
    benchmark = data.get("benchmark") or {}
    try:
        benchmark_seconds = int(benchmark["seconds"])
        benchmark_date = date.fromisoformat(str(benchmark.get("date", "")))
    except (KeyError, TypeError, ValueError):
        raise ValueError("Choose a recent race result and enter its date and finish time") from None
    if benchmark_date > today or benchmark_date < today - timedelta(days=730):
        raise ValueError("Use a benchmark race from the last two years")
    if not str(data.get("race_name", "")).strip():
        raise ValueError("Enter a marathon name")
    vdot = vdot_from_performance(float(benchmark["distance_km"]), benchmark_seconds)
    paces = training_paces(vdot)
    peak = round(baseline["weekly_km"] * level.peak_multiplier)
    core_weeks = min(24, weeks)
    base_weeks = weeks - core_weeks
    build_weeks = core_weeks - level.taper_weeks
    generated = []
    previous_long = baseline["long_run_km"]
    for index in range(weeks):
        start = first_monday + timedelta(weeks=index)
        number = index + 1
        if index == weeks - 1:
            training_km = round(max(10, peak * .38))
            easy_days = [day for day in run_days if day != race_date.weekday()][:3]
            portions = []
            remaining = training_km
            for position, day in enumerate(easy_days):
                km = round(remaining / (len(easy_days) - position), 1) if position < len(easy_days) - 1 else remaining
                portions.append({"day": day, "label": "Short easy run", "segments": [{"intensity": "E", "km": km}]})
                remaining = round(remaining - km, 1)
            portions.append({"day": race_date.weekday(), "label": data["race_name"], "race": True,
                             "segments": [{"intensity": "RACE", "km": MARATHON_KM}]})
            generated.append({"number": number, "start": start.isoformat(), "training_km": training_km,
                              "phase": "Race week", "context": "Keep the week familiar and arrive fresh.",
                              "workouts": sorted(portions, key=lambda item: item["day"])})
            continue
        core_index = index - base_weeks
        if index < base_weeks:
            base_progress = index / max(1, base_weeks - 1)
            training_km = round(baseline["weekly_km"] * (1 + .08 * base_progress))
            phase = "Base conditioning"
            if index and (index + 1) % level.recovery_every == 0:
                training_km = round(training_km * level.recovery_factor)
                phase = "Recovery"
        elif core_index >= build_weeks:
            taper_position = core_index - build_weeks
            factors = ([.82, .64] if level.taper_weeks == 3 else [.68])
            training_km = round(peak * factors[min(taper_position, len(factors) - 1)])
            phase = "Taper"
        else:
            progress = core_index / max(1, build_weeks - 1)
            starting_km = baseline["weekly_km"] * (1.08 if base_weeks else 1)
            training_km = round(starting_km + (peak - starting_km) * progress)
            phase = _phase(core_index, build_weeks)
            if core_index and (core_index + 1) % level.recovery_every == 0:
                training_km = round(training_km * level.recovery_factor)
                phase = "Recovery"
        development_index = max(0, core_index)
        desired_long = baseline["long_run_km"] + (development_index // 2) * (1.5 if level.name == "Conservative" else 2)
        long_km = min(level.long_run_cap_km, max(baseline["long_run_km"], desired_long), training_km * .42)
        if phase in {"Recovery", "Taper"}:
            long_km = min(previous_long * .75, training_km * .38)
        long_km = round(max(8, long_km), 1)
        previous_long = long_km
        workouts = _draft_workouts(training_km, phase, run_days, long_day, long_km, index,
                                    level.name == "Aggressive")
        context = ("Draft generated from the confirmed race result and recent training. "
                   "Training paces use current fitness, not goal fitness.")
        generated.append({"number": number, "start": start.isoformat(), "training_km": training_km,
                          "phase": phase, "context": context, "workouts": workouts})
    target_seconds = int(data["goal_seconds"])
    if not 2 * 3600 <= target_seconds <= 8 * 3600:
        raise ValueError("Marathon goal time is outside the supported range")
    config = {
        "timezone": data.get("timezone", "Europe/Copenhagen"), "language": data.get("language", "English"),
        "goal": {"race_name": data["race_name"], "date": race_date.isoformat(),
                 "distance_km": MARATHON_KM, "target_seconds": target_seconds},
        "weeks": generated,
        "profile": {"vdot": {"value": vdot, "source": benchmark.get("name", "Confirmed race result"),
                              "date": benchmark_date.isoformat()}},
        "checkins": {}, "race_strategies": [],
        "planning_context": str(data.get("context", ""))[:4000],
        "plan_settings": {"aggressiveness": level.name, "draft": True,
                          "starting_weekly_km": baseline["weekly_km"],
                          "starting_runs_per_week": baseline["runs_per_week"],
                          "starting_long_run_km": baseline["long_run_km"],
                          "history_weeks": baseline["history_weeks"],
                          "requested_start_date": requested_start.isoformat(),
                          "first_training_week": first_monday.isoformat()},
    }
    load_plan(config)
    longest_planned = max(
        _segments_total(workout["segments"])
        for week in generated for workout in week["workouts"]
        if workout.get("long_run")
    )
    easy_slow_seconds = round(60_000 / _oxygen_velocity(vdot * .62))
    warnings = []
    if longest_planned * easy_slow_seconds > 150 * 60:
        warnings.append("The longest easy run may exceed 150 minutes; shorten it if recovery or form deteriorates.")
    return {
        "config": config, "vdot": vdot, "paces": paces, "readiness": readiness(baseline),
        "weeks": weeks, "peak_km": max(week["training_km"] for week in generated[:-1]),
        "marathon_equivalent_seconds": equivalent_time(vdot, MARATHON_KM),
        "warnings": warnings,
        "assumptions": [
            f"{level.name} plan aggressiveness", f"Starting volume {baseline['weekly_km']:g} km/week",
            f"{len(run_days)} available running days", "Training paces based on the confirmed race result",
        ],
    }
