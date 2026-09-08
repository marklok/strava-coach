# Strava Coach

Strava Coach turns one athlete's Strava activities into a compact weekly running
dashboard. It shows last week's mileage and runs, pace at matched heart rate, the
coming week, and the remaining training programme. Email delivery, local history,
and frank AI coaching are optional.

The code is open source under the [MIT license](LICENSE). The repository contains
no built-in athlete, race target, or training plan. Your credentials, activities,
reports, and programme stay in an ignored `.private/` directory on your computer.
The files under `examples/` contain fictional data.

## Create a marathon plan on macOS

The local setup app is the simplest way to start. It supports established runners
with a marathon at least 12 weeks away.

```sh
git clone https://github.com/marklok/strava-coach.git
cd strava-coach
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python coach_app.py
```

Your browser opens a five-step private setup:

1. Choose from 40 common Nordic, European, and US marathons, or enter another race.
   A date is filled only when the organiser has published and the catalog has
   verified that edition; otherwise the app links to the official race site.
2. Connect Strava or enter a recent 5K, 10K, half-marathon, or marathon result.
   Strava suggests likely races from the last year and measures eight complete
   weeks of recent training.
3. Confirm weekly distance, run frequency, and recent long-run distance. Gaps from
   the suggested foundation are shown as advice and do not lock you out.
4. Choose Conservative, Balanced, or Aggressive progression, running days, add
   personal context, and optionally store an Anthropic API key for AI commentary.
5. Review the draft, current-fitness training paces, weekly distance, and longest
   run before saving to `.private/coach_config.json`.

The Strava client secret and optional Anthropic key entered in the setup app are
stored in macOS Keychain. OAuth tokens and the plan use owner-only files under `.private/`. The app listens only on
your Mac at `127.0.0.1`; stop it with Control-C when setup is complete. Use
`python coach_app.py --port 9000` if port 8765 is occupied.

The generator uses the published Daniels/Gilbert performance equation to estimate
VDOT and derives E, M, T, I, and R pace ranges from the confirmed current result.
Goal time is kept as an ambition and never used to manufacture training paces.
The schedule combines one controlled threshold session, mostly easy running,
progressive long runs, periodic recovery weeks, marathon-pace work, and a two- or
three-week taper depending on the selected approach. A lead time over 24 weeks gets
a separate base-conditioning period. This project is independently developed and
is not affiliated with or endorsed by Jack Daniels or the VDOT organization.

## Try the example

You need Python 3.11 or newer. This first run is offline and cannot send email or
data to an AI provider.

```sh
git clone https://github.com/marklok/strava-coach.git
cd strava-coach
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python strava_coach.py --dry-run --date 2030-01-13 \
  --config examples/coach_config.json \
  --activities-file examples/activities.json
```

Open `.private/reports/report.html` to see the example dashboard. On Windows,
activate the environment with `.venv\Scripts\activate`.

## Command-line Strava setup

