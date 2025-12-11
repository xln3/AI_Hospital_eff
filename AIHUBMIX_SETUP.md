# AiHubMix Integration Setup and Test Results

## Overview
Successfully integrated AiHubMix API (cheapest model: `gpt-5-nano`) into the AI Hospital system for both single consultations and collaborative discussions using a minimal 10-patient dataset.

## What Was Done

### 1. Created Minimal Dataset
- **File**: `src/data/patients_small_10.json`
- **Size**: 10 patients (reduced from 506)
- **Purpose**: Minimize token usage for testing

### 2. AiHubMix Engine Integration
- **File**: `src/engine/aihubmix.py`
- **Configuration**:
  - API Endpoint: `https://aihubmix.com/v1`
  - Model: `gpt-5-nano` (cheapest/free tier)
  - Uses `max_completion_tokens` parameter (AiHubMix compatibility)
- **Features**:
  - Retry logic (5 attempts) for rate limiting
  - Error handling for API failures
  - Compatible with OpenAI client library

### 3. AiHubMix Doctor Agent
- **File**: `src/agents/doctor.py` (added `AiHubMixDoctor` class)
- **Registration**: `Agent.Doctor.AiHubMix`
- **Command-line Args**:
  - `--doctor_aihubmix_api_key`: Your API key
  - `--doctor_aihubmix_model_name`: Model selection (default: `gpt-5-nano`)

### 4. GPT Engine Fix
- **File**: `src/engine/gpt.py`
- **Fix**: Added fallback to `max_completion_tokens` when `max_tokens` fails
- **Reason**: AiHubMix API uses different parameter naming for some models

### 5. Test Scripts Created
- **Single Consultation**: `src/scripts/run_aihubmix_single.sh`
- **Collaborative Config**: `src/data/collaborative_doctors/doctors_aihubmix.json`
- **Updated Scripts**: `src/scripts/run_md_aihubmix.sh`

## Test Results

### ✅ Single Consultation Test (1 patient, 2 turns)
- **Status**: SUCCESS
- **Time**: ~32 seconds
- **Output**: `outputs/test_aihubmix_1patient.jsonl`

### ✅ Single Consultation Test (10 patients, 3 turns each)
- **Status**: SUCCESS
- **Time**: ~8 minutes total (~50 seconds per patient)
- **Output**: `outputs/dialog_history_iiyi/dialog_history_aihubmix_10patients.jsonl`
- **Size**: 16 KB (very token efficient!)

### ✅ Collaborative Consultation Test (2 doctors, 3 discussion turns)
- **Status**: SUCCESS
- **Patients Processed**: 6 cases (2 doctors × 3 discussion turns = 10 total interactions)
- **Time**: ~8.75 minutes
- **Output**: `outputs/collaboration_history_iiyi/doctors_2_aihubmix_gpt5_nano_parallel_discussion.jsonl`
- **Size**: 16 KB
- **Features**: 
  - Parallel discussion mode
  - Both doctors providing independent diagnoses
  - Collaborative discussion on disagreements

## How to Run

### Single Consultation (Recommended for testing)
```bash
cd src
bash scripts/run_aihubmix_single.sh
```

### Collaborative Consultation
```bash
cd src
bash scripts/run_md_aihubmix.sh
```

### Manual Command
```bash
cd src
/mnt/data/anaconda3/envs/AI_Hospital/bin/python run.py \
    --patient_database ./data/patients_small_10.json \
    --doctor Agent.Doctor.AiHubMix --doctor_aihubmix_model_name gpt-5-nano \
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-5-nano \
    --reporter Agent.Reporter.GPT --reporter_openai_model_name gpt-5-nano \
    --save_path outputs/dialog_history_iiyi/test_output.jsonl \
    --max_conversation_turn 3 \
    --patient_openai_api_key "YOUR_AIHUBMIX_KEY" \
    --patient_openai_api_base "https://aihubmix.com/v1" \
    --reporter_openai_api_key "YOUR_AIHUBMIX_KEY" \
    --reporter_openai_api_base "https://aihubmix.com/v1" \
    --doctor_aihubmix_api_key "YOUR_AIHUBMIX_KEY"
```

## Key Technical Notes

### API Compatibility Issue Solved
- AiHubMix uses `max_completion_tokens` instead of OpenAI's `max_tokens`
- GPT engine now handles both parameters gracefully
- This allows using the same API key for all agents (patient, doctor, reporter, host)

### Cost Efficiency
- Model: `gpt-5-nano` is the cheapest available
- 10-patient dataset keeps token usage minimal
- Output files are only ~16 KB even with full conversation history

### Token Usage Estimate
- Single consultation per patient: ~500-1000 tokens
- 10 patients × 3 turns: ~15,000-30,000 tokens
- At typical rates: Very low cost

## Files Modified/Created

### Created
- `src/engine/aihubmix.py` - AiHubMix engine wrapper
- `src/scripts/run_aihubmix_single.sh` - Single consultation runner
- `src/data/patients_small_10.json` - Minimal test dataset
- `src/data/patients_test_1.json` - Single patient test dataset
- `src/data/collaborative_doctors/doctors_aihubmix.json` - Collaborative config

### Modified
- `src/engine/__init__.py` - Added AiHubMixEngine import
- `src/engine/gpt.py` - Fixed max_tokens compatibility
- `src/agents/__init__.py` - Added AiHubMixDoctor export
- `src/agents/doctor.py` - Added AiHubMixDoctor class

## Troubleshooting

### API Key Issues
- Ensure API key is valid and has credits
- Check that base_url is correct: `https://aihubmix.com/v1`

### Timeout Issues
- Increase `max_conversation_turn` gradually
- Start with 1-2 turns for testing
- Collaborative mode is slower (multiple models discussing)

### Model Not Found
- Verify model name: `gpt-5-nano`
- Use AiHubMix dashboard to check available models
- Fallback to known models if needed

## Sources
- [AiHubMix Documentation](https://doc.aihubmix.com/en/)
- [AiHubMix Models](https://aihubmix.com/models)
