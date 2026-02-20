# Weekly Report自動生成システム - デプロイガイド

## 前提条件

- 必要なAPIが有効化済み（Sheets, Docs, Drive, Cloud Functions, Cloud Scheduler）
- サービスアカウント作成済み
- Spreadsheet と Drive フォルダへの共有設定完了（サービスアカウントに「投稿者」）

## 1. ローカル（.env）で動作確認

Cloud Functionsにデプロイする前は、`UF_internal_tools/apps/weekly-report/.env` に環境変数を置くのが簡単です。

- テンプレ: `UF_internal_tools/apps/weekly-report/.env.example`
- `.env` は **gitにコミットしない**（`UF_internal_tools/.gitignore`で無視）

起動:

```bash
cd UF_internal_tools/apps/weekly-report
uv run python main.py
```

## 2. Google Driveフォルダ設定（分離運用）

共有Driveの親フォルダ配下に、以下の3サブフォルダを作成し、それぞれの **フォルダID** を環境変数で渡します。

- **`general_reports`**（全体向け）→ `GENERAL_FOLDER_ID`
- **`for_exec`**（エグゼクティブ向け）→ `EXEC_FOLDER_ID`
- **`logs`**（ログ）→ `LOGS_FOLDER_ID`

### 日付フォルダの自動生成

各サブフォルダ配下に、実行日（YYYY-MM-DD）のフォルダが自動作成され、その中にファイルが保存されます。

## 3. 環境変数（Cloud Functions / 本番）

### 必須（全体向け）

| 変数名 | 説明 |
|---|---|
| `SPREADSHEET_ID` | 日報SpreadsheetのID |
| `SHEET_NAME` | シート名（例: `Weekly_report_datas`） |
| `GENERAL_FOLDER_ID` | 全体向け出力フォルダ |
| `LOGS_FOLDER_ID` | ログ出力フォルダ |
| `UF_API_ENDPOINT` | UF API endpoint |
| `UF_API_KEY` | UF API key |
| `UF_MODEL` | 使用モデル（例: `glm-4.7-flash`） |
| `SLACK_WEBHOOK_URL` | 全体向け Slack Webhook |
| `SLACK_CHANNEL` | 全体向けチャンネル名（Webhookが固定することが多いので整合用） |

### オプション（エグゼクティブ向け）

**誤配信防止**のため、以下が **すべて設定されている場合のみ** Exec レポートを生成します。

| 変数名 | 説明 |
|---|---|
| `EXEC_FOLDER_ID` | Exec向け出力フォルダ |
| `EXEC_SLACK_WEBHOOK_URL` | Exec向け Slack Webhook |
| `EXEC_SLACK_CHANNEL` | Exec向けチャンネル名（整合用） |

### 後方互換

`OUTPUT_FOLDER_ID` は後方互換用です。基本は `GENERAL_FOLDER_ID` / `EXEC_FOLDER_ID` / `LOGS_FOLDER_ID` を使ってください。

## 4. Cloud Functions へのデプロイ（例）

### 全体向けのみ

```bash
gcloud functions deploy generate-weekly-report \
  --gen2 \
  --runtime python311 \
  --region asia-northeast1 \
  --source . \
  --entry-point generate_weekly_report \
  --trigger-http \
  --allow-unauthenticated \
  --timeout 300 \
  --memory 512MB \
  --set-env-vars "SPREADSHEET_ID=xxx,SHEET_NAME=Weekly_report_datas,GENERAL_FOLDER_ID=xxx,LOGS_FOLDER_ID=xxx,UF_API_ENDPOINT=xxx,UF_API_KEY=xxx,UF_MODEL=glm-4.7-flash,SLACK_WEBHOOK_URL=xxx,SLACK_CHANNEL=#weekly-report"
```

### Exec向けも含む

```bash
gcloud functions deploy generate-weekly-report \
  --gen2 \
  --runtime python311 \
  --region asia-northeast1 \
  --source . \
  --entry-point generate_weekly_report \
  --trigger-http \
  --allow-unauthenticated \
  --timeout 300 \
  --memory 512MB \
  --set-env-vars "SPREADSHEET_ID=xxx,SHEET_NAME=Weekly_report_datas,GENERAL_FOLDER_ID=xxx,EXEC_FOLDER_ID=xxx,LOGS_FOLDER_ID=xxx,UF_API_ENDPOINT=xxx,UF_API_KEY=xxx,UF_MODEL=glm-4.7-flash,SLACK_WEBHOOK_URL=xxx,SLACK_CHANNEL=#weekly-report,EXEC_SLACK_WEBHOOK_URL=xxx,EXEC_SLACK_CHANNEL=#weekly-report-exec"
```

## 5. ローカル実行時のDrive 403（スコープ不足）の対処

ローカルでADC（`gcloud auth application-default login`）を使っている場合、Drive/Docsのスコープが足りないと以下が出ます。

- `"Request had insufficient authentication scopes."`

この場合、ADCを **Drive/Docs/Sheets** のスコープ付きで取り直してください。

```bash
gcloud auth application-default revoke
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/spreadsheets.readonly,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/documents"
```

