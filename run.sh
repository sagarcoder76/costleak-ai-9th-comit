#!/usr/bin/env bash
# CostLeak AI — one-command local start
set -e
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
echo "→ CostLeak AI running at http://localhost:8000"
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
