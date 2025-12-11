# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Hospital is a research project for evaluating Large Language Models (LLMs) as intern doctors for clinical diagnosis. The system simulates medical consultations with three main components:
- **Doctors**: LLM-based agents that diagnose patients (GPT, Qwen, WenXin, ChatGLM, HuatuoGPT, etc.)
- **Patients**: Agents simulating patients with predefined medical conditions and symptoms
- **Reporters**: Agents that synthesize and evaluate diagnostic results

The project includes two main scenarios: single consultation (doctor-patient interaction) and collaborative consultation (multiple doctors discussing cases).

## Development Setup

### Installation
```bash
pip install -r requirements.txt
```

Dependencies: dashscope, openai, bootstrapped, transformers

### Running Scenarios

All commands are run from the `src/` directory.

**Single Consultation (MVME Benchmark)**:
```bash
cd ./src
bash scripts/run.sh
```

This runs single doctor-patient consultations. Before running:
1. Open `scripts/run.sh`
2. Set API keys for required services:
   - `OPENAI_API_KEY` and `OPENAI_API_BASE` for GPT models
   - `DASHSCOPE_API_KEY` for Qwen/Baichuan models
   - `WENXIN_API_KEY` and `WENXIN_SECRET_KEY` for WenXin models
   - `HUATUOGPT_MODEL` for local HuatuoGPT

**Collaborative Consultation (Pre-Computed Diagnosis)**:
```bash
cd ./src
bash scripts/run_md.sh
```

This runs multi-doctor scenarios with dispute resolution, using pre-computed diagnoses from existing dialog histories.

**Collaborative Consultation (Online Mode)**:
```bash
cd ./src
python run.py --scenario Scenario.CollaborativeConsultation \
    --patient_database ./data/patients.json \
    --doctor_database ./data/collaborative_doctors/doctors_online_test.json \
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-3.5-turbo \
    --reporter Agent.Reporter.GPT --reporter_openai_model_name gpt-3.5-turbo \
    --host Agent.Host.GPT --host_openai_model_name gpt-4 \
    --save_path outputs/dialog_history_online.jsonl \
    --max_conversation_turn 10 \
    --number_of_doctors 2
```

Online mode generates diagnoses through real-time doctor-patient conversations instead of using pre-computed diagnoses. Key differences:
- Omit `diagnosis_filepath` from doctor config JSON to enable online consultation
- Each doctor conducts independent consultation with patient (separate dialog turns)
- Initial diagnoses generated from dialog before discussion phase begins
- Output includes full dialog histories for each doctor's consultation
- Example config: `data/collaborative_doctors/doctors_online_test.json` (no diagnosis_filepath fields)

**Evaluation**:
```bash
cd ./src
bash scripts/eval.sh
```

Generates quantitative performance metrics from dialog histories.

### Direct Script Execution
```bash
cd ./src
python run.py --patient_database ./data/patients.json \
    --doctor Agent.Doctor.GPT --doctor_openai_model_name gpt-4 \
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-3.5-turbo \
    --reporter Agent.Reporter.GPT --reporter_openai_model_name gpt-3.5-turbo \
    --save_path outputs/dialog_history_iiyi/output.jsonl \
    --max_conversation_turn 10
```

Key options:
- `--parallel`: Enable parallel execution across patients
- `--max_workers N`: Number of parallel workers
- `--scenario Scenario.CollaborativeConsultation`: Run collaborative mode

## Architecture

### Module Structure

