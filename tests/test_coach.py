import contextlib
from datetime import date, timedelta
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import strava_coach as c
from private_data import private_write, write_json, config_from_env_or_file
from training_metrics import analyse_week, report_metrics, get_week_runs, report_end, hr_pace_curve
from training_plan import load_plan

ROOT=Path(__file__).resolve().parents[1]

def activity(day='2030-01-13',km=5,minutes=30,hr=140,**extra):
    return dict(sport_type='Run',start_date=day+'T12:00:00Z',distance=km*1000,moving_time=minutes*60,
                average_heartrate=hr,average_speed=km*1000/(minutes*60),**extra)

class MetricsTests(unittest.TestCase):
    def test_weighted_metrics(self):
        s=analyse_week([activity(km=5,minutes=20,hr=170),activity(km=20,minutes=120,hr=140)])
        self.assertEqual(s['avg_pace'],'5:36/km'); self.assertEqual(s['avg_hr'],144)
    def test_missing_data(self):
        s=analyse_week([activity(minutes=20,hr=None),activity(minutes=80,hr=150)])
        self.assertEqual(s['avg_hr'],150); self.assertEqual(s['hr_coverage_pct'],80)
        self.assertIsNone(analyse_week([])['avg_hr'])
    def test_rolling_and_dates(self):
        end=date(2030,1,13)
        runs=[activity((end-timedelta(weeks=i)).isoformat(),km=k) for i,k in enumerate([10,20,30,40,90])]
        self.assertEqual(report_metrics(runs,end)['rolling_km'],25)
        self.assertEqual(report_end(date(2030,1,14)),end)
        a=dict(activity(),start_date='2030-01-13T23:30:00Z')
        self.assertEqual(len(get_week_runs([a],date(2030,1,7))),1)
        self.assertEqual(len(get_week_runs([a],date(2030,1,7),ZoneInfo('Europe/Paris'))),0)
    def test_plan_and_race_accounting(self):
        plan=load_plan(json.loads((ROOT/'examples/coach_config.json').read_text()))
        self.assertEqual([w.total_km for w in plan],[12,19])
        race=next(x for x in plan[1].workouts if x.race)
        self.assertEqual(race.race_km,10); self.assertEqual(race.km,12)
        config=json.loads((ROOT/'examples/coach_config.json').read_text()); config['weeks'][0]['training_km']=99
        with self.assertRaises(ValueError): load_plan(config)

    def test_hr_pace_curve_compares_fixed_windows_with_weighted_pace(self):
        end=date(2030,4,28)
        runs=[]
        for weeks_ago in (9,10):
            runs.append(activity((end-timedelta(weeks=weeks_ago)).isoformat(),km=10,minutes=50,hr=145))
        for weeks_ago in (0,1):
            runs.append(activity((end-timedelta(weeks=weeks_ago)).isoformat(),km=10,minutes=48,hr=145))
        curve=hr_pace_curve(runs,end)
        point=next(x for x in curve if x['hr']==145)
        self.assertEqual(point['baseline_pace'],'5:00/km')
        self.assertEqual(point['recent_pace'],'4:48/km')
        self.assertEqual(point['change_seconds'],-12)

