#!/usr/bin/env bash
# Weekly Report Web アプリ起動
# 使用: ./run_web.sh  (apps/weekly-report_build から実行)
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
# credential/.env を読み込む（インラインコメント # 以降を除去）
if [ -f credential/.env ]; then
  set -a
  source <(grep -v '^#' credential/.env | sed 's/[[:space:]]*#.*$//' | grep -v '^$')
  set +a
fi
# プロジェクトルートで uv run（依存関係を解決）
ROOT="$(cd ../.. && pwd)"
cd "$ROOT"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
exec uv run uvicorn web.app:app --reload --host 0.0.0.0 --port 8000
