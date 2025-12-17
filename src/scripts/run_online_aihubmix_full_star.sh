#!/bin/bash

# AiHubMix API Key
export AIHUBMIX_API_KEY="sk-mczTH3kUyOTvvDBY7c971967488341C6B9F3Aa36Dc5eCf9c"

# Run online multi-doctor collaborative consultation in STAR Mode with AiHubMix gpt-5-nano
# STAR Mode: Doctors do not see each other's diagnoses during discussion
# Each doctor only receives host's critique and revises based on that
# Using 1 patient - FULL RUN (no output truncation)
cd "$(dirname "$0")/.."

python -u run.py \
    --scenario Scenario.CollaborativeConsultationStar \
    --patient_database ./data/patients.json \
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
    --max_conversation_turn 7 \
    --max_discussion_turn 5 \
    --save_path outputs/token_test_3doctors_patient_1212_star.jsonl \
    --discussion_mode Parallel_with_Critique \
    --ff_print
