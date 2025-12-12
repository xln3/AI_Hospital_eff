"""
Unified Evaluation Script
Supports three evaluation modes:
1. Objective disease matching (eval_db)
2. Expert AI evaluation (eval_gpt)
3. Statistical summarization (with caching of expert evaluation results)

Dependencies: pip install openai jsonlines numpy bootstrapped fuzzywuzzy python-Levenshtein prettytable tqdm xlrd
Or run: bash scripts/install_eval_unified_deps.sh
"""

import argparse
import json
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Try importing optional dependencies and provide helpful error messages
try:
    import jsonlines
except ImportError:
    print("[ERROR] jsonlines not installed.")
    print("Run: bash scripts/install_eval_unified_deps.sh")
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("[ERROR] numpy not installed. Run: pip install numpy")
    sys.exit(1)

try:
    import bootstrapped.bootstrap as bs
    import bootstrapped.stats_functions as bs_stats
except ImportError:
    print("[ERROR] bootstrapped not installed. Run: pip install bootstrapped")
    bs = None
    bs_stats = None

try:
    from tqdm import tqdm
except ImportError:
    print("[ERROR] tqdm not installed. Run: pip install tqdm")
    sys.exit(1)

try:
    from fuzzywuzzy import process
except ImportError:
    print("[ERROR] fuzzywuzzy not installed. Run: pip install fuzzywuzzy python-Levenshtein")
    sys.exit(1)

try:
    from prettytable import PrettyTable
except ImportError:
    print("[ERROR] prettytable not installed. Run: pip install prettytable")
    sys.exit(1)

try:
    from openai import OpenAI
    import openai
except ImportError:
    print("[ERROR] openai not installed. Run: pip install openai")
    sys.exit(1)


