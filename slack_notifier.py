"""
Slack通知サービス
Weekly Report完成時にSlackへ通知
"""
import requests
from datetime import datetime

from config import config


class SlackNotifier:
    def __init__(self, webhook_url: str = None, channel: str = None):
        """
        Slack通知サービスを初期化
        
        Args:
            webhook_url: Webhook URL（Noneの場合はconfigから取得）
            channel: チャンネル名（Noneの場合はconfigから取得）
        """
        self.webhook_url = webhook_url or config.SLACK_WEBHOOK_URL
        self.channel = channel or config.SLACK_CHANNEL
    
    def send_report_notification(
        self, 
        doc_url: str, 
        pdf_url: str,
        week_start: datetime,
        week_end: datetime
    ) -> bool:
        """
        Weekly Report完成通知をSlackに送信
        
        Args:
            doc_url: Google DocsのURL
            pdf_url: PDFのURL
            week_start: 対象週の開始日
            week_end: 対象週の終了日
        
        Returns:
            送信成功したかどうか
        """
        if config.DRY_RUN:
            print("[DRY_RUN] Slack通知をスキップしました（send_report_notification）")
            return True
        
        if not self.webhook_url:
            print("Slack Webhook URLが設定されていません")
            return False
        
        start_str = week_start.strftime('%Y/%m/%d')
        end_str = week_end.strftime('%Y/%m/%d')
        
        message = {
            "channel": self.channel,
            "username": "Weekly Report Bot",
            "icon_emoji": ":clipboard:",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Weekly Report が作成されました",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*対象期間:* {start_str} ~ {end_str}"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "以下のリンクからレポートをご確認ください。"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📄 Google Docs で開く",
                                "emoji": True
                            },
                            "url": doc_url,
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📑 PDF をダウンロード",
                                "emoji": True
                            },
                            "url": pdf_url
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=30
            )
            response.raise_for_status()
            print(f"Slack通知送信成功: {self.channel}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Slack通知送信エラー: {e}")
            return False
    
    def send_error_notification(self, error_message: str) -> bool:
        """
        エラー通知をSlackに送信
        """
        if config.DRY_RUN:
            print("[DRY_RUN] Slack通知をスキップしました（send_error_notification）")
            return True
        
        if not self.webhook_url:
            return False
        
        message = {
            "channel": self.channel,
            "username": "Weekly Report Bot",
            "icon_emoji": ":warning:",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⚠️ Weekly Report 生成エラー",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```{error_message}```"
                    }
                }
            ]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=30
            )
            response.raise_for_status()
            return True
        except:
            return False
    
    def send_report_content(
        self,
        report_content: dict,
        week_start: datetime,
        week_end: datetime
    ) -> bool:
        """
        Weekly Reportの内容を直接Slackに送信
        """
        if config.DRY_RUN:
            print("[DRY_RUN] Slack通知をスキップしました（send_report_content）")
            return True
        
        if not self.webhook_url:
            print("Slack Webhook URLが設定されていません")
            return False
        
        start_str = week_start.strftime('%Y/%m/%d')
        end_str = week_end.strftime('%Y/%m/%d')
        
        # サマリー
        summary = report_content.get('summary', 'サマリーなし')
        
        # 部署別ハイライト
        dept_highlights = report_content.get('department_highlights', {})
        dept_text = ""
        for dept, highlights in dept_highlights.items():
            if highlights and highlights != "該当期間の報告なし":
                dept_text += f"*{dept}*\n{highlights}\n\n"
        
        # 課題・リスク
        issues = report_content.get('issues_and_risks', [])
        issues_text = ""
        for issue in issues:
            if isinstance(issue, dict):
                severity = issue.get('severity', '中')
                dept = issue.get('department', '')
                text = issue.get('issue', '')
                issues_text += f"• [{severity}] {text} ({dept})\n"
            else:
                issues_text += f"• {issue}\n"
        if not issues_text:
            issues_text = "特になし"
        
        # 来週の注目ポイント
        next_week = report_content.get('next_week_focus', [])
        next_week_text = "\n".join([f"• {item}" for item in next_week]) if next_week else "特になし"
        
        message = {
            "channel": self.channel,
            "username": "Weekly Report Bot",
            "icon_emoji": ":clipboard:",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Weekly Report",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*対象期間:* {start_str} ~ {end_str}\n*分析レポート数:* {report_content.get('total_reports', 0)}件"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*📝 サマリー*\n{summary}"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🏢 部署別ハイライト*\n{dept_text if dept_text else '特になし'}"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*⚠️ 課題・リスク*\n{issues_text}"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*📅 来週の注目ポイント*\n{next_week_text}"
                    }
                }
            ]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=30
            )
            response.raise_for_status()
            print(f"Slack通知送信成功: {self.channel}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Slack通知送信エラー: {e}")
            return False
    
    def send_submission_status(
        self,
        week_end: str,
        status_summary: dict
    ) -> bool:
        """
        提出状況をSlackに通知
        
        Args:
            week_end: 対象週の終了日（YYYY-MM-DD形式）
            status_summary: 提出状況サマリー（submission_tracker.get_status_summary_for_slack()の戻り値）
        
        Returns:
            送信成功したかどうか
        """
        if config.DRY_RUN:
            print("[DRY_RUN] Slack通知をスキップしました（send_submission_status）")
            return True
        
        if not self.webhook_url:
            print("Slack Webhook URLが設定されていません")
            return False
        
        # 日付をフォーマット
        try:
            date_obj = datetime.strptime(week_end, '%Y-%m-%d')
            date_str = date_obj.strftime('%Y/%m/%d')
        except ValueError:
            date_str = week_end
        
        total = status_summary.get('total_members', 0)
        submitted = status_summary.get('submitted_count', 0)
        missing = status_summary.get('missing_count', 0)
        submission_rate = status_summary.get('submission_rate', 0)
        missing_by_dept = status_summary.get('missing_by_department', {})
        
        # ブロックを構築
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🧾 提出状況",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*対象日:* {date_str}（金）"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*提出状況サマリー*\n• 総メンバー数: {total}名\n• 提出済み: {submitted}名\n• 未提出: {missing}名\n• 提出率: {submission_rate}%"
                }
            }
        ]
        
        # 未提出者がいる場合、部署別に表示
        if missing_by_dept:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*未提出者（部署別）*"
                }
            })
            
            # 部署ごとにセクションを追加
            for dept, missing_names in missing_by_dept.items():
                if missing_names:
                    # 名前リストをフォーマット（長すぎる場合は省略）
                    names_text = "\n".join([f"• {name}" for name in missing_names])
                    if len(names_text) > 2000:  # Slackの制限を考慮
                        names_text = "\n".join([f"• {name}" for name in missing_names[:10]])
                        names_text += f"\n... 他{len(missing_names) - 10}名"
                    
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{dept}* ({len(missing_names)}名)\n{names_text}"
                        }
                    })
        else:
            # 全員提出済みの場合
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "✅ 全員提出済みです！"
                }
            })
        
        message = {
            "channel": self.channel,
            "username": "Weekly Report Bot",
            "icon_emoji": ":clipboard:",
            "blocks": blocks
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=30
            )
            response.raise_for_status()
            print(f"提出状況通知送信成功: {self.channel}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"提出状況通知送信エラー: {e}")
            return False
    
    def send_exec_report_notification(
        self,
        doc_url: str,
        pdf_url: str,
        week_start: datetime,
        week_end: datetime,
        exec_content: dict
    ) -> bool:
        """
        エグゼクティブ向けWeekly Report完成通知をSlackに送信
        
        Args:
            doc_url: Google DocsのURL
            pdf_url: PDFのURL
            week_start: 対象週の開始日
            week_end: 対象週の終了日
            exec_content: エグゼクティブ向けレポート内容（executive_summary, private_feedback, submission_status等）
        
        Returns:
            送信成功したかどうか
        """
        if config.DRY_RUN:
            print("[DRY_RUN] Slack通知をスキップしました（send_exec_report_notification）")
            return True
        
        if not self.webhook_url:
            print("Slack Webhook URLが設定されていません")
            return False
        
        start_str = week_start.strftime('%Y/%m/%d')
        end_str = week_end.strftime('%Y/%m/%d')
        
        # エグゼクティブサマリー
        exec_summary = exec_content.get('executive_summary', '')
        
        # プライベートフィードバック（個人名＋要点）
        private_feedback = exec_content.get('private_feedback', [])
        feedback_text = ""
        if private_feedback:
            for item in private_feedback:
                if isinstance(item, dict):
                    name = item.get('name', '')
                    feedback = item.get('feedback', '')
                    feedback_text += f"• *{name}*: {feedback}\n"
                else:
                    feedback_text += f"• {item}\n"
        else:
            feedback_text = "特になし"
        
        # 提出状況（簡易版）
        submission = exec_content.get('submission_status', {})
        submitted_count = len(submission.get('submitted', []))
        missing_count = len(submission.get('missing', []))
        total = submission.get('total_members', 0)
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Executive Weekly Report が作成されました",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*対象期間:* {start_str} ~ {end_str}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*エグゼクティブサマリー*\n{exec_summary}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*提出状況*\n• 総メンバー数: {total}名\n• 提出済み: {submitted_count}名\n• 未提出: {missing_count}名"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*個人からの要望・意見*\n{feedback_text}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "以下のリンクから詳細レポートをご確認ください。"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "📄 Google Docs で開く",
                            "emoji": True
                        },
                        "url": doc_url,
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "📑 PDF をダウンロード",
                            "emoji": True
                        },
                        "url": pdf_url
                    }
                ]
            }
        ]
        
        message = {
            "channel": self.channel,
            "username": "Weekly Report Bot (Executive)",
            "icon_emoji": ":briefcase:",
            "blocks": blocks
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=30
            )
            response.raise_for_status()
            print(f"エグゼクティブ向けSlack通知送信成功: {self.channel}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"エグゼクティブ向けSlack通知送信エラー: {e}")
            return False