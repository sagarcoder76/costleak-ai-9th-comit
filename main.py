"""Root entrypoint for CostLeak AI.

Most PaaS hosts (Render, Railway, Fly, Vercel, Hugging Face Spaces, …) look for
a FastAPI instance named `app` at `main.py` in the repository root — Vercel's
native FastAPI support specifically scans app.py / index.py / server.py /
main.py and routes every request to it with the original path intact (which is
why this project must NOT define a catch-all rewrite). The real
application lives in `backend/app/main.py`; this module simply re-exports it so
both of these work:

    uvicorn main:app --host 0.0.0.0 --port $PORT      # root entrypoint (deploy)
    uvicorn backend.app.main:app --reload             # nested path (local dev)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make sure the repo root is importable even when the host starts the process
# from a different working directory.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Serverless hosts (Vercel/Lambda) ship a read-only filesystem: only /tmp can be
# written, so the SQLite file has to live there. Set before importing the app,
# which opens the database at import time.
if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    os.environ.setdefault("COSTLEAK_DB", "/tmp/costleak.db")

from backend.app.main import app  # noqa: E402  (re-export for `main:app`)

# Some platforms look for `application` (WSGI/ASGI convention) instead of `app`.
application = app

__all__ = ["app", "application"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("COSTLEAK_RELOAD") == "1",
    )
