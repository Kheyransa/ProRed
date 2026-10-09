"""Load ignored local server settings without overriding environment values."""
from pathlib import Path
from dotenv import load_dotenv


def load_config():
    load_dotenv(Path(__file__).resolve().parent.parent / '.env', override=False)