1. Create an application in [Strava API settings](https://www.strava.com/settings/api).
   Set its **Authorization Callback Domain** to `localhost`.
2. Create your private files:

   ```sh
   mkdir -p .private
   chmod 700 .private
   cp examples/credentials.json .private/credentials.json
   cp examples/coach_config.json .private/coach_config.json
   chmod 600 .private/*.json
   ```

3. Put only your Strava `client_id` and `client_secret` in
   `.private/credentials.json`. Then connect your account:

   ```sh
   python authorize_strava.py
   ```

   The helper opens Strava in your browser and saves the returned tokens directly
   to `.private/tokens.json`; you do not need to copy an authorization code or
   refresh token. Add `--read-private` if the report must include Strava activities
   whose visibility is **Only You**.

4. Generate your first live report:

   ```sh
   python strava_coach.py
   ```

The report is written to `.private/reports/`. A normal run fetches Strava data but
does not send email, invoke AI, or save weekly history. Strava may rotate refresh
tokens; the latest token is atomically stored with owner-only permissions. Keep
`.private/` on durable private storage and use a different state directory for
each athlete.

Environment variables can replace credential-file values:
`STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, and `STRAVA_REFRESH_TOKEN`.
Environment variables take precedence. Avoid putting secret values directly in
commands, shell history, public CI settings, or issue reports.

## Add or edit your programme

Edit `.private/coach_config.json`. The synthetic
[example configuration](examples/coach_config.json) is the full schema and can be
used as a starting point. Use `{}` if you only want activity statistics.
The local setup app can generate this file for you; it remains a draft so you can
edit or replace any week before relying on it.

- `timezone` is an IANA timezone such as `Europe/Copenhagen`.
- `language` controls optional AI commentary.
- `goal` contains `race_name`, ISO `date`, `distance_km`, and `target_seconds`.
- `weeks` contains the private programme. Each week has a Monday `start`,
  `training_km`, `phase`, optional `context`, and `workouts`.
- `profile` can include `vdot`, `threshold_pace`, `threshold_hr`, `vo2max`, and
  `marathon_prediction`, preferably with a source and date.
- `benchmarks`, `checkins`, and `race_strategies` are optional.

Workout `day` uses 0 for Monday. Segments contain an `intensity`, `km`, optional
`repeats`, and `recovery_km`. The labels E/M/T/I/R/H are your own effort categories;
the application does not assign their paces. `long_run` and `race` classify special
workouts. Invalid dates, segments, or weekly totals stop the run before any network
request is made.

You can keep the configuration elsewhere with `--config /private/path/plan.json`
or supply a JSON object through `COACH_CONFIG_JSON`. Never commit a real plan merely
to make it available to a scheduler.

## Email, AI, and history

All three features require explicit command options.

For Gmail, add `gmail_sender`, `gmail_app_password`, and `email_to` to your private
credentials file. Use a [Google app password](https://support.google.com/accounts/answer/185833),
then test the exact recipient:

```sh
python strava_coach.py --send
```

For AI coaching, create `.private/ai_credentials.json`:

```json
{"anthropic_api_key": "your-key"}
```

Restrict that file to your user and run:

```sh
chmod 600 .private/ai_credentials.json
python strava_coach.py --ai
```

`--ai` sends Anthropic the race goal, selected measurements, weekly statistics,
matched-HR trend, up to four saved summaries, the coming plan, and these fields for
each completed run: date, name, distance, pace, average/max HR, temperature, power,
and athlete note. It excludes activity IDs, routes, GPS, laps, check-ins, and
credentials. Inspect activity names, notes, and plan context before opting in.
`ANTHROPIC_API_KEY` can replace the private file and `ANTHROPIC_MODEL` can select a
model. An API key by itself does not enable AI.

Save up to 12 local weekly summaries with `--save-history`. A complete weekly run is:

```sh
python strava_coach.py --send --ai --save-history
```

`--state-dir` and `--output-dir` can move private state and reports. These files
have restricted permissions but are not encrypted at rest. Email providers process
the full report; Anthropic processes only the documented AI payload.

## Schedule Sunday delivery

First run the complete command manually and confirm the recipient. Then schedule
that same command on a private machine that remains awake and has durable access to
`.private/`. For example, a local cron entry for Sunday at 23:00 is:

```cron
0 23 * * 0 cd /absolute/path/to/strava-coach && .venv/bin/python strava_coach.py --send --ai --save-history >> .private/scheduler.log 2>&1
```

Use an absolute path and the machine's local timezone. Do not place credentials in
the scheduler command. macOS users may prefer `launchd`, which can run missed jobs
after wake; Linux users can use a systemd timer. The public GitHub workflow runs
synthetic tests only and never fetches or publishes an athlete's data.

## How the metrics work

- Weeks are local Monday–Sunday. A Sunday report includes activities available at
  the time it runs.
- Weekly pace is total moving time divided by total distance. HR is weighted by
  activity duration, and its coverage is reported separately.
- The four-week average includes the completed week and the previous three.
  Missing weeks contribute zero, which is not proof that no running occurred.
- Matched-HR pace compares runs over 5 km in ±7 bpm bands: weeks 8–16 before the
  report against the latest four weeks. A band needs at least two runs in both
  windows. Route, weather, fatigue, and workout mix can still change the result.
- Run, TrailRun, and VirtualRun contribute mileage. Whole-run averages do not prove
  completion of prescribed intervals or measure cardiac drift.
- Goal pace is an ambition, not a measured fitness level. VDOT and watch-estimated
  VO₂max are distinct. The software does not generate an injury-risk score or a
  guaranteed race prediction.

## Develop and contribute

```sh
python -m unittest discover -s tests -v
```

Tests use synthetic data and mocked providers. CI has read-only permissions and
commit-pinned GitHub Actions. Dependabot checks Python packages and Actions weekly.
See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability. Never attach a
real export, report, token, email address, or plan to a public issue. Deleting a
file from the latest version does not erase it from Git history, pull-request refs,
forks, or clones; follow [GitHub's sensitive-data removal guide](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
if personal data was ever committed.
