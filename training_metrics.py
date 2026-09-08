"""Descriptive training metrics; no inferred race readiness from activity averages."""
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo('UTC')
RUN_TYPES = {'Run', 'TrailRun', 'VirtualRun'}


def report_end(today):
    """Latest Sunday (Sunday itself for the scheduled evening report)."""
    return today - timedelta(days=(today.weekday() + 1) % 7)


def activity_date(run, tz=LOCAL_TZ):
    # start_date is an actual UTC instant; start_date_local is a wall-clock value.
    return datetime.fromisoformat(run['start_date'].replace('Z', '+00:00')).astimezone(tz).date()


def get_week_runs(runs, start, tz=LOCAL_TZ):
    if isinstance(start, str):
        start = date.fromisoformat(start)
    return [r for r in runs if start <= activity_date(r,tz) < start + timedelta(days=7)]


def pace(speed):
    if not speed or speed <= 0:
        return '—'
    seconds = round(1000 / speed)
    return f'{seconds // 60}:{seconds % 60:02d}/km'


def analyse_week(runs):
    dist = sum(r.get('distance', 0) for r in runs)
    # Require duration for aggregate pace; never silently mix incompatible samples.
    timed = [r for r in runs if (r.get('moving_time') or 0) > 0]
    seconds = sum(r['moving_time'] for r in timed)
    hr_runs = [r for r in timed if (r.get('average_heartrate') or 0) > 0]
    hr_seconds = sum(r['moving_time'] for r in hr_runs)
    average_hr = sum(r['average_heartrate'] * r['moving_time'] for r in hr_runs) / hr_seconds if hr_seconds else None
    longest = max(runs, key=lambda r:r.get('distance',0), default={})
    return {
        'total_km':round(dist/1000, 1), 'n_runs':len(runs),
        'moving_minutes':round(seconds/60,1),
        'time_coverage_pct':round(100*len(timed)/len(runs)) if runs else 0,
        'avg_pace':pace(dist/seconds) if seconds and len(timed)==len(runs) else '—',
        'avg_hr':round(average_hr) if average_hr is not None else None,
        'hr_coverage_pct':round(100*hr_seconds/seconds) if seconds else 0,
        'longest_km':round(longest.get('distance',0)/1000,1),
        'longest_minutes':round(longest['moving_time']/60,1) if longest.get('moving_time') else None,
        'long_run_pct':round(100*longest.get('distance',0)/dist,1) if dist else 0,
    }


def rolling_weeks(runs, end, count=4, tz=LOCAL_TZ):
    return [analyse_week(get_week_runs(runs, end-timedelta(days=6,weeks=i),tz)) for i in range(count)]


def report_metrics(runs, end, tz=LOCAL_TZ):
    weeks = rolling_weeks(runs,end,8,tz)
    current = weeks[0]
    previous = weeks[1]['total_km']
    return {**current,
        'rolling_km':round(sum(w['total_km'] for w in weeks[:4])/4,1),
        'previous_km':previous,
        'change_pct':round(100*(current['total_km']-previous)/previous,1) if previous else None,
        'long_run_history':[{ 'week_start':(end-timedelta(days=6,weeks=i)).isoformat(),
            'km':w['longest_km'],'minutes':w['longest_minutes']} for i,w in enumerate(weeks)],
    }


def hr_pace_curve(runs, end, tz=LOCAL_TZ):
    """Compare whole-run pace at similar average HR: 8–16 weeks ago vs last 4 weeks."""
    valid=[]
    for run in runs:
        hr=run.get('average_heartrate')
        distance=run.get('distance') or 0
        seconds=run.get('moving_time') or 0
        if (run.get('sport_type',run.get('type')) in RUN_TYPES and hr and distance >= 5000
                and seconds > 0):
            valid.append((activity_date(run,tz),float(hr),float(distance),float(seconds)))
    recent_start=end-timedelta(weeks=4)+timedelta(days=1)
    baseline_start=end-timedelta(weeks=16)+timedelta(days=1)
    baseline_end=end-timedelta(weeks=8)
    recent=[x for x in valid if recent_start <= x[0] <= end]
    baseline=[x for x in valid if baseline_start <= x[0] <= baseline_end]

    def matched_period(period,target,band=7):
        points=[x for x in period if abs(x[1]-target) <= band]
        if len(points) < 2:
            return None
        distance=sum(x[2] for x in points); seconds=sum(x[3] for x in points)
        return {'pace':pace(distance/seconds),'seconds_per_km':seconds/(distance/1000),'runs':len(points)}

    rows=[]
    for target in (140,145,150,155,160):
        old=matched_period(baseline,target); new=matched_period(recent,target)
        if old and new:
            rows.append({'hr':target,'baseline_pace':old['pace'],'recent_pace':new['pace'],
                'change_seconds':round(new['seconds_per_km']-old['seconds_per_km'],1),
                'baseline_runs':old['runs'],'recent_runs':new['runs']})
    return rows


def fitness_status(profile, end):
    """Only dated, attributed manual measurements. Never substitute watch VO2max for VDOT."""
    lines = []
    for key,label in [('vdot','VDOT'),('threshold_pace','T-pace'),('vo2max','Watch-estimated VO₂max'),('marathon_prediction','Watch-estimated marathon')]:
        m = profile.get(key)
        if not isinstance(m,dict) or not m.get('source') or not m.get('date') or m.get('value') is None:
            lines.append(f'{label}: not supplied with source and date')
            continue
        try:
            measured = date.fromisoformat(m['date'])
        except (ValueError,TypeError):
            lines.append(f'{label}: invalid measurement date')
            continue
        if measured > end:
            lines.append(f'{label}: no measurement as of the report date')
            continue
        age = (end-measured).days
        lines.append(f'{label}: {m["value"]} ({m["source"]}, {m["date"]}; {age} days old)')
    return '\n'.join(lines)


def lap_summary(run):
    laps = run.get('laps') or []
    if not laps:
        return 'No lap data; quality-work execution and HR drift are not verified.'
    # Do not assign zones to laps without explicit, validated intensity mapping.
    rows=[]
    for i,lap in enumerate(laps,1):
        seconds=lap.get('moving_time') or 0
        distance=lap.get('distance') or 0
        rows.append(f'{i}: {distance/1000:.2f} km, {pace(distance/seconds) if seconds else "—"}, HR {lap.get("average_heartrate", "—")}')
    return 'Laps (not automatically zone-classified): ' + '; '.join(rows)
