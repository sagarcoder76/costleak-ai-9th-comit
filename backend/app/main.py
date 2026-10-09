"""CostLeak AI — FastAPI application (v2, multi-tenant SaaS)."""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .core import config
from .routers import admin, analysis, auth, billing, gst_reports, invoices, masters
from .routers import compat
from .services import seed

app = FastAPI(
    title=config.APP_NAME, version=config.VERSION,
    description="AI-powered cost-waste analyzer, GST invoicing and spend intelligence for Indian SMBs.",
)
app.add_middleware(GZipMiddleware, minimum_size=700)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Serverless hosts (Vercel, Lambda) have a read-only filesystem and recycle the
# container, so the database is rebuilt on cold start. Never let that crash the
# whole function — the API should still answer even if seeding fails.
import logging  # noqa: E402

log = logging.getLogger("costleak")
try:
    db.init()
    if os.getenv("COSTLEAK_SEED", "1") != "0":
        seed.run()
except Exception:  # pragma: no cover - defensive, keeps the app bootable
    log.exception("Startup initialisation failed; continuing with an empty database.")

for r in (auth.router, masters.router, invoices.router, gst_reports.router,
          billing.router, admin.router, analysis.router, compat.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": config.VERSION,
            "payments": "razorpay" if config.RAZORPAY_ENABLED else "simulated",
            "companies": db.count("companies")}


@app.get("/api/public/plans")
def public_plans():
    return {"plans": config.PLANS, "trial_days": config.TRIAL_DAYS,
            "demo": {"email": seed.DEMO_EMAIL, "password": seed.DEMO_PASSWORD}}


@app.exception_handler(HTTPException)
def http_err(_req: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(detail, status_code=exc.status_code)
    return JSONResponse({"error": str(detail)}, status_code=exc.status_code)


# --------------------------------------------------------------- static ---
STATIC_CACHE = "public, max-age=3600"


class CachedStatic(StaticFiles):
    """Adds cache headers so repeat navigations don't re-download assets."""

    async def get_response(self, path: str, scope):
        resp = await super().get_response(path, scope)
        if path.endswith((".css", ".js", ".svg", ".woff2", ".png", ".jpg", ".webp")):
            resp.headers["Cache-Control"] = STATIC_CACHE
        return resp


app.mount("/assets", CachedStatic(directory=config.FRONTEND), name="assets")


# Platform entrypoint filenames that can arrive as the request path.
ENTRYPOINT_ALIASES = {
    "api", "api/index", "api/index.py", "api/main", "api/main.py",
    "index.py", "main.py", "app.py", "server.py", "asgi.py", "wsgi.py",
}


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    """Single-page app: every non-API route serves the shell (no full reloads).

    Some platforms (Vercel's backend-framework routing in particular) hand the
    app the *entrypoint* path instead of the URL the visitor asked for, e.g.
    "api/index" or "main.py". Those are not real API calls — serving the shell
    keeps the site up instead of answering every request with a 404.
    """
    clean = path.strip("/")
    if clean in ENTRYPOINT_ALIASES:
        clean = ""
    elif clean.startswith("api/"):
        # Name the path. A rewritten path and a genuinely missing endpoint used
        # to produce identical responses, which made this hard to diagnose.
        raise HTTPException(404, {
            "error": f"No API route matches /{clean}",
            "hint": "If this says /api/index, a catch-all rewrite is replacing the "
                    "real URL. Remove 'rewrites' from vercel.json — Vercel's FastAPI "
                    "support already routes every path to this app.",
        })

    candidate = config.FRONTEND / clean
    if clean and candidate.is_file():
        return FileResponse(candidate)
    index = config.FRONTEND / "index.html"
    if not index.is_file():
        # The API is alive but the frontend was not bundled with the function.
        return JSONResponse({
            "error": "Frontend files are missing from this deployment.",
            "expected_at": str(config.FRONTEND),
            "api": "running — try /api/health or /docs",
        }, status_code=503)
    return FileResponse(index)
