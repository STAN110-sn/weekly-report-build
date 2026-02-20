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
