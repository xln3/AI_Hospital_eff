# CRITICAL BUG: Empty Doctor Responses in Online Multi-Doctor Consultation

**Date Discovered**: 2025-11-27
**Severity**: CRITICAL - Blocks all functionality
**Status**: UNRESOLVED

---

## Bug Description

All doctor responses are completely empty (blank strings) during online consultation when using the updated code with named doctors. The `doctor.speak()` method returns empty content, causing the consultation to fail.

## Reproduction Steps

1. Navigate to `src/` directory
2. Run: `bash scripts/run_online_aihubmix_full.sh`
3. Observe output - all doctor responses are blank lines
4. Patient starts self-diagnosing because doctor isn't responding

## Expected Behavior

Doctor should respond to patient's symptoms with questions or examination requests:

```
1 Patient
<对医生讲> 昨天上午开始，左边手和脚都没劲...
--------------------------------------
1 Doctor Dr_Zhang <gpt-5-nano>
请问这种无力感是突然出现的吗？有没有伴随头痛或其他症状？
```

## Actual Behavior

Doctor responses are completely empty:

```
1 Patient
<对医生讲> 昨天上午开始，左边手和脚都没劲...
--------------------------------------
1 Doctor Dr_Zhang <gpt-5-nano>
[BLANK LINE - NO CONTENT]
--------------------------------------
2 Patient
<对医生讲> 昨天上午左边手脚就没劲...
--------------------------------------
2 Doctor Dr_Zhang <gpt-5-nano>
[BLANK LINE - NO CONTENT]
```

This continues for all turns, with patient eventually self-requesting examinations.

## Environment

- **Model**: gpt-5-nano via AiHubMix (aihubmix.com)
- **Script**: `src/scripts/run_online_aihubmix_full.sh`
- **Config**: `src/data/collaborative_doctors/doctors_aihubmix_named.json`
- **Python**: Unbuffered output (`python -u`)

## Working vs Broken Comparison

### ✅ WORKING Configuration

**Script**: `src/scripts/run_online_aihubmix.sh`
**Config**: `src/data/collaborative_doctors/doctors_aihubmix.json`

```json
[
    {
        "doctor_name": "Agent.Doctor.AiHubMix",
        "doctor_aihubmix_model_name": "gpt-5-nano"
    },
    {
        "doctor_name": "Agent.Doctor.AiHubMix",
        "doctor_aihubmix_model_name": "gpt-5-nano"
    }
]
```

**Output**: Shows proper doctor responses

```
1 Doctor
请问这次左边手脚的无力是突然在起床时出现的吗？大概持续了多久？
```

**Key difference**: Uses OLD collaborative_consultation.py code without name/model printing

### ❌ BROKEN Configuration

**Script**: `src/scripts/run_online_aihubmix_full.sh`
**Config**: `src/data/collaborative_doctors/doctors_aihubmix_named.json`

```json
[
    {
        "doctor_name": "Agent.Doctor.AiHubMix",
        "doctor_aihubmix_model_name": "gpt-5-nano",
        "doctor_nickname": "Dr_Zhang"
    },
    {
        "doctor_name": "Agent.Doctor.AiHubMix",
        "doctor_aihubmix_model_name": "gpt-5-nano",
        "doctor_nickname": "Dr_Li"
    }
]
```

**Output**: Empty doctor responses

```
1 Doctor Dr_Zhang <gpt-5-nano>
[BLANK]
```

**Key difference**: Uses NEW collaborative_consultation.py with enhanced printing

## Investigation Results

### Verified as NOT the Issue

1. **AiHubMix Engine** (`src/engine/aihubmix.py`)
   - Implementation looks correct
   - Returns `response.choices[0].message.content`
   - Has proper error handling with 5 retries
   - Exception handling would print error messages (none observed)

2. **AiHubMixDoctor Class** (`src/agents/doctor.py:602-641`)
   - Properly registered as `Agent.Doctor.AiHubMix`
   - Exported in `src/agents/__init__.py`
   - Inherits from `Doctor` base class
   - `speak()` method implementation looks correct

3. **API Configuration**
   - API key: Correctly set via environment variable
   - Base URL: `https://aihubmix.com/v1` is correct
   - Model name: `gpt-5-nano` is valid

4. **Config File Differences**
   - Only difference: `doctor_nickname` field
   - This should ONLY affect display names, not API calls

### Suspected Root Causes

#### Theory 1: Code Changes Breaking Initialization
The doctor name handling changes in `collaborative_consultation.py` might be breaking doctor initialization:

```python
# Lines 20-44 in collaborative_consultation.py
doctor_name = getattr(doctor_args, 'doctor_nickname', None) or default_names[i]

doctor = registry.get_class(doctor_args.doctor_name)(
    doctor_args,
    name=doctor_name
)
doctor.id = f"Doctor_{doctor_name}_{doctor_args.doctor_name}"
```

Possible issues:
- `doctor_args` not being constructed properly
- `name` parameter breaking something in AiHubMixDoctor.__init__()
- `doctor.id` assignment causing side effects

#### Theory 2: API Key Not Being Passed
If `doctor_args.doctor_aihubmix_api_key` is None and environment variable not set in the right context:

