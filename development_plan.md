設計方針の提案
以下の方針で進めてよいか確認させてください：
Phase 0（現在〜1月中旬）- 最小改善

現行のSlack→SpreadSheet→AI要約フローを維持
週報フォームの項目を新構造（highlight/next week/roadblocks）に変更
特定メンバーでテスト

Phase 1（1月末目標）- 基盤構築

GCP上でまず構築し、動作確認後にUF Cloudへ移行
DB：PostgreSQL または MongoDB（Docker on UF Cloud）
提出状況トラッキング機能
基本的なサマリービュー（まだSlack出力でOK）

Phase 2（2月末目標）- ダッシュボード

Webダッシュボード構築（Next.js等）
階層アクセス制御
分析・エクスポート機能

技術スタック案

入力：Slack Workflow（継続）
バックエンド：Python FastAPI または Node.js
DB：PostgreSQL（構造化データ向き、社員・部署の関係管理に適切）
フロント：Next.js（Phase 2）
AI：UF Cloud API
インフラ：Docker on UF Cloud