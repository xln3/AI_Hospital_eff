#!/bin/bash

# AiHubMix API Key
export AIHUBMIX_API_KEY="sk-EaniAUFQLJ9uQM6M224cEfF89e2241419eD9Ff13Ed8eD8Af"

# Run online multi-doctor collaborative consultation with AiHubMix gpt-5-nano
# Using 1 patient for testing
cd "$(dirname "$0")/.."

python run.py \
    --scenario Scenario.CollaborativeConsultation \
    --patient_database ./data/patients_test_1.json \
    --doctor_database ./data/collaborative_doctors/doctors_aihubmix.json \
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
    --number_of_doctors 2 \
    --max_conversation_turn 10 \
    --max_discussion_turn 4 \
    --save_path outputs/test_online_aihubmix_gpt5nano.jsonl \
    --discussion_mode Parallel \
    --ff_print