**agents/** - LLM agent implementations:
- `base_agent.py`: Base class for all agents
- `doctor.py`: Doctor agents with model-specific implementations (GPTDoctor, QwenDoctor, WenXinDoctor, etc.)
- `patient.py`: Patient agents simulating medical conditions
- `reporter.py`: Agents that evaluate and synthesize diagnoses
- `host.py`: Facilitator for collaborative consultations

**engine/** - Language model API backends:
- `gpt.py`: OpenAI API wrapper
- `qwen.py`: Alibaba Qwen API wrapper
- `wenxin.py`: Baidu WenXin API wrapper
- `huatuogpt.py`: HuatuoGPT local model wrapper
- `chatglm.py`, `minimax.py`: Other model backends
- `base_engine.py`: Base interface

**hospital/** - Scenario orchestration:
- `consultation.py`: Single consultation scenario (doctor-patient-reporter)
- `collaborative_consultation.py`: Multi-doctor collaborative scenario

**utils/** - Core utilities:
- `register.py`: Registry pattern for dynamic class instantiation (classes decorated with `@register_class(alias="...")`
- `options.py`: Argument parser that dynamically builds options based on selected agents
- `options.py` uses the registry to dynamically add arguments for chosen doctor/patient/reporter/host classes

**data/** - Medical datasets:
- `patients.json`: Patient database with symptoms, medical records, and reference diagnoses
- `collaborative_doctors/`: Configuration for multi-doctor scenarios

### Class Registration Pattern

The codebase uses a decorator-based registry for dynamic component selection:

```python
@register_class(alias="Agent.Doctor.GPT")
class GPTDoctor(Doctor):
    pass
```

This allows CLI selection: `--doctor Agent.Doctor.GPT`

The options parser dynamically discovers and registers arguments from selected classes by calling their `add_parser_args()` class method.

### Adding Custom Agents

1. Create a class inheriting from `Doctor`, `Patient`, or `Reporter`
2. Implement required methods from the base class
3. Add `@register_class(alias="...")` decorator with a unique alias
4. Add to `__all__` export in `agents/__init__.py`
5. Implement `add_parser_args()` class method to register CLI arguments for your agent

For example, a custom doctor:

```python
@register_class(alias="Agent.Doctor.Custom")
class CustomDoctor(Doctor):
    @classmethod
    def add_parser_args(cls, parser):
        parser.add_argument("--custom_param", type=str, default="value")
```

Then use: `python run.py --doctor Agent.Doctor.Custom --custom_param ...`

## Key Data Formats

**Patient Database** (`data/patients.json`):
```json
{
  "id": "...",
  "profile": {...medical symptoms...},
  "medical_record": {...test results, history...},
  "standard_diagnosis": {...reference diagnosis...}
}
```

**Dialog History Output** (`.jsonl` format):
Each line is a JSON object containing:
- Full conversation transcript (doctor-patient exchanges)
- Final diagnosis from doctor
- Evaluation metrics

**Collaborative Doctor Config** (`data/collaborative_doctors/doctors.json`):

Pre-computed mode (with diagnosis_filepath):
```json
[
  {
    "doctor_name": "Agent.Doctor.GPT",
    "doctor_openai_model_name": "gpt-4",
    "diagnosis_filepath": "./outputs/dialog_history_gpt4.jsonl"
  },
  {
    "doctor_name": "Agent.Doctor.GPT",
    "doctor_openai_model_name": "gpt-3.5-turbo",
    "diagnosis_filepath": "./outputs/dialog_history_gpt35.jsonl"
  }
]
```

Online mode (without diagnosis_filepath):
```json
[
  {"doctor_name": "Agent.Doctor.GPT", "doctor_openai_model_name": "gpt-4"},
  {"doctor_name": "Agent.Doctor.GPT", "doctor_openai_model_name": "gpt-3.5-turbo"}
]
```

In online mode, omitting `diagnosis_filepath` tells the system to generate diagnoses through real-time doctor-patient consultations.

## Common Development Tasks

### Add Support for a New LLM
1. Create new engine wrapper in `engine/` (implement `get_response(messages)`)
2. Create new doctor class in `agents/doctor.py` inheriting from `Doctor`
3. Implement `add_parser_args()` and `get_response()` override if needed
4. Register with `@register_class(alias="Agent.Doctor.YourModel")`

### Debug a Consultation Flow
Dialog histories are saved as `.jsonl` files. Each line is a complete patient case with full conversation transcript. Use these for analysis.

### Run Evaluation
The evaluation pipeline compares doctor diagnoses against reference diagnoses and generates metrics. Modify `evaluate/eval.py` to change evaluation criteria.

### Parallel Execution
Use `--parallel --max_workers N` flags. Note: Some models have rate limits or don't support parallel API calls.

### Collaborative Consultation (Online Mode)

The collaborative consultation workflow consists of two phases:

**Phase 1: Independent Consultations**
- Each doctor independently consults with patient (separate patient instance per doctor)
- Full dialog history captured for each doctor-patient interaction
- Initial diagnosis generated for each doctor from their consultation

**Phase 2: Discussion and Revision**
- Host summarizes symptoms/examinations from all doctors
- Each doctor revises diagnosis based on consolidated information
- Multi-turn discussion loop where doctors consider each other's opinions
- Host measures agreement and guides discussion toward consensus
- Final diagnosis synthesized from all doctor inputs

**Output Structure:**
Each line in the output JSONL contains:
```json
{
  "patient_id": "...",
  "initial_consultations": [
    {
      "doctor_id": 0,
      "doctor_name": "A",
      "doctor_engine_name": "gpt-4",
      "dialog_history": [...full doctor-patient dialog...],
      "initial_diagnosis": {...structured diagnosis...}
    }
  ],
  "symptom_and_examination": {...consolidated by host...},
  "diagnosis_in_discussion": [...revision rounds...],
  "diagnosis": {...final consensus diagnosis...}
}
```

Use online mode when you want fresh, real-time diagnoses. Use pre-computed mode for reproducible results or when running multiple experiments on the same dataset.

## Important Notes

- **API Keys**: Never commit API keys. They're expected in environment variables (`OPENAI_API_KEY`, `DASHSCOPE_API_KEY`, etc.)
- **Patient Data**: Medical records are sourced from iiyi.com as per README
- **Conversation Format**: All doctor-patient interactions use a message-based format (list of dicts with "role" and "content" keys), compatible with OpenAI API
- **Diagnosis Format**: Doctors must extract and structure diagnoses into: symptoms, auxiliary tests, diagnosis result, reasoning, and treatment plan
- **Chinese Language**: Much of the prompt engineering and patient data is in Chinese; maintain consistency when modifying system messages or prompts
