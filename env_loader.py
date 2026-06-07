import os
from pathlib import Path


def load_env(env_file='.env'):
    env_path = Path(__file__).resolve().parent / env_file

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()

        if not line or line.startswith('#') or '=' not in line:
            continue

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        os.environ.setdefault(key, value)


def get_env_value(*names):
    load_env()

    for name in names:
        value = os.getenv(name)
        if value:
            return value

    raise ValueError(f'.env 파일에 {names[0]} 값을 설정해주세요.')
