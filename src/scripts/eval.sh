# API Configuration

export EVAL_AIHUBMIX_API_KEY="sk-EaniAUFQLJ9uQM6M224cEfF89e2241419eD9Ff13Ed8eD8Af"

# Convert to OpenAI format for eval script compatibility
export EVAL_OPENAI_API_KEY="$EVAL_AIHUBMIX_API_KEY"
export OPENAI_API_BASE="https://aihubmix.com/v1"

# Target file to evaluate (collaborative consultation results)
TARGET_FILE="$1"

# Check if TARGET_FILE is provided
if [ -z "$TARGET_FILE" ]; then
    echo "Usage: bash eval.sh <path_to_collaborative_results.jsonl>"
    echo "Example: bash eval.sh outputs/test_online_named_doctors_discussion.jsonl"
    exit 1
fi

# Extract directory and filename
TARGET_DIR=$(dirname "$TARGET_FILE")
TARGET_FILENAME=$(basename "$TARGET_FILE" .jsonl)

# Generate output filename based on input
OUTPUT_FILE="$TARGET_DIR/evaluation_${TARGET_FILENAME}.jsonl"

# ============================================================
# Evaluate Collaborative Consultation Results
# ============================================================
echo "Evaluating collaborative consultation results..."
echo "Input: $TARGET_FILE"
echo "Golden Label: data/patients.json"
echo "Output: $OUTPUT_FILE"
echo "Evaluator Model: gpt-5-nano (AiHubMix)"
echo "============================================================"

python evaluate/eval_collaborative.py \
    "$TARGET_FILE" \
    --reference data/patients.json \
    --output "$OUTPUT_FILE" \
    --model gpt-5-nano \
    --api-key "$EVAL_OPENAI_API_KEY" \
    --api-base "$OPENAI_API_BASE"

echo ""
echo "============================================================"
echo "Evaluation completed!"
echo "Results saved to: $OUTPUT_FILE"
echo "============================================================"