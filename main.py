"""
Weekly Report自動生成システム - メインエントリーポイント
Cloud Functions用 / ローカル実行対応
"""
import functions_framework
from datetime import datetime, timedelta
import json
import argparse

from config import config
from spreadsheet import SpreadsheetService
from ai_analyzer import AIAnalyzer
from slack_notifier import SlackNotifier
from docs_generator import DocsGenerator
from submission_tracker import SubmissionTracker


def calculate_default_period():
    """
    デフォルトの対象期間を計算
    
    Returns:
        week_start: 作業対象週の開始日（月曜）
        week_end: 作業対象週の終了日（金曜）- レポートタイトル用
        target_friday: 対象の金曜日
        submission_end: 提出締切日（日曜）- データ集計用
    """
    today = datetime.now()
    # 月曜日(0)から金曜日(4)までの日数を計算
    days_since_friday = (today.weekday() - 4) % 7
    if days_since_friday == 0:
        days_since_friday = 7
    target_friday = today - timedelta(days=days_since_friday)
    
    # 週の開始日（月曜）と終了日（金曜）
    week_start = target_friday - timedelta(days=4)
    week_end = target_friday
    
    # 提出締切日（日曜）- 金曜〜日曜に提出された週報を含める
    submission_end = target_friday + timedelta(days=2)
    
    return week_start, week_end, target_friday, submission_end


