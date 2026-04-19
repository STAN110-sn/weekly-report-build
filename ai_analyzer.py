"""
AI分析サービス
Unsung Fields APIを使用して日報を分析・要約
"""
from openai import OpenAI
from typing import List, Dict, Optional
import time

from config import config


def estimate_tokens(text: str) -> int:
    """
    テキストのトークン数を推定（簡易版）
    日本語は1文字≒1-2トークン、英語は1単語≒1トークンとして概算
    """
    # 簡易的な推定: 文字数 * 0.5 (日本語混在を考慮)
    # より正確にはtiktokenを使うべきだが、依存関係を増やさないため簡易版
    return int(len(text) * 0.5) + len(text.split())


def clean_reasoning_tags(response: str) -> str:
    """
    LLMレスポンスから<think>タグやreasoning部分を除去（テキスト出力用）
    
    Args:
        response: LLMからの生レスポンス
    
    Returns:
        クリーニング済みのテキスト
    """
    if response is None:
        return ""
    
    cleaned = response.strip()
    
    # reasoning model対応: <think>...</think>タグを除去
    if "<think>" in cleaned and "</think>" in cleaned:
        # </think>の後の部分だけを取得
        cleaned = cleaned.split("</think>", 1)[-1].strip()
    elif "</think>" in cleaned:
        # <think>がないが</think>がある場合（開始タグが欠落）
        cleaned = cleaned.split("</think>", 1)[-1].strip()
    
    return cleaned


def clean_llm_response(response: str) -> str:
    """
    LLMレスポンスからJSONを抽出（reasoning modelの<think>タグ対応）
    
    Args:
        response: LLMからの生レスポンス
    
    Returns:
        クリーニング済みのJSON文字列
    """
    # まずreasoningタグを除去
    cleaned = clean_reasoning_tags(response)
    
    # 先頭が日本語の思考プロセス（「まず」「次に」等で始まる）で、
    # その後にJSONが続く場合
    if not cleaned.startswith("{") and not cleaned.startswith("```"):
        # JSONの開始位置を探す
        json_start = cleaned.find("{")
        code_block_start = cleaned.find("```")
        
        if json_start != -1 and (code_block_start == -1 or json_start < code_block_start):
            # 直接JSONが始まる場合
            cleaned = cleaned[json_start:]
        elif code_block_start != -1:
            # コードブロックで始まる場合
            cleaned = cleaned[code_block_start:]
    
    # コードブロックを除去
    if cleaned.startswith("```"):
        # ```json や ``` を除去
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    
    cleaned = cleaned.strip()
    
    # JSONの終端を探す（最後の } を見つける）
    if cleaned.startswith("{"):
        # 括弧のバランスを確認
        brace_count = 0
        last_valid_end = -1
        for i, char in enumerate(cleaned):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    last_valid_end = i + 1
                    break
        
        if last_valid_end > 0:
            cleaned = cleaned[:last_valid_end]
    
    return cleaned