class UnifiedEvaluator:
    """Unified evaluator supporting objective disease matching, expert AI evaluation, and statistical summarization."""

    def __init__(self, args):
        """
        Initialize the evaluator.

        Args:
            args: Command-line arguments containing:
                - diagnosis_filepath: Input file path with raw diagnoses
                - evaluation_mode: 'objective', 'expert', or 'statistical'
                - openai_api_key: API key for expert evaluation
                - openai_api_base: API base URL for expert evaluation
                - model_name: LLM model name for expert evaluation
                - output_filepath: Where to save evaluation results
                - reference_diagnosis_filepath: Path to ground truth diagnoses
                - database: ICD-10 database file for objective matching
        """
        self.args = args
        self.diagnosis_filepath = args.diagnosis_filepath
        self.evaluation_mode = args.evaluation_mode
        self.output_filepath = args.output_filepath
        self.reference_diagnosis_filepath = args.reference_diagnosis_filepath

        # Load reference diagnoses
        self.reference_diagnosis = self._load_reference_diagnosis(
            self.reference_diagnosis_filepath
        )
        self.patient_ids = list(self.reference_diagnosis.keys())

        # Initialize API client for expert evaluation
        self._init_api_client()

        # Initialize database for objective evaluation
        if self.evaluation_mode in ["objective", "all"]:
            self._init_disease_database()

    def _init_api_client(self):
        """Initialize OpenAI API client."""
        openai_api_key = getattr(self.args, "openai_api_key", None)
        openai_api_key = openai_api_key if openai_api_key is not None else os.environ.get('OPENAI_API_KEY')

        # Suppress assertion error if not using expert mode
        if self.evaluation_mode in ["expert", "statistical", "all"]:
            assert openai_api_key is not None, "openai_api_key is required for expert evaluation"

        openai_api_base = getattr(self.args, "openai_api_base", None)
        openai_api_base = openai_api_base if openai_api_base is not None else os.environ.get('OPENAI_API_BASE')

        self.api_key = openai_api_key
        self.api_base = openai_api_base
        self.model_name = getattr(self.args, "model_name", "gpt-5-nano")
        self.temperature = getattr(self.args, "temperature", 0.0)
        self.max_tokens = getattr(self.args, "max_tokens", 4096)

        if openai_api_key:
            if openai_api_base:
                self.client = OpenAI(
                    api_key=openai_api_key,
                    base_url=openai_api_base
                )
            else:
                self.client = OpenAI(api_key=openai_api_key)

    def _init_disease_database(self):
        """Initialize ICD-10 disease database for objective matching."""
        if not hasattr(self.args, 'database') or not self.args.database:
            print("[WARNING] No database file specified for objective evaluation")
            return

        try:
            import xlrd
            xls = xlrd.open_workbook(self.args.database)
            sheet = xls.sheet_by_index(0)
            disease_ids = sheet.col_values(colx=0, start_rowx=1)
            disease_names = sheet.col_values(colx=1, start_rowx=1)
            self.disease = {}
            for disease_id, disease_name in zip(disease_ids, disease_names):
                self.disease[disease_name] = disease_id
        except Exception as e:
            print(f"[ERROR] Failed to load disease database: {e}")
            self.disease = {}

    def _load_reference_diagnosis(self, reference_diagnosis_filepath: str) -> Dict:
        """Load reference diagnoses from JSON file."""
        with open(reference_diagnosis_filepath, 'r') as f:
            data = json.load(f)

        patient_id_to_reference_diagnosis = {}
        for item in data:
            medical_record = item["medical_record"]
            diagnosis = medical_record.get("诊断结果") or medical_record.get("初步诊断")
            basis = medical_record.get("诊断依据")
            treatment = medical_record.get("诊治经过")

            patient_id_to_reference_diagnosis[item["id"]] = {
                "patient_id": item["id"],
                "symptom": medical_record.get("现病史"),
                "medical_test": medical_record.get("辅助检查"),
                "diagnosis": diagnosis,
                "basis": basis,
                "treatment": treatment
            }
        return patient_id_to_reference_diagnosis

    def _load_doctor_diagnoses(self, diagnosis_filepath: str) -> Dict:
        """Load doctor diagnoses from JSONL file."""
        patient_id_to_diagnosis = {}

        with jsonlines.open(diagnosis_filepath, "r") as reader:
            for obj in reader:
                patient_id = obj.get("patient_id")

                # Handle different diagnosis formats
                if "diagnosis" in obj:
                    diagnosis = obj["diagnosis"]
                elif "dialog_history" in obj:
                    dialog = obj["dialog_history"]
                    diagnosis = dialog[-1]["content"] if dialog else ""
                else:
                    continue

                patient_id_to_diagnosis[patient_id] = {
                    "patient_id": patient_id,
                    "diagnosis": diagnosis,
                    "raw_data": obj
                }

        return patient_id_to_diagnosis

    def evaluate(self):
        """Main evaluation entry point."""
        print(f"\n[INFO] Starting evaluation in '{self.evaluation_mode}' mode")
        print(f"[INFO] Input diagnoses: {self.diagnosis_filepath}")
        print(f"[INFO] Output file: {self.output_filepath}")

        # Load doctor diagnoses
        doctor_diagnoses = self._load_doctor_diagnoses(self.diagnosis_filepath)
        print(f"[INFO] Loaded {len(doctor_diagnoses)} diagnoses")

        if self.evaluation_mode == "objective":
            self._evaluate_objective(doctor_diagnoses)
        elif self.evaluation_mode == "expert":
            self._evaluate_expert(doctor_diagnoses)
        elif self.evaluation_mode == "statistical":
            self._evaluate_statistical(doctor_diagnoses)
        elif self.evaluation_mode == "all":
            self._evaluate_objective(doctor_diagnoses)
            self._evaluate_expert(doctor_diagnoses)
            self._evaluate_statistical(doctor_diagnoses)
        else:
            raise ValueError(f"Unknown evaluation mode: {self.evaluation_mode}")

        # Display token usage summary if available
        self._print_token_usage_summary(doctor_diagnoses)

        print(f"\n[INFO] Evaluation completed. Results saved to: {self.output_filepath}")

    def _print_token_usage_summary(self, doctor_diagnoses: Dict):
        """Print total token usage summary from all diagnoses."""
        total_initial_input = 0
        total_initial_output = 0
        total_discussion_input = 0
        total_discussion_output = 0
        count_with_tokens = 0

        for patient_id, diagnosis_data in doctor_diagnoses.items():
            raw_data = diagnosis_data.get("raw_data", {})
            token_usage = raw_data.get("token_usage", {})

            if not token_usage:
                continue

            count_with_tokens += 1

            # Collect initial consultation tokens
            initial_phase = token_usage.get("initial_consultation_phase", {})
            initial_doctors = initial_phase.get("doctors", {})
            for doctor_name, tokens in initial_doctors.items():
                total_initial_input += tokens.get("total_input_tokens", 0)
                total_initial_output += tokens.get("total_output_tokens", 0)

            # Collect discussion phase tokens
            discussion_phase = token_usage.get("discussion_phase", {})
            total_discussion_input += discussion_phase.get("total_input_tokens", 0)
            total_discussion_output += discussion_phase.get("total_output_tokens", 0)

        # Print summary if we found token data
        if count_with_tokens > 0:
            initial_total = total_initial_input + total_initial_output
            discussion_total = total_discussion_input + total_discussion_output
            grand_total_input = total_initial_input + total_discussion_input
            grand_total_output = total_initial_output + total_discussion_output
            grand_total = grand_total_input + grand_total_output

            # Calculate means per patient
            mean_initial = initial_total / count_with_tokens
            mean_discussion = discussion_total / count_with_tokens
            mean_total = grand_total / count_with_tokens

            print("\n" + "="*80)
            print("COMPLETE CONSULTATION SUMMARY")
            print("="*80)
            print(f"  Initial Consultation: {initial_total:,} tokens (mean: {mean_initial:,.0f}/patient)")
            print(f"  Discussion Turns:     {discussion_total:,} tokens (mean: {mean_discussion:,.0f}/patient)")
            print(f"  Total Tokens Used:    {grand_total:,} tokens (mean: {mean_total:,.0f}/patient)")
            print(f"    - Input:  {grand_total_input:,}")
            print(f"    - Output: {grand_total_output:,}")
            print("="*80 + "\n")

    # ========== OBJECTIVE EVALUATION (Disease Matching) ==========

    def _evaluate_objective(self, doctor_diagnoses: Dict):
        """Evaluate using objective disease matching against ICD-10."""
        print("\n" + "="*80)
        print("OBJECTIVE DISEASE MATCHING EVALUATION")
        print("="*80)

        if not self.disease:
            print("[ERROR] Disease database not initialized. Skipping objective evaluation.")
            return

        output_data = []
        for patient_id, diagnosis_data in tqdm(doctor_diagnoses.items(), desc="Processing diagnoses"):
            if patient_id not in self.reference_diagnosis:
                continue

            reference_diagnosis = self.reference_diagnosis[patient_id]
            # Extract diagnosis text, handling both string and dict formats
            doctor_diagnosis_text = self._extract_diagnosis_text(diagnosis_data["diagnosis"])

            # Parse reference diagnosis
            reference_diagnosis_text = self._extract_diagnosis_text(reference_diagnosis["diagnosis"])
            reference_response = self._parse_diagnosis_to_diseases(reference_diagnosis_text)
            reference_matches = self._fuzzy_match_diseases(reference_response)

            # Parse doctor diagnosis
            doctor_response = self._parse_diagnosis_to_diseases(doctor_diagnosis_text)
            doctor_matches = self._fuzzy_match_diseases(doctor_response)

            result = {
                "patient_id": patient_id,
                "evaluation_mode": "objective",
                "evaluator_model": "fuzzy_matching_icd10",
                "reference_diagnosis": reference_diagnosis["diagnosis"],
                "doctor_diagnosis": doctor_diagnosis_text,
                "reference_response": reference_response,
                "reference_matches": reference_matches,
                "doctor_response": doctor_response,
                "doctor_matches": doctor_matches,
            }

            # Calculate metrics
            recall, precision, f1 = self._calculate_set_metrics(
                reference_matches, doctor_matches
            )
            result.update({
                "set_recall": recall,
                "set_precision": precision,
                "set_f1": f1,
            })

            output_data.append(result)

        self._save_results(output_data, mode="objective")
        self._print_objective_results(output_data)

    def _extract_diagnosis_text(self, diagnosis_data) -> str:
        """Extract diagnosis text from either string or dict format."""
        if isinstance(diagnosis_data, str):
            return diagnosis_data
        elif isinstance(diagnosis_data, dict):
            # For collaborative consultation with structured diagnosis
            # Try to get the diagnosis result field
            diagnosis_text = diagnosis_data.get('诊断结果', '')
            if not diagnosis_text:
                # Fallback to other possible fields
                diagnosis_text = diagnosis_data.get('diagnosis', '')
            if not diagnosis_text:
                # Last resort: join all values
                diagnosis_text = ' '.join(str(v) for v in diagnosis_data.values() if v)
            return diagnosis_text
        else:
            return str(diagnosis_data)

    def _parse_diagnosis_to_diseases(self, diagnosis_text: str) -> List[str]:
        """Parse diagnosis text to extract individual diseases."""
        # Split by common separators and clean up
        diseases = re.split(r'[；;，,、]', diagnosis_text)
        diseases = [d.strip() for d in diseases if d.strip()]
        return diseases

    def _fuzzy_match_diseases(self, diseases: List[str]) -> List[List[Tuple]]:
        """
        Fuzzy match disease names to ICD-10 database.

        Returns:
            List of lists, where each inner list contains (disease_name, disease_id, confidence)
        """
        if not self.disease:
            return []

        matches = []
        for disease in diseases:
            top_matches = process.extract(
                disease, self.disease.keys(),
                limit=self.args.top_n if hasattr(self.args, 'top_n') else 10
            )
            formatted_matches = [
                (match[0], self.disease[match[0]], match[1])
                for match in top_matches
            ]
            matches.append(formatted_matches)

        return matches

    def _calculate_set_metrics(self, reference_matches: List, doctor_matches: List) -> Tuple[float, float, float]:
        """Calculate set-level recall, precision, and F1."""
        threshold = self.args.threshold if hasattr(self.args, 'threshold') else 50

        def set_match(pred, refs, matched):
            """Find matching reference for predicted disease."""
            pred_set = [p[0] for p in pred]
            for idx, ref in enumerate(refs):
                if matched[idx] == 1:
                    continue
                ref_set = [r[0] for r in ref]
                for p in pred_set:
                    for r in ref_set:
                        if p == r:
                            return idx
            return None

        true_positive = 0.00001  # smooth
        false_positive = 0
        false_negative = 0

        refs = [[n for n in m if n[2] >= threshold] for m in reference_matches]
        preds = [[n for n in m if n[2] >= threshold] for m in doctor_matches]

        set_matched = [0] * len(refs)
        for pred in preds:
            match_idx = set_match(pred, refs, set_matched)
            if match_idx is None:
                false_positive += 1
            elif set_matched[match_idx] == 1:
                false_positive += 1
            else:
                set_matched[match_idx] = 1

        true_positive += sum(set_matched)
        false_negative += len(refs) - sum(set_matched)

        recall = true_positive / (true_positive + false_negative)
        precision = true_positive / (true_positive + false_positive)
        f1 = 2 * precision * recall / (recall + precision) if (recall + precision) > 0 else 0

        return recall, precision, f1

    def _print_objective_results(self, results: List[Dict]):
        """Print objective evaluation results in table format."""
        if not results:
            print("[WARNING] No results to display")
            return

        total_patients = len(results)
        total_recall = sum(r.get("set_recall", 0) for r in results) / total_patients if total_patients > 0 else 0
        total_precision = sum(r.get("set_precision", 0) for r in results) / total_patients if total_patients > 0 else 0
        total_f1 = sum(r.get("set_f1", 0) for r in results) / total_patients if total_patients > 0 else 0

        table = PrettyTable(['Metric', 'Value'])
        table.add_row(['Total Patients', total_patients])
        table.add_row(['Average Recall (%)', f"{total_recall*100:.2f}"])
        table.add_row(['Average Precision (%)', f"{total_precision*100:.2f}"])
        table.add_row(['Average F1 (%)', f"{total_f1*100:.2f}"])
        print(table)

    # ========== EXPERT AI EVALUATION ==========

    def _evaluate_expert(self, doctor_diagnoses: Dict):
        """Evaluate using expert AI."""
        print("\n" + "="*80)
        print("EXPERT AI EVALUATION")
        print("="*80)
        print(f"[INFO] Using model: {self.model_name}")
        print(f"[INFO] Total doctor diagnoses loaded: {len(doctor_diagnoses)}")
        print(f"[INFO] Total reference diagnoses loaded: {len(self.reference_diagnosis)}")

        output_data = []
        processed_count = 0
        skipped_count = 0

        for patient_id, diagnosis_data in tqdm(doctor_diagnoses.items(), desc="Expert evaluation"):
            if patient_id not in self.reference_diagnosis:
                # print(f"[DEBUG] Skipping patient {patient_id}: no reference diagnosis found")
                skipped_count += 1
                continue

            # print(f"\n[DEBUG] Processing patient {patient_id}...")
            reference_diagnosis = self.reference_diagnosis[patient_id]
            doctor_diagnosis = diagnosis_data["diagnosis"]

            # print(f"[DEBUG]   Reference diagnosis type: {type(reference_diagnosis.get('diagnosis'))}")
            # print(f"[DEBUG]   Doctor diagnosis type: {type(doctor_diagnosis)}")

            result = self._evaluate_one_expert(
                patient_id, reference_diagnosis, doctor_diagnosis
            )
            output_data.append(result)
            processed_count += 1

            # Print section scores for this patient
            section_scores = {
                "Symptom": result.get("sympton_choice"),
                "Tests": result.get("test_choice"),
                "Diagnosis": result.get("diagnosis_choice"),
                "Basis": result.get("basis_choice"),
                "Treatment": result.get("treatment_choice"),
            }
            scores_str = " | ".join([f"{k}: {v or 'N/A'}" for k, v in section_scores.items()])
            print(f"[SCORE] Patient {patient_id}: {scores_str}")

        self._save_results(output_data, mode="expert")
        self._print_expert_results(output_data)
        print(f"\n[INFO] Processed {processed_count} diagnoses with expert evaluation")
        print(f"[INFO] Skipped {skipped_count} diagnoses (no reference)")
        print(f"[INFO] Success rate: {processed_count}/{processed_count + skipped_count}")

    def _evaluate_one_expert(self, patient_id: str, reference_diagnosis: Dict, doctor_diagnosis) -> Dict:
        """Evaluate a single diagnosis using expert AI with split section-by-section approach."""
        try:
            # print(f"\n[DEBUG] === Evaluating patient {patient_id} (split mode) ===")

            # Format doctor diagnosis (handle both string and dict formats)
            doctor_diagnosis_str = self._format_doctor_diagnosis(doctor_diagnosis)
            # print(f"[DEBUG] Doctor diagnosis formatted length: {len(doctor_diagnosis_str)}")

            # Show reference diagnosis info
            ref_symptom = reference_diagnosis.get('symptom', '')
            ref_medical_test = reference_diagnosis.get('medical_test', '')
            ref_diagnosis = reference_diagnosis.get('diagnosis', '')
            ref_basis = reference_diagnosis.get('basis', '')
            ref_treatment = reference_diagnosis.get('treatment', '')

            # print(f"[DEBUG] Reference diagnosis components:")
            # print(f"[DEBUG]   - symptom length: {len(str(ref_symptom))}")
            # print(f"[DEBUG]   - medical_test length: {len(str(ref_medical_test))}")
            # print(f"[DEBUG]   - diagnosis length: {len(str(ref_diagnosis))}")
            # print(f"[DEBUG]   - basis length: {len(str(ref_basis))}")
            # print(f"[DEBUG]   - treatment length: {len(str(ref_treatment))}")

            # Evaluate each section separately to avoid token limit issues
            parsed_result = {}

            # 1. Evaluate Symptoms
            # print(f"\n[DEBUG] Evaluating Symptom section...")
            symptom_result = self._evaluate_section_expert(
                patient_id,
                section_name="症状",
                section_title="病人症状掌握情况",
                reference_data=ref_symptom,
                doctor_data=doctor_diagnosis_str
            )
            parsed_result.update(symptom_result)

            # 2. Evaluate Medical Tests
            # print(f"\n[DEBUG] Evaluating Medical Tests section...")
            test_result = self._evaluate_section_expert(
                patient_id,
                section_name="医学检查项目",
                section_title="医学检查项目的完整性",
                reference_data=ref_medical_test,
                doctor_data=doctor_diagnosis_str
            )
            parsed_result.update(test_result)

            # 3. Evaluate Diagnosis
            # print(f"\n[DEBUG] Evaluating Diagnosis section...")
            diagnosis_result = self._evaluate_section_expert(
                patient_id,
                section_name="诊断结果",
                section_title="诊断结果的一致性",
                reference_data=ref_diagnosis,
                doctor_data=doctor_diagnosis_str
            )
            parsed_result.update(diagnosis_result)

            # 4. Evaluate Diagnostic Basis
            # print(f"\n[DEBUG] Evaluating Diagnostic Basis section...")
            basis_result = self._evaluate_section_expert(
                patient_id,
                section_name="诊断依据",
                section_title="诊断依据的一致性",
                reference_data=ref_basis,
                doctor_data=doctor_diagnosis_str
            )
            parsed_result.update(basis_result)

            # 5. Evaluate Treatment Plan
            # print(f"\n[DEBUG] Evaluating Treatment Plan section...")
            treatment_result = self._evaluate_section_expert(
                patient_id,
                section_name="治疗方案",
                section_title="治疗方案的一致性",
                reference_data=ref_treatment,
                doctor_data=doctor_diagnosis_str
            )
            parsed_result.update(treatment_result)

            result = {
                "patient_id": patient_id,
                "evaluation_mode": "expert",
                "evaluator_model": self.model_name,
                "reference_diagnosis": reference_diagnosis.get("diagnosis"),
                "doctor_diagnosis_text": doctor_diagnosis_str if isinstance(doctor_diagnosis_str, str) else str(doctor_diagnosis_str),
                "evaluation_result": "[SPLIT MODE] Section-by-section evaluation",
            }
            result.update(parsed_result)

            # print(f"\n[DEBUG] ✓ Successfully evaluated patient {patient_id}")
            return result
        except Exception as e:
            # Return a result with error information if evaluation fails
            print(f"[ERROR] Failed to evaluate patient {patient_id}: {type(e).__name__}: {str(e)}")
            print(f"[ERROR] Exception traceback: {e}")
            doctor_diagnosis_str = self._format_doctor_diagnosis(doctor_diagnosis)
            return {
                "patient_id": patient_id,
                "evaluation_mode": "expert",
                "evaluator_model": self.model_name,
                "reference_diagnosis": reference_diagnosis.get("diagnosis"),
                "doctor_diagnosis_text": doctor_diagnosis_str if isinstance(doctor_diagnosis_str, str) else str(doctor_diagnosis_str),
                "evaluation_result": "",
                "error": str(e),
            }


    def _evaluate_section_expert(self, patient_id: str, section_name: str, section_title: str, reference_data: str, doctor_data: str) -> Dict:
        """Evaluate a single section using expert AI (focused, short API call)."""
        try:
            # print(f"[DEBUG] Evaluating {section_name}...")

            # Build focused prompt for this section only
            statement = (
                f"请你根据以下信息，评价实习医生对{section_title}的掌握情况。\n\n"
                f"# 专家的{section_name}\n{reference_data}\n\n"
                f"# 实习医生的{section_name}\n{doctor_data}\n\n"
                f"请按照以下格式评价：\n"
                f"## 分析\n<简要分析实习医生的{section_title}如何>\n"
                f"## 选项\n<选择A/B/C/D中的一个>\n\n"
                f"评分标准：\nA) 完全/高度一致；B) 相当部分一致；C) 小部分一致；D) 完全不一致"
            )

            # print(f"[DEBUG]   Statement length: {len(statement)}")

            # Build messages
            system_message = (
                "你是资深的医学专家。请基于提供的信息，"
                "对实习医生的诊疗方案各部分的质量进行评价。"
                "请简洁直接地回答，避免过长的分析。"
            )

            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": statement}
            ]

            # print(f"[DEBUG]   Calling API for {section_name}...")
            response = self._get_api_response(messages)
            # print(f"[DEBUG]   Response received, length: {len(response)}")

            # Parse the response to extract choice
            choice_val = None
            analysis = response.strip()

            # Try to extract choice from response
            for char in ["A", "B", "C", "D"]:
                if char in response:
                    choice_val = char
                    break

            # Build result key names
            section_key_map = {
                "症状": "sympton",
                "医学检查项目": "test",
                "诊断结果": "diagnosis",
                "诊断依据": "basis",
                "治疗方案": "treatment"
            }
            key_prefix = section_key_map.get(section_name, section_name)

            result = {
                f"{key_prefix}_analysis": analysis,
                f"{key_prefix}_choice": choice_val,
            }

            # print(f"[DEBUG]   ✓ {section_name}: choice={choice_val}")
            return result

        except Exception as e:
            print(f"[ERROR] Failed to evaluate {section_name}: {type(e).__name__}: {str(e)}")
            section_key_map = {
                "症状": "sympton",
                "医学检查项目": "test",
                "诊断结果": "diagnosis",
                "诊断依据": "basis",
                "治疗方案": "treatment"
            }
            key_prefix = section_key_map.get(section_name, section_name)
            return {
                f"{key_prefix}_analysis": f"[ERROR] {str(e)}",
                f"{key_prefix}_choice": None,
            }

    def _format_doctor_diagnosis(self, diagnosis) -> str:
        """Format doctor diagnosis from either dict or string format."""
        if isinstance(diagnosis, dict):
            parts = []
            if diagnosis.get("症状"):
                parts.append("症状:\n" + str(diagnosis.get("症状")))
            if diagnosis.get("辅助检查"):
                parts.append("辅助检查:\n" + str(diagnosis.get("辅助检查")))
            if diagnosis.get("诊断结果"):
                parts.append("诊断结果:\n" + str(diagnosis.get("诊断结果")))
            if diagnosis.get("诊断依据"):
                parts.append("诊断依据:\n" + str(diagnosis.get("诊断依据")))
            if diagnosis.get("治疗方案"):
                parts.append("治疗方案:\n" + str(diagnosis.get("治疗方案")))
            return "\n\n".join(parts) if parts else str(diagnosis)
        else:
            return str(diagnosis)

    def _get_expert_messages(self, statement: str) -> List[Dict]:
        """Build messages for expert evaluation."""
        system_message = (
            "你是资深的医学专家。"
            "请你根据专家诊疗结果中的现病史、辅助检查、诊断结果、诊断依据和治疗方案，来判断实习医生诊疗结果的质量。\n\n"
            "请参考下面的细则进行评价。\n"
            "1. 病人症状的掌握情况\n"
            "(A) 全面掌握\n(B) 相当部分掌握\n(C) 小部分掌握\n(D) 绝大部分不掌握\n"
            "2. 医学检查项目的完整性\n"
            "(A) 非常完整\n(B) 相当部分完整\n(C) 小部分完整\n(D) 绝大部分不完整\n"
            "3. 诊断结果的一致性\n"
            "(A) 完全一致，诊断正确\n(B) 相当部分一致，诊断基本正确\n(C) 小部分一致，诊断存在错误\n(D) 完全不一致，诊断完全错误\n"
            "4. 诊断依据的一致性\n"
            "(A) 完全一致\n(B) 相当部分一致\n(C) 小部分一致\n(D) 完全不一致\n"
            "5. 治疗方案的一致性\n"
            "(A) 完全一致\n(B) 相当部分一致\n(C) 小部分一致\n(D) 完全不一致\n\n"
            "通过下面的方式来呈现结果\n"
            "# 症状\n## 分析\n<根据专家记录的病人病史，分析实习医生对病人病情的掌握情况>\n## 选项<根据症状分析做出选择>\n"
            "# 医学检查项目\n## 分析\n<基于专家所做的医学检查项目，全面分析实习医生所做的医学检查项目的完整性>\n## 选项<根据分析得到的完整性做出选择>\n"
            "# 诊断结果\n## 分析\n<基于专家做出的诊断结果，结合你的医学常识，分析实习医生诊断结果与专家的一致性>\n## 选项\n<根据分析得到的一致性做出选择>\n"
            "# 诊断依据\n## 分析\n<对比专家的诊断依据，分析实习医生的诊断依据与其的一致性>\n## 选项\n<根据分析得到的一致性做出选择>\n"
            "# 治疗方案\n## 分析\n<对比专家的治疗方案，分析实习医生的治疗方案与其的一致性>\n## 选项\n<根据分析得到的一致性做出选择>\n\n"
            "(1) 请侧重医学答案的事实内容，不需关注风格、语法、标点和无关医学的内容。\n"
            "(2) 请你充分利用医学知识，分析并判断每个点的重要性，再做评价。\n"
            "(3) 注意诊断结果、诊断依据和治疗方案三者之间的承接关系。例如，如果诊断错误，那么后面两部分与专家的一致性就必然很低。"
        )

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": statement}
        ]

    def _get_api_response(self, messages: List[Dict]) -> str:
        """Get response from API with retry logic (follows aihubmix.py pattern)."""
        model_name = self.model_name
        i = 0
        response = None

        # Log request info
        total_msg_len = sum(len(m.get("content", "")) for m in messages)
        # print(f"[DEBUG] API Request: model={model_name}, num_messages={len(messages)}, content_length={total_msg_len}")

        # Models that don't support frequency_penalty and presence_penalty
        models_without_penalties = [
            "grok-4-1-fast-reasoning",
            "gemini-2.5-flash-lite",
            "qwen-turbo-latest",
            "DeepSeek-V3.2-Exp-Think"
        ]

        while i < 5:
            try:
                api_params = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_completion_tokens": self.max_tokens,
                    "top_p": 1.0,
                }

                # Only add penalty parameters for models that support them
                if model_name not in models_without_penalties:
                    api_params["frequency_penalty"] = 0.0
                    api_params["presence_penalty"] = 0.0

                # print(f"[DEBUG] Attempt {i+1}/5: Sending API request...")
                response = self.client.chat.completions.create(**api_params)
                break
            except openai.RateLimitError:
                print(f"[WARNING] Rate limit hit, waiting 10 seconds... (attempt {i+1}/5)")
                time.sleep(10)
                i += 1
            except Exception as e:
                print(f"[ERROR] API error (attempt {i+1}/5): {type(e).__name__}: {str(e)}")
                i += 1
                time.sleep(2)
                continue

        if response is None:
            raise Exception(f"Failed to get response after 5 retries")

        content = response.choices[0].message.content
        # print(f"[DEBUG] Response received: content_length={len(content) if content else 0}")

        if not content or not content.strip():
            print(f"[ERROR] API returned empty content. Full response object: {response}")
            raise Exception("API returned empty response")

        return content

    def _parse_expert_response(self, response: str) -> Dict:
        """Parse expert evaluation response."""
        characters = ["A", "B", "C", "D"]

        def identify_character(text: str) -> Optional[str]:
            for char in characters:
                if char in text:
                    return char
            return None

        # print(f"\n[DEBUG] Parsing expert response (length={len(response)})...")
        # print(f"[DEBUG] Response preview:\n{response}\n")

        parsed = {"evaluation_result": response}
        response_normalized = response.replace("\n# ", "\n\n\n\n# ").replace("\n## ", "\n\n## ")

        # Parse symptoms
        # print(f"[DEBUG] Parsing symptom section...")
        sympton_match = re.findall(r"\# 症状\n(.*?)\n\n\n\n", response_normalized, re.S)
        if sympton_match:
            section = sympton_match[0].strip() + "\n\n\n"
            analysis = re.findall(r"\#\# 分析\n(.*?)\n\n", section, re.S)
            if analysis:
                parsed["sympton_analysis"] = analysis[0].strip()
                # print(f"[DEBUG]   ✓ Found symptom analysis")
            choice = re.findall(r"\#\# 选项\n(.*?)\n\n", section, re.S)
            if choice:
                choice_val = identify_character(choice[0].strip())
                parsed["sympton_choice"] = choice_val
                # print(f"[DEBUG]   ✓ Found symptom choice: {choice_val}")
        else:
            print(f"[DEBUG]   ✗ No symptom section found")

        # Parse medical tests
        # print(f"[DEBUG] Parsing medical test section...")
        test_match = re.findall(r"\# 医学检查项目\n(.*?)\n\n\n\n", response_normalized, re.S)
        if test_match:
            section = test_match[0].strip() + "\n\n\n"
            analysis = re.findall(r"\#\# 分析\n(.*?)\n\n", section, re.S)
            if analysis:
                parsed["test_analysis"] = analysis[0].strip()
                # print(f"[DEBUG]   ✓ Found test analysis")
            choice = re.findall(r"\#\# 选项\n(.*?)\n\n", section, re.S)
            if choice:
                choice_val = identify_character(choice[0].strip())
                parsed["test_choice"] = choice_val
                # print(f"[DEBUG]   ✓ Found test choice: {choice_val}")
        else:
            print(f"[DEBUG]   ✗ No medical test section found")

        # Parse diagnosis
        # print(f"[DEBUG] Parsing diagnosis section...")
        diagnosis_match = re.findall(r"\# 诊断结果\n(.*?)\n\n\n\n", response_normalized, re.S)
        if diagnosis_match:
            section = diagnosis_match[0].strip() + "\n\n\n"
            analysis = re.findall(r"\#\# 分析\n(.*?)\n\n", section, re.S)
            if analysis:
                parsed["diagnosis_analysis"] = analysis[0].strip()
                # print(f"[DEBUG]   ✓ Found diagnosis analysis")
            choice = re.findall(r"\#\# 选项\n(.*?)\n\n", section, re.S)
            if choice:
                choice_val = identify_character(choice[0].strip())
                parsed["diagnosis_choice"] = choice_val
                # print(f"[DEBUG]   ✓ Found diagnosis choice: {choice_val}")
        else:
            print(f"[DEBUG]   ✗ No diagnosis section found")

        # Parse diagnostic basis
        # print(f"[DEBUG] Parsing diagnostic basis section...")
        basis_match = re.findall(r"\# 诊断依据\n(.*?)\n\n\n\n", response_normalized, re.S)
        if basis_match:
            section = basis_match[0].strip() + "\n\n\n"
            analysis = re.findall(r"\#\# 分析\n(.*?)\n\n", section, re.S)
            if analysis:
                parsed["basis_analysis"] = analysis[0].strip()
                # print(f"[DEBUG]   ✓ Found basis analysis")
            choice = re.findall(r"\#\# 选项\n(.*?)\n\n", section, re.S)
            if choice:
                choice_val = identify_character(choice[0].strip())
                parsed["basis_choice"] = choice_val
                # print(f"[DEBUG]   ✓ Found basis choice: {choice_val}")
        else:
            print(f"[DEBUG]   ✗ No diagnostic basis section found")

        # Parse treatment plan - handle case where it's at end or followed by non-standard section
        # print(f"[DEBUG] Parsing treatment plan section...")
        # Try matching with 4 newlines first (normal case)
        treatment_match = re.findall(r"\# 治疗方案\n(.*?)\n\n\n\n", response_normalized, re.S)
        # If not found, try matching until end of string or any line that doesn't start with #/#
        if not treatment_match:
            treatment_match = re.findall(r"\# 治疗方案\n(.*?)(?=\n\n[^\#\n]|\Z)", response_normalized, re.S)

        if treatment_match:
            section = treatment_match[0].strip() + "\n\n\n"
            analysis = re.findall(r"\#\# 分析\n(.*?)\n\n", section, re.S)
            if analysis:
                parsed["treatment_analysis"] = analysis[0].strip()
                # print(f"[DEBUG]   ✓ Found treatment analysis")
            choice = re.findall(r"\#\# 选项\n(.*?)\n\n", section, re.S)
            if choice:
                choice_val = identify_character(choice[0].strip())
                parsed["treatment_choice"] = choice_val
                # print(f"[DEBUG]   ✓ Found treatment choice: {choice_val}")
        else:
            print(f"[DEBUG]   ✗ No treatment plan section found")

        # print(f"[DEBUG] Parse complete. Found {len([k for k in parsed.keys() if k != 'evaluation_result'])} fields")
        return parsed

    def _print_expert_results(self, results: List[Dict]):
        """Print expert evaluation results."""
        if not results:
            print("[WARNING] No results to display")
            return

        choice_counts = {
            "sympton_choice": {"A": 0, "B": 0, "C": 0, "D": 0, "total": 0},
            "test_choice": {"A": 0, "B": 0, "C": 0, "D": 0, "total": 0},
            "diagnosis_choice": {"A": 0, "B": 0, "C": 0, "D": 0, "total": 0},
            "basis_choice": {"A": 0, "B": 0, "C": 0, "D": 0, "total": 0},
            "treatment_choice": {"A": 0, "B": 0, "C": 0, "D": 0, "total": 0},
        }

        for result in results:
            for choice_key in choice_counts.keys():
                choice_value = result.get(choice_key)
                if choice_value:
                    choice_counts[choice_key][choice_value] += 1
                    choice_counts[choice_key]["total"] += 1

        metrics_labels = {
            "sympton_choice": "Symptom Comprehension",
            "test_choice": "Medical Examination Completeness",
            "diagnosis_choice": "Diagnosis Consistency",
            "basis_choice": "Diagnostic Basis Consistency",
            "treatment_choice": "Treatment Plan Consistency"
        }

        print(f"\nTotal Patients Evaluated: {len(results)}")
        print(f"Evaluator Model: {self.model_name}\n")
        print("-" * 80)
        print("Evaluation Metrics Distribution:")
        print("-" * 80)

        for metric_key, metric_label in metrics_labels.items():
            counts = choice_counts[metric_key]
            total = counts["total"]
            if total == 0:
                print(f"\n{metric_label}: No data")
                continue

            print(f"\n{metric_label}:")
            print(f"  Total evaluated: {total}/{len(results)}")
            for choice in ["A", "B", "C", "D"]:
                count = counts[choice]
                percentage = (count / total * 100) if total > 0 else 0
                print(f"    {choice}: {count:3d} ({percentage:6.2f}%)")

    # ========== STATISTICAL SUMMARIZATION ==========

    def _evaluate_statistical(self, doctor_diagnoses: Dict):
        """Statistical summarization with optional expert evaluation caching."""
        print("\n" + "="*80)
        print("STATISTICAL SUMMARIZATION")
        print("="*80)

        # Check if expert evaluation results already exist
        expert_results_path = self._get_expert_results_path()
        if os.path.exists(expert_results_path):
            print(f"[INFO] Loading existing expert evaluation results from: {expert_results_path}")
            expert_results = self._load_expert_results(expert_results_path)
        else:
            print("[INFO] No existing expert evaluation results found. Running expert evaluation first...")
            self._evaluate_expert(doctor_diagnoses)
            expert_results = self._load_expert_results(self.output_filepath)

        # Perform statistical summarization
        self._compute_statistics(expert_results)

    def _get_expert_results_path(self) -> str:
        """Determine the path for cached expert results."""
        base, ext = os.path.splitext(self.output_filepath)
        return f"{base}_expert{ext}"

    def _load_expert_results(self, filepath: str) -> List[Dict]:
        """Load expert evaluation results from JSONL file."""
        results = []
        if os.path.exists(filepath):
            with jsonlines.open(filepath, "r") as reader:
                for obj in reader:
                    results.append(obj)
        return results

    def _compute_statistics(self, expert_results: List[Dict]):
        """Compute bootstrap statistics from expert results."""
        char_to_score = {"A": 4, "B": 3, "C": 2, "D": 1}

        doctor_scores = {}
        for result in expert_results:
            sympton = char_to_score.get(result.get("sympton_choice"), 1)
            test = char_to_score.get(result.get("test_choice"), 1)
            diagnosis = char_to_score.get(result.get("diagnosis_choice"), 1)
            basis = char_to_score.get(result.get("basis_choice"), 1)
            treatment = char_to_score.get(result.get("treatment_choice"), 1)

            scores = [diagnosis, basis, treatment, sympton, test]
            if "doctor_name" in result:
                doctor = result["doctor_name"]
                if doctor not in doctor_scores:
                    doctor_scores[doctor] = []
                doctor_scores[doctor].append(scores)

        # Compute bootstrap CI for each doctor and metric
        idx_to_name = {0: "Diagnosis", 1: "Basis", 2: "Treatment", 3: "Symptom", 4: "Test"}

        for doctor, scores in doctor_scores.items():
            print(f"\n{doctor}:")
            scores_array = np.array(scores)

            for idx in [3, 4, 0, 1, 2]:  # Order: Symptom, Test, Diagnosis, Basis, Treatment
                metric_scores = scores_array[:, idx]
                results = bs.bootstrap(
                    metric_scores, stat_func=bs_stats.mean, num_iterations=10000
                )
                ci_range = results.upper_bound - results.value

                print(
                    f"  {idx_to_name[idx]}: "
                    f"mean={results.value:.3f}, "
                    f"ci=({results.lower_bound:.3f}, {results.upper_bound:.3f}), "
                    f"range={ci_range:.3f}"
                )

    # ========== UTILITY METHODS ==========

    def _save_results(self, results: List[Dict], mode: str):
        """Save evaluation results to output file."""
        os.makedirs(os.path.dirname(self.output_filepath) or ".", exist_ok=True)

        output_path = self.output_filepath
        if mode == "expert":
            base, ext = os.path.splitext(output_path)
            output_path = f"{base}_expert{ext}"
        elif mode == "objective":
            base, ext = os.path.splitext(output_path)
            output_path = f"{base}_objective{ext}"

        with jsonlines.open(output_path, "w") as writer:
            for result in results:
                writer.write(result)

        print(f"[INFO] Results saved to: {output_path}")


