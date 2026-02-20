"""
Google Docs生成サービス
Weekly ReportをGoogle Docsとして作成し、PDF出力
"""
from typing import Dict, Tuple, Optional
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import io
import json

from config import config


class DocsGenerator:
    def __init__(self, output_folder_id: Optional[str] = None):
        """
        Docs生成サービスを初期化
        
        Args:
            output_folder_id: 出力先フォルダID（Noneの場合はconfigから取得）
        """
        self.output_folder_id = output_folder_id or config.OUTPUT_FOLDER_ID
        self.docs_service = self._build_docs_service()
        self.drive_service = self._build_drive_service()
    
    def _get_credentials(self, scopes):
        """認証情報を取得"""
        credentials_info = config.get_google_credentials_info()
        if credentials_info:
            # Build/Heroku等: 環境変数からJSONを直接読み込む
            return service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=scopes
            )
        elif config.GOOGLE_APPLICATION_CREDENTIALS:
            return service_account.Credentials.from_service_account_file(
                config.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=scopes
            )
        else:
            from google.auth import default
            credentials, _ = default(scopes=scopes)
            return credentials
    
    def _build_docs_service(self):
        """Google Docs APIサービスを構築"""
        scopes = ['https://www.googleapis.com/auth/documents']
        credentials = self._get_credentials(scopes)
        return build('docs', 'v1', credentials=credentials)
    
    def _build_drive_service(self):
        """Google Drive APIサービスを構築"""
        scopes = ['https://www.googleapis.com/auth/drive']
        credentials = self._get_credentials(scopes)
        return build('drive', 'v3', credentials=credentials)
    
    def _get_or_create_date_folder(self, base_folder_id: str, date_str: str) -> str:
        """
        指定日付のフォルダを取得または作成
        
        Args:
            base_folder_id: ベースフォルダID（例: GENERAL_FOLDER_ID）
            date_str: 日付文字列（YYYY-MM-DD形式）
        
        Returns:
            日付フォルダのID
        """
        if not base_folder_id:
            return None
        
        folder_name = date_str
        
        # 既存フォルダを検索
        query = f"name='{folder_name}' and '{base_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.drive_service.files().list(
            q=query,
            fields='files(id, name)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        files = results.get('files', [])
        if files:
            # 既存フォルダが見つかった
            folder_id = files[0]['id']
            print(f"既存の日付フォルダを使用: {folder_name} ({folder_id})")
            return folder_id
        
        # フォルダが存在しない場合は作成
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [base_folder_id]
        }
        
        folder = self.drive_service.files().create(
            body=file_metadata,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        folder_id = folder.get('id')
        print(f"日付フォルダを作成: {folder_name} ({folder_id})")
        return folder_id
    
    def create_report(
        self, 
        content: Dict, 
        start_date: str, 
        end_date: str,
        use_date_folder: bool = True,
        file_prefix: str = None
    ) -> Tuple[str, str]:
        """
        Weekly Reportを作成
        
        Args:
            content: レポート内容
            start_date: 開始日（YYYY-MM-DD）
            end_date: 終了日（YYYY-MM-DD）
            use_date_folder: 日付フォルダ（実行日）を作成してその中に保存するか
            file_prefix: ファイル名の接頭辞（例: "glm-4.7-flash"）
        
        Returns:
            (doc_url, pdf_url) のタプル
        """
        if file_prefix:
            title = f"[{file_prefix}] Weekly Report ({start_date} ~ {end_date})"
        else:
            title = f"Weekly Report ({start_date} ~ {end_date})"
        
        # 出力先フォルダを決定（日付フォルダ使用時は作成/取得）
        target_folder_id = self.output_folder_id
        if use_date_folder and target_folder_id:
            run_date = datetime.now().strftime('%Y-%m-%d')
            target_folder_id = self._get_or_create_date_folder(target_folder_id, run_date)
        
        # Drive APIを使って直接共有フォルダ内にGoogle Docsを作成
        # （サービスアカウントにはマイドライブがないため、Docs API直接作成は不可）
        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document'
        }
        
        # 出力フォルダが指定されている場合は直接そこに作成
        if target_folder_id:
            file_metadata['parents'] = [target_folder_id]
        
        # 共有ドライブ対応: supportsAllDrives=True を追加
        doc_file = self.drive_service.files().create(
            body=file_metadata,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        doc_id = doc_file.get('id')
        
        # コンテンツを挿入
        requests = self._build_document_requests(content, start_date, end_date)
        
        self.docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        
        # PDF出力（同じフォルダに保存）
        pdf_url = self._export_as_pdf(doc_id, title, target_folder_id)
        
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        
        return doc_url, pdf_url
    
    def _build_document_requests(self, content: Dict, start_date: str, end_date: str) -> list:
        """ドキュメント挿入リクエストを構築"""
        requests = []
        current_index = 1
        
        def add_text(text: str, style: dict = None):
            nonlocal current_index
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text
                }
            })
            
            if style:
                requests.append({
                    'updateParagraphStyle': {
                        'range': {
                            'startIndex': current_index,
                            'endIndex': current_index + len(text)
                        },
                        'paragraphStyle': style,
                        'fields': ','.join(style.keys())
                    }
                })
            
            current_index += len(text)
        
        def add_heading(text: str, level: str = "HEADING_1"):
            nonlocal current_index
            text_with_newline = text + "\n"
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text_with_newline
                }
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + len(text_with_newline)
                    },
                    'paragraphStyle': {'namedStyleType': level},
                    'fields': 'namedStyleType'
                }
            })
            current_index += len(text_with_newline)
        
        def add_paragraph(text: str):
            nonlocal current_index
            text_with_newline = text + "\n\n"
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text_with_newline
                }
            })
            current_index += len(text_with_newline)
        
        def add_bullet_list(items: list):
            nonlocal current_index
            for item in items:
                text = item + "\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': text
                    }
                })
                requests.append({
                    'createParagraphBullets': {
                        'range': {
                            'startIndex': current_index,
                            'endIndex': current_index + len(text)
                        },
                        'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                    }
                })
                current_index += len(text)
            # 箇条書き後に空行
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': "\n"
                }
            })
            current_index += 1
        
        # メタデータ取得
        token_usage = content.get('token_usage', {})
        elapsed_time = content.get('elapsed_time', 0)
        
        # タイトル
        add_heading(f"Weekly Report", "TITLE")
        add_paragraph(f"対象期間: {start_date} ~ {end_date}")
        add_paragraph(f"分析対象レポート数: {content.get('total_reports', 0)}件")
        add_paragraph(f"モデル: {config.UF_MODEL}")
        
        # 処理時間とトークン使用量（データがあれば表示）
        if elapsed_time:
            add_paragraph(f"生成時間: {elapsed_time:.2f}秒")
        if token_usage and isinstance(token_usage, dict):
            summary = token_usage.get('summary', {})
            if summary:
                add_paragraph(f"トークン使用量: プロンプト={summary.get('total_prompt_tokens', 0)}, 完了={summary.get('total_completion_tokens', 0)}, 合計={summary.get('total_tokens', 0)}")

        
        # サマリー
        add_heading("サマリー", "HEADING_1")
        add_paragraph(content.get('summary', ''))
        
        # 部署別ハイライト
        add_heading("部署別ハイライト", "HEADING_1")
        dept_highlights = content.get('department_highlights', {})
        for dept, highlights in dept_highlights.items():
            add_heading(dept, "HEADING_2")
            add_paragraph(highlights)
        
        # 課題・リスク
        add_heading("課題・リスク", "HEADING_1")
        issues = content.get('issues_and_risks', [])
        if issues:
            issue_texts = []
            for issue in issues:
                if isinstance(issue, dict):
                    severity = issue.get('severity', '中')
                    dept = issue.get('department', '')
                    text = issue.get('issue', '')
                    issue_texts.append(f"[{severity}] {text} ({dept})")
                else:
                    issue_texts.append(str(issue))
            add_bullet_list(issue_texts)
        else:
            add_paragraph("特になし")
        
        # 来週の注目ポイント
        add_heading("来週の注目ポイント", "HEADING_1")
        next_week = content.get('next_week_focus', [])
        if next_week:
            add_bullet_list(next_week)
        else:
            add_paragraph("特になし")
        
        return requests
    
    def _export_as_pdf(self, doc_id: str, title: str, target_folder_id: str = None) -> str:
        """
        ドキュメントをPDFとしてエクスポート
        
        Args:
            doc_id: ドキュメントID
            title: ファイル名（拡張子なし）
            target_folder_id: 保存先フォルダID（Noneの場合はself.output_folder_id）
        """
        request = self.drive_service.files().export_media(
            fileId=doc_id,
            mimeType='application/pdf'
        )
        
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        # PDFをDriveに保存
        buffer.seek(0)
        file_metadata = {
            'name': f"{title}.pdf",
            'mimeType': 'application/pdf'
        }
        
        folder_id = target_folder_id or self.output_folder_id
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        from googleapiclient.http import MediaIoBaseUpload
        media = MediaIoBaseUpload(buffer, mimetype='application/pdf')
        
        # 共有ドライブ対応: supportsAllDrives=True を追加
        pdf_file = self.drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink',
            supportsAllDrives=True
        ).execute()
        
        return pdf_file.get('webViewLink', '')
    
    def save_token_usage_log(
        self, 
        token_usage: Dict, 
        start_date: str, 
        end_date: str,
        use_date_folder: bool = True
    ) -> str:
        """
        トークン使用量をJSONファイルとしてGoogle Driveに保存
        
        Args:
            token_usage: トークン使用量データ
            start_date: 対象期間開始日
            end_date: 対象期間終了日
            use_date_folder: 日付フォルダ（実行日）を作成してその中に保存するか
        
        Returns:
            保存したファイルのURL
        """
        from datetime import datetime
        
        # ファイル名を生成
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"token_usage_{start_date}_{end_date}_{timestamp}.json"
        
        # JSONデータを作成
        log_data = {
            "report_period": {
                "start": start_date,
                "end": end_date
            },
            "generated_at": datetime.now().isoformat(),
            "token_usage": token_usage
        }
        
        # JSONをバイトストリームに変換
        json_content = json.dumps(log_data, ensure_ascii=False, indent=2)
        buffer = io.BytesIO(json_content.encode('utf-8'))
        
        # 出力先フォルダを決定（日付フォルダ使用時は作成/取得）
        target_folder_id = self.output_folder_id
        if use_date_folder and target_folder_id:
            run_date = datetime.now().strftime('%Y-%m-%d')
            target_folder_id = self._get_or_create_date_folder(target_folder_id, run_date)
        
        # Google Driveにアップロード
        file_metadata = {
            'name': filename,
            'mimeType': 'application/json'
        }
        
        if target_folder_id:
            file_metadata['parents'] = [target_folder_id]
        
        media = MediaIoBaseUpload(buffer, mimetype='application/json')
        
        json_file = self.drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink',
            supportsAllDrives=True
        ).execute()
        
        file_url = json_file.get('webViewLink', '')
        print(f"[Token Log] トークン使用量ログを保存: {filename}")
        print(f"[Token Log] URL: {file_url}")
        
        return file_url
    
    def save_output_log(
        self, 
        log_content: str, 
        start_date: str, 
        end_date: str,
        status: str = "completed",
        use_date_folder: bool = True
    ) -> str:
        """
        出力ログをテキストファイルとしてGoogle Driveに保存
        
        Args:
            log_content: ログのテキスト内容
            start_date: 対象期間開始日
            end_date: 対象期間終了日
            status: 処理のステータス（completed/error）
            use_date_folder: 日付フォルダ（実行日）を作成してその中に保存するか
        
        Returns:
            保存したファイルのURL
        """
        from datetime import datetime
        
        # ファイル名を生成
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"output_log_{start_date}_{end_date}_{status}_{timestamp}.txt"
        
        # ヘッダー情報を追加
        header = f"""========================================
Weekly Report Output Log
========================================
対象期間: {start_date} ~ {end_date}
生成日時: {datetime.now().isoformat()}
ステータス: {status}
========================================

"""
        full_content = header + log_content
        
        # テキストをバイトストリームに変換
        buffer = io.BytesIO(full_content.encode('utf-8'))
        
        # 出力先フォルダを決定（日付フォルダ使用時は作成/取得）
        target_folder_id = self.output_folder_id
        if use_date_folder and target_folder_id:
            run_date = datetime.now().strftime('%Y-%m-%d')
            target_folder_id = self._get_or_create_date_folder(target_folder_id, run_date)
        
        # Google Driveにアップロード
        file_metadata = {
            'name': filename,
            'mimeType': 'text/plain'
        }
        
        if target_folder_id:
            file_metadata['parents'] = [target_folder_id]
        
        media = MediaIoBaseUpload(buffer, mimetype='text/plain')
        
        txt_file = self.drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink',
            supportsAllDrives=True
        ).execute()
        
        file_url = txt_file.get('webViewLink', '')
        print(f"[Output Log] ログファイルを保存: {filename}")
        print(f"[Output Log] URL: {file_url}")
        
        return file_url
    
    def save_submission_status(
        self,
        submission_status: Dict,
        week_end: str,
        use_date_folder: bool = True
    ) -> str:
        """
        提出状況をJSONファイルとしてGoogle Driveに保存
        
        Args:
            submission_status: 提出状況データ（submission_tracker.check_submission_status()の戻り値）
            week_end: 対象週の終了日（YYYY-MM-DD形式）
            use_date_folder: 日付フォルダ（実行日）を作成してその中に保存するか
        
        Returns:
            保存したファイルのURL
        """
        from datetime import datetime
        
        # ファイル名を生成
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"submission_status_{week_end}_{timestamp}.json"
        
        # JSONデータを作成
        log_data = {
            "week_end": week_end,
            "generated_at": datetime.now().isoformat(),
            "submission_status": submission_status
        }
        
        # JSONをバイトストリームに変換
        json_content = json.dumps(log_data, ensure_ascii=False, indent=2)
        buffer = io.BytesIO(json_content.encode('utf-8'))
        
        # 出力先フォルダを決定（日付フォルダ使用時は作成/取得）
        target_folder_id = self.output_folder_id
        if use_date_folder and target_folder_id:
            run_date = datetime.now().strftime('%Y-%m-%d')
            target_folder_id = self._get_or_create_date_folder(target_folder_id, run_date)
        
        # Google Driveにアップロード
        file_metadata = {
            'name': filename,
            'mimeType': 'application/json'
        }
        
        if target_folder_id:
            file_metadata['parents'] = [target_folder_id]
        
        media = MediaIoBaseUpload(buffer, mimetype='application/json')
        
        json_file = self.drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink',
            supportsAllDrives=True
        ).execute()
        
        file_url = json_file.get('webViewLink', '')
        print(f"[Submission Status] 提出状況ログを保存: {filename}")
        print(f"[Submission Status] URL: {file_url}")
        
        return file_url
    
    def create_exec_report(
        self,
        content: Dict,
        start_date: str,
        end_date: str,
        submission_status: Dict,
        general_report: Dict = None,
        use_date_folder: bool = True,
        file_prefix: str = None
    ) -> Tuple[str, str]:
        """
        エグゼクティブ向けWeekly Reportを作成
        
        Args:
            content: エグゼクティブ向けレポート内容（executive_summary, private_feedback, action_items等）
            start_date: 開始日（YYYY-MM-DD）
            end_date: 終了日（YYYY-MM-DD）
            submission_status: 提出状況データ（submission_tracker.check_submission_status()の戻り値）
            general_report: 一般向けレポートの分析結果（部署別ハイライト等を含む）
            use_date_folder: 日付フォルダ（実行日）を作成してその中に保存するか
            file_prefix: ファイル名の接頭辞（例: "glm-4.7-flash"）
        
        Returns:
            (doc_url, pdf_url) のタプル
        """
        if file_prefix:
            title = f"[{file_prefix}] Executive Weekly Report ({start_date} ~ {end_date})"
        else:
            title = f"Executive Weekly Report ({start_date} ~ {end_date})"
        
        # 出力先フォルダを決定（日付フォルダ使用時は作成/取得）
        target_folder_id = self.output_folder_id
        if use_date_folder and target_folder_id:
            run_date = datetime.now().strftime('%Y-%m-%d')
            target_folder_id = self._get_or_create_date_folder(target_folder_id, run_date)
        
        # Drive APIを使って直接共有フォルダ内にGoogle Docsを作成
        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document'
        }
        
        if target_folder_id:
            file_metadata['parents'] = [target_folder_id]
        
        doc_file = self.drive_service.files().create(
            body=file_metadata,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        doc_id = doc_file.get('id')
        
        # コンテンツを挿入
        requests = self._build_exec_document_requests(content, start_date, end_date, submission_status, general_report)
        
        self.docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        
        # PDF出力
        pdf_url = self._export_as_pdf(doc_id, title, target_folder_id)
        
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        
        return doc_url, pdf_url
    
    def _build_exec_document_requests(
        self,
        content: Dict,
        start_date: str,
        end_date: str,
        submission_status: Dict,
        general_report: Dict = None
    ) -> list:
        """エグゼクティブ向けドキュメント挿入リクエストを構築"""
        requests = []
        current_index = 1
        
        def add_text(text: str, style: dict = None):
            nonlocal current_index
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text
                }
            })
            
            if style:
                requests.append({
                    'updateParagraphStyle': {
                        'range': {
                            'startIndex': current_index,
                            'endIndex': current_index + len(text)
                        },
                        'paragraphStyle': style,
                        'fields': ','.join(style.keys())
                    }
                })
            
            current_index += len(text)
        
        def add_heading(text: str, level: str = "HEADING_1"):
            nonlocal current_index
            text_with_newline = text + "\n"
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text_with_newline
                }
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + len(text_with_newline)
                    },
                    'paragraphStyle': {'namedStyleType': level},
                    'fields': 'namedStyleType'
                }
            })
            current_index += len(text_with_newline)
        
        def add_paragraph(text: str):
            nonlocal current_index
            text_with_newline = text + "\n\n"
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text_with_newline
                }
            })
            current_index += len(text_with_newline)
        
        def add_bullet_list(items: list):
            nonlocal current_index
            for item in items:
                text = item + "\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': text
                    }
                })
                requests.append({
                    'createParagraphBullets': {
                        'range': {
                            'startIndex': current_index,
                            'endIndex': current_index + len(text)
                        },
                        'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                    }
                })
                current_index += len(text)
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': "\n"
                }
            })
            current_index += 1
        
        # メタデータ取得
        token_usage = content.get('token_usage', {})
        elapsed_time = content.get('elapsed_time', 0)
        
        # ==== 1. タイトル・対象期間・分析対象レポート数 ====
        add_heading("Executive Weekly Report", "TITLE")
        add_paragraph(f"対象期間: {start_date} ~ {end_date}")
        add_paragraph(f"分析対象レポート数: {content.get('total_reports', 0)}件")
        add_paragraph(f"モデル: {config.UF_MODEL}")
        
        # 処理時間とトークン使用量（データがあれば表示）
        if elapsed_time:
            add_paragraph(f"生成時間: {elapsed_time:.2f}秒")
        if token_usage and isinstance(token_usage, dict):
            summary = token_usage.get('summary', {})
            if summary:
                add_paragraph(f"トークン使用量: プロンプト={summary.get('total_prompt_tokens', 0)}, 完了={summary.get('total_completion_tokens', 0)}, 合計={summary.get('total_tokens', 0)}")
        
        # ==== 2. エグゼクティブサマリー ====
        add_heading("エグゼクティブサマリー", "HEADING_1")
        exec_summary = content.get('executive_summary', '')
        add_paragraph(exec_summary if exec_summary else "サマリーなし")
        
        # ==== 3. 部署別ハイライト（一般向けから追加） ====
        dept_highlights = content.get('department_highlights', {})
        if not dept_highlights and general_report:
            dept_highlights = general_report.get('department_highlights', {})
        
        if dept_highlights:
            add_heading("部署別ハイライト", "HEADING_1")
            for dept, highlights in dept_highlights.items():
                if highlights and highlights != "該当期間の報告なし":
                    add_heading(dept, "HEADING_2")
                    add_paragraph(highlights)
        
        # ==== 4. 課題・リスク（一般向けから追加） ====
        issues_and_risks = content.get('issues_and_risks', [])
        if not issues_and_risks and general_report:
            issues_and_risks = general_report.get('issues_and_risks', [])
        
        if issues_and_risks:
            add_heading("課題・リスク", "HEADING_1")
            issue_texts = []
            for issue in issues_and_risks:
                if isinstance(issue, dict):
                    severity = issue.get('severity', '中')
                    dept = issue.get('department', '')
                    text = issue.get('issue', '')
                    issue_texts.append(f"[{severity}] {text} ({dept})")
                else:
                    issue_texts.append(str(issue))
            add_bullet_list(issue_texts)
        
        # ==== 6. 来週の注目ポイント（一般向けから追加） ====
        next_week_focus = content.get('next_week_focus', [])
        if not next_week_focus and general_report:
            next_week_focus = general_report.get('next_week_focus', [])
        
        if next_week_focus:
            add_heading("来週の注目ポイント", "HEADING_1")
            add_bullet_list(next_week_focus)
        
        
        # ==== 7. 個人からの要望・意見 ====
        private_feedback = content.get('private_feedback', [])
        if private_feedback:
            add_heading("個人からの要望・意見", "HEADING_1")
            feedback_items = []
            for item in private_feedback:
                if isinstance(item, dict):
                    name = item.get('name', '')
                    feedback = item.get('feedback', '')
                    feedback_items.append(f"{name}: {feedback}")
                else:
                    feedback_items.append(str(item))
            add_bullet_list(feedback_items)
        
        # ==== 8. アクションアイテム ====
        action_items = content.get('action_items', [])
        if action_items:
            add_heading("アクションアイテム", "HEADING_1")
            if isinstance(action_items, list):
                add_bullet_list([str(item) for item in action_items])
            else:
                add_paragraph(str(action_items))

        # ==== 9. 提出状況 ====
        add_heading("提出状況", "HEADING_1")
        total = submission_status.get('total_members', 0)
        submitted_count = len(submission_status.get('submitted', []))
        missing_count = len(submission_status.get('missing', []))
        add_paragraph(f"総メンバー数: {total}名 / 提出済み: {submitted_count}名 / 未提出: {missing_count}名")
        
        # 提出者リスト
        submitted = submission_status.get('submitted', [])
        if submitted:
            add_heading("提出者リスト", "HEADING_2")
            submitted_names = [s.get('name', '') for s in submitted if s.get('name')]
            if submitted_names:
                add_bullet_list(submitted_names)
        
        # 未提出者リスト
        missing = submission_status.get('missing', [])
        if missing:
            add_heading("未提出者リスト", "HEADING_2")
            missing_names = [m.get('name', '') for m in missing if m.get('name')]
            if missing_names:
                add_bullet_list(missing_names)
        
        # 部署別提出状況
        by_dept = submission_status.get('by_department', {})
        if by_dept:
            add_heading("部署別提出状況", "HEADING_2")
            for dept, dept_data in by_dept.items():
                dept_total = dept_data.get('total', 0)
                dept_submitted = len(dept_data.get('submitted', []))
                dept_missing = len(dept_data.get('missing', []))
                add_paragraph(f"{dept}: 提出済み {dept_submitted}名 / 未提出 {dept_missing}名 / 合計 {dept_total}名")
        
        return requests
