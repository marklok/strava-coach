"""Runtime-only private state. Never print configuration or provider responses."""
import json
import os
from pathlib import Path
import tempfile

MAX_JSON_BYTES = 2 * 1024 * 1024


def read_json(path, default=None):
    path=Path(path)
    if not path.exists():
        return {} if default is None else default
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError('JSON input exceeds size limit')
    return json.loads(path.read_text(encoding='utf-8'))


def config_from_env_or_file(path):
    raw=os.environ.get('COACH_CONFIG_JSON')
    if raw:
        if len(raw.encode('utf-8')) > MAX_JSON_BYTES:
            raise ValueError('Configuration exceeds size limit')
        value=json.loads(raw)
    else:
        value=read_json(path)
    if not isinstance(value,dict):
        raise ValueError('Configuration must be an object')
    return value


def private_write(path, content):
    """Atomic replacement, owner-only permissions, reject symlink destinations."""
    path=Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError('Refusing symlink destination')
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.coach-')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            os.chmod(tmp,0o600)
            f.write(content)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_json(path, data):
    private_write(path,json.dumps(data,ensure_ascii=False,indent=2))


def mask_secret(value):
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        escaped=str(value).replace('%','%25').replace('\r','%0D').replace('\n','%0A')
        print('::add-mask::'+escaped)
