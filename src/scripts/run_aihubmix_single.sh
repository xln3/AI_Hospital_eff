#!/bin/bash

# AiHubMix API Key
export AIHUBMIX_API_KEY="sk-EaniAUFQLJ9uQM6M224cEfF89e2241419eD9Ff13Ed8eD8Af"

# OpenAI keys for Patient and Reporter agents (using AiHubMix as proxy)
export OPENAI_API_KEY="sk-EaniAUFQLJ9uQM6M224cEfF89e2241419eD9Ff13Ed8eD8Af"
export OPENAI_API_BASE="https://aihubmix.com/v1"

/mnt/data/anaconda3/envs/AI_Hospital/bin/python run.py \
    --patient_database ./data/patients_small_10.json \
    --doctor Agent.Doctor.AiHubMix --doctor_aihubmix_model_name gpt-5-nano \
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-5-nano \
    --reporter Agent.Reporter.GPT --reporter_openai_model_name gpt-5-nano \
    --save_path outputs/dialog_history_iiyi/dialog_history_aihubmix_small_10.jsonl \
    --max_conversation_turn 10 \
    --patient_openai_api_key "sk-EaniAUFQLJ9uQM6M224cEfF89e2241419eD9Ff13Ed8eD8Af" \
    --patient_openai_api_base "https://aihubmix.com/v1" \
    --reporter_openai_api_key "sk-EaniAUFQLJ9uQM6M224cEfF89e2241419eD9Ff13Ed8eD8Af" \
    --reporter_openai_api_base "https://aihubmix.com/v1" \
    --doctor_aihubmix_api_key "sk-EaniAUFQLJ9uQM6M224cEfF89e2241419eD9Ff13Ed8eD8Af"
