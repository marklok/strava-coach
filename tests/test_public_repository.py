from pathlib import Path
import json
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
class PublicRepositoryTests(unittest.TestCase):
    def test_private_filenames_and_tokens_absent(self):
        forbidden=re.compile(r'(^|/)(history|activities|tokens|credentials|coach_config|athlete_profile|weekly_checkins)\.json$|(^|/)\.env($|\.)|\.(fit|gpx|tcx|log)$')
        for p in ROOT.rglob('*'):
            if not p.is_file() or '.private' in p.parts or '__pycache__' in p.parts: continue
            name=str(p.relative_to(ROOT))
            if not name.startswith('examples/'):
                self.assertFalse(forbidden.search(name),name)
            if p.suffix in {'.py','.yml','.md','.json'}:
                self.assertFalse(re.search(r'sk-ant-[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}',p.read_text()),name)
        credentials=json.loads((ROOT/'examples/credentials.json').read_text())
        self.assertTrue(all(value == '' for value in credentials.values()))
    def test_workflows_are_read_only_and_pinned(self):
        for p in (ROOT/'.github/workflows').glob('*.yml'):
            text=p.read_text()
            for forbidden in ['contents: write','upload-artifact','actions/cache','secrets.','pull_request_target','git push','schedule:']: self.assertNotIn(forbidden,text)
            self.assertIn('contents: read',text)
            for action in re.findall(r'uses:\s*([^\s]+)',text): self.assertRegex(action,r'@[a-f0-9]{40}$')
if __name__=='__main__': unittest.main()
