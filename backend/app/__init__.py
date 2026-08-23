"""NiyamCart deterministic commerce backend."""

from pathlib import Path

from dotenv import load_dotenv

# Local secrets stay in the gitignored repository-root .env file. Existing
# process variables always win, which keeps tests and deployments deterministic.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
