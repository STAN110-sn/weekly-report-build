#!/bin/bash
#
# 複数モデルでの週報レポート比較生成スクリプト
# 各モデルで指定した2週分のレポートを生成します
#

# 設定
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 比較対象のモデル一覧
MODELS=(
    "moonshotai/Kimi-K2.5"
    "deepseek-ai/DeepSeek-R1"
    "openai/gpt-oss-120b"
    "glm-4.7-flash"
)

# 対象期間（2週分）
PERIODS=(
    "2026-01-26:2026-01-30"
    "2026-01-19:2026-01-23"
)

# ログファイル
LOG_FILE="model_comparison_$(date +%Y%m%d_%H%M%S).log"

echo "========================================" | tee -a "$LOG_FILE"
echo "モデル比較レポート生成開始" | tee -a "$LOG_FILE"
echo "実行日時: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 各モデルと各期間でレポートを生成
for MODEL in "${MODELS[@]}"; do
    # モデル名から接頭辞を生成（/をハイフンに変換）
    PREFIX=$(echo "$MODEL" | tr '/' '-')
    
    for PERIOD in "${PERIODS[@]}"; do
        START_DATE="${PERIOD%%:*}"
        END_DATE="${PERIOD##*:}"
        
        echo "----------------------------------------" | tee -a "$LOG_FILE"
        echo "モデル: $MODEL" | tee -a "$LOG_FILE"
        echo "期間: $START_DATE ~ $END_DATE" | tee -a "$LOG_FILE"
        echo "プレフィックス: $PREFIX" | tee -a "$LOG_FILE"
        echo "----------------------------------------" | tee -a "$LOG_FILE"
        
        # レポート生成コマンド実行
        python main.py \
            --start-date "$START_DATE" \
            --end-date "$END_DATE" \
            --model "$MODEL" \
            --output-prefix "$PREFIX" \
            2>&1 | tee -a "$LOG_FILE"
        
        # 結果確認
        if [ ${PIPESTATUS[0]} -eq 0 ]; then
            echo "[SUCCESS] $MODEL ($START_DATE ~ $END_DATE)" | tee -a "$LOG_FILE"
        else
            echo "[FAILED] $MODEL ($START_DATE ~ $END_DATE)" | tee -a "$LOG_FILE"
        fi
        
        echo "" | tee -a "$LOG_FILE"
        
        # API制限を考慮して少し待機
        echo "次の生成まで10秒待機..." | tee -a "$LOG_FILE"
        sleep 10
    done
done

echo "========================================" | tee -a "$LOG_FILE"
echo "全レポート生成完了" | tee -a "$LOG_FILE"
echo "ログファイル: $LOG_FILE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