class PrivacyTests(unittest.TestCase):
    def test_private_ai_key_can_be_loaded_for_unattended_runs(self):
        with tempfile.TemporaryDirectory() as d:
            state=Path(d); write_json(state/'credentials.json',{})
            write_json(state/'ai_credentials.json',{'anthropic_api_key':'AI_KEY_SENTINEL'})
            with patch.dict(os.environ,{},clear=True):
                self.assertEqual(c.credentials(state)['anthropic_api_key'],'AI_KEY_SENTINEL')

    def test_dashboard_is_compact_and_escapes_private_content(self):
        config=json.loads((ROOT/'examples/coach_config.json').read_text())
        config['profile']={'vo2max':{'value':'53 ml/kg/min'},'threshold_pace':{'value':'4:03/km'}}
        config['benchmarks']={'vo2max':'58+ ml/kg/min'}
        run=activity(name='<b>Tempo</b>',description='PRIVATE_NOTE',laps=[{'distance':1000,'moving_time':240}])
        html,_,_=c.build_report([run],date(2030,1,13),config)
        for expected in ['WEEKLY TRAINING REPORT','UPCOMING WEEK','RUNS LAST WEEK','REMAINING PROGRAM','W2','9 + 10 race km','10 km race','53 ml/kg/min','target 58+ ml/kg/min','4:03/km','&lt;b&gt;Tempo&lt;/b&gt;']:
            self.assertIn(expected,html)
        for omitted in ['Long runs: last eight weeks','not supplied','PRIVATE_NOTE','Omgange','1.00 km']:
            self.assertNotIn(omitted,html)

    def test_email_delivery_uses_tls_and_multipart_content(self):
        cfg={'gmail_sender':'sender@example.com','gmail_app_password':'APP_PASSWORD_SENTINEL',
             'email_to':'recipient@example.com'}
        smtp=Mock()
        smtp.__enter__=Mock(return_value=smtp); smtp.__exit__=Mock(return_value=False)
        with patch.object(c.smtplib,'SMTP_SSL',return_value=smtp) as smtp_ssl:
            c.send_email(cfg,'<h1>Weekly report</h1>','Weekly report')
        smtp_ssl.assert_called_once_with('smtp.gmail.com',465,timeout=30)
        smtp.login.assert_called_once_with('sender@example.com','APP_PASSWORD_SENTINEL')
        message=smtp.send_message.call_args.args[0]
        self.assertEqual(message['From'],'sender@example.com')
        self.assertEqual(message['To'],'recipient@example.com')
        self.assertEqual(message['Subject'],'Weekly running report')
        self.assertEqual([part.get_content_type() for part in message.get_payload()],
                         ['text/plain','text/html'])
        payloads=[part.get_payload(decode=True).decode(part.get_content_charset())
                  for part in message.get_payload()]
        self.assertEqual(payloads,['Weekly report','<h1>Weekly report</h1>'])

    def test_email_delivery_requires_all_credentials(self):
        with patch.object(c.smtplib,'SMTP_SSL') as smtp_ssl, \
             self.assertRaisesRegex(ValueError,'Missing email credentials'):
            c.send_email({'gmail_sender':'sender@example.com'},'<h1>Report</h1>','Report')
        smtp_ssl.assert_not_called()

    def test_private_permissions_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state'/'test.json'; write_json(p,{'test':True})
            self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600); self.assertEqual(stat.S_IMODE(p.parent.stat().st_mode),0o700)
            outside=Path(d)/'outside'; outside.write_text('unchanged'); link=Path(d)/'link'; link.symlink_to(outside)
            with self.assertRaises(ValueError): private_write(link,'changed')
            self.assertEqual(outside.read_text(),'unchanged')
    def test_ai_opt_in_and_payload_minimized(self):
        a=activity(name='<script>NAME_SENTINEL</script>',description='NOTE_SENTINEL',id=123456789)
        config={'profile':{'private':'PROFILE_SENTINEL'},'checkins':{'2030-01-07':{'note':'CHECKIN_SENTINEL'}}}
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'KEY_SENTINEL'}),patch.object(c.requests,'post') as post:
            html,_,_=c.build_report([a],date(2030,1,13),config); post.assert_not_called()
            self.assertNotIn('<script>',html); self.assertIn('&lt;script&gt;',html)
        response=Mock(status_code=200); response.json.return_value={'content':[{'type':'text','text':'<b>hello</b>'}]}
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'KEY_SENTINEL'}),patch.object(c.requests,'post',return_value=response) as post:
            html,_,_=c.build_report([a],date(2030,1,13),config,use_ai=True)
            body=json.dumps(post.call_args.kwargs['json'])
            for value in ['PROFILE_SENTINEL','CHECKIN_SENTINEL','KEY_SENTINEL','123456789']:
                self.assertNotIn(value,body)
            self.assertIn('NAME_SENTINEL',body); self.assertIn('NOTE_SENTINEL',body)
            self.assertIn('&lt;b&gt;hello&lt;/b&gt;',html)
    def test_provider_and_cli_errors_do_not_leak(self):
        with self.assertRaises(RuntimeError) as caught: c.provider_json(Mock(status_code=400,text='SECRET_SENTINEL'))
        self.assertNotIn('SECRET_SENTINEL',str(caught.exception))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json'; p.write_text('SECRET_SENTINEL invalid json')
            result=subprocess.run([__import__('sys').executable,str(ROOT/'strava_coach.py'),'--config',str(p)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0); self.assertNotIn('SECRET_SENTINEL',result.stderr+result.stdout); self.assertNotIn('Traceback',result.stderr)
    def test_offline_preview_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as d,patch.object(c.requests,'get') as get,patch.object(c.requests,'post') as post,patch.object(c,'send_email') as send:
            c.main(['--dry-run','--date','2030-01-13','--state-dir',d,'--config',str(ROOT/'examples/coach_config.json'),'--activities-file',str(ROOT/'examples/activities.json')])
            get.assert_not_called(); post.assert_not_called(); send.assert_not_called(); self.assertTrue((Path(d)/'reports/report.html').exists())
    def test_simulations_reject_transfers(self):
        for flag in ['--send','--ai','--save-history']:
            with self.subTest(flag=flag),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit): c.main(['--date','2030-01-13',flag])

if __name__=='__main__': unittest.main()
