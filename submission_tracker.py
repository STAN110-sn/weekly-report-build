"""
提出状況トラッキングサービス
金曜日の提出状況を判定し、未提出者を抽出
"""
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

from spreadsheet import SpreadsheetService


class SubmissionTracker:
    def __init__(self, spreadsheet_service: SpreadsheetService):
        """
        提出状況トラッカーを初期化
        
        Args:
            spreadsheet_service: SpreadsheetServiceのインスタンス
        """
        self.spreadsheet_service = spreadsheet_service
    
    def _format_person_for_slack(self, name: str, slack_id: Optional[str]) -> str:
        """
        Slack表示用に名前/Slack IDを整形（Slack IDが本物ならメンション化）
        """
        if slack_id:
            sid = str(slack_id).strip()
            if sid and sid[0] in ['U', 'W'] and sid.replace('_', '').isalnum():
                return f"<@{sid}>"
        return name
    
    def _normalize_name(self, name: str) -> str:
        """
        名簿/提出シート間の突合用に名前を正規化。
        - 先頭の@を除去（例: '@Mike' -> 'Mike'）
        - 前後空白除去、連続空白の圧縮
        - 大小差を吸収（casefold）
        """
        s = (name or "").strip()
        if s.startswith("@"):
            s = s[1:].strip()
        # 連続空白を1つに
        s = " ".join(s.split())
        return s.casefold()
    
    def _combine_date_and_time(self, date_base: datetime, parsed_time: datetime) -> datetime:
        """
        parse_timestamp が時刻のみ(1900-01-01)を返した場合に、日付を差し替えて結合する
        """
        return datetime(
            year=date_base.year,
            month=date_base.month,
            day=date_base.day,
            hour=parsed_time.hour,
            minute=parsed_time.minute,
            second=parsed_time.second
        )
    
    def check_submission_status(
        self,
        target_friday: datetime,
        submission_end: datetime = None
    ) -> Dict:
        """
        指定期間の提出状況をチェック（金曜〜日曜の提出を含む）
        
        Args:
            target_friday: 対象の金曜日（datetimeオブジェクト）
            submission_end: 提出締切日（datetimeオブジェクト）。Noneの場合は金曜+2日（日曜）
        
        Returns:
            提出状況のサマリー辞書:
            {
                'week_end': 'YYYY-MM-DD',
                'total_members': int,
                'submitted': List[Dict],  # {name, department, submitted_at}
                'missing': List[Dict],     # {name, department}
                'by_department': {
                    'department_name': {
                        'submitted': List[str],  # 名前のリスト
                        'missing': List[str],
                        'total': int
                    }
                }
            }
        """
        # 提出締切日が指定されていない場合は金曜+2日（日曜）
        if submission_end is None:
            from datetime import timedelta
            submission_end = target_friday + timedelta(days=2)
        
        # 名簿を取得
        members = self.spreadsheet_service.get_members()
        if not members:
            print("警告: 名簿が空です")
            return {
                'week_end': target_friday.strftime('%Y-%m-%d'),
                'total_members': 0,
                'submitted': [],
                'missing': [],
                'by_department': {}
            }
        
        # 金曜〜日曜のレポートを取得（遅延提出も含む）
        reports = self.spreadsheet_service.get_reports_by_date_range(
            target_friday.strftime('%Y-%m-%d'),
            submission_end.strftime('%Y-%m-%d')
        )
        print(f"提出状況チェック: {target_friday.strftime('%Y-%m-%d')} ~ {submission_end.strftime('%Y-%m-%d')}")
        
        # 提出済み者をマッピング（名前 -> 最新の提出時刻）
        submitted_map = {}  # normalized_name -> {report, submitted_at}
        
        for report in reports:
            raw_name = report.get('名前', '')
            name_key = self._normalize_name(raw_name)
            if not name_key:
                continue
            
            # タイムスタンプを取得（優先）
            timestamp_str = report.get('タイムスタンプ', '')
            submitted_at = None
            
            if timestamp_str:
                parsed_dt = self.spreadsheet_service.parse_timestamp(timestamp_str)
                if parsed_dt:
                    # 表示形式で時刻のみ(1900-01-01)になっている場合は、対象日の金曜に結合
                    if parsed_dt.year == 1900:
                        submitted_at = self._combine_date_and_time(target_friday, parsed_dt)
                    else:
                        submitted_at = parsed_dt
            
            # 既に提出済みとして記録されている場合、より新しいタイムスタンプで更新
            if name_key in submitted_map:
                existing_timestamp = submitted_map[name_key].get('submitted_at')
                if submitted_at and (not existing_timestamp or submitted_at > existing_timestamp):
                    submitted_map[name_key] = {
                        'report': report,
                        'submitted_at': submitted_at
                    }
            else:
                submitted_map[name_key] = {
                    'report': report,
                    'submitted_at': submitted_at
                }
        
        # 提出済みと未提出を分類
        submitted = []
        missing = []
        by_department = defaultdict(lambda: {'submitted': [], 'missing': [], 'total': 0})
        
        for member in members:
            raw_name = member.get('名前', '')
            name_key = self._normalize_name(raw_name)
            department = member.get('部署', 'Other')
            slack_id = member.get('Slack ID') or member.get('slack_user_id') or member.get('slack_user') or ""
            
            if not name_key:
                continue
            
            # 表示は「名前」を優先（Slack IDはデータとして保持）
            display_name = str(raw_name).strip().lstrip("@")
            
            if name_key in submitted_map:
                # 提出済み
                submission_info = submitted_map[name_key]
                submitted.append({
                    'name': display_name,
                    'department': department,
                    'slack_id': slack_id,
                    'submitted_at': submission_info['submitted_at'].isoformat() if submission_info['submitted_at'] else None
                })
                by_department[department]['submitted'].append(display_name)
            else:
                # 未提出
                missing.append({
                    'name': display_name,
                    'department': department,
                    'slack_id': slack_id
                })
                by_department[department]['missing'].append(display_name)
            
            by_department[department]['total'] += 1
        
        # defaultdictを通常のdictに変換
        by_department_dict = dict(by_department)
        
        result = {
            'week_end': target_friday.strftime('%Y-%m-%d'),
            'total_members': len(members),
            'submitted': submitted,
            'missing': missing,
            'by_department': by_department_dict
        }
        
        print(f"提出状況チェック完了: {target_friday.strftime('%Y-%m-%d')}")
        print(f"  総メンバー数: {len(members)}")
        print(f"  提出済み: {len(submitted)}名")
        print(f"  未提出: {len(missing)}名")
        
        return result
    
    def get_status_summary_for_slack(self, status: Dict) -> Dict:
        """
        Slack通知用のサマリーを生成
        
        Args:
            status: check_submission_status()の戻り値
        
        Returns:
            Slack通知用のフォーマット済み辞書
        """
        week_end = status['week_end']
        total = status['total_members']
        submitted_count = len(status['submitted'])
        missing_count = len(status['missing'])
        
        # 部署別の未提出者リスト
        dept_missing = {}
        for dept, dept_data in status['by_department'].items():
            if dept_data['missing']:
                dept_missing[dept] = dept_data['missing']
        
        return {
            'week_end': week_end,
            'total_members': total,
            'submitted_count': submitted_count,
            'missing_count': missing_count,
            'missing_by_department': dept_missing,
            'submission_rate': round(submitted_count / total * 100, 1) if total > 0 else 0
        }
