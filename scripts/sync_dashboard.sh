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

  # 2️⃣ Stash any local changes (the export may have modified data/properties.json)
  STASH_CREATED=0
  echo "📦 暫存本地變更（如有）"
  if git diff --quiet -- "$DATA_FILE"; then
    echo "無本地變更，跳過 stash"
  else
    if git stash push -m "pre-sync stash $(date +%Y%m%d%H%M%S)" -- "$DATA_FILE"; then
      STASH_CREATED=1
    else
      echo "❌ git stash 失敗，中止同步" >&2
      exit 1
    fi
  fi

  # 3️⃣ 拉取遠端最新變更並 rebase
  echo "🔄 拉取遠端最新變更並 rebase…"
  if ! git fetch --quiet origin; then
    echo "❌ git fetch 失敗，中止同步（遠端未動）" >&2
    exit 1
  fi
  if ! git rebase --quiet origin/main; then
    echo "⚠️  rebase 衝突，放棄 rebase（不留下中間狀態）並改用 merge…" >&2
    git rebase --abort 2>/dev/null || true
    if ! git merge --quiet origin/main -m "Merge origin/main (sync)"; then
      if git diff --name-only --diff-filter=U | grep -qv '^data/properties\.json$'; then
        echo "❌ merge 衝突包含非 data/properties.json 檔案，放棄合併並中止同步" >&2
        git merge --abort 2>/dev/null || true
        exit 1
      fi
      # data/properties.json 為可重新生成的產出檔：衝突時一律採用本機 HEAD 版，隨後由 stash pop／步驟 5 以最新匯出覆蓋。
      echo "⚠️  merge 衝突，以本機版本解決 data/properties.json" >&2
      git checkout --ours -- "$DATA_FILE" 2>/dev/null || true
      git add "$DATA_FILE"
      if ! git commit --no-edit; then
        echo "❌ merge commit 失敗，放棄合併並中止同步" >&2
        git merge --abort 2>/dev/null || true
        exit 1
      fi
    fi
  fi

  # 4️⃣ 套用暫存的變更（如果有的話）
  echo "📤 套用暫存的變更"
  if [ "$STASH_CREATED" -eq 1 ]; then
    if ! git stash pop; then
      echo "⚠️  stash pop 衝突：直接採用暫存版（本機最新匯出）" >&2
      STASH_REF="$(git stash list -1 --format='%gd')"
      if [ -z "$STASH_REF" ]; then
        echo "❌ 找不到可套用的 stash，中止同步" >&2
        exit 1
      fi
      if ! git checkout "$STASH_REF" -- "$DATA_FILE"; then
        echo "❌ 無法從 $STASH_REF 取回 $DATA_FILE，中止同步" >&2
        exit 1
      fi
      git stash drop "$STASH_REF" || true
    fi
  else
    echo "無暫存變更，跳過"
  fi

  # 5️⃣ git 操作後重新匯出一次，保證最終檔案必為全新乾淨 JSON（不可能含有衝突標記）
  if ! "$PYTHON" "$EXPORT_SCRIPT"; then
    echo "❌ 最終 Excel 匯出失敗" >&2
    exit 1
  fi

  # 6️⃣ 若有實質變動則提交並推送（防禦性檢查：檔案不得含有衝突標記）
  if git diff --quiet -- "$DATA_FILE"; then
    echo "📄 資料未變動，跳過提交"
  else
    if grep -q '^<<<<<<<\|^>>>>>>>' "$DATA_FILE"; then
      echo "❌ data/properties.json 含有衝突標記，中止提交（不會推送）" >&2
      exit 1
    fi
    git add "$DATA_FILE"
    git commit -m "Update property data $(date +%Y-%m-%d %H:%M:%S)"
    echo "📤 推送到遠端…"
    if ! git push origin main; then
      echo "❌ 推送失敗" >&2
      exit 1
    fi
    echo "🚀 推送成功，Vercel 將重新部署"
  fi

  echo "=== $(date '+%Y-%m-%d %H:%M:%S') 同步結束 ==="
} 2>&1 | tee -a "$LOG_FILE"