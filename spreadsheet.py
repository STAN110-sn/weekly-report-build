"""
Google Spreadsheet連携サービス
日報データの読み込み
"""
from datetime import datetime
from typing import List, Dict, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import config


class SpreadsheetService:
    def __init__(self):
        self.spreadsheet_id = config.SPREADSHEET_ID
        self.sheet_name = config.SHEET_NAME
        self.service = self._build_service()
        self._members_cache: Optional[List[Dict]] = None
        self._member_map_cache: Optional[Dict[str, Dict]] = None
    
    def _build_service(self):
        """Google Sheets APIサービスを構築"""
        scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']

        credentials_info = config.get_google_credentials_info()
        if credentials_info:
            # Build/Heroku等: 環境変数からJSONを直接読み込む
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=scopes
            )
        elif config.GOOGLE_APPLICATION_CREDENTIALS:
            credentials = service_account.Credentials.from_service_account_file(
                config.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=scopes
            )
        else:
            # Cloud Functions環境ではデフォルト認証を使用
            from google.auth import default
            credentials, _ = default()
            if hasattr(credentials, "with_scopes"):
                try:
                    credentials = credentials.with_scopes(scopes)
                except Exception:
                    pass

        return build('sheets', 'v4', credentials=credentials)
    
    def get_all_reports(self) -> List[Dict]:
        """全ての日報データを取得"""
        range_name = f"{self.sheet_name}!A:I"  # 部署列を追加してA:I
        
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            return []
        
        # ヘッダー行を取得
        headers = values[0]
        
        # データ行を辞書のリストに変換
        reports = []
        for row in values[1:]:
            report = {}
            for i, header in enumerate(headers):
                report[header] = row[i] if i < len(row) else ""
            reports.append(report)
        
        return reports
    
    def get_reports_by_date_range(
        self, 
        start_date: str, 
        end_date: str
    ) -> List[Dict]:
        """
        指定期間の日報データを取得
        
        Args:
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)
        
        Returns:
            日報データのリスト
        """
        all_reports = self.get_all_reports()
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        filtered_reports = []
        for report in all_reports:
            try:
                date_str = report.get('日付', '')
                if not date_str:
                    continue
                
                report_dt = self.parse_date(date_str)
                if not report_dt:
                    continue
                
                if start <= report_dt <= end:
                    filtered_reports.append(report)
                    
            except Exception as e:
                print(f"日付解析エラー: {e}, データ: {report}")
                continue
        
        # 名簿から部署を補完（部署列が空/欠損の場合）
        return self.enrich_reports_with_member_info(filtered_reports)
    
    def get_reports_by_department(
        self, 
        reports: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        日報を部署別に分類
        
        Args:
            reports: 日報データのリスト
        
        Returns:
            部署名をキー、日報リストを値とする辞書
        """
        by_department = {dept: [] for dept in config.DEPARTMENTS}
        
        for report in reports:
            dept = report.get('部署', 'Other')
            if dept not in by_department:
                dept = 'Other'
            by_department[dept].append(report)
        
        return by_department

    def normalize_name(self, name: str) -> str:
        """
        名簿/提出シート間の突合用に名前を正規化
        """
        s = (name or "").strip()
        if s.startswith("@"):
            s = s[1:].strip()
        s = " ".join(s.split())
        return s.casefold()
    
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        日付文字列をdatetimeに変換（時刻は00:00:00）
        """
        if not date_str or not str(date_str).strip():
            return None
        
        raw = str(date_str).strip()
        
        # まずはそのままパース（年月日 or 年月日時分秒）
        for fmt in [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%m/%d/%Y',
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y/%m/%d %H:%M',
        ]:
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        
        # 日本語表記（例: 2026年1月30日）や曜日付き（例: 2026/1/30(金)）を吸収
        import re
        m = re.search(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})', raw)
        if m:
            try:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return datetime(year=y, month=mo, day=d)
            except ValueError:
                return None
        return None
    
    def parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """
        タイムスタンプ文字列をdatetimeに変換
        Google Forms由来の形式に対応
        
        Args:
            timestamp_str: タイムスタンプ文字列
        
        Returns:
            datetimeオブジェクト（解析失敗時はNone）
        """
        if not timestamp_str or not timestamp_str.strip():
            return None
        
        # Google Formsのタイムスタンプ形式（例: "2024/1/5 10:30:45"）
        # 複数の形式に対応
        formats = [
            '%Y/%m/%d %H:%M:%S',      # 2024/1/5 10:30:45
            '%Y/%m/%d %H:%M',         # 2024/1/5 10:30
            '%Y-%m-%d %H:%M:%S',      # 2024-01-05 10:30:45
            '%Y-%m-%d %H:%M',         # 2024-01-05 10:30
            '%Y/%m/%d',                # 2024/1/5
            '%Y-%m-%d',                # 2024-01-05
            '%m/%d/%Y %H:%M:%S',      # 1/5/2024 10:30:45
            '%m/%d/%Y %H:%M',         # 1/5/2024 10:30
            '%m/%d/%Y',                # 1/5/2024
            '%H:%M:%S',                # 10:30:45（表示形式で時刻のみ抽出している場合）
            '%H:%M',                   # 10:30（表示形式で時刻のみ抽出している場合）
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str.strip(), fmt)
            except ValueError:
                continue
        
        # 日付と時刻が分離されている場合の処理（例: "2024/1/5" と "10:30:45"）
        # スペースで分割して試行
        parts = timestamp_str.strip().split()
        if len(parts) >= 2:
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00:00"
            combined = f"{date_part} {time_part}"
            for fmt in formats:
                try:
                    return datetime.strptime(combined, fmt)
                except ValueError:
                    continue
        
        print(f"タイムスタンプ解析失敗: {timestamp_str}")
        return None
    
    def get_reports_by_exact_date(
        self,
        target_date: datetime
    ) -> List[Dict]:
        """
        指定日の日報データを取得（スプレッドシート側で整形済みの「日付」列を優先）
        
        Args:
            target_date: 対象日（datetimeオブジェクト、時刻部分は無視）
        
        Returns:
            該当日の日報データのリスト
        """
        all_reports = self.get_all_reports()
        target_date_only = target_date.date()
        
        filtered_reports = []
        for report in all_reports:
            report_date = None
            
            # 1) 日付列を優先（Spreadsheet側で年月日表示に整形されている前提）
            date_str = report.get('日付', '')
            parsed_date = self.parse_date(date_str)
            if parsed_date:
                report_date = parsed_date.date()
            
            # 2) 日付列が無い/解析失敗の場合のみ、タイムスタンプ列から日付を推定（互換用）
            if not report_date:
                timestamp_str = report.get('タイムスタンプ', '')
                if timestamp_str:
                    parsed_ts = self.parse_timestamp(timestamp_str)
                    if parsed_ts and parsed_ts.year >= 1970:
                        report_date = parsed_ts.date()
            
            if report_date and report_date == target_date_only:
                filtered_reports.append(report)
        
        # 名簿から部署を補完（部署列が空/欠損の場合）
        return self.enrich_reports_with_member_info(filtered_reports)
    
    def get_members(self) -> List[Dict]:
        """
        名簿シートから名簿を取得
        
        優先: Member_list（ヘッダー: 名前,Slack ID,部署）
        互換: Members（ヘッダー: 名前,部署,active）
        
        Returns:
            名簿データのリスト（各要素は名前、部署、Slack ID等を含む）
        """
        if self._members_cache is not None:
            return self._members_cache
        
        ranges_to_try = [
            "Member_list!A:Z",
            "Members!A:Z",
        ]
        
        for range_name in ranges_to_try:
            try:
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name
                ).execute()
                
                values = result.get('values', [])
                if not values:
                    continue
                
                headers = [h.strip() for h in values[0]]
                header_index = {h: i for i, h in enumerate(headers) if h}
                
                # 必須列（どちらのシートでも最低限、名前と部署）
                if '名前' not in header_index or '部署' not in header_index:
                    print(f"警告: 名簿シート {range_name} に必須列(名前/部署)がありません: {headers}")
                    continue
                
                active_idx = header_index.get('active')
                slack_idx = header_index.get('Slack ID') or header_index.get('slack_user_id')
                
                members: List[Dict] = []
                for row in values[1:]:
                    # 行を辞書化（欠損は空文字）
                    member: Dict[str, str] = {}
                    for h, idx in header_index.items():
                        member[h] = row[idx] if idx < len(row) else ""
                    
                    name = str(member.get('名前', '')).strip()
                    if not name:
                        continue
                    
                    # active列が存在する場合のみフィルタ
                    if active_idx is not None:
                        active_value = (row[active_idx] if active_idx < len(row) else "")
                        active_norm = str(active_value).strip().upper()
                        if active_norm not in ['TRUE', '1', 'YES', 'Y']:
                            continue
                    
                    # 互換: Slack IDが無い場合は空にする
                    if slack_idx is None and 'Slack ID' not in member:
                        member['Slack ID'] = ""
                    
                    # 部署が空の場合はOther
                    if not str(member.get('部署', '')).strip():
                        member['部署'] = 'Other'
                    
                    members.append(member)
                
                print(f"名簿取得: {len(members)}名（range={range_name}）")
                self._members_cache = members
                self._member_map_cache = None
                return members
                
            except Exception as e:
                print(f"名簿シート読み取りエラー（range={range_name}）: {e}")
                continue
        
        print("警告: 名簿シートが見つからないか、データがありません（Member_list / Members）")
        self._members_cache = []
        self._member_map_cache = None
        return []

    def get_member_map(self) -> Dict[str, Dict]:
        """
        normalized_name -> member dict のマップを生成（キャッシュ）
        """
        if self._member_map_cache is not None:
            return self._member_map_cache
        
        members = self.get_members()
        member_map: Dict[str, Dict] = {}
        for m in members:
            key = self.normalize_name(m.get("名前", ""))
            if not key:
                continue
            member_map[key] = m
        
        self._member_map_cache = member_map
        return member_map

    def enrich_reports_with_member_info(self, reports: List[Dict]) -> List[Dict]:
        """
        名簿（Member_list/Members）と突合し、report側に不足情報（部署など）を補完する。
        - reportに`部署`キーが無い、または空の場合に名簿の部署で補完
        """
        if not reports:
            return reports
        
        member_map = self.get_member_map()
        if not member_map:
            return reports
        
        for report in reports:
            name_raw = report.get("名前", "")
            key = self.normalize_name(name_raw)
            if not key:
                continue
            member = member_map.get(key)
            if not member:
                continue
            
            # 部署補完
            dept = report.get("部署", "")
            if ("部署" not in report) or (not str(dept).strip()):
                report["部署"] = member.get("部署", "Other") or "Other"
        
        return reports
