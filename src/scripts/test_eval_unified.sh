#!/bin/bash
# Quick test script to verify the unified eval script works

cd "$(dirname "$0")/../src"

echo "========================================"
echo "Testing Unified Evaluation Script"
echo "========================================"

# Check if input files exist
if [ ! -f "data/patients.json" ]; then
    echo "[ERROR] data/patients.json not found"
    exit 1
fi

echo ""
echo "Test 1: Show help message"
python evaluate/eval_unified.py --help

echo ""
echo "========================================"
echo "Test 2: Dry run - Check argument parsing"
echo "========================================"
echo "This would run:"
echo "python evaluate/eval_unified.py \\"
echo "    --diagnosis_filepath outputs/dialog_history_iiyi/dialog_history_gpt4.jsonl \\"
echo "    --reference_diagnosis_filepath data/patients.json \\"
echo "    --evaluation_mode objective \\"
echo "    --output_filepath outputs/evaluation/test_eval.jsonl"

echo ""
echo "========================================"
echo "Test 3: Verify output directory exists"
echo "========================================"
mkdir -p outputs/evaluation
echo "[OK] Output directory created/verified"

echo ""
echo "========================================"
echo "To run actual evaluations, use:"
echo "========================================"
echo ""
echo "# 1. Objective evaluation only (no API needed)"
echo "python evaluate/eval_unified.py \\"
echo "    --diagnosis_filepath outputs/dialog_history_iiyi/dialog_history_gpt4.jsonl \\"
echo "    --evaluation_mode objective \\"
echo "    --database './国际疾病分类ICD-10北京临床版v601.xls'"
echo ""
echo "# 2. Expert AI evaluation (requires API)"
echo "export OPENAI_API_KEY='sk-...'"
echo "export OPENAI_API_BASE='https://aihubmix.com/v1'"
echo "python evaluate/eval_unified.py \\"
echo "    --diagnosis_filepath outputs/dialog_history_iiyi/dialog_history_gpt4.jsonl \\"
echo "    --evaluation_mode expert \\"
echo "    --model_name 'gpt-5-nano'"
echo ""
echo "# 3. Statistical summarization (uses cached expert results)"
echo "python evaluate/eval_unified.py \\"
echo "    --diagnosis_filepath outputs/dialog_history_iiyi/dialog_history_gpt4.jsonl \\"
echo "    --evaluation_mode statistical"
echo ""
echo "# 4. All three evaluations"
echo "python evaluate/eval_unified.py \\"
echo "    --diagnosis_filepath outputs/dialog_history_iiyi/dialog_history_gpt4.jsonl \\"
echo "    --evaluation_mode all \\"
echo "    --model_name 'gpt-5-nano'"
