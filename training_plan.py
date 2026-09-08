"""Validated workout models. Real plans are loaded from private JSON at runtime."""
from dataclasses import dataclass
from datetime import date, timedelta
import math

DAYS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')

@dataclass(frozen=True)
class Segment:
    intensity: str
    km: float
    repeats: int = 1
    recovery_km: float = 0

    @property
    def total(self):
        return self.km * self.repeats + self.recovery_km * max(0, self.repeats - 1)

    def describe(self):
        work = f'{self.repeats} × {self.km:g} km' if self.repeats > 1 else f'{self.km:g} km'
        rest = f', {self.recovery_km:g} km easy between repetitions' if self.recovery_km else ''
        return f'{work} {self.intensity}{rest}'

@dataclass(frozen=True)
class Workout:
    day: int
    label: str
    segments: tuple
    long_run: bool = False
    race: bool = False

    @property
    def km(self):
        return round(sum(s.total for s in self.segments), 4)

    @property
    def race_km(self):
        return sum(s.km * s.repeats for s in self.segments if s.intensity == 'RACE') if self.race else 0

    @property
    def description(self):
        return self.label + ': ' + ' + '.join(s.describe() for s in self.segments)

@dataclass(frozen=True)
class Week:
    number: int
    start: date
    training_km: float
    phase: str
    workouts: tuple
    context: str = ''

    @property
    def race_km(self):
        return sum(w.race_km for w in self.workouts)

    @property
    def total_km(self):
        return self.training_km + self.race_km

    @property
    def long_km(self):
        return max((w.km for w in self.workouts if w.long_run), default=0)


def nonnegative(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def validate_week(w):
    valid = (w.start.weekday() == 0 and nonnegative(w.training_km)
             and len(w.workouts) <= 7 and len({x.day for x in w.workouts}) == len(w.workouts))
    for x in w.workouts:
        valid = valid and type(x.day) is int and 0 <= x.day <= 6 and 0 < len(x.segments) <= 50
        for s in x.segments:
            valid = (valid and s.intensity in {'E','M','T','I','R','H','RACE'}
                     and nonnegative(s.km) and nonnegative(s.recovery_km)
                     and type(s.repeats) is int and 1 <= s.repeats <= 100)
    if not valid or abs(sum(x.km for x in w.workouts)-w.total_km) > .01:
        raise ValueError('Invalid week: check dates, components and mileage totals')


def load_plan(config):
    plan=[]
    for raw in config.get('weeks', []):
        workouts=[]
        for x in raw['workouts']:
            workouts.append(Workout(day=x['day'], label=x['label'],
                segments=tuple(Segment(**s) for s in x['segments']),
                long_run=x.get('long_run',False),race=x.get('race',False)))
        w=Week(raw['number'],date.fromisoformat(raw['start']),raw['training_km'],raw['phase'],tuple(workouts),raw.get('context',''))
        validate_week(w)
        plan.append(w)
    if len({w.start for w in plan}) != len(plan):
        raise ValueError('Duplicate week dates')
    return sorted(plan,key=lambda w:w.start)


def get_plan_for_date(plan, day):
    return next((w for w in plan if w.start <= day < w.start+timedelta(days=7)),None)


def schedule_text(w):
    if not w:
        return 'No plan supplied for the coming week.'
    rows=[f'{DAYS[x.day]}: {x.description} — {x.km:g} km' for x in w.workouts]
    rows += [f'Training {w.training_km:g} km; racing {w.race_km:g} km; total {w.total_km:g} km.',w.context]
    return '\n'.join(rows)