def get_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Unified evaluation script for clinical diagnosis"
    )

    # Input/Output
    parser.add_argument(
        "--diagnosis_filepath", type=str, required=True,
        help="File path with raw diagnoses (JSONL format)"
    )
    parser.add_argument(
        "--output_filepath", type=str, default="outputs/evaluation/eval_results.jsonl",
        help="Output file path for evaluation results"
    )
    parser.add_argument(
        "--reference_diagnosis_filepath", type=str, default="data/patients.json",
        help="Path to reference diagnoses (ground truth)"
    )

    # Evaluation mode
    parser.add_argument(
        "--evaluation_mode", type=str,
        choices=["objective", "expert", "statistical", "all"],
        default="all",
        help="Evaluation mode: objective (disease matching), expert (AI), statistical (bootstrap), or all"
    )

    # API configuration (for expert evaluation)
    parser.add_argument(
        "--openai_api_key", type=str, default=None,
        help="OpenAI API key (or use OPENAI_API_KEY env var)"
    )
    parser.add_argument(
        "--openai_api_base", type=str, default=None,
        help="OpenAI API base URL (e.g., https://aihubmix.com/v1)"
    )
    parser.add_argument(
        "--model_name", type=str, default="gpt-4",
        help="LLM model name for expert evaluation"
    )
    parser.add_argument(
        "--temperature", type=float, default=0.0,
        help="Temperature for expert evaluation"
    )
    parser.add_argument(
        "--max_tokens", type=int, default=4096,
        help="Max tokens for expert evaluation"
    )

    # Objective evaluation parameters
    parser.add_argument(
        "--database", type=str, default=None,
        help="ICD-10 disease database file (XLS format)"
    )
    parser.add_argument(
        "--top_n", type=int, default=10,
        help="Top N disease matches for fuzzy matching"
    )
    parser.add_argument(
        "--threshold", type=int, default=50,
        help="Confidence threshold for disease matching"
    )

    # Parallel execution
    parser.add_argument(
        "--max_workers", type=int, default=5,
        help="Max workers for parallel processing"
    )
    parser.add_argument(
        "--parallel", action="store_true", default=False,
        help="Enable parallel evaluation"
    )

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = get_args()
    evaluator = UnifiedEvaluator(args)
    evaluator.evaluate()
