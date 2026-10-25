import os
from pathlib import Path

from openai import AsyncOpenAI


BASE_URL_ENV_VAR = "DEFAULT_BASE_URL"
DEFAULT_MODEL = "gpt-5.4"
API_KEY_ENV_VAR = "AZURE_OPENAI_API_KEY"
ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_env(env_path=ENV_PATH):
    """Load KEY=VALUE lines from .env. Existing environment variables stay in place."""
    path = Path(env_path)
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def get_openai_client():
    load_env()
    api_key = os.environ.get(API_KEY_ENV_VAR)
    base_url = os.environ.get(BASE_URL_ENV_VAR)
    if not api_key:
        raise RuntimeError(
            f"Missing {API_KEY_ENV_VAR}. Add it to {ENV_PATH}."
        )
    return AsyncOpenAI(api_key=api_key, base_url=base_url)
