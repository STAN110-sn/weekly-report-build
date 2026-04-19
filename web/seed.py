"""
初期データ投入スクリプト
開発・初回セットアップ時に実行
"""
import os
import sys
from pathlib import Path

# アプリルートをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web.database import get_db_context, init_db
from web.models import Member


def seed_admin(email: str, name: str = "Admin") -> None:
    """初期 admin ユーザーを作成（既存ならスキップ）"""
    init_db()
    with get_db_context() as db:
        existing = db.query(Member).filter(Member.email == email).first()
        if existing:
            print(f"既存: {existing.name} ({existing.email})")
            return
        m = Member(name=name, email=email, role="admin", active=True)
        db.add(m)
        print(f"作成: {name} ({email}) - role=admin")


if __name__ == "__main__":
    email = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
    name = os.getenv("SEED_ADMIN_NAME", "Admin")
    seed_admin(email, name)
