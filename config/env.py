import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

def get_env(name, default=None):
    return os.environ.get(name, default)
