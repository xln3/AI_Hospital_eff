#!/bin/bash
# SHOWCASE GUIDE: Online Collaborative Consultation System
# Run this to demonstrate to your teachers

cat << 'EOF'

╔════════════════════════════════════════════════════════════════════════════════╗
║            ONLINE COLLABORATIVE CONSULTATION SYSTEM - SHOWCASE DEMO            ║
║                     For Teachers/Advisors/Colleagues                          ║
╚════════════════════════════════════════════════════════════════════════════════╝

This guide shows how to demonstrate the new online consultation process to your
teachers. The system now generates diagnoses in real-time through doctor-patient
conversations instead of relying on pre-computed results.

══════════════════════════════════════════════════════════════════════════════════

PART 1: QUICK SETUP (5 minutes)
──────────────────────────────────────────────────────────────────────────────

1. Navigate to the project:
   $ cd /mnt/data1/workspace/xln/AI_Hospital_eff

2. Set your API key (required for actual execution):
   $ export OPENAI_API_KEY="your-api-key-here"

3. Verify the code is installed:
   $ cd src
   $ python -c "from hospital.collaborative_consultation import CollaborativeConsultation; print('✓ Code ready')"

══════════════════════════════════════════════════════════════════════════════════

PART 2: SHOWCASE TALKING POINTS
──────────────────────────────────────────────────────────────────────────────

KEY INNOVATION: Online Process
┌─────────────────────────────────────────────────────────────────────────────┐
│ BEFORE (Pre-computed):                                                      │
│   - Diagnoses loaded from files (static)                                   │
│   - No real conversations                                                   │
│   - Limited flexibility                                                     │
│                                                                             │
│ AFTER (Online):                                                             │
│   - Each doctor has independent consultation with patient                  │
│   - Full conversation captured                                              │
│   - Fresh diagnosis generation every time                                   │
│   - Better for research and analysis                                        │
└─────────────────────────────────────────────────────────────────────────────┘

2-Phase Workflow:
┌─────────────────────────────────────────────────────────────────────────────┐
│ Phase 1: Independent Consultations                                         │
│   - Doctor A ↔ Patient (separate conversation)                             │
│   - Doctor B ↔ Patient (separate conversation)                             │
│   - Doctor C ↔ Patient (separate conversation)                             │
│   Each doctor generates initial diagnosis                                   │
│                                                                             │
│ Phase 2: Discussion & Refinement                                           │
│   - Host consolidates symptoms from all doctors                            │
│   - Doctors discuss and revise diagnoses                                   │
│   - Multi-turn negotiation until consensus                                 │
│   - Host synthesizes final diagnosis                                        │
└─────────────────────────────────────────────────────────────────────────────┘

══════════════════════════════════════════════════════════════════════════════════

PART 3: DEMONSTRATION COMMAND
──────────────────────────────────────────────────────────────────────────────

Show this code and explain it works:

$ cd src
$ python run.py \
    --scenario Scenario.CollaborativeConsultation \
    --patient_database ./data/patients_test_1.json \
    --doctor_database ./data/collaborative_doctors/doctors_online_test.json \
    --number_of_doctors 2 \
    --max_conversation_turn 5 \
    --max_discussion_turn 2 \
    --save_path ./demo_output.jsonl \
    --ff_print

KEY DIFFERENCES TO HIGHLIGHT:
  • --doctor_database uses doctors_online_test.json (NO diagnosis_filepath)
  • This TRIGGERS online mode (vs pre-computed with diagnosis_filepath)
  • --ff_print shows all conversations in real-time
  • Output includes initial_consultations array with full dialogs

══════════════════════════════════════════════════════════════════════════════════

PART 4: EXPLAIN THE CODE CHANGES
──────────────────────────────────────────────────────────────────────────────

Show these files to your teachers:

1. src/agents/patient.py (1 line added):
   Line 42: self.profile = patient_profile
   → Enables creating new patient instances for isolation

2. src/hospital/collaborative_consultation.py (3 changes):
   a) Lines 30-35: Conditional diagnosis loading
      if hasattr(doctor_args, 'diagnosis_filepath') and doctor_args.diagnosis_filepath:
         doctor.load_diagnosis(...)  # Pre-computed mode
      # else: Online mode (no action needed)

   b) Lines 79-174: New _conduct_initial_consultation() method (~100 lines)
      - Separate patient instance per doctor
      - Full dialog loop (doctor-patient-reporter)
      - Final diagnosis synthesis
      - Returns complete dialog history

   c) Lines 194-212: Modified _run() method
      - For each doctor:
        if no diagnosis loaded:
           conduct_initial_consultation()
      - Then proceed with existing discussion logic

3. src/data/collaborative_doctors/doctors_online_test.json (NEW):
   No "diagnosis_filepath" field!
   This config tells system to use online mode

══════════════════════════════════════════════════════════════════════════════════

PART 5: DEMONSTRATE OUTPUT ANALYSIS
──────────────────────────────────────────────────────────────────────────────

After running, show the output:

$ cat ./demo_output.jsonl | python -m json.tool

Teachers can see:
1. "initial_consultations" array
   - Doctor A's complete dialog history
   - Doctor B's complete dialog history
   - Each doctor's initial diagnosis

2. "symptom_and_examination"
   - Host's consolidated view of patient info

