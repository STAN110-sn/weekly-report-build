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
    GOOGLE_CREDENTIALS_JSON: str = os.getenv("GOOGLE_CREDENTIALS_JSON", "Error: [Errno 36] File name too long: '/opt/render/project/src/ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInByb2plY3RfaWQiOiAiZGFpbHktcmVwb3J0LWF1dG9tYXRpb24tNDgxNzA3IiwKICAicHJpdmF0ZV9rZXlfaWQiOiAiNGE3ZDgwNTFjOTcxY2UwMzViOWZlOWViOTRmNjIzNjA4YzU0MTY4MSIsCiAgInByaXZhdGVfa2V5IjogIi0tLS0tQkVHSU4gUFJJVkFURSBLRVktLS0tLVxuTUlJRXZRSUJBREFOQmdrcWhraUc5dzBCQVFFRkFBU0NCS2N3Z2dTakFnRUFBb0lCQVFDdkFyTklPV0xsTUN6dFxuOEZFKzhCRmJWNGNzNC90d3Y0dkcrL1VRd0Vabjd0dmxCQUIvQ1RtOEhMeXEyZ282bHozOXc2SFBSKy9kTG8vNFxuTkNIUzM5VmZzTzM0dk5YZ3dXTThyMy9yS1ZRWTRZRVhwMVcxZEtIMTJzZXU3U0hLVXU0TUhhRmxWUTZzeGpVWlxuM2U2aUE0Rzl6UStRUFdnTExHV3AwcnVGTkdldSttOGpKVy8wUjRIU2pUYXprT01Wem9JNGpkQmdhTlFTUjU4MVxucmJsS29BRjhvMkcxL2Q2d1Jmc050amFaQ2ZJYUVVT0htY3BySzdaS2VtNDhVKzBTVVZsQWUweUxKSGVWNjZoUlxuem5USmI4WE1nM1RKcnRBd3NvZ2lZemF0TngzbWErK1BIOXp1MnZyNi8zWHpBd1pNMEUyZ3pRQlZabExJYldOUFxuN042VEh2c1BBZ01CQUFFQ2dnRUFFTE5qUkdzbGd0VjhGQ0N3d0I3TXFUakxEMythQ1FKZVpsaTQ1Q1pWRWFuN1xubGZreHl1Mm9jc2tUUUFLYW8waTNnN1hkaFJoS1RZTVovZ2VMaXNJTmJKcEh1MHJaNWg3T1I0WS80TU1LNFd6elxua3J4SE00K3p2UEJweWNtYlJlRndFZnZwNE8raS9OM1ZSMmlrVXhXZWxld3hwZ1FXSDZyVzhNUEpYVWJJOWl1TFxuZFpUMko5Y09QK3RvSTlieFRXY3Q3Q3VXMitwUldGOGdxRTFtTStGNVlBYkU2cG9sSG00dTNaTXJyUFFPNUNjOVxuOFFCYnVyUVM0VGc3YVZNR1lEK0RGTm45bklJREs2NERUdVVtYXR6ZGR4OXAzU2JmbGtIbDlXZHQvVGlYc2VFU1xuWHhqdTJpY3piNTVpaEpvTU9tV3BJcGRna3k4czJEZmhhSUhXb1I2Vk1RS0JnUURVTG10OEhqUER1SHBwa2FXK1xuemdJbVYwSVdHeDhLVHlVM3dNRG5Qb1d5K2lMaS92VXNNYTlGd09BSTc2cDQ0bG96VFFCdmRuR2JLd1Z3cWVsRVxucEErN1RwS2ZnVVJyT0orYkc2MDhYTW50U2Z3ZFBCMnB2N1VMQ2lMTW5WY21oVjBRVVJJaHdvd1lXNUs5S1V0alxuSWVacHQwU3NQc0c2RFk2K0hkb0dHUXp6TlFLQmdRRFRKeU84ZGY4d3JUUWVkVGNtWlJaUUhpUzNiUElqWVFtalxuVTBaeDRkOVBnenViRVNCelJPYU8xUkFXNWJoaldhOUlOMlRaSndCeWdTbFJxd3A1eThEeTA2Zm1VMU5wdE1QZFxuaHY4SEk3dXc0dTdJUXZTV3pKOEJMUDA1MExzcmwyTUZqS3pOVGFCSFNVNnJ1d28xTTRPb0kzbE1pSnptWFlMT1xuSFJDQnZXWFpzd0tCZ1FDRzBCZXEvT1dXN1plWmk5anJxcWpqQTM0UjNabVRTMFl5Ymw0aWp5OFQwS3BwMytTV1xuOTlxTlQwY0pabjNCNE0rKzJLWDJMQ055bTVzUlFtUGNJUUY5MlNhQUFmb2V4aE5pMGVyMzkxeTFUOVRJSG5JYVxuY0p2dkw3bDhtRnZQTmQwemlNOGtkQi9mT2crNThJcmRxYVJrZHZWREczeXJZZ0hYK2MrVklFV0NJUUtCZ0dLd1xualhSZFZqdkRDSFFmNXZuc0QyUzg0ZjVWVGtzWTVLOVFrY0ZTaDlRYkN6WHI2RlhYNDBibzhJOHpLVjVPSWEzSVxuTGp1TWpobjJvb0JJU0NvckFIQytXbUE5bStQeEdBYW5QUFZ5VHh4YXhLNFhGVWlTTk5NUTJ2NDF2L1djMlN4VFxuMXNSU1B0Snl3ZkZrQjE1Y1NISEN1c1A1cWhQRnF3aDQ3eWtrZzhFZkFvR0FScWd1NUxtLzNmQ3VxSENield3RVxuekI3MldEVy9ObEZwRWtabUZkZjZvYVYvQlp6MFMwUmxpYWVQbkhsb2NZNFFtV3g1bG4yMHV3Z2dPZTZNNVV2SVxuMEJsMTR2VDYwSUJOdTZ5MFprTkFuRVpyQWwvMmp5RGhHbFdNZ29ORnBabnhDY01idFVuVzRRVDJDZitzVXFBMFxudzRZUU8yWFY0Q24xYlJKYTRWOWxhbG89XG4tLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tXG4iLAogICJjbGllbnRfZW1haWwiOiAid2Vla2x5LXJlcG9ydC1ib3QtZGV2QGRhaWx5LXJlcG9ydC1hdXRvbWF0aW9uLTQ4MTcwNy5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSIsCiAgImNsaWVudF9pZCI6ICIxMTUxOTY5NjY3NTMwNzI1MDExMDQiLAogICJhdXRoX3VyaSI6ICJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20vby9vYXV0aDIvYXV0aCIsCiAgInRva2VuX3VyaSI6ICJodHRwczovL29hdXRoMi5nb29nbGVhcGlzLmNvbS90b2tlbiIsCiAgImF1dGhfcHJvdmlkZXJfeDUwOV9jZXJ0X3VybCI6ICJodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9vYXV0aDIvdjEvY2VydHMiLAogICJjbGllbnRfeDUwOV9jZXJ0X3VybCI6ICJodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9yb2JvdC92MS9tZXRhZGF0YS94NTA5L3dlZWtseS1yZXBvcnQtYm90LWRldiU0MGRhaWx5LXJlcG9ydC1hdXRvbWF0aW9uLTQ4MTcwNy5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSIsCiAgInVuaXZlcnNlX2RvbWFpbiI6ICJnb29nbGVhcGlzLmNvbSIKfQo=%'")

    # Web アプリ用（OAuth2, DB）
    GOOGLE_OAUTH_CLIENT_ID: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./weekly_report.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:8000")

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
