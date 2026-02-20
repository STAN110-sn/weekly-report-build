"""
設定管理モジュール
環境変数（ローカルは .env）から設定を読み込む
"""

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _setenv_if_missing(key: str, value: str) -> None:
    key = (key or "").strip()
    if not key:
        return
    if key in os.environ and os.environ[key] != "":
        return
    os.environ[key] = (value or "").strip().strip('"').strip("'")


def _load_env_file_fallback(path: Path) -> None:
    """
    .env ファイルを簡易的に読み込むフォールバック。

    サポート:
    - dotenv形式: KEY=VALUE
    - 誤って Python コードを貼った形式（救済）:
      SPREADSHEET_ID: str = os.getenv("SPREADSHEET_ID", "xxx")
    """
    if not path.exists():
        return

    try:
        import re

        text = path.read_text(encoding="utf-8")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            # 1) os.getenv("KEY", "VALUE") 形式（救済）
            m = re.search(
                r'os\.getenv\(\s*["\'](?P<key>[^"\']+)["\']\s*,\s*["\'](?P<val>[^"\']*)["\']\s*\)',
                line,
            )
            if m:
                _setenv_if_missing(m.group("key"), m.group("val"))
                continue

            # 2) KEY=VALUE 形式
            if "=" in line:
                key, value = line.split("=", 1)
                _setenv_if_missing(key, value)
    except Exception:
        return


def _load_envs() -> None:
    # どこから実行しても拾えるように候補を広めに取る
    candidates = [
        Path.cwd() / ".env",
        BASE_DIR / ".env",
        BASE_DIR / "credential" / ".env",  # 誤ってここに置いても拾う
        BASE_DIR / "credentials" / ".env",
    ]

    try:
        from dotenv import load_dotenv  # type: ignore

        for p in candidates:
            load_dotenv(dotenv_path=p, override=False)
    except Exception:
        pass

    for p in candidates:
        _load_env_file_fallback(p)


_load_envs()


@dataclass
class Config:
    # Google Spreadsheet
    SPREADSHEET_ID: str = os.getenv("SPREADSHEET_ID", "")
    SHEET_NAME: str = os.getenv("SHEET_NAME", "Weekly_report_datas")

    # Google Drive (出力先フォルダ)
    # 後方互換: OUTPUT_FOLDER_ID は残す（GENERAL_FOLDER_ID が無ければこちらを使う）
    OUTPUT_FOLDER_ID: str = os.getenv("OUTPUT_FOLDER_ID", "")
    GENERAL_FOLDER_ID: str = os.getenv("GENERAL_FOLDER_ID", "")
    EXEC_FOLDER_ID: str = os.getenv("EXEC_FOLDER_ID", "")
    LOGS_FOLDER_ID: str = os.getenv("LOGS_FOLDER_ID", "")

    # Unsung Fields API
    UF_API_ENDPOINT: str = os.getenv("UF_API_ENDPOINT", "https://api.ufcloud.ai/openai/v1")
    UF_API_KEY: str = os.getenv("UF_API_KEY", "")
    UF_MODEL: str = os.getenv("UF_MODEL", "glm-4.7-flash")

    # Slack（全体向け）
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    SLACK_CHANNEL: str = os.getenv("SLACK_CHANNEL", "")

    # Slack（エグゼクティブ向け）
    EXEC_SLACK_WEBHOOK_URL: str = os.getenv("EXEC_SLACK_WEBHOOK_URL", "")
    EXEC_SLACK_CHANNEL: str = os.getenv("EXEC_SLACK_CHANNEL", "")

    # テスト/開発モード設定
    DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")

    # GCP認証（サービスアカウントキーのパス or 環境変数）
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    # Build/Heroku等ファイルを置けない環境向け: サービスアカウントJSONをそのまま or base64エンコードして渡す
    GOOGLE_CREDENTIALS_JSON: str = os.getenv("GOOGLE_CREDENTIALS_JSON", "")

    # 部署リスト
    DEPARTMENTS: list = None

    def __post_init__(self):
        self.DEPARTMENTS = ["Development", "Sales&PoC", "Operation", "Other"]

        # 鍵パスが相対なら weekly-report ディレクトリ基準で絶対パスへ
        if self.GOOGLE_APPLICATION_CREDENTIALS and not os.path.isabs(self.GOOGLE_APPLICATION_CREDENTIALS):
            self.GOOGLE_APPLICATION_CREDENTIALS = str((BASE_DIR / self.GOOGLE_APPLICATION_CREDENTIALS).resolve())

    def get_google_credentials_info(self) -> dict | None:
        """
        GOOGLE_CREDENTIALS_JSON からサービスアカウント情報を取得。
        JSON文字列 と base64エンコード済みJSON の両方に対応。
        """
        if not self.GOOGLE_CREDENTIALS_JSON:
            return None
        import json
        import base64
        # まずそのままJSONとしてパース
        try:
            return json.loads(self.GOOGLE_CREDENTIALS_JSON)
        except Exception:
            pass
        # 次にbase64デコードしてパース
        try:
            decoded = base64.b64decode(self.GOOGLE_CREDENTIALS_JSON).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            return None


# シングルトンインスタンス
config = Config()
