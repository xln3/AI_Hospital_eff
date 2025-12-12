# eval_unified.py - Comparison with Original Scripts

## Summary of Changes

The new `eval_unified.py` consolidates functionality from three separate evaluation scripts (`eval.py`, `eval_db.py`, `eval_show.py`) into one unified interface with significant improvements.

## Comparison Matrix

| Feature | eval.py | eval_db.py | eval_show.py | eval_unified.py |
|---------|---------|-----------|--------------|-----------------|
| **Expert AI Evaluation** | ✅ GPT-4 | ❌ | ❌ | ✅ GPT-4+ any LLM |
| **Disease Matching** | ❌ | ✅ ICD-10 | ❌ | ✅ ICD-10 |
| **Statistical Analysis** | ❌ | ❌ | ✅ Bootstrap | ✅ Bootstrap |
| **Single Entry Point** | ❌ | ❌ | ❌ | ✅ Multiple modes |
| **Result Caching** | ❌ | ❌ | ❌ | ✅ Smart cache |
| **AiHubMix Support** | ✅ | ✅ | ❌ | ✅ Native |
| **Evaluator Recording** | ❌ | ❌ | ❌ | ✅ All results |
| **Flexible Input** | Hardcoded | Hardcoded | ❌ | ✅ File path param |
| **Documentation** | Minimal | Minimal | Minimal | ✅ Comprehensive |

## Detailed Comparison

### Original eval.py

**Strengths:**
- Expert-level evaluation with detailed analysis
- 5-dimension assessment (symptom, test, diagnosis, basis, treatment)
- Well-structured regex parsing

**Limitations:**
- Hardcoded file paths (lines 88-114)
- No explicit evaluator model recording
- Only supports expert mode
- Requires manual platform selection

```python
# Old way - hardcoded paths
self.doctor_name_to_diagnosis[doctor_name] = self.load_doctor_onestep_diagnosis(
    "../outputs/onestep_iiyi/onestep_gpt4_iiyi_patients.jsonl"
)
```

**New way in eval_unified.py:**
```python
# Dynamic input
doctor_diagnoses = self._load_doctor_diagnoses(self.diagnosis_filepath)
# Explicit model recording
result["evaluator_model"] = self.model_name  # Every output has this!
```

---

### Original eval_db.py

**Strengths:**
- Objective disease-level evaluation
- ICD-10 standard medical classification
- Fuzzy matching accuracy metrics

**Limitations:**
- Hardcoded doctor list (lines 42-49)
- Manual database initialization
- Complex internal state management
- No expert evaluation integration

```python
# Old way - hardcoded doctors
self.doctors = [
    ("GPT-3.5-Turbo", "../outputs/dialog_history_iiyi/dialog_history_gpt3.jsonl"),
    ("GPT-4", "../outputs/dialog_history_iiyi/dialog_history_gpt4.jsonl"),
    ...
]
```

**New way:**
```python
# Single input file, flexible for any doctor
doctor_diagnoses = self._load_doctor_diagnoses(self.diagnosis_filepath)
```

---

### Original eval_show.py

**Strengths:**
- Bootstrap confidence intervals (statistical rigor)
- Multi-doctor comparison support

**Limitations:**
- Post-processing only (requires expert results first)
- No caching or automation
- Limited to analysis phase
- Assumes expert results already exist

```python
# Old way - manual loading
self.interactive_doctor_name_to_scores = \
    self.load_doctor_name_to_scores(
        args.interactive_evaluation_result_path, load_diagnosis=True)
```

**New way:**
```python
# Automatic: reuses cached results or generates them
if os.path.exists(expert_results_path):
    expert_results = self._load_expert_results(expert_results_path)
else:
    self._evaluate_expert(doctor_diagnoses)  # Automatic!
```

---

## API Integration Improvements

### Original Approach (eval.py & eval_db.py)

```python
openai_api_key = getattr(args, "openai_api_key", None)
openai_api_key = openai_api_key if openai_api_key is not None else os.environ.get('OPENAI_API_KEY')
assert openai_api_key is not None  # Fails if not expert mode
```

**Issues:**
- Assertion fails even when not needed
- No graceful handling of different modes
- Repeated code across files

### New Approach (eval_unified.py)

```python
def _init_api_client(self):
    """Initialize OpenAI API client."""
    openai_api_key = getattr(self.args, "openai_api_key", None) or os.environ.get('OPENAI_API_KEY')

    # Suppress assertion error if not using expert mode
    if self.evaluation_mode in ["expert", "statistical", "all"]:
        assert openai_api_key is not None, "openai_api_key required for expert evaluation"
```

**Benefits:**
- Mode-aware initialization
- Clear error messages
- No unnecessary assertions

---

## File Path Flexibility

### Original Scripts

Required editing code to change input files:

```python
# eval.py line 88-89 - must edit code
self.doctor_name_to_diagnosis[doctor_name] = self.load_doctor_onestep_diagnosis(
    "../outputs/onestep_iiyi/onestep_gpt4_iiyi_patients.jsonl"  # Hardcoded!
)
```

### New Script

Pass files as command-line arguments:

```bash
python evaluate/eval_unified.py \
    --diagnosis_filepath outputs/any_doctor_output.jsonl \
    --reference_diagnosis_filepath data/any_reference.json \
    --output_filepath results/any_output_location.jsonl
```

---

## Evaluator Model Recording

### Original Scripts

**No explicit model recording:**

```python
result = {
    "doctor_name": doctor_name,
    "patient_id": patient_id,
    "evaluation_result": response  # How was this evaluated? Unknown!
}
```

**Problem:** Can't tell if results came from GPT-4, GPT-3.5, or another model