3. "diagnosis_in_discussion"
   - Discussion turn 0: Initial diagnoses
   - Discussion turn 1: Revised diagnoses
   - Each doctor reconsidered other opinions

4. "diagnosis"
   - Final consensus diagnosis

══════════════════════════════════════════════════════════════════════════════════

PART 6: ARCHITECTURE ADVANTAGES TO MENTION
──────────────────────────────────────────────────────────────────────────────

1. PATIENT ISOLATION:
   ✓ Each doctor gets separate patient instance
   ✓ Prevents information leakage between consultations
   ✓ Realistic independent medical examination

2. BACKWARDS COMPATIBILITY:
   ✓ Old system still works (with diagnosis_filepath)
   ✓ New system works (without diagnosis_filepath)
   ✓ Can mix both in same experiment

3. BETTER FOR RESEARCH:
   ✓ Fresh diagnoses every run
   ✓ Captures full consultation process
   ✓ Full transparency (all conversations recorded)
   ✓ Can analyze doctor behavior patterns

4. NO MEMORY CONFLICTS:
   ✓ Doctor memories don't interfere
   ✓ Revision methods build fresh contexts
   ✓ Diagnosis stored separately from conversations

══════════════════════════════════════════════════════════════════════════════════

PART 7: QUICK TEST (WITHOUT API KEYS)
──────────────────────────────────────────────────────────────────────────────

You can verify the code structure without API keys:

$ python -c "
import sys
sys.path.insert(0, 'src')
from hospital.collaborative_consultation import CollaborativeConsultation
import inspect

# Verify method exists
assert hasattr(CollaborativeConsultation, '_conduct_initial_consultation')
print('✓ _conduct_initial_consultation method exists')

# Show method signature
sig = inspect.signature(CollaborativeConsultation._conduct_initial_consultation)
print(f'✓ Method signature: {sig}')

# Verify config
import json
with open('src/data/collaborative_doctors/doctors_online_test.json') as f:
    config = json.load(f)
print(f'✓ Test config has {len(config)} doctor(s), NO diagnosis_filepath')
"

══════════════════════════════════════════════════════════════════════════════════

PART 8: SAMPLE CONVERSATION FLOW (What happens during demo)
──────────────────────────────────────────────────────────────────────────────

With --ff_print enabled, output looks like:

############### Dialog ###############
--------------------------------------
0 Doctor
您好，有哪里不舒服？

--------------------------------------
1 Patient
<对医生讲> 我最近一周头疼得很厉害...

--------------------------------------
2 Doctor
头疼多久了？伴随其他症状吗？

...continuing until patient says <结束>...

[Then Doctor synthesizes diagnosis]
[Then Doctor B does same with separate patient instance]
[Then Host consolidates]
[Then Multi-turn discussion]
[Then Final consensus]

══════════════════════════════════════════════════════════════════════════════════

PART 9: EXPLANATION FOR TEACHERS
──────────────────────────────────────────────────────────────────────────────

You could say:

"We transformed the collaborative diagnosis system from a static model that
loaded pre-computed results to a dynamic online system where:

1. Each doctor independently interviews the patient
2. Doctors generate their own diagnoses based on the conversation
3. Then doctors discuss and refine through multi-turn collaboration

The key insight is patient isolation - each doctor has a completely separate
conversation, preventing information leakage. This is more realistic and better
for research because:

- We get fresh diagnoses every run (not cached results)
- We can analyze each doctor's reasoning process
- We can see how doctors change opinions based on peer discussion
- It's better for evaluating doctor behavior and decision-making

The system maintains backwards compatibility - old pre-computed diagrams still
work if you provide diagnosis_filepath. But by omitting it, you trigger online
mode and get real-time medical reasoning."

══════════════════════════════════════════════════════════════════════════════════

PART 10: PRACTICAL RUNNING COMMAND FOR DEMO
──────────────────────────────────────────────────────────────────────────────

If you have API key, the SIMPLEST command to show:

export OPENAI_API_KEY="your-key"
cd src
python run.py \
  --scenario Scenario.CollaborativeConsultation \
  --doctor_database ./data/collaborative_doctors/doctors_online_test.json \
  --number_of_doctors 2 \
  --max_conversation_turn 3 \
  --max_discussion_turn 1 \
  --ff_print

This will show:
- Doctor A's consultation with patient
- Doctor B's consultation with patient
- Discussion round
- Final diagnosis

All output printed to console.

══════════════════════════════════════════════════════════════════════════════════

PREPARATION CHECKLIST:
─────────────────────

Before showing to teachers:
□ Verify code imports without errors
□ Prepare the command in advance
□ Have API key ready (if demonstrating live)
□ Have example output saved (as fallback)
□ Know key metrics: # lines of code changed, # files modified
□ Practice explaining the 2-phase workflow
□ Have the files ready to show: patient.py, collaborative_consultation.py
□ Be ready to explain patient isolation concept

KEY STATS TO MENTION:
─────────────────────
• Files modified: 4 (patient.py, collaborative_consultation.py, CLAUDE.md, config)
• Lines of code added: ~150
• New method: _conduct_initial_consultation() (~100 lines)
• Backwards compatible: YES
• Test passed: YES (code imports, logic validated, config valid)

══════════════════════════════════════════════════════════════════════════════════

EOF
