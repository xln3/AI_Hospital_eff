"""
Clean evaluation script for collaborative consultation results.
Input: JSONL file with collaborative consultation outputs
Golden label: data/patients.json (expert diagnoses)
Task: Compare system diagnosis against expert diagnosis and rate on A/B/C/D scale
"""

import jsonlines
import json
import os
import argparse
from openai import OpenAI
import re
from tqdm import tqdm
import time


class CollaborativeEvaluator:
    def __init__(self, api_key, api_base, model_name):
        self.client = OpenAI(api_key=api_key, base_url=api_base)
        self.model_name = model_name
        self.temperature = 0.0
        self.max_tokens = 4096  # Will use max_completion_tokens for newer models

        self.system_message = (
            "你是资深的医学专家。"
            "请你根据专家诊疗结果中的现病史、辅助检查、诊断结果、诊断依据和治疗方案，来判断实习医生诊疗结果的质量。\n\n"
            "请参考下面的细则进行评价。\n"
            "1. 病人症状的掌握情况\n(A) 全面掌握\n(B) 相当部分掌握\n(C) 小部分掌握\n(D) 绝大部分不掌握\n"
            "2. 医学检查项目的完整性\n(A) 非常完整\n(B) 相当部分完整\n(C) 小部分完整\n(D) 绝大部分不完整\n"
            "3. 诊断结果的一致性\n(A) 完全一致，诊断正确\n(B) 相当部分一致，诊断基本正确\n(C) 小部分一致，诊断存在错误\n(D) 完全不一致，诊断完全错误\n"
            "4. 诊断依据的一致性\n(A) 完全一致\n(B) 相当部分一致\n(C) 小部分一致\n(D) 完全不一致\n"
            "5. 治疗方案的一致性\n(A) 完全一致\n(B) 相当部分一致\n(C) 小部分一致\n(D) 完全不一致\n\n"
            "通过下面的方式来呈现结果\n"
            "# 症状\n## 分析\n<根据专家记录的病人病史，分析实习医生对病人病情的掌握情况>\n## 选项<根据症状分析做出选择>\n"
            "# 医学检查项目\n## 分析\n<基于专家所做的医学检查项目，全面分析实习医生所做的医学检查项目的完整性>\n## 选项<根据分析得到的完整性做出选择>\n"
            "# 诊断结果\n## 分析\n<基于专家做出的诊断结果，结合你的医学常识，分析实习医生诊断结果与专家的一致性>\n## 选项\n<根据分析得到的一致性做出选择>\n"
            "# 诊断依据\n## 分析\n<对比专家的诊断依据，分析实习医生的治疗方案与其的一致性>\n## 选项\n<根据分析得到的一致性做出选择>\n"
            "# 治疗方案\n## 分析\n<对比专家的治疗方案，分析实习医生的治疗方案与其的一致性>\n## 选项\n<根据分析得到的一致性做出选择>\n\n"
            "(1) 请侧重医学答案的事实内容，不需关注风格、语法、标点和无关医学的内容。\n"
            "(2) 请你充分利用医学知识，分析并判断每个点的重要性，再做评价。\n"
            "(3) 注意诊断结果、诊断依据和治疗方案三者之间的承接关系。"
        )

    def load_golden_labels(self, reference_filepath):
        """Load expert diagnoses from patients.json"""
        with open(reference_filepath, 'r', encoding='utf-8') as f:
            patients = json.load(f)

        patient_diagnoses = {}
        for patient in patients:
            patient_id = patient.get("id")
            medical_record = patient.get("medical_record", patient.get("raw_medical_record", {}))

            diagnosis = medical_record.get("诊断结果") or medical_record.get("初步诊断")
            patient_diagnoses[patient_id] = {
                "patient_id": patient_id,
                "症状": medical_record.get("现病史", ""),
                "辅助检查": medical_record.get("辅助检查", ""),
                "诊断结果": diagnosis,
                "诊断依据": medical_record.get("诊断依据", ""),
                "治疗方案": medical_record.get("诊治经过", ""),
            }

        return patient_diagnoses

    def load_system_results(self, results_filepath):
        """Load system outputs from collaborative consultation JSONL"""
        system_diagnoses = {}
        with jsonlines.open(results_filepath, "r") as reader:
            for obj in reader:
                patient_id = obj.get("patient_id")
                diagnosis = obj.get("diagnosis", {})

                # Handle both dict and string formats
                if isinstance(diagnosis, str):
                    # If diagnosis is a string, create empty dict
                    diagnosis = {
                        "症状": "",
                        "辅助检查": "",
                        "诊断结果": diagnosis,  # Use the string as diagnosis result
                        "诊断依据": "",
                        "治疗方案": "",
                    }
                else:
                    # Ensure all fields exist in dict
                    diagnosis = {
                        "症状": diagnosis.get("症状", ""),
                        "辅助检查": diagnosis.get("辅助检查", ""),
                        "诊断结果": diagnosis.get("诊断结果", ""),
                        "诊断依据": diagnosis.get("诊断依据", ""),
                        "治疗方案": diagnosis.get("治疗方案", ""),
                    }

                system_diagnoses[patient_id] = {
                    "patient_id": patient_id,
                    "症状": diagnosis.get("症状", ""),
                    "辅助检查": diagnosis.get("辅助检查", ""),
                    "诊断结果": diagnosis.get("诊断结果", ""),
                    "诊断依据": diagnosis.get("诊断依据", ""),
                    "治疗方案": diagnosis.get("治疗方案", ""),
                    "doctor_names": obj.get("doctor_names", []),
                    "host_engine_name": obj.get("host_engine_name", ""),
                }
        return system_diagnoses

    def evaluate_patient(self, patient_id, golden, system):
        """Evaluate one patient by comparing system diagnosis to golden label"""

        # Build prompt
        statement = (
            "# 专家诊疗结果\n"
            "## 现病史\n{}\n"
            "## 辅助检查\n{}\n"
            "## 诊断结果\n{}\n"
            "## 诊断依据\n{}\n"
            "## 治疗方案\n{}\n\n"
            "# 实习医生诊疗结果\n"
            "## 症状\n{}\n"
            "## 辅助检查\n{}\n"
            "## 诊断结果\n{}\n"
            "## 诊断依据\n{}\n"
            "## 治疗方案\n{}"
        ).format(
            golden["症状"],
            golden["辅助检查"],
            golden["诊断结果"],
            golden["诊断依据"],
            golden["治疗方案"],
            system["症状"],
            system["辅助检查"],
            system["诊断结果"],
            system["诊断依据"],
            system["治疗方案"],
        )

        messages = [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": statement}
        ]

        # Get evaluation
        # Try with max_tokens first, then fall back to max_completion_tokens for newer models
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as e:
            if "max_tokens" in str(e) or "max_completion_tokens" in str(e):
                # Try with max_completion_tokens for models that don't support max_tokens
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_completion_tokens=self.max_tokens,
                )
            else:
                raise

        eval_text = response.choices[0].message.content

        # Parse choices
        parsed = self.parse_evaluation(eval_text)

        return {
            "patient_id": patient_id,
            "evaluation_text": eval_text,
            "symptom_choice": parsed.get("symptom_choice"),
            "test_choice": parsed.get("test_choice"),
            "diagnosis_choice": parsed.get("diagnosis_choice"),
            "basis_choice": parsed.get("basis_choice"),
            "treatment_choice": parsed.get("treatment_choice"),
        }

    @staticmethod
    def parse_evaluation(text):
        """Extract A/B/C/D choices from evaluation text"""
        result = {}

        # Find choices after ## 选项
        lines = text.split("\n")
        current_section = None

        for i, line in enumerate(lines):
            if "## 选项" in line and i + 1 < len(lines):
                # Next line should have the choice
                choice_line = lines[i + 1]
                # Extract first A/B/C/D found
                for char in ["A", "B", "C", "D"]:
                    if char in choice_line:
                        if "症状" in "".join(lines[max(0, i-3):i]):
                            result["symptom_choice"] = char
                        elif "医学检查" in "".join(lines[max(0, i-3):i]):
                            result["test_choice"] = char
                        elif "诊断结果" in "".join(lines[max(0, i-3):i]):
                            result["diagnosis_choice"] = char
                        elif "诊断依据" in "".join(lines[max(0, i-3):i]):
                            result["basis_choice"] = char
                        elif "治疗方案" in "".join(lines[max(0, i-3):i]):
                            result["treatment_choice"] = char
                        break

        return result

    def evaluate_all(self, results_filepath, reference_filepath, output_filepath):
        """Evaluate all patients and save results"""

        print(f"[INFO] Loading golden labels from: {reference_filepath}")
        golden_labels = self.load_golden_labels(reference_filepath)
        print(f"[INFO] Loaded {len(golden_labels)} golden label diagnoses")

        print(f"[INFO] Loading system results from: {results_filepath}")
        system_results = self.load_system_results(results_filepath)
        print(f"[INFO] Loaded {len(system_results)} system diagnosis results")

        # Find patients in both
        common_patients = set(golden_labels.keys()) & set(system_results.keys())
        print(f"[INFO] Found {len(common_patients)} patients in both files")

        # Evaluate each patient
        results = []
        for patient_id in tqdm(sorted(common_patients), desc="Evaluating patients"):
            golden = golden_labels[patient_id]
            system = system_results[patient_id]

            try:
                eval_result = self.evaluate_patient(patient_id, golden, system)
                eval_result["system_info"] = {
                    "doctors": system.get("doctor_names", []),
                    "host": system.get("host_engine_name", ""),
                }
                results.append(eval_result)
            except Exception as e:
                print(f"[ERROR] Failed to evaluate patient {patient_id}: {e}")
                continue

        # Save results
        with jsonlines.open(output_filepath, "w") as writer:
            for result in results:
                writer.write(result)

        print(f"\n[INFO] Saved {len(results)} evaluation results to: {output_filepath}")

        # Print summary
        self.print_summary(results)

    def print_summary(self, results):
        """Print evaluation summary"""
        print("\n" + "=" * 80)
        print(f"EVALUATION SUMMARY ({len(results)} patients)")
        print("=" * 80)

        metrics = ["symptom_choice", "test_choice", "diagnosis_choice", "basis_choice", "treatment_choice"]
        labels = ["Symptom Comprehension", "Medical Test Completeness", "Diagnosis Consistency",
                  "Diagnostic Basis Consistency", "Treatment Plan Consistency"]

        for metric, label in zip(metrics, labels):
            counts = {"A": 0, "B": 0, "C": 0, "D": 0}
            for result in results:
                choice = result.get(metric)
                if choice in counts:
                    counts[choice] += 1

            total = sum(counts.values())
            if total == 0:
                continue

            print(f"\n{label}:")
            for grade in ["A", "B", "C", "D"]:
                count = counts[grade]
                pct = 100 * count / total
                print(f"  {grade}: {count:3d} ({pct:6.2f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate collaborative consultation results against golden labels"
    )
    parser.add_argument("--model", default="gpt-5-nano", help="Evaluator LLM model")
    parser.add_argument("--api-key", default=None, help="OpenAI API key (or use OPENAI_API_KEY env var)")
    parser.add_argument("--api-base", default=None, help="OpenAI API base (or use OPENAI_API_BASE env var)")
    parser.add_argument("--reference", default="data/patients.json", help="Golden label file (patients.json)")
    parser.add_argument("--output", default="outputs/evaluation/collaborative_eval.jsonl", help="Output evaluation results")
    parser.add_argument("results_file", help="Input JSONL file with collaborative consultation results")

    args = parser.parse_args()

    # Get API credentials
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    api_base = args.api_base or os.environ.get("OPENAI_API_BASE")

    if not api_key:
        print("[ERROR] OPENAI_API_KEY not set")
        return

    # Create output directory
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Run evaluation
    evaluator = CollaborativeEvaluator(api_key, api_base, args.model)
    evaluator.evaluate_all(args.results_file, args.reference, args.output)


if __name__ == "__main__":
    main()