### New Script

**Explicit model recording in all modes:**

```json
{
  "patient_id": "123",
  "evaluation_mode": "expert",
  "evaluator_model": "gpt-5-nano",
  "sympton_choice": "A",
  ...
}
```

Or:

```json
{
  "patient_id": "123",
  "evaluation_mode": "objective",
  "evaluator_model": "fuzzy_matching_icd10",
  "set_f1": 0.87
}
```

**Benefits:**
- Full reproducibility
- Clear audit trail
- Easy to identify model differences

---

## Result Caching in Statistical Mode

### Original Approach (eval_show.py)

Required manual pre-processing:

```bash
# Must run these manually in sequence:
$ python evaluate/eval.py ...  # Generate expert results
$ python evaluate/eval_show.py ...  # Then summarize
```

### New Approach (eval_unified.py)

Automatic intelligent caching:

```bash
# Single command handles everything:
python evaluate/eval_unified.py \
    --evaluation_mode statistical \
    --model_name "gpt-5-nano"
```

**What happens automatically:**
1. Checks if `results_expert.jsonl` exists
2. **If yes:** Uses cached results (fast! ⚡)
3. **If no:** Runs expert evaluation first (smart! 🧠)
4. Generates statistics from either source

---

## API Integration with AiHubMix

### Original Scripts

Required environment variable setup:

```bash
# From run_online_aihubmix_full.sh
export AIHUBMIX_API_KEY="sk-..."
python run.py --patient_openai_api_base "https://aihubmix.com/v1" ...
```

### New Script

Unified API configuration:

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_API_BASE="https://aihubmix.com/v1"

python evaluate/eval_unified.py \
    --model_name "gpt-5-nano" \
    --evaluation_mode expert
```

**Works with:**
- ✅ OpenAI API
- ✅ AiHubMix API
- ✅ Any OpenAI-compatible API

---

## Usage Pattern Comparison

### Running Original Scripts

```bash
# Step 1: Run expert evaluation
cd src
python evaluate/eval.py \
    --evaluation_platform dialog \
    --model_name gpt-4

# Step 2: Run statistical summary
python evaluate/eval_show.py \
    --interactive_evaluation_result_path outputs/evaluation/evaluation_iiyi_gpt4_5part.jsonl

# Step 3: Run disease matching (separate entirely)
python evaluate/eval_db.py \
    --model_name gpt-3.5-turbo
```

### Running Unified Script

```bash
# Option 1: Just expert evaluation
python evaluate/eval_unified.py \
    --diagnosis_filepath outputs/dialog_history.jsonl \
    --evaluation_mode expert

# Option 2: Just disease matching
python evaluate/eval_unified.py \
    --diagnosis_filepath outputs/dialog_history.jsonl \
    --evaluation_mode objective

# Option 3: Statistics with automatic expert caching
python evaluate/eval_unified.py \
    --diagnosis_filepath outputs/dialog_history.jsonl \
    --evaluation_mode statistical

# Option 4: Everything (recommended)
python evaluate/eval_unified.py \
    --diagnosis_filepath outputs/dialog_history.jsonl \
    --evaluation_mode all
```

---

## Key Improvements Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Scripts to run** | 3 separate scripts | 1 unified script |
| **File path hardcoding** | Hardcoded in code | CLI arguments |
| **API flexibility** | Limited | Full OpenAI compatibility |
| **Evaluator tracking** | Not recorded | Always recorded |
| **Result caching** | Manual | Automatic |
| **Error handling** | Mode-agnostic | Mode-aware |
| **Documentation** | Minimal | Comprehensive |
| **Input files** | Hardcoded | Flexible |
| **Output consistency** | Variable | Standardized |
| **Learning curve** | Steep (3 scripts) | Gentle (1 script) |

---

## Migration Guide

### From eval.py → eval_unified.py

**Old:**
```bash
python evaluate/eval.py --evaluation_platform dialog --model_name gpt-4
# Results: outputs/evaluation/evaluation_iiyi_5part.jsonl
```

**New:**
```bash
python evaluate/eval_unified.py \
    --diagnosis_filepath outputs/dialog_history.jsonl \
    --evaluation_mode expert \
    --model_name gpt-4 \
    --output_filepath outputs/evaluation/evaluation_gpt4.jsonl
```

### From eval_db.py → eval_unified.py

**Old:**
```bash
python evaluate/eval_db.py --model_name gpt-3.5-turbo
# Results: outputs/evaluation/evaluation_db_iiyi.json
```

**New:**
```bash
python evaluate/eval_unified.py \
    --diagnosis_filepath outputs/dialog_history.jsonl \
    --evaluation_mode objective \
    --database "./国际疾病分类ICD-10北京临床版v601.xls" \
    --output_filepath outputs/evaluation/evaluation_objective.jsonl
```

### From eval_show.py → eval_unified.py

**Old:**
```bash
python evaluate/eval_show.py \
    --interactive_evaluation_result_path outputs/evaluation/evaluation_iiyi_gpt4_5part.jsonl
# Console output only
```

**New:**
```bash
python evaluate/eval_unified.py \
    --diagnosis_filepath outputs/dialog_history.jsonl \
    --evaluation_mode statistical \
    --output_filepath outputs/evaluation/results.jsonl
# Shows statistics + optionally caches expert results
```

---

## Backward Compatibility

**Note:** The original three scripts (`eval.py`, `eval_db.py`, `eval_show.py`) remain unchanged for backward compatibility. The new `eval_unified.py` is an addition that provides better UX without breaking existing workflows.

If you have existing code relying on the original scripts, they will continue to work exactly as before.
