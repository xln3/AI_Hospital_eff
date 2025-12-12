#!/bin/bash
# Unified Evaluation Script Examples
export AIHUBMIX_API_KEY="sk-EaniAUFQLJ9uQM6M224cEfF89e2241419eD9Ff13Ed8eD8Af"
# Set API key for AiHubMix or OpenAI
export OPENAI_API_KEY="$AIHUBMIX_API_KEY"
export OPENAI_API_BASE="https://aihubmix.com/v1"  # For AiHubMix
# or
# export OPENAI_API_BASE="https://api.openai.com/v1"  # For OpenAI

# Get the script directory and change to src
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

# ============================================================================
# Example 1: Objective Evaluation Only (Disease Matching against ICD-10)
# ============================================================================
# Evaluates doctor diagnoses using fuzzy matching against ICD-10 database
# No API calls required - fast and objective

python -u evaluate/eval_unified.py \
    --diagnosis_filepath outputs/token_test_3doctors_patient_discussion_1212_star.jsonl \
    --reference_diagnosis_filepath data/patients.json \
    --evaluation_mode objective \
    --database "evaluate/国际疾病分类ICD-10北京临床版v601.xls" \
    --top_n 10 \
    --threshold 50 \
    --output_filepath outputs/evaluation/eval_results_objective_token_test_3doctors_patient_discussion_1212_star.jsonl


# ============================================================================
# Example 2: Expert AI Evaluation Only (GPT-4 as Medical Expert)
# ============================================================================
# Uses AiHubMix API with gpt-5-nano model
# Evaluates on 5 dimensions: symptom, examination, diagnosis, basis, treatment

# python -u evaluate/eval_unified.py \
#     --diagnosis_filepath outputs/token_test_3doctors_patient_discussion_1212.jsonl \
#     --reference_diagnosis_filepath data/patients.json \
#     --evaluation_mode expert \
#     --openai_api_key "$OPENAI_API_KEY" \
#     --openai_api_base "$OPENAI_API_BASE" \
#     --model_name "gpt-5-nano" \
#     --output_filepath outputs/evaluation/eval_results_expert_token_test_3doctors_patient_discussion_1212.jsonl


# ============================================================================
# Example 3: Statistical Summarization Only
# ============================================================================
# If expert evaluation results already exist, uses them directly
# Otherwise, runs expert evaluation first
# Computes bootstrap confidence intervals for all metrics

# python -u evaluate/eval_unified.py \
#     --diagnosis_filepath outputs/dialog_history_iiyi/dialog_history_gpt4.jsonl \
#     --reference_diagnosis_filepath data/patients.json \
#     --evaluation_mode statistical \
#     --openai_api_key "$OPENAI_API_KEY" \
#     --openai_api_base "$OPENAI_API_BASE" \
#     --model_name "gpt-5-nano" \
#     --output_filepath outputs/evaluation/eval_results.jsonl


# ============================================================================
# Example 4: All Three Evaluations (Complete Pipeline)
# ============================================================================
# Runs objective, expert, and statistical evaluations sequentially
# Produces three output files:
#   - eval_results_objective.jsonl (disease matching results)
#   - eval_results_expert.jsonl (expert AI scores)
#   - eval_results.jsonl (bootstrap statistics)

# python -u evaluate/eval_unified.py \
#     --diagnosis_filepath outputs/dialog_history_iiyi/dialog_history_gpt4.jsonl \
#     --reference_diagnosis_filepath data/patients.json \
#     --evaluation_mode all \
#     --openai_api_key "$OPENAI_API_KEY" \
#     --openai_api_base "$OPENAI_API_BASE" \
#     --model_name "gpt-5-nano" \
#     --database "./国际疾病分类ICD-10北京临床版v601.xls" \
#     --output_filepath outputs/evaluation/eval_results.jsonl \
#     --top_n 10 \
#     --threshold 50


# ============================================================================
# Example 5: Evaluate Multiple Doctor Outputs
# ============================================================================
# Loop through multiple doctor results and evaluate each

# for doctor in gpt3 gpt4 wenxin qwen; do
#     python -u evaluate/eval_unified.py \
#         --diagnosis_filepath outputs/dialog_history_iiyi/dialog_history_${doctor}.jsonl \
#         --reference_diagnosis_filepath data/patients.json \
#         --evaluation_mode all \
#         --openai_api_key "$OPENAI_API_KEY" \
#         --openai_api_base "$OPENAI_API_BASE" \
#         --model_name "gpt-5-nano" \
#         --output_filepath outputs/evaluation/eval_results_${doctor}.jsonl
# done


# ============================================================================
# Example 6: Using Custom OpenAI API (not AiHubMix)
# ============================================================================

# python -u evaluate/eval_unified.py \
#     --diagnosis_filepath outputs/dialog_history_iiyi/dialog_history_gpt4.jsonl \
#     --reference_diagnosis_filepath data/patients.json \
#     --evaluation_mode expert \
#     --openai_api_key "sk-..." \
#     --model_name "gpt-4-turbo" \
#     --output_filepath outputs/evaluation/eval_results_openai.jsonl
