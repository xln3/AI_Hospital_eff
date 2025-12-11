#!/usr/bin/env python3
"""
Demonstration of online consultation process with 3 doctors and 1 host
Shows the flow without requiring actual API calls.
"""

import sys
sys.path.insert(0, '/mnt/data1/workspace/xln/AI_Hospital_eff/src')

from utils.register import registry
import json

# Create a mock args object for demonstration
class MockArgs:
    def __init__(self):
        self.patient = "Agent.Patient.GPT"
        self.patient_openai_api_key = "dummy"
        self.patient_openai_api_base = "https://api.openai.com/v1"
        self.patient_openai_model_name = "gpt-3.5-turbo"
        self.patient_temperature = 0.0
        self.patient_max_tokens = 2048
        self.patient_top_p = 1
        self.patient_frequency_penalty = 0
        self.patient_presence_penalty = 0

        self.doctor = "Agent.Doctor.GPT"
        self.doctor_openai_api_key = "dummy"
        self.doctor_openai_api_base = "https://api.openai.com/v1"
        self.doctor_openai_model_name = "gpt-4"
        self.doctor_temperature = 0.0
        self.doctor_max_tokens = 2048
        self.doctor_top_p = 1
        self.doctor_frequency_penalty = 0
        self.doctor_presence_penalty = 0

        self.reporter = "Agent.Reporter.GPT"
        self.reporter_openai_api_key = "dummy"
        self.reporter_openai_api_base = "https://api.openai.com/v1"
        self.reporter_openai_model_name = "gpt-3.5-turbo"
        self.reporter_temperature = 0.0
        self.reporter_max_tokens = 2048
        self.reporter_top_p = 1
        self.reporter_frequency_penalty = 0
        self.reporter_presence_penalty = 0

        self.host = "Agent.Host.GPT"
        self.host_openai_api_key = "dummy"
        self.host_openai_api_base = "https://api.openai.com/v1"
        self.host_openai_model_name = "gpt-4"
        self.host_temperature = 0.0
        self.host_max_tokens = 2048
        self.host_top_p = 1
        self.host_frequency_penalty = 0
        self.host_presence_penalty = 0

        self.max_conversation_turn = 3
        self.max_discussion_turn = 2
        self.number_of_doctors = 3
        self.discussion_mode = "Parallel"
        self.ff_print = False
        self.parallel = False
        self.scenario = "Scenario.CollaborativeConsultation"
        self.patient_database = "data/patients_test_1.json"
        self.doctor_database = "data/collaborative_doctors/doctors_online_test.json"
        self.save_path = "outputs/test_online_consultation.jsonl"

# Demonstrate the workflow
print("=" * 100)
print("ONLINE CONSULTATION PROCESS DEMONSTRATION")
print("=" * 100)
print()

print("CONFIGURATION:")
print("- Patient Database: data/patients_test_1.json")
print("- Doctor Config: doctors_online_test.json (WITHOUT diagnosis_filepath)")
print("- Number of Doctors: 3")
print("- Host: Central coordinator")
print()

print("WORKFLOW:")
print()

print("PHASE 1: INDEPENDENT CONSULTATIONS")
print("-" * 100)
print()

# Demonstrate the consultation flow
consultation_script = """
Doctor A consults with Patient (isolation #1):
  [Turn 0] Doctor A: "您好，有哪里不舒服？"
  [Turn 1] Patient: "<对医生讲> 我最近一周头疼得很厉害..."
  [Turn 2] Doctor A: "头疼多久了？伴随其他症状吗？"
  [Turn 3] Patient: "<对医生讲> 持续一周，还有点发热..."
  ...
  [Final] Doctor A synthesizes diagnosis from consultation

Doctor B consults with Patient (isolation #2):
  [Turn 0] Doctor B: "您好，有哪里不舒服？"
  [Turn 1] Patient: "<对医生讲> 我最近一周头疼得很厉害..." (FRESH START - independent dialog)
  [Turn 2] Doctor B: "头疼的特点是什么？持续还是间断？"
  [Turn 3] Patient: "<对医生讲> 持续性头疼，还伴随发热..."
  ...
  [Final] Doctor B synthesizes diagnosis from consultation

Doctor C consults with Patient (isolation #3):
  [Turn 0] Doctor C: "您好，有哪里不舒服？"
  [Turn 1] Patient: "<对医生讲> 我最近一周头疼得很厉害..." (FRESH START - independent dialog)
  [Turn 2] Doctor C: "除了头疼还有其他症状吗？"
  [Turn 3] Patient: "<对医生讲> 头疼、发热、还有点颈僵..."
  ...
  [Final] Doctor C synthesizes diagnosis from consultation
"""

print(consultation_script)
print()

print("PHASE 2: DISCUSSION AND REVISION")
print("-" * 100)
print()

