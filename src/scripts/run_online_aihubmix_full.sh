#!/bin/bash

# AiHubMix API Key
export AIHUBMIX_API_KEY="sk-EaniAUFQLJ9uQM6M224cEfF89e2241419eD9Ff13Ed8eD8Af"

# Run online multi-doctor collaborative consultation with AiHubMix gpt-5-nano
# Using 1 patient - FULL RUN (no output truncation)
cd "$(dirname "$0")/.."

python -u run.py \
    --scenario Scenario.CollaborativeConsultation \
    --patient_database ./data/patients_discussion.json \
    --doctor_database ./data/collaborative_doctors/doctors_3_aihubmix.json \
    --patient Agent.Patient.GPT \
    --patient_openai_api_key "$AIHUBMIX_API_KEY" \
    --patient_openai_api_base "https://aihubmix.com/v1" \
    --patient_openai_model_name gpt-5-nano \
    --reporter Agent.Reporter.GPT \
    --reporter_openai_api_key "$AIHUBMIX_API_KEY" \
    --reporter_openai_api_base "https://aihubmix.com/v1" \
    --reporter_openai_model_name gpt-5-nano \
    --host Agent.Host.GPT \
    --host_openai_api_key "$AIHUBMIX_API_KEY" \
    --host_openai_api_base "https://aihubmix.com/v1" \
    --host_openai_model_name gpt-5-nano \
    --number_of_doctors 3 \
    --max_conversation_turn 8 \
    --max_discussion_turn 8 \
    --save_path outputs/test_3doctors_patient_discussion_1205.jsonl \
    --discussion_mode Parallel \
    --ff_print
