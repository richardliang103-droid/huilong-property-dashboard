#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$HOME/.hermes/venvs/web-clipper/bin/python3"

cd "$ROOT"
"$PYTHON" scripts/export_excel.py

if git diff --quiet -- data/properties.json; then
  echo "dashboard data unchanged"
  exit 0
fi

git add data/properties.json
git commit -m "Update property data $(date +%Y-%m-%d)"
git push origin main
echo "dashboard data pushed; Vercel will redeploy from GitHub"
