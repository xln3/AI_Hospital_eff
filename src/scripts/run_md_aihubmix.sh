#!/bin/bash

# AiHubMix API Key
export AIHUBMIX_API_KEY="sk-EaniAUFQLJ9uQM6M224cEfF89e2241419eD9Ff13Ed8eD8Af"

# OpenAI keys for Patient and Host agents (using AiHubMix as proxy for these)
export OPENAI_API_KEY="sk-EaniAUFQLJ9uQM6M224cEfF89e2241419eD9Ff13Ed8eD8Af"
export OPENAI_API_BASE="https://aihubmix.com/v1"

python run.py \
    --scenario Scenario.CollaborativeConsultation \
    --patient_database ./data/patients_small_10.json \
    --doctor_database ./data/collaborative_doctors/doctors_aihubmix.json \
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-5-nano \
    --reporter Agent.Reporter.GPT --reporter_openai_model_name gpt-5-nano \
    --host Agent.Host.GPT --host_openai_model_name gpt-5-nano \
    --number_of_doctors 2 --max_discussion_turn 4 \
    --save_path outputs/collaboration_history_iiyi/doctors_2_aihubmix_gpt5_nano_parallel_discussion_history.jsonl \
    --discussion_mode Parallel --ff_print 