@functions_framework.http
def generate_weekly_report(request, start_date_override=None, end_date_override=None, model_override=None, output_prefix=None):
    """
    Weekly Report生成のメインエントリーポイント
    Cloud Schedulerから毎週月曜朝に呼び出される
    
    Args:
        request: Cloud Functions用リクエストオブジェクト
        start_date_override: 開始日の上書き（datetime or None）
        end_date_override: 終了日の上書き（datetime or None）
        model_override: 使用するモデル名（None の場合は config.UF_MODEL）
        output_prefix: 出力ファイル名の接頭辞（None の場合は接頭辞なし）
    """
    try:
        # 対象期間を計算
        if start_date_override and end_date_override:
            week_start = start_date_override
            week_end = end_date_override
            target_friday = week_end
            # 手動指定の場合、提出締切は終了日+2日（日曜まで）
            submission_end = end_date_override + timedelta(days=2)
        else:
            week_start, week_end, target_friday, submission_end = calculate_default_period()
        
        print(f"対象期間: {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}")
        print(f"提出締切: {submission_end.strftime('%Y-%m-%d')}（金曜〜日曜の提出を含む）")
        
        # Spreadsheetサービスを初期化
        spreadsheet_service = SpreadsheetService()
        
        # 提出状況トラッキング（AI分析とは独立して実行）
        submission_status_url = None
        try:
            tracker = SubmissionTracker(spreadsheet_service)
            submission_status = tracker.check_submission_status(target_friday, submission_end)
            status_summary = tracker.get_status_summary_for_slack(submission_status)
            
            # Slackに提出状況を通知
            notifier = SlackNotifier()
            notifier.send_submission_status(
                target_friday.strftime('%Y-%m-%d'),
                status_summary
            )
            
            # 提出状況をDriveに保存（LOGS_FOLDER_ID使用）
            if config.LOGS_FOLDER_ID:
                try:
                    logs_generator = DocsGenerator(output_folder_id=config.LOGS_FOLDER_ID)
                    submission_status_url = logs_generator.save_submission_status(
                        submission_status,
                        target_friday.strftime('%Y-%m-%d'),
                        use_date_folder=True
                    )
                except Exception as e:
                    print(f"提出状況保存エラー（続行）: {str(e)}")
        except Exception as e:
            print(f"提出状況トラッキングエラー（続行）: {str(e)}")
        
        # 1. Spreadsheetから日報データを取得（金曜〜日曜の提出も含む）
        daily_reports = spreadsheet_service.get_reports_by_date_range(
            target_friday.strftime('%Y-%m-%d'),
            submission_end.strftime('%Y-%m-%d')
        )
        
        if not daily_reports:
            return json.dumps({
                "status": "warning",
                "message": "対象期間の日報データがありません"
            }), 200
        
        print(f"取得した日報数: {len(daily_reports)}")
        
        # 2. AI分析でレポート生成
        analyzer = AIAnalyzer(model_override=model_override)
        try:
            report_content = analyzer.analyze_and_generate_report(
                daily_reports,
                week_start.strftime('%Y-%m-%d'),
                week_end.strftime('%Y-%m-%d')
            )
            analysis_success = True
        except Exception as e:
            analysis_success = False
            # エラー時もログを保存するためにDocsGeneratorを初期化（LOGS_FOLDER_ID使用）
            if config.LOGS_FOLDER_ID:
                try:
                    logs_generator = DocsGenerator(output_folder_id=config.LOGS_FOLDER_ID)
                    output_log = analyzer.get_output_log()
                    logs_generator.save_output_log(
                        output_log,
                        week_start.strftime('%Y-%m-%d'),
                        week_end.strftime('%Y-%m-%d'),
                        status="error",
                        use_date_folder=True
                    )
                except Exception as log_error:
                    print(f"ログ保存エラー: {str(log_error)}")
            raise e
        
        # トークン使用量と処理時間を取得（レポートからは削除せず、後で別管理）
        token_usage = report_content.get('token_usage', None)
        elapsed_time = report_content.get('elapsed_time', None)
        
        # 3. Google Docs/PDF生成（全体向け：GENERAL_FOLDER_ID使用）
        doc_url = None
        pdf_url = None
        token_log_url = None
        output_log_url = None
        if config.GENERAL_FOLDER_ID or config.OUTPUT_FOLDER_ID:
            try:
                general_folder_id = config.GENERAL_FOLDER_ID or config.OUTPUT_FOLDER_ID
                docs_generator = DocsGenerator(output_folder_id=general_folder_id)
                doc_url, pdf_url = docs_generator.create_report(
                    report_content,
                    week_start.strftime('%Y-%m-%d'),
                    week_end.strftime('%Y-%m-%d'),
                    use_date_folder=True
                )
                print(f"Google Docs作成: {doc_url}")
                print(f"PDF作成: {pdf_url}")
                
                # トークン使用量をJSONファイルとして保存（LOGS_FOLDER_ID使用）
                if token_usage and config.LOGS_FOLDER_ID:
                    try:
                        logs_generator = DocsGenerator(output_folder_id=config.LOGS_FOLDER_ID)
                        token_log_url = logs_generator.save_token_usage_log(
                            token_usage,
                            week_start.strftime('%Y-%m-%d'),
                            week_end.strftime('%Y-%m-%d'),
                            use_date_folder=True
                        )
                    except Exception as e:
                        print(f"トークンログ保存エラー（続行）: {str(e)}")
                
                # 出力ログをテキストファイルとして保存（LOGS_FOLDER_ID使用）
                if config.LOGS_FOLDER_ID:
                    try:
                        logs_generator = DocsGenerator(output_folder_id=config.LOGS_FOLDER_ID)
                        output_log = analyzer.get_output_log()
                        output_log_url = logs_generator.save_output_log(
                            output_log,
                            week_start.strftime('%Y-%m-%d'),
                            week_end.strftime('%Y-%m-%d'),
                            status="completed",
                            use_date_folder=True
                        )
                    except Exception as e:
                        print(f"出力ログ保存エラー（続行）: {str(e)}")
                    
            except Exception as e:
                print(f"ドキュメント生成エラー（続行）: {str(e)}")
        
        # 4. Slack通知（全体向け）
        general_notifier = SlackNotifier()
        if doc_url and pdf_url:
            # ドキュメントリンク付きで通知
            general_notifier.send_report_notification(doc_url, pdf_url, week_start, week_end)
        else:
            # レポート内容を直接送信
            general_notifier.send_report_content(report_content, week_start, week_end)
        
        # 5. エグゼクティブ向けレポート生成（EXEC_FOLDER_IDが設定されている場合）
        exec_doc_url = None
        exec_pdf_url = None
        exec_result = {
            "status": "skipped",
            "reason": "環境変数未設定"
        }
        
        # テスト用：EXEC_FOLDER_IDのみで判定（Slack通知は別途コメントアウト済み）
        exec_env_ready = bool(config.EXEC_FOLDER_ID)
        
        if exec_env_ready:
            try:
                print("エグゼクティブ向けレポート生成を開始")
                
                # Exec向けAI分析（一般向け分析結果を再利用）
                exec_analyzer = AIAnalyzer(model_override=model_override)
                exec_content = exec_analyzer.analyze_and_generate_exec_report(
                    daily_reports,
                    week_start.strftime('%Y-%m-%d'),
                    week_end.strftime('%Y-%m-%d'),
                    submission_status,
                    general_report=report_content
                )
                
                # Exec向けトークン使用量と処理時間を取得（レポートからは削除せず、後で別管理）
                exec_token_usage = exec_content.get('token_usage', None)
                exec_elapsed_time = exec_content.get('elapsed_time', None)
                
                # Exec向けDocs/PDF生成（EXEC_FOLDER_ID使用、一般向け分析結果も含む）
                exec_docs_generator = DocsGenerator(output_folder_id=config.EXEC_FOLDER_ID)
                exec_doc_url, exec_pdf_url = exec_docs_generator.create_exec_report(
                    exec_content,
                    week_start.strftime('%Y-%m-%d'),
                    week_end.strftime('%Y-%m-%d'),
                    submission_status,
                    general_report=report_content,
                    use_date_folder=True,
                    file_prefix=output_prefix
                )
                print(f"エグゼクティブ向けGoogle Docs作成: {exec_doc_url}")
                print(f"エグゼクティブ向けPDF作成: {exec_pdf_url}")
                
                # Exec向けトークンログ保存（LOGS_FOLDER_ID使用）
                if exec_token_usage and config.LOGS_FOLDER_ID:
                    try:
                        logs_generator = DocsGenerator(output_folder_id=config.LOGS_FOLDER_ID)
                        exec_token_log_url = logs_generator.save_token_usage_log(
                            exec_token_usage,
                            week_start.strftime('%Y-%m-%d'),
                            week_end.strftime('%Y-%m-%d'),
                            use_date_folder=True
                        )
                    except Exception as e:
                        print(f"エグゼクティブ向けトークンログ保存エラー（続行）: {str(e)}")
                
                # Exec向けSlack通知
                exec_notifier = SlackNotifier(
                    webhook_url=config.EXEC_SLACK_WEBHOOK_URL,
                    channel=config.EXEC_SLACK_CHANNEL
                )

                # Slackに提出状況を通知
                exec_notifier.send_submission_status(
                    target_friday.strftime('%Y-%m-%d'),
                    status_summary
                )
                exec_notifier.send_exec_report_notification(
                    exec_doc_url,
                    exec_pdf_url,
                    week_start,
                    week_end,
                    exec_content
                )
                
                exec_result = {
                    "status": "success",
                    "doc_url": exec_doc_url,
                    "pdf_url": exec_pdf_url
                }
                print("エグゼクティブ向けレポート生成完了")
                
            except Exception as e:
                exec_result = {
                    "status": "error",
                    "message": str(e)
                }
                print(f"エグゼクティブ向けレポート生成エラー（続行）: {str(e)}")
        else:
            print("エグゼクティブ向けレポート生成をスキップ（EXEC_FOLDER_ID未設定）")
        
        return json.dumps({
            "status": "success",
            "message": "Weekly report sent to Slack",
            "reports_analyzed": len(daily_reports),
            "general": {
                "doc_url": doc_url,
                "pdf_url": pdf_url,
                "token_log_url": token_log_url,
                "output_log_url": output_log_url,
                "submission_status_url": submission_status_url
            },
            "executive": exec_result
        }), 200
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": str(e)
        }), 500