discussion_script = """
Host gathers initial diagnoses:
  - Doctor A diagnosis: 脑膜炎 (诊断依据: 头疼、发热、颈僵)
  - Doctor B diagnosis: 感冒并发头疼 (诊断依据: 头疼、发热)
  - Doctor C diagnosis: 脑膜炎 (诊断依据: 头疼、发热、颈僵、意识改变)

Host: "我看到医生A和C倾向于脑膜炎的诊断，医生B认为是感冒。
       让我们基于以下汇总的信息进行讨论:"

Symptom Summary (from Host):
  症状: 头疼（一周）、发热、颈部僵硬
  辅助检查: 脑脊液检查异常

[Discussion Turn 1]
  Doctor A revision: "考虑到颈僵和脑脊液异常，我认为脑膜炎的诊断更合理"
  Doctor B revision: "我同意，颈僵是关键症状，脑脊液异常支持脑膜炎"
  Doctor C revision: "确认脑膜炎诊断。治疗方案应该是抗生素治疗..."

  Host assessment: "三位医生已达成共识，建议停止讨论"

[Final Diagnosis Synthesis]
  Host: "基于三位医生的意见和患者信息，最终诊断为：
        脑膜炎（细菌性）
        诊断依据：头疼、发热、颈部僵硬、脑脊液异常
        治疗方案：第三代头孢菌素 + 其他支持性治疗"
"""

print(discussion_script)
print()

print("OUTPUT STRUCTURE:")
print("-" * 100)
print()

output_structure = """
Output JSONL (outputs/test_online_consultation.jsonl):
{
  "patient_id": "patient_001",

  "initial_consultations": [
    {
      "doctor_id": 0,
      "doctor_name": "A",
      "doctor_class": "GPTDoctor",
      "doctor_engine_name": "gpt-4",
      "dialog_history": [
        {"turn": 0, "role": "Doctor", "content": "您好，有哪里不舒服？"},
        {"turn": 1, "role": "Patient", "content": "<对医生讲> 我最近一周头疼..."},
        ... (full doctor A + patient dialog)
      ],
      "initial_diagnosis": {
        "症状": "头疼、发热、颈部僵硬",
        "辅助检查": "脑脊液异常",
        "诊断结果": "脑膜炎",
        "诊断依据": "...",
        "治疗方案": "..."
      }
    },
    {
      "doctor_id": 1,
      "doctor_name": "B",
      ... (same for doctor B)
    },
    {
      "doctor_id": 2,
      "doctor_name": "C",
      ... (same for doctor C)
    }
  ],

  "symptom_and_examination": "（由Host汇总）症状：头疼、发热、颈部僵硬...",

  "diagnosis_in_discussion": [
    {
      "turn": 0,
      "diagnosis_in_turn": [
        {"doctor_id": 0, "diagnosis": {...}},
        {"doctor_id": 1, "diagnosis": {...}},
        {"doctor_id": 2, "diagnosis": {...}}
      ],
      "host_critique": "..."
    },
    {
      "turn": 1,
      "diagnosis_in_turn": [
        {"doctor_id": 0, "diagnosis": {...revised...}},
        {"doctor_id": 1, "diagnosis": {...revised...}},
        {"doctor_id": 2, "diagnosis": {...revised...}}
      ],
      "host_critique": "#结束#"
    }
  ],

  "diagnosis": "最终诊断：脑膜炎（细菌性）...",
  "doctor_engine_names": ["gpt-4", "gpt-3.5-turbo-16k", "gpt-4"],
  "time": "2024-11-27 10:30:45"
}
"""

print(output_structure)
print()

print("=" * 100)
print("KEY DIFFERENCES FROM PRE-COMPUTED MODE:")
print("=" * 100)
print("""
1. Each doctor has INDEPENDENT patient consultation
   - Separate dialog history for each doctor
   - No information leakage between doctors' consultations

2. Diagnosis generation is ONLINE
   - Real-time medical reasoning
   - Based on actual doctor-patient conversations
   - Not relying on pre-stored files

3. Better for research
   - Fresh diagnoses every run
   - Suitable for evaluating doctor behavior
   - Can test different doctor models

4. Output includes full dialog histories
   - Complete transparency of consultation process
   - Can analyze reasoning patterns
   - Useful for debugging and analysis

5. Discussion phase remains the same
   - Multi-turn refinement based on consensus
   - Host coordination of doctors
""")

print("=" * 100)
print("RUNNING ONLINE CONSULTATION:")
print("=" * 100)
print()
print("""
Command to run:
$ cd src
$ python run.py \\
    --scenario Scenario.CollaborativeConsultation \\
    --patient_database ./data/patients_test_1.json \\
    --doctor_database ./data/collaborative_doctors/doctors_online_test.json \\
    --patient Agent.Patient.GPT --patient_openai_model_name gpt-3.5-turbo \\
    --reporter Agent.Reporter.GPT --reporter_openai_model_name gpt-3.5-turbo \\
    --host Agent.Host.GPT --host_openai_model_name gpt-4 \\
    --number_of_doctors 3 \\
    --max_conversation_turn 10 \\
    --max_discussion_turn 4 \\
    --save_path outputs/online_consultation_results.jsonl \\
    --ff_print  # Set this to see detailed dialog output

Key points:
- NO diagnosis_filepath in doctor config
- Each doctor will consult independently
- Full dialogs will be captured and printed with --ff_print
- Results saved to JSONL with complete conversation history
""")

print("=" * 100)
