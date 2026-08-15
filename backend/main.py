# Entry point for FastAPI Cloud deployment.
# FastAPI Cloud detects `backend/main.py` automatically; this module
# re-exports the application so no internal code is modified.
from api.main import app  # noqa: F401