class AIAnalyzer:
    def __init__(self, model_override: str = None):
        """
        AI分析サービスを初期化
        
        Args:
            model_override: 使用するモデル名（Noneの場合はconfig.UF_MODELを使用）
        """
        self.client = OpenAI(
            base_url=config.UF_API_ENDPOINT,
            api_key=config.UF_API_KEY
        )
        self.model = model_override or config.UF_MODEL
        self.departments = config.DEPARTMENTS
        # トークン使用量の追跡
        self.token_usage = {
            "calls": [],  # 各API呼び出しの詳細
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0
        }
        # 出力ログの蓄積
        self.output_log = []
    
    def _log(self, message: str) -> None:
        """ログを出力し、同時に蓄積する"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(message)  # 従来通りコンソール出力
        self.output_log.append(log_entry)
    
    def get_output_log(self) -> str:
        """蓄積したログをテキストとして取得"""
        return "\n".join(self.output_log)
    
    def _log_token_usage(self, context: str, usage) -> None:
        """トークン使用量をログに記録"""
        if usage is None:
            self._log(f"[Token] {context}: usage情報なし")
            return
        
        # usageオブジェクトの全属性をログ出力（reasoning tokens確認用）
        self._log(f"[Token Debug] {context}: usage全体 = {usage}")
        
        prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
        completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
        total_tokens = getattr(usage, 'total_tokens', 0) or 0
        
        # reasoning tokens があるか確認
        reasoning_tokens = getattr(usage, 'reasoning_tokens', None)
        completion_details = getattr(usage, 'completion_tokens_details', None)
        if reasoning_tokens:
            self._log(f"[Token] {context}: reasoning_tokens = {reasoning_tokens}")
        if completion_details:
            self._log(f"[Token] {context}: completion_tokens_details = {completion_details}")
        
        # 個別の呼び出し記録
        call_record = {
            "context": context,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.token_usage["calls"].append(call_record)
        
        # 累積カウント
        self.token_usage["total_prompt_tokens"] += prompt_tokens
        self.token_usage["total_completion_tokens"] += completion_tokens
        self.token_usage["total_tokens"] += total_tokens
        
        # ログ出力
        self._log(f"[Token] {context}: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
        self._log(f"[Token] 累積: prompt={self.token_usage['total_prompt_tokens']}, completion={self.token_usage['total_completion_tokens']}, total={self.token_usage['total_tokens']}")
    
    def get_token_usage_summary(self) -> dict:
        """トークン使用量のサマリーを取得"""
        return {
            "calls": self.token_usage["calls"],
            "summary": {
                "total_api_calls": len(self.token_usage["calls"]),
                "total_prompt_tokens": self.token_usage["total_prompt_tokens"],
                "total_completion_tokens": self.token_usage["total_completion_tokens"],
                "total_tokens": self.token_usage["total_tokens"]
            }
        }
    
    def reset_token_usage(self) -> None:
        """トークン使用量をリセット"""
        self.token_usage = {
            "calls": [],
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0
        }
    
    def _call_api(self, messages: List[Dict], context: str = "", max_retries: int = 3) -> str:
        """
        Unsung Fields APIを呼び出し（リトライ機能付き）
        
        Args:
            messages: APIに送信するメッセージ
            context: ログ用のコンテキスト情報
            max_retries: 最大リトライ回数（デフォルト: 3回）
        
        Returns:
            APIからのレスポンス
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # 指数バックオフ: 2秒、4秒、8秒...
                    wait_time = 2 ** attempt
                    self._log(f"リトライ {attempt}/{max_retries-1} - {wait_time}秒待機: {context}")
                    time.sleep(wait_time)
                
                # プロンプトのトークン数を推定
                prompt_text = " ".join([m.get("content", "") for m in messages])
                estimated_tokens = estimate_tokens(prompt_text)
                self._log(f"API呼び出し開始 (試行 {attempt + 1}/{max_retries}): {context}")
                self._log(f"[Token Estimate] {context}: 推定プロンプトトークン={estimated_tokens}, 文字数={len(prompt_text)}")
                
                completion = self.client.chat.completions.create(
                    messages=messages,
                    model=self.model,
                    temperature=0.3,
                    max_tokens=4096,
                    top_p=1,
                    stream=False,
                    reasoning_effort="medium",
                )
                self._log(f"API呼び出し成功: {context}")
                
                # トークン使用量を記録
                self._log_token_usage(context, completion.usage)
                
                return completion.choices[0].message.content
                
            except Exception as e:
                last_error = e
                error_message = f"{type(e).__name__} - {str(e)}"
                
                # APIサーバーからのエラー詳細を取得
                self._log(f"[API Error Detail] エラータイプ: {type(e).__name__}")
                self._log(f"[API Error Detail] エラーメッセージ: {str(e)}")
                
                # OpenAI APIエラーの詳細情報を取得
                if hasattr(e, 'response'):
                    response = e.response
                    self._log(f"[API Error Detail] HTTPステータス: {getattr(response, 'status_code', 'N/A')}")
                    self._log(f"[API Error Detail] HTTPヘッダー: {dict(getattr(response, 'headers', {}))}")
                    try:
                        response_text = getattr(response, 'text', None)
                        if response_text:
                            self._log(f"[API Error Detail] レスポンスボディ: {response_text}")
                    except:
                        pass
                
                if hasattr(e, 'body'):
                    self._log(f"[API Error Detail] エラーボディ: {e.body}")
                
                if hasattr(e, 'code'):
                    self._log(f"[API Error Detail] エラーコード: {e.code}")
                
                if hasattr(e, 'param'):
                    self._log(f"[API Error Detail] エラーパラメータ: {e.param}")
                
                if hasattr(e, 'type'):
                    self._log(f"[API Error Detail] エラータイプ(API): {e.type}")
                
                # 500系エラーやタイムアウトの場合はリトライ
                should_retry = (
                    "500" in str(e) or 
                    "Internal server error" in str(e) or
                    "timeout" in str(e).lower() or
                    "connection" in str(e).lower()
                )
                
                if should_retry and attempt < max_retries - 1:
                    self._log(f"API呼び出しエラー [{context}]: {error_message} - リトライします")
                else:
                    self._log(f"API呼び出しエラー [{context}]: {error_message}")
                    if attempt >= max_retries - 1:
                        self._log(f"最大リトライ回数({max_retries})に達しました: {context}")
                    break
        
        # 全てのリトライが失敗した場合
        raise last_error
    
    def _format_reports_for_analysis(self, reports: List[Dict]) -> str:
        """日報データを分析用テキストに整形（全体向け：個人名なし）"""
        formatted = []
        
        for report in reports:
            entry = f"""
---
日付: {report.get('日付', 'N/A')}
部署: {report.get('部署', 'N/A')}
今週の作業内容: {report.get('今週の作業内容', 'N/A')}
来週の作業予定: {report.get('来週の作業予定', 'N/A')}
会社への要望・意見: {report.get('会社への要望・意見', 'N/A')}
"""
            formatted.append(entry)
        
        return "\n".join(formatted)
    
    def _format_reports_for_exec_analysis(self, reports: List[Dict]) -> str:
        """日報データをエグゼクティブ向け分析用テキストに整形（個人名を含む）"""
        formatted = []
        
        for report in reports:
            name = report.get('名前', '').strip().lstrip('@')
            entry = f"""
---
名前: {name}
日付: {report.get('日付', 'N/A')}
部署: {report.get('部署', 'N/A')}
今週の作業内容: {report.get('今週の作業内容', 'N/A')}
来週の作業予定: {report.get('来週の作業予定', 'N/A')}
会社への要望・意見: {report.get('会社への要望・意見', 'N/A')}
"""
            formatted.append(entry)
        
        return "\n".join(formatted)
    
    def _group_by_department(self, reports: List[Dict]) -> Dict[str, List[Dict]]:
        """部署別にグループ化"""
        grouped = {dept: [] for dept in self.departments}
        
        for report in reports:
            dept = report.get('部署', 'Other')
            if dept not in grouped:
                dept = 'Other'
            grouped[dept].append(report)
        
        return grouped
    
    def analyze_and_generate_report(
        self, 
        reports: List[Dict],
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        日報を分析してWeekly Reportを生成
        
        Returns:
            レポートコンテンツ（セクション別の辞書）
        """
        start_time = time.time()  # 処理開始時刻を記録
        try:
            grouped_reports = self._group_by_department(reports)
            formatted_data = self._format_reports_for_analysis(reports)
            self._log(f"データフォーマット完了: {len(reports)}件の日報")
            
            # 部署別サマリー作成
            dept_summaries = {}
            for dept, dept_reports in grouped_reports.items():
                if dept_reports:
                    try:
                        dept_summaries[dept] = self._analyze_department(dept, dept_reports)
                        self._log(f"部署別分析完了: {dept}")
                    except Exception as e:
                        self._log(f"部署別分析エラー [{dept}]: {str(e)}")
                        dept_summaries[dept] = f"分析エラー: {str(e)}"
                else:
                    dept_summaries[dept] = "該当期間の報告なし"
            
            # 全体分析
            try:
                overall_analysis = self._analyze_overall(formatted_data, start_date, end_date)
                self._log("全体分析完了")
            except Exception as e:
                self._log(f"全体分析エラー: {str(e)}")
                raise
            
            # トークン使用量サマリーを出力
            usage_summary = self.get_token_usage_summary()
            elapsed_time = time.time() - start_time  # 処理時間を計算
            
            self._log(f"\n[Token Summary] レポート生成完了")
            self._log(f"[Token Summary] 処理時間: {elapsed_time:.2f}秒")
            self._log(f"[Token Summary] API呼び出し回数: {usage_summary['summary']['total_api_calls']}")
            self._log(f"[Token Summary] 総プロンプトトークン: {usage_summary['summary']['total_prompt_tokens']}")
            self._log(f"[Token Summary] 総完了トークン: {usage_summary['summary']['total_completion_tokens']}")
            self._log(f"[Token Summary] 総トークン数: {usage_summary['summary']['total_tokens']}")
            self._log("[Token Summary] 詳細:")
            for call in usage_summary['calls']:
                self._log(f"  - {call['context']}: {call['total_tokens']} tokens ({call['timestamp']})")
            
            return {
                "period": {
                    "start": start_date,
                    "end": end_date
                },
                "summary": overall_analysis["summary"],
                "department_highlights": dept_summaries,
                "issues_and_risks": overall_analysis["issues_and_risks"],
                "next_week_focus": overall_analysis["next_week_focus"],
                "total_reports": len(reports),
                "token_usage": usage_summary,  # トークン使用量も返す
                "elapsed_time": elapsed_time  # 処理時間も返す
            }
        except Exception as e:
            # エラー時もトークン使用量を出力
            usage_summary = self.get_token_usage_summary()
            self._log(f"\n[Token Summary] エラー発生時点のトークン使用量")
            self._log(f"[Token Summary] API呼び出し回数: {usage_summary['summary']['total_api_calls']}")
            self._log(f"[Token Summary] 総トークン数: {usage_summary['summary']['total_tokens']}")
            
            self._log(f"レポート生成エラー: {type(e).__name__} - {str(e)}")
            raise
    
    def _analyze_department(self, department: str, reports: List[Dict]) -> str:
        """部署別の分析"""
        self._log(f"部署別分析開始: {department} ({len(reports)}件)")
        # 個人名を含む形式でデータを整形（誰が何をしたかわかるように）
        formatted = self._format_reports_for_exec_analysis(reports)
        
        prompt = f"""以下は{department}部署の今週の日報データです（個人名を含む）。
この部署の主な進捗・成果を箇条書きで簡潔にまとめてください。
誰が何を行ったかがわかるように、個人名を含めてまとめてください。

{formatted}

出力形式（箇条書きのみ、前置きなし）:
• [名前] 成果の内容
• [名前] 成果の内容
• [名前] 成果の内容
"""
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        response = self._call_api(messages, context=f"部署別分析: {department}")
        
        # reasoning modelの<think>タグを除去
        return clean_reasoning_tags(response)
    
    def _analyze_overall(self, formatted_data: str, start_date: str, end_date: str) -> Dict:
        """全体分析"""
        self._log(f"全体分析開始: {start_date} ~ {end_date}")
        prompt = f"""あなたは社内日報を分析し、経営者向けのWeekly Reportを作成するアシスタントです。

以下は{start_date}から{end_date}までの全社員の日報データです。
このデータを分析し、以下の3つのセクションを作成してください。

【重要な注意事項】
- 個人名は絶対に出さないこと
- 部署単位（Development, PoC, Other）で言及すること
- 簡潔かつ経営判断に役立つ情報を優先すること

{formatted_data}

以下のJSON形式で出力してください（日本語で）:

{{
    "summary": "今週の全体傾向を3-5文で要約",
    "issues_and_risks": [
        {{
            "issue": "課題の内容",
            "severity": "高/中/低",
            "department": "関連部署"
        }}
    ],
    "next_week_focus": [
        "来週の注目ポイント1",
        "来週の注目ポイント2",
        "来週の注目ポイント3"
    ]
}}
"""
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        response = self._call_api(messages, context="全体分析")
        
        # JSONパース（reasoning model対応）
        import json
        try:
            cleaned = clean_llm_response(response)
            if not cleaned:
                raise ValueError("空のレスポンス")
            result = json.loads(cleaned)
            # 必須フィールドの存在確認
            if not isinstance(result, dict):
                raise ValueError("レスポンスが辞書ではない")
            return {
                "summary": result.get("summary", "分析結果を取得できませんでした"),
                "issues_and_risks": result.get("issues_and_risks", []),
                "next_week_focus": result.get("next_week_focus", [])
            }
        except (json.JSONDecodeError, ValueError) as e:
            self._log(f"JSON解析エラー: {e}")
            if response:
                self._log(f"レスポンス: {response[:500]}...")
            # フォールバック
            return {
                "summary": response if response else "分析結果を取得できませんでした",
                "issues_and_risks": [],
                "next_week_focus": []
            }
    
    def analyze_and_generate_exec_report(
        self,
        reports: List[Dict],
        start_date: str,
        end_date: str,
        submission_status: Dict,
        general_report: Dict = None,
        consultations_for_exec: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        エグゼクティブ向けWeekly Reportを生成（個人名を含む）
        
        Args:
            reports: 日報データのリスト
            start_date: 開始日（YYYY-MM-DD）
            end_date: 終了日（YYYY-MM-DD）
            submission_status: 提出状況データ（submission_tracker.check_submission_status()の戻り値）
            general_report: 一般向けレポートの分析結果（再利用用）
            consultations_for_exec: DBから取得した相談（閲覧権限フィルタ済み）。
                各要素は {"name": str, "feedback": str} または {"content": str, "author_name": str} 形式。
                指定時は Exec 向け private_feedback にマージされる。
        
        Returns:
            エグゼクティブ向けレポートコンテンツ
        """
        start_time = time.time()  # 処理開始時刻を記録
        try:
            formatted_data = self._format_reports_for_exec_analysis(reports)
            self._log(f"エグゼクティブ向けデータフォーマット完了: {len(reports)}件の日報")
            
            # エグゼクティブ向け分析
            try:
                exec_analysis = self._analyze_for_exec(formatted_data, start_date, end_date)
                self._log("エグゼクティブ向け分析完了")
            except Exception as e:
                self._log(f"エグゼクティブ向け分析エラー: {str(e)}")
                raise
            
            # トークン使用量サマリーを出力
            usage_summary = self.get_token_usage_summary()
            elapsed_time = time.time() - start_time  # 処理時間を計算
            
            self._log(f"\n[Token Summary] エグゼクティブ向けレポート生成完了")
            self._log(f"[Token Summary] 処理時間: {elapsed_time:.2f}秒")
            self._log(f"[Token Summary] API呼び出し回数: {usage_summary['summary']['total_api_calls']}")
            self._log(f"[Token Summary] 総トークン数: {usage_summary['summary']['total_tokens']}")
            
            # 相談データを private_feedback にマージ（閲覧権限フィルタ済みのものを渡す）
            private_feedback = list(exec_analysis.get("private_feedback", []))
            if consultations_for_exec:
                for c in consultations_for_exec:
                    if isinstance(c, dict):
                        name = c.get("name") or c.get("author_name") or "匿名"
                        feedback = c.get("feedback") or c.get("content", "")
                        if feedback:
                            private_feedback.append({"name": name, "feedback": feedback})

            result = {
                "period": {
                    "start": start_date,
                    "end": end_date
                },
                "executive_summary": exec_analysis.get("executive_summary", ""),
                "private_feedback": private_feedback,
                "action_items": exec_analysis.get("action_items", []),
                "submission_status": submission_status,
                "total_reports": len(reports),
                "token_usage": usage_summary,
                "elapsed_time": elapsed_time  # 処理時間も返す
            }
            
            # 一般向けレポートの内容を追加（再利用）
            if general_report:
                result["department_highlights"] = general_report.get("department_highlights", {})
                result["issues_and_risks"] = general_report.get("issues_and_risks", [])
                result["next_week_focus"] = general_report.get("next_week_focus", [])
                result["summary"] = general_report.get("summary", "")
            
            return result
        except Exception as e:
            usage_summary = self.get_token_usage_summary()
            self._log(f"\n[Token Summary] エラー発生時点のトークン使用量")
            self._log(f"[Token Summary] 総トークン数: {usage_summary['summary']['total_tokens']}")
            
            self._log(f"エグゼクティブ向けレポート生成エラー: {type(e).__name__} - {str(e)}")
            raise
    
    def generate_markdown_report(self, report_content: Dict, report_type: str = "general") -> str:
        """
        analyze_and_generate_report() / analyze_and_generate_exec_report() の戻り値を
        Markdown 文字列に変換する（API 呼び出しなし）。
        """
        period = report_content.get("period", {})
        start = period.get("start", "")
        end = period.get("end", "")

        lines = [f"# Weekly Report: {start} ～ {end}", ""]

        summary = report_content.get("summary") or report_content.get("executive_summary", "")
        if summary:
            section = "エグゼクティブサマリー" if report_type == "executive" else "全体サマリー"
            lines += [f"## {section}", "", summary, ""]

        issues = report_content.get("issues_and_risks", [])
        if issues:
            lines += ["## 課題・リスク", ""]
            for item in issues:
                if isinstance(item, dict):
                    lines.append(
                        f"- {item.get('issue', '')} [{item.get('severity', '')}] ({item.get('department', '')})"
                    )
                else:
                    lines.append(f"- {item}")
            lines.append("")

        focus = report_content.get("next_week_focus", [])
        if focus:
            lines += ["## 来週の注目点", ""]
            for item in focus:
                lines.append(f"- {item}")
            lines.append("")

        dept_highlights = report_content.get("department_highlights", {})
        if dept_highlights:
            lines += ["## 部署別ハイライト", ""]
            for dept, highlights in dept_highlights.items():
                if highlights and highlights != "該当期間の報告なし":
                    lines += [f"### {dept}", "", str(highlights), ""]

        if report_type == "executive":
            feedback = report_content.get("private_feedback", [])
            if feedback:
                lines += ["## 個人フィードバック", ""]
                for item in feedback:
                    if isinstance(item, dict):
                        name = item.get("name", "匿名")
                        fb = item.get("feedback", "")
                        lines.append(f"- **{name}**: {fb}")
                    else:
                        lines.append(f"- {item}")
                lines.append("")

            actions = report_content.get("action_items", [])
            if actions:
                lines += ["## アクションアイテム", ""]
                for item in actions:
                    lines.append(f"- {item}")
                lines.append("")

        return "\n".join(lines)

    def _analyze_for_exec(self, formatted_data: str, start_date: str, end_date: str) -> Dict:
        """エグゼクティブ向け分析（個人名を含む）"""
        self._log(f"エグゼクティブ向け分析開始: {start_date} ~ {end_date}")
        prompt = f"""あなたは社内日報を分析し、エグゼクティブ（経営層）向けのWeekly Reportを作成するアシスタントです。

以下は{start_date}から{end_date}までの全社員の日報データです（個人名を含む）。
このデータを分析し、以下の3つのセクションを作成してください。

【重要な注意事項】
- 個人名を出してよい（エグゼクティブ向けのため）
- 「会社への要望・意見」「課題・困っていること」を中心に、重要なものを抽出すること
- 簡潔かつ経営判断に役立つ情報を優先すること

{formatted_data}

以下のJSON形式で出力してください（日本語で）:

{{
    "executive_summary": "今週の全体傾向を3-7文で要約（個人名を含めて具体的に）",
    "private_feedback": [
        {{
            "name": "個人名",
            "feedback": "要望・意見・不満点の要点"
        }},
        {{
            "name": "個人名2",
            "feedback": "要望・意見・不満点の要点"
        }}
    ],
    "action_items": [
        "経営層が対応すべきアクションアイテム1",
        "経営層が対応すべきアクションアイテム2",
        "経営層が対応すべきアクションアイテム3"
    ]
}}
"""
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        response = self._call_api(messages, context="エグゼクティブ向け分析")
        
        # JSONパース（reasoning model対応）
        import json
        try:
            cleaned = clean_llm_response(response)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            self._log(f"JSON解析エラー: {e}")
            self._log(f"レスポンス: {response[:500]}...")
            # フォールバック
            return {
                "executive_summary": response,
                "private_feedback": [],
                "action_items": []
            }
