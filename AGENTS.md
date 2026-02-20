# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Overview

Weekly Report自動生成システム - Google Spreadsheetから日報データを取得し、AI（UF Cloud API）で週次レポートを生成してSlack通知・Google Drive保存するCloud Functions アプリケーション。

Two report types are generated:
- **全体向けレポート**: General weekly summary (no personal names)
- **エグゼクティブ向けレポート**: Executive summary with individual names and urgency ratings

## Commands

### Local Development

```bash
# Run locally (from this directory)
uv run python main.py

# Or with dependencies from monorepo root
cd /path/to/UF_internal_tools && uv sync
```

### Deploy to Cloud Functions

```bash
# General report only
gcloud functions deploy generate-weekly-report \
  --gen2 --runtime python311 --region asia-northeast1 \
  --source . --entry-point generate_weekly_report \
  --trigger-http --allow-unauthenticated \
  --timeout 300 --memory 512MB \
  --set-env-vars "SPREADSHEET_ID=xxx,SHEET_NAME=Weekly_report_datas,..."

# See DEPLOY.md for full environment variable list
```

### Local Auth Setup (if Drive 403 errors)

```bash
gcloud auth application-default revoke
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/spreadsheets.readonly,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/documents"
```

## Architecture

```
main.py (entry point, Cloud Functions handler)
    │
    ├─→ SpreadsheetService (spreadsheet.py)
    │       Reads 日報 data from Google Sheets
    │
    ├─→ SubmissionTracker (submission_tracker.py)
    │       Tracks who submitted reports
    │
    ├─→ AIAnalyzer (ai_analyzer.py)
    │       LLM analysis via UF Cloud API (OpenAI-compatible)
    │       - Department analysis (max 3 calls)
    │       - Overall analysis (1 call)
    │       - Executive analysis (1 call)
    │       - Individual issue urgency (1 call)
    │       Max 6 API calls per run
    │
    ├─→ DocsGenerator (docs_generator.py)
    │       Creates Google Docs/PDF, saves to Drive folders
    │
    └─→ SlackNotifier (slack_notifier.py)
            Sends notifications via webhook
```

### Data Flow

1. `SpreadsheetService` fetches reports from date range (previous week Mon-Fri)
2. `AIAnalyzer` processes with department-level then company-level analysis
3. `DocsGenerator` creates formatted Docs/PDF in Drive folders:
   - `GENERAL_FOLDER_ID` → public reports
   - `EXEC_FOLDER_ID` → executive reports
   - `LOGS_FOLDER_ID` → token usage, output logs
4. `SlackNotifier` posts to configured channels

### Key Configuration (config.py)

- Loads from `.env` file (local) or environment variables (Cloud Functions)
- Department list: `["Development", "Sales&PoC", "Operation", "Other"]`
- Default model: `glm-4.7-flash`
- API retry: 3 attempts with exponential backoff (2s → 4s → 8s)

## Important Notes

- `.env` file goes in `credential/.env` or project root (never commit)
- Executive report only runs if `EXEC_FOLDER_ID` is set
- Some Slack/Docs code is currently commented out for testing (see `main.py`)
- LLM responses may contain `<think>` tags from reasoning models - `ai_analyzer.py` strips these
- Japanese日報 columns: `日付`, `名前`, `部署`, `今週の作業内容`, `来週の作業予定`, `会社への要望・意見`, `課題・困っていること`