```python
# In AiHubMixEngine.__init__()
aihubmix_api_key = aihubmix_api_key if aihubmix_api_key is not None else os.environ.get('AIHUBMIX_API_KEY')
```

But this should raise an assertion error, not return empty strings.

#### Theory 3: Arguments Not Being Parsed
The `add_parser_args()` mechanism might not be registering arguments for AiHubMix doctors properly when using custom names.

#### Theory 4: Response Content Actually Null
API might be returning successful response but with empty content. But then we'd see this in the working version too.

#### Theory 5: Print Statement Issue
Maybe responses are NOT actually empty, but print statement has a bug that makes them appear empty. But then `dialog_history` would still contain content.

## Debug Steps Needed

### Step 1: Add Initialization Logging
```python
# In src/agents/doctor.py AiHubMixDoctor.__init__()
def __init__(self, args=None, doctor_info=None, name="A"):
    print(f"[DEBUG] AiHubMixDoctor init: name={name}")
    print(f"[DEBUG] args.doctor_aihubmix_api_key = {args.doctor_aihubmix_api_key if hasattr(args, 'doctor_aihubmix_api_key') else 'MISSING'}")
    print(f"[DEBUG] args.doctor_aihubmix_model_name = {args.doctor_aihubmix_model_name if hasattr(args, 'doctor_aihubmix_model_name') else 'MISSING'}")

    engine = registry.get_class("Engine.AiHubMix")(...)
    print(f"[DEBUG] Engine initialized: {engine.model_name}")

    super(AiHubMixDoctor, self).__init__(engine, doctor_info, name=name)
    print(f"[DEBUG] AiHubMixDoctor init complete")
```

### Step 2: Add Speak Method Logging
```python
# In src/agents/doctor.py AiHubMixDoctor.speak()
def speak(self, content, patient_id, save_to_memory=True):
    print(f"[DEBUG] Doctor {self.name} speak() called")
    print(f"[DEBUG] Patient ID: {patient_id}")
    print(f"[DEBUG] Input content length: {len(content)}")

    memories = self.memories[patient_id]
    messages = [{...}]

    print(f"[DEBUG] Messages to send: {len(messages)} messages")
    response = self.get_response(messages)
    print(f"[DEBUG] Response received, length: {len(response) if response else 0}")
    print(f"[DEBUG] Response content: {response[:100] if response else 'EMPTY'}")

    return response
```

### Step 3: Add Engine Response Logging
```python
# In src/engine/aihubmix.py get_response()
def get_response(self, messages):
    print(f"[DEBUG] AiHubMixEngine.get_response() called")
    print(f"[DEBUG] Model: {self.model_name}")
    print(f"[DEBUG] Messages count: {len(messages)}")

    response = self.client.chat.completions.create(...)

    print(f"[DEBUG] API Response received")
    print(f"[DEBUG] Response choices: {len(response.choices)}")
    print(f"[DEBUG] Message content: {response.choices[0].message.content[:100] if response.choices[0].message.content else 'EMPTY'}")

    return response.choices[0].message.content
```

### Step 4: Compare Working vs Broken Args
Create minimal test script:

```python
# test_doctor_init.py
import sys
sys.path.append('/mnt/data1/workspace/xln/AI_Hospital_eff/src')

from utils.options import parse_args
import json

# Load both configs
with open('data/collaborative_doctors/doctors_aihubmix.json') as f:
    working_config = json.load(f)

with open('data/collaborative_doctors/doctors_aihubmix_named.json') as f:
    broken_config = json.load(f)

print("Working config:", working_config)
print("Broken config:", broken_config)

# Test doctor creation with both configs
# Compare resulting args objects
```

### Step 5: Test Without Nickname
Create config file without nickname but with all other new code:

```json
[
    {
        "doctor_name": "Agent.Doctor.AiHubMix",
        "doctor_aihubmix_model_name": "gpt-5-nano"
    }
]
```

Run with NEW collaborative_consultation.py code to isolate if nickname is the issue.

## Workaround

Use the old script that works:
```bash
cd src
bash scripts/run_online_aihubmix.sh
```

But this loses all the improvements:
- No doctor names in output
- No model names in output
- No enhanced reporter visibility
- No host-patient interaction logging

## Impact

**Severity: CRITICAL**
- Blocks all multi-doctor online consultation functionality
- Prevents testing of reporter role
- Prevents validation of efficiency improvements
- Makes output debugging impossible with named doctors

## Files Involved

- `src/hospital/collaborative_consultation.py` - Lines 20-44 (initialization)
- `src/hospital/collaborative_consultation.py` - Lines 87-202 (_conduct_initial_consultation)
- `src/agents/doctor.py` - Lines 602-641 (AiHubMixDoctor class)
- `src/agents/doctor.py` - Lines 630-641 (speak method)
- `src/engine/aihubmix.py` - Lines 28-60 (get_response method)
- `src/data/collaborative_doctors/doctors_aihubmix_named.json` - Config file

## Related Issues

- Reporter role verification blocked by this bug
- Cannot validate doctor efficiency improvements
- Cannot demonstrate enhanced output visibility features
