from datetime import date, datetime, timedelta
import unittest
from zoneinfo import ZoneInfo

from plan_generator import (analyse_training, draft_marathon_plan, race_candidates,
                            training_paces, vdot_from_performance)
from race_catalog import public_catalog
from training_plan import load_plan


def activity(day, km, name="Run", workout_type=None, seconds=3600):
    return {"start_date": datetime.combine(day, datetime.min.time()).isoformat()+"Z",
            "sport_type":"Run", "distance":km*1000, "moving_time":seconds,
            "elapsed_time":seconds, "name":name, "workout_type":workout_type}


def input_data(level="balanced", goal_seconds=3*3600):
    return {"race_name":"Example Marathon", "race_date":"2030-05-19", "goal_seconds":goal_seconds,
            "benchmark":{"name":"Example Half", "distance_km":21.0975, "seconds":5400, "date":"2029-10-01"},
            "weekly_km":40, "runs_per_week":4, "long_run_km":18, "history_weeks":8,
            "run_days":[1,3,5,6], "long_run_day":6, "aggressiveness":level,
            "timezone":"Europe/Copenhagen", "context":"Travel in February."}


class FitnessTests(unittest.TestCase):
    def test_vdot_and_paces_are_plausible(self):
        vdot=vdot_from_performance(21.0975,5400)
        self.assertTrue(50 < vdot < 55)
        self.assertEqual(set(training_paces(vdot)),{"E","M","T","I","R"})

    def test_strava_analysis_uses_recent_complete_weeks(self):
        tz=ZoneInfo("UTC"); today=date(2030,1,14)
        runs=[activity(today-timedelta(days=8),10,"City 10K",1,2400),
              activity(today-timedelta(days=10),14),activity(today-timedelta(days=17),20)]
        baseline=analyse_training(runs,today,tz)
        self.assertEqual(len(baseline["weekly_km"]),8)
        self.assertEqual(baseline["longest_run_km"],20)
        candidates=race_candidates(runs,today,tz)
        self.assertEqual(candidates[0]["distance_label"],"10K")

    def test_standard_distance_is_suggested_without_race_label(self):
        today=date(2030,1,14);tz=ZoneInfo("UTC")
        candidates=race_candidates([activity(today-timedelta(days=20),21.3,"Sunday run",None,5407)],today,tz)
        self.assertEqual(candidates[0]["confidence"],"fastest_distance_match")

    def test_only_fastest_unlabelled_match_per_distance_is_suggested(self):
        today=date(2030,1,14);tz=ZoneInfo("UTC")
        candidates=race_candidates([
            activity(today-timedelta(days=20),10.1,"Morning run",None,2700),
            activity(today-timedelta(days=10),10.2,"Evening run",None,2500),
        ],today,tz)
        self.assertEqual(len(candidates),1)
        self.assertEqual(candidates[0]["name"],"Evening run")


class DraftTests(unittest.TestCase):
    def test_under_twelve_weeks_is_rejected(self):
        data=input_data();data["race_date"]="2030-03-10"
        with self.assertRaisesRegex(ValueError,"at least 12 weeks"):
            draft_marathon_plan(data,date(2030,1,1))

    def test_missing_dates_have_user_facing_errors(self):
        data=input_data();data["benchmark"]["date"]=""
        with self.assertRaisesRegex(ValueError,"recent race result"):
            draft_marathon_plan(data,date(2030,1,1))

    def test_goal_time_does_not_change_training_paces(self):
        a=draft_marathon_plan(input_data(goal_seconds=3*3600),date(2030,1,1))
        b=draft_marathon_plan(input_data(goal_seconds=4*3600),date(2030,1,1))
        self.assertEqual(a["paces"],b["paces"])
        self.assertNotEqual(a["config"]["goal"]["target_seconds"],b["config"]["goal"]["target_seconds"])

    def test_runner_can_choose_a_future_programme_start(self):
        data=input_data();data["start_date"]="2030-02-03"
        draft=draft_marathon_plan(data,date(2030,1,1))
        self.assertEqual(draft["config"]["plan_settings"]["requested_start_date"],"2030-02-03")
        self.assertEqual(draft["config"]["weeks"][0]["start"],"2030-02-04")

    def test_programme_cannot_start_in_the_past(self):
        data=input_data();data["start_date"]="2029-12-31"
        with self.assertRaisesRegex(ValueError,"cannot be in the past"):
            draft_marathon_plan(data,date(2030,1,1))

    def test_all_levels_generate_valid_editable_drafts(self):
        drafts={level:draft_marathon_plan(input_data(level),date(2030,1,1))
                for level in ("conservative","balanced","aggressive")}
        for draft in drafts.values():
            self.assertTrue(load_plan(draft["config"]))
            self.assertTrue(draft["config"]["plan_settings"]["draft"])
            self.assertEqual(draft["config"]["planning_context"],"Travel in February.")
        self.assertLess(drafts["conservative"]["peak_km"],drafts["balanced"]["peak_km"])
        self.assertLess(drafts["balanced"]["peak_km"],drafts["aggressive"]["peak_km"])

    def test_baseline_gaps_are_advisory(self):
        data=input_data();data.update(weekly_km=18,runs_per_week=2,long_run_km=9,history_weeks=3)
        draft=draft_marathon_plan(data,date(2030,1,1))
        self.assertTrue(draft["readiness"]["advisory_only"])
        self.assertEqual(len(draft["readiness"]["gaps"]),4)

    def test_catalog_has_forty_unique_marathons_with_nordic_focus(self):
        races=public_catalog()
        self.assertEqual(len(races),40)
        self.assertEqual(len({race["id"] for race in races}),40)
        self.assertGreaterEqual(sum(race["region"]=="Nordic" for race in races),18)
        self.assertTrue(all(race["url"].startswith("https://") for race in races))
        copenhagen=next(race for race in races if race["id"]=="copenhagen")
        self.assertEqual(copenhagen["next_date"],"2027-05-09")

    def test_plan_shape_across_supported_lead_times_and_schedules(self):
        today=date(2030,1,1)
        for lead_weeks in (12,16,24,40,52):
            for level in ("conservative","balanced","aggressive"):
                with self.subTest(lead_weeks=lead_weeks,level=level):
                    data=input_data(level)
                    data["race_date"]=(today+timedelta(weeks=lead_weeks-1,days=6)).isoformat()
                    data["run_days"]=[0,2,4,6]
                    draft=draft_marathon_plan(data,today)
                    self.assertEqual(len(draft["config"]["weeks"]),lead_weeks)
                    self.assertTrue(load_plan(draft["config"]))
                    self.assertTrue(all(len(week["workouts"])>=2 for week in draft["config"]["weeks"]))
                    if lead_weeks>24:
                        self.assertEqual(draft["config"]["weeks"][0]["phase"],"Base conditioning")

    def test_aggressive_five_day_plan_adds_controlled_second_stimulus(self):
        data=input_data("aggressive")
        data["run_days"]=[0,1,3,5,6]
        draft=draft_marathon_plan(data,date(2030,1,1))
        labels=[workout["label"] for week in draft["config"]["weeks"]
                for workout in week["workouts"]]
        self.assertIn("Steady aerobic run",labels)


if __name__ == "__main__":
    unittest.main()
