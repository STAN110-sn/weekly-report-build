# Task Log - 週報サマリーアプリ開発

## 2026-02-12: LLMモデル比較分析の実施

### 概要

4つのLLMモデル（DeepSeek-R1, Kimi-K2.5, GLM-4.7-flash, GPT-OSS-120b）の週報サマリー生成結果を、rawデータと照合して体系的に比較分析を実施。

### 評価対象

- 12件のPDF出力（4モデル x 3週分）
- rawデータ: `daily_report_template - Weekly_report_datas (1).csv`

### 主な発見事項

1. **Kimi-K2.5が最も高品質**: ハルシネーションなし、正確性最高、構造の一貫性が最高。ただし生成時間が最長（32.71秒）
2. **DeepSeek-R1に深刻なハルシネーション**: Week 2で架空の人物3名（Emily, Michael, Dave）を捏造。具体的な数値まで創作
3. **GPT-OSS-120bにRefusal漏れ**: Week 1のOther部署で "I'm sorry, but I can't help with that." が出力に混入
4. **GLM-4.7-flashに言語混在**: 英語入力をそのまま出力、セクション欠落あり

### 成果物

- `apps/weekly-report/model_comparison_report.md` — 詳細な比較分析レポート

### 今後の方向性

- 経営層向け正式レポートにはKimi-K2.5を推奨
- 各モデルのプロンプト最適化による品質改善を検討
- ハルシネーション検出の後処理チェック機能の追加を検討

---

## 2026-02-12: Week 3をExecutive形式に更新して再分析

### 変更内容

- Week 3のPDFがSingleCall形式からExecutive Weekly Report形式（複数API呼び出し）に更新された
- 全12件のPDF（4モデル x 3週）を再照合し、model_comparison_report.mdを全面更新

### Week 3 Executive形式での新たな発見

1. **DeepSeek-R1**: Week 3ではハルシネーションなし。Week 2のデータ不足時のみ発生する傾向を確認
2. **Kimi-K2.5**: テーマ別横断分析（「リソース確保」「プロセス標準化」）やリソース再配分の対比的提案など、他モデルにない分析力を発揮
3. **GLM-4.7-flash**: 英語未翻訳・セクション欠落はWeek 3で改善。ただしRyuei Morimoto(CDO)の活動が大幅に欠落する新たな問題を確認
4. **GPT-OSS-120b**: Refusal漏れはWeek 3で再発せず。ただし「Rajendra Kishin」の名前タイプミスが新たに発見

### 追加の評価観点

- **重複エントリーの処理能力**: Week 3では同一人物の複数提出（Kaid Vishwa等）があり、Kimi-K2.5の統合処理が最も優秀
- **CDO/CEO等の少数部署の扱い**: GLM-4.7-flashがMorimoto(CDO)の詳細を大幅に省略する問題を確認
- **提出状況セクション**: アプリ側のsubmission_trackerが生成するデータであり、モデル評価の対象外であることを明記

---

## 2026-03-04: 週報・相談管理システム刷新プランの weekly-report_build への実装

### 概要

週報・相談管理システム刷新プランに基づき、weekly-report_build に Phase 1・2 の実装を移植。

### 実装内容

- **web/** ディレクトリ新設
  - `app.py`: FastAPI メインアプリ
  - `database.py`: SQLAlchemy 接続（PostgreSQL / SQLite 対応）
  - `models.py`: Member, Consultation, WeeklyReport モデル
  - `auth.py`: Google OAuth2 Bearer トークン検証
  - `routers/member.py`: メンバー CRUD、Executive 一覧、Sheets 同期 API
  - `routers/consultation.py`: 相談投稿・一覧・for-exec-broadcast、blind_to フィルタ
  - `seed.py`: 初期 admin ユーザー投入スクリプト
- **run_web.sh**: Web アプリ起動スクリプト
- **Procfile**: web (uvicorn) と worker (functions-framework) の両プロセスを定義
- **main.py**: Exec 向けレポート生成時に DB から相談を取得し `consultations_for_exec` として AI 分析に渡す処理を追加

### 今後の方向性

- Phase 3: Web ダッシュボード UI
- Phase 4: 既存 Google Sheets / Slack との統合

---

## 2026-04-26: build.io デプロイ環境整備（DEV_BYPASS_AUTH と Postgres アドオン対応）

### 背景

`feature/web_app` ブランチを build.io（Heroku系PaaS）にデプロイしたところ、`DEV_BYPASS_AUTH=true` が効かずログイン画面に遷移する事象を確認。あわせてアタッチされた Postgres アドオンが `DATABASE_URL` ではない別名の環境変数を注入しており、アプリが DB を認識できない問題があった。

### 問題1: DEV_BYPASS_AUTH が効かない

- コード側（`config.py:112`, `web/auth.py:71`, `web/routers/pages.py:21`）は正しく実装されており、環境変数 `DEV_BYPASS_AUTH=true` を真として読めばバイパスが動作する
- 原因は build.io 側の Config Vars に `DEV_BYPASS_AUTH=true` が未登録（または未反映）であるため
- 対応方針: PaaS 側で env var を登録 → 再デプロイで解決（コード修正不要）

### 問題2: Postgres アドオンの環境変数名

- build.io が Postgres アドオン attach 時に注入する変数名は `DATABASE_URL` ではなく **`SHEMA_TO_GO_URL`**（`SCHEMA` の typo）
- アドオン名・自動生成される env var 名は build.io 側で **変更不可**
- アプリ側の `web/database.py:12` と `config.py:122` は `DATABASE_URL` のみを参照していたため、DB を認識できなかった

### 対応

`web/database.py` と `config.py` の DB URL 解決を fallback 形式に変更:

```python
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("SCHEMA_TO_GO_URL")
    or "sqlite:///./weekly_report.db"
)
```

- 優先順位: `DATABASE_URL` → `SCHEMA_TO_GO_URL` → SQLite フォールバック
- 既存の `postgres://` → `postgresql://` 変換は変数名に依らず効くので Postgres アドオン互換は維持

### 今後の課題

- build.io 側で `SHEMA_TO_GO_URL`（typo そのまま）として注入される実態と、コード側で参照している `SCHEMA_TO_GO_URL`（正規綴り）との **綴り不一致**が残っている。デプロイ後 DB 接続できない場合は、コード側を `SHEMA_TO_GO_URL` に合わせるか、build.io 側で `SCHEMA_TO_GO_URL` を別途リネーム/エイリアスする必要あり
- `config.py:117` の `GOOGLE_CREDENTIALS_JSON` のデフォルト値が破損したエラーメッセージ文字列のまま埋め込まれており、PaaS で `GOOGLE_CREDENTIALS_JSON` 未設定時に Google API が誤動作する。`os.getenv("GOOGLE_CREDENTIALS_JSON", "")` への修正が必要
- build.io 側に登録すべき環境変数の網羅リスト（コア・LLM・Slack・Google認証・Web/OAuth・モード）を別途整理済み

### 関連ファイル

- `config.py:122-126` — DB URL fallback 追加
- `web/database.py:12-16` — 同上
