"""
main.generate_weekly_report を Web プロセス内から同期呼び出しするためのアダプタ。

main.py は Cloud Functions 用に書かれており、`@functions_framework.http` デコレータで
ラップされている。第1引数 `request` は関数本体内で参照されていないため、None を渡せば
そのまま動作する。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# プロジェクトルート（main.py の場所）を import パスに追加
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def run_weekly_report(report_type: str = "both") -> dict:
    """
    main.generate_weekly_report を呼び出して結果を返す。

    Args:
        report_type: "general" | "executive" | "both"
            初期版では report_type を無視し、main.py の挙動（general + executive 両方）に従う。
            EXEC_FOLDER_ID が空の環境では executive はスキップされる。

    Returns:
        実行結果のサマリ dict（成否、メッセージ）

    Raises:
        Exception: レポート生成本体が失敗した場合は例外を伝播。
    """
    from main import generate_weekly_report

    logger.info("invoking generate_weekly_report (report_type=%s)", report_type)
    result = generate_weekly_report(None)

    # functions_framework wrapper の戻り値は (body, status) タプル or Flask Response 相当。
    # 形式を緩く解釈してサマリ化。
    summary: dict = {"report_type": report_type}
    if isinstance(result, tuple) and len(result) >= 2:
        body, status_code = result[0], result[1]
        summary["status_code"] = status_code
        if isinstance(body, str):
            summary["body"] = body[:1000]
        else:
            summary["body"] = str(body)[:1000]
        if int(status_code) >= 400:
            raise RuntimeError(f"generate_weekly_report failed with status {status_code}: {summary['body']}")
    else:
        summary["body"] = str(result)[:1000]

    return summary
