#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Load environment variables from .env if exists
if [ -f "$ROOT/.env" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/.env"
fi
PYTHON="${PYTHON:-$HOME/.hermes/venvs/web-clipper/bin/python3}"
EXPORT_SCRIPT="$ROOT/scripts/export_excel.py"
DATA_FILE="$ROOT/data/properties.json"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/sync_$(date +%Y%m%d).log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') 開始同步 ==="
  cd "$ROOT"

  # 1️⃣ 匯出 Excel → JSON
  if "$PYTHON" "$EXPORT_SCRIPT"; then
    echo "✅ Excel 匯出成功"
  else
    echo "❌ Excel 匯出失敗" >&2
    exit 1
  fi

  # 2️⃣ Git 拉取（避免落後）
  echo "🔄 拉取遠端最新變更…"
  if ! git fetch --quiet origin; then
    echo "⚠️  git fetch 失敗，仍嘗試推送" >&2
  fi
  # 若有分歧，先 rebase 再 push（可依需求改為 merge）
  if ! git rebase --quiet origin/main; then
    echo "⚠️  rebase 失敗，請手動處理衝突" >&2
    git rebase --abort
    exit 1
  fi

  # 3️⃣ 若無實質變動則跳過提交
  if git diff --quiet -- "$DATA_FILE"; then
    echo "📄 資料未變動，跳過提交"
  else
    git add "$DATA_FILE"
    git commit -m "Update property data $(date +%Y-%m-%d %H:%M:%S)"
    echo "📤 推送到遠端…"
    if ! git push origin main; then
      echo "❌ 推送失敗（可能仍有衝突）" >&2
      exit 1
    fi
    echo "🚀 推送成功，Vercel 將重新部署"
  fi

  echo "=== $(date '+%Y-%m-%d %H:%M:%S') 同步結束 ==="
} 2>&1 | tee -a "$LOG_FILE"