# ローカルテスト用
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weekly Report生成")
    parser.add_argument(
        "--start-date", 
        type=str, 
        default=None, 
        help="開始日（YYYY-MM-DD）。指定しない場合は前週月曜日"
    )
    parser.add_argument(
        "--end-date", 
        type=str, 
        default=None, 
        help="作業対象週の終了日/金曜日（YYYY-MM-DD）。提出は終了日+2日（日曜）まで含む"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="使用するLLMモデル名（例: glm-4.7-flash, deepseek-ai/DeepSeek-R1）"
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default=None,
        help="出力ファイル名の接頭辞（例: glm-4.7-flash）。指定しない場合は--modelの値を使用"
    )
    args = parser.parse_args()
    
    # 日付のパース
    start_date_override = None
    end_date_override = None
    
    if args.start_date and args.end_date:
        try:
            start_date_override = datetime.strptime(args.start_date, '%Y-%m-%d')
            end_date_override = datetime.strptime(args.end_date, '%Y-%m-%d')
            print(f"日付指定モード: {args.start_date} ~ {args.end_date}")
        except ValueError as e:
            print(f"日付フォーマットエラー: {e}")
            print("日付はYYYY-MM-DD形式で指定してください（例: 2026-01-26）")
            exit(1)
    elif args.start_date or args.end_date:
        print("エラー: --start-date と --end-date は両方指定してください")
        exit(1)
    else:
        print("デフォルトモード: 前週の週報を生成")
    
    # モデルとプレフィックスの設定
    model_override = args.model
    output_prefix = args.output_prefix or args.model  # prefixが指定されない場合はモデル名を使用
    
    if model_override:
        print(f"モデル指定: {model_override}")
    if output_prefix:
        print(f"出力プレフィックス: {output_prefix}")
    
    class MockRequest:
        pass
    
    result, status = generate_weekly_report(
        MockRequest(),
        start_date_override=start_date_override,
        end_date_override=end_date_override,
        model_override=model_override,
        output_prefix=output_prefix
    )
    print(f"Status: {status}")
    print(f"Result: {result}")