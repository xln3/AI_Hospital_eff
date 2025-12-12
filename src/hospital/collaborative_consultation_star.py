import argparse
import os
import json
from typing import List
import jsonlines
from tqdm import tqdm
import time
import random
import concurrent
import copy
from utils.register import registry, register_class


@register_class(alias="Scenario.CollaborativeConsultationStar")
class CollaborativeConsultationStar:
    """
    STAR Mode: Doctors do not see each other's diagnoses during discussion.
    Each doctor only receives host's critique and revises based on that.

    Key difference from CollaborativeConsultation:
    - revise_diagnosis_by_others() is called with empty list for other_doctors
    - Doctors revise based ONLY on host's critique, not on other doctors' opinions
    """
    def __init__(self, args):
        patient_database = json.load(open(args.patient_database))
        self.args = args

        # Load Different Doctor Agents
        # Use human-readable names for better log differentiation
        default_names = ["Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry",
                        "Iris", "Jack", "Kate", "Leo", "Mary", "Noah", "Olivia", "Paul"]
        self.doctors = []
        for i, doctor_args in enumerate(args.doctors_args[:args.number_of_doctors]):
            # Use custom nickname from config if provided, otherwise use default
            doctor_name = getattr(doctor_args, 'doctor_nickname', None) or default_names[i]

            doctor = registry.get_class(doctor_args.doctor_name)(
                doctor_args,
                name=doctor_name
            )
            # Set doctor ID for tracking (includes nickname for easy identification)
            doctor.id = f"Doctor_{doctor_name}_{doctor_args.doctor_name}"
            self.doctors.append(doctor)

        # Load Different Patient Agents
        self.patients = []
        for patient_profile in patient_database:
            patient = registry.get_class(args.patient)(
                args,
                patient_profile=patient_profile["profile"],
                medical_records=patient_profile["medical_record"],
                patient_id=patient_profile["id"],
            )
            self.patients.append(patient)

        self.reporter = registry.get_class(args.reporter)(args)
        self.host = registry.get_class(args.host)(args)

        self.discussion_mode = args.discussion_mode
        self.max_discussion_turn = args.max_discussion_turn
        self.max_conversation_turn = args.max_conversation_turn
        self.delay_between_tasks = args.delay_between_tasks
        self.max_workers = args.max_workers
        self.save_path = args.save_path
        self.ff_print = args.ff_print
        self.start_time = time.strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def add_parser_args(parser: argparse.ArgumentParser):
        parser.add_argument("--patient_database", default="patients.json", type=str)
        parser.add_argument("--doctor_database", default="doctor.json", type=str)
        parser.add_argument("--number_of_doctors", default=2, type=int, help="number of doctors in the consultation collaboration")
        parser.add_argument("--max_discussion_turn", default=4, type=int, help="max discussion turn between doctors")
        parser.add_argument("--max_conversation_turn", default=10, type=int, help="max conversation turn between doctor and patient")
        parser.add_argument("--max_workers", default=4, type=int, help="max workers for parallel diagnosis")
        parser.add_argument("--delay_between_tasks", default=10, type=int, help="delay between tasks")
        parser.add_argument("--save_path", default="dialog_history.jsonl", help="save path for dialog history")

        parser.add_argument("--patient", default="Agent.Patient.GPT", help="registry name of patient agent")
        parser.add_argument("--reporter", default="Agent.Reporter.GPT", help="registry name of reporter agent")
        parser.add_argument("--host", default="Agent.Host.GPT", help="registry name of host agent")
        parser.add_argument("--ff_print", default=False, action="store_true", help="print dialog history")
        parser.add_argument("--parallel", default=False, action="store_true", help="parallel diagnosis")
        parser.add_argument("--discussion_mode", default="Parallel", choices=["Parallel", "Parallel_with_Critique"], help="discussion mode")

    def _print_doctor_tokens(self, doctor, patient_id, current_turn=None):
        """Print doctor's token usage for current interaction with accumulated totals"""
        tokens = doctor.token_usage.get(patient_id, {})
        if tokens and tokens.get("interactions"):
            # Get the last interaction
            last_interaction = tokens["interactions"][-1] if tokens["interactions"] else {}
            input_tokens = last_interaction.get("input_tokens", 0)
            output_tokens = last_interaction.get("output_tokens", 0)
            interaction_type = last_interaction.get("type", "unknown")

            if input_tokens > 0 or output_tokens > 0:
                print(f"    [Tokens] Input: {input_tokens:,} | Output: {output_tokens:,} | Type: {interaction_type}")

            # Print accumulated tokens for this turn if in discussion phase
            if current_turn:
                turn_interactions = [i for i in tokens.get("interactions", []) if i.get("turn") == current_turn]
                accumulated_interactions = [i for i in tokens.get("interactions", []) if i.get("turn") and i.get("turn") <= current_turn]

                if turn_interactions or accumulated_interactions:
                    acc_input = sum(i.get('input_tokens', 0) for i in accumulated_interactions)
                    acc_output = sum(i.get('output_tokens', 0) for i in accumulated_interactions)
                    print(f"    [Accumulated] Input: {acc_input:,} | Output: {acc_output:,}")

    def _print_host_tokens(self, current_turn=None):
        """Print host's token usage for current turn with accumulated totals"""
        tokens = self.host.token_usage
        if tokens and tokens.get("interactions"):
            # Get the last interaction
            last_interaction = tokens["interactions"][-1] if tokens["interactions"] else {}
            input_tokens = last_interaction.get("input_tokens", 0)
            output_tokens = last_interaction.get("output_tokens", 0)
            interaction_type = last_interaction.get("type", "unknown")

            if input_tokens > 0 or output_tokens > 0:
                print(f"    [Tokens] Input: {input_tokens:,} | Output: {output_tokens:,} | Type: {interaction_type}")

            # Print accumulated tokens for this turn if in discussion phase
            if current_turn:
                turn_interactions = [i for i in tokens.get("interactions", []) if i.get("turn") == current_turn]
                accumulated_interactions = [i for i in tokens.get("interactions", []) if i.get("turn") and i.get("turn") <= current_turn]

                if turn_interactions or accumulated_interactions:
                    acc_input = sum(i.get('input_tokens', 0) for i in accumulated_interactions)
                    acc_output = sum(i.get('output_tokens', 0) for i in accumulated_interactions)
                    print(f"    [Accumulated] Input: {acc_input:,} | Output: {acc_output:,}")

    def _print_token_usage_summary(self, token_usage_summary, patient_id):
        """Print token usage summary for the consultation."""
        print("\n" + "="*100)
        print("TOKEN USAGE SUMMARY")
        print("="*100)

        # Initial consultation phase
        print("\n[PHASE 1: Initial Consultation]")
        print("-"*100)
        initial_doctors = token_usage_summary.get("initial_consultation_phase", {}).get("doctors", {})
        total_initial_input = 0
        total_initial_output = 0

        for doctor_name, tokens in initial_doctors.items():
            input_tokens = tokens.get("total_input_tokens", 0)
            output_tokens = tokens.get("total_output_tokens", 0)
            interaction_count = tokens.get("interaction_count", 0)
            total_tokens = input_tokens + output_tokens

            total_initial_input += input_tokens
            total_initial_output += output_tokens

            print(f"\nDoctor {doctor_name}:")
            print(f"  Input Tokens:  {input_tokens:,}")
            print(f"  Output Tokens: {output_tokens:,}")
            print(f"  Total Tokens:  {total_tokens:,}")
            print(f"  Interactions:  {interaction_count}")

        print(f"\n[Initial Consultation - Total]")
        print(f"  Total Input:  {total_initial_input:,}")
        print(f"  Total Output: {total_initial_output:,}")
        print(f"  Grand Total:  {total_initial_input + total_initial_output:,}")

        # Discussion phase
        print("\n" + "="*100)
        print("[PHASE 2: Discussion Phase]")
        print("-"*100)

        discussion_doctors = token_usage_summary.get("discussion_phase", {}).get("doctors", {})
        host_tokens = token_usage_summary.get("discussion_phase", {}).get("host", {})
        reporter_tokens = token_usage_summary.get("reporter", {})

        total_discussion_input = 0
        total_discussion_output = 0

        # Doctors during discussion
        if discussion_doctors:
            print("\nDoctors (Discussion Phase):")
            for doctor_name, tokens in discussion_doctors.items():
                input_tokens = tokens.get("total_input_tokens", 0)
                output_tokens = tokens.get("total_output_tokens", 0)
                total_tokens = input_tokens + output_tokens
                total_discussion_input += input_tokens
                total_discussion_output += output_tokens

                if total_tokens > 0:  # Only print if tokens were used
                    print(f"  {doctor_name}: Input={input_tokens:,}, Output={output_tokens:,}, Total={total_tokens:,}")

        # Host tokens
        if host_tokens:
            host_input = host_tokens.get("total_input_tokens", 0)
            host_output = host_tokens.get("total_output_tokens", 0)
            host_total = host_input + host_output
            total_discussion_input += host_input
            total_discussion_output += host_output

            print(f"\nHost:")
            print(f"  Input Tokens:  {host_input:,}")
            print(f"  Output Tokens: {host_output:,}")
            print(f"  Total Tokens:  {host_total:,}")

        # Reporter tokens
        if reporter_tokens:
            reporter_input = reporter_tokens.get("total_input_tokens", 0)
            reporter_output = reporter_tokens.get("total_output_tokens", 0)
            reporter_total = reporter_input + reporter_output
            total_discussion_input += reporter_input
            total_discussion_output += reporter_output

            if reporter_total > 0:  # Only print if tokens were used
                print(f"\nReporter:")
                print(f"  Input Tokens:  {reporter_input:,}")
                print(f"  Output Tokens: {reporter_output:,}")
                print(f"  Total Tokens:  {reporter_total:,}")

        print(f"\n[Discussion Phase - Total]")
        print(f"  Total Input:  {total_discussion_input:,}")
        print(f"  Total Output: {total_discussion_output:,}")
        print(f"  Grand Total:  {total_discussion_input + total_discussion_output:,}")

        # Grand summary
        print("\n" + "="*100)
        print("[COMPLETE CONSULTATION SUMMARY]")
        print("="*100)
        grand_total_input = total_initial_input + total_discussion_input
        grand_total_output = total_initial_output + total_discussion_output
        grand_total = grand_total_input + grand_total_output

        print(f"\nInitial Consultation: {total_initial_input + total_initial_output:,} tokens")
        print(f"Discussion Phase:     {total_discussion_input + total_discussion_output:,} tokens")
        print(f"Total Tokens Used:    {grand_total:,} tokens")
        print(f"  - Input:  {grand_total_input:,}")
        print(f"  - Output: {grand_total_output:,}")
        print("="*100 + "\n")

    def _print_doctor_token_summary(self, doctor, patient_id):
        """Print token usage for a single doctor's consultation."""
        if not self.ff_print:
            return

        doctor_name = doctor.name
        token_data = doctor.token_usage.get(patient_id, {})
        input_tokens = token_data.get("total_input_tokens", 0)
        output_tokens = token_data.get("total_output_tokens", 0)
        interaction_count = len(token_data.get("interactions", []))
        total_tokens = input_tokens + output_tokens

        print("\n" + "-"*100)
        print(f"[Token Usage - Doctor {doctor_name} Initial Consultation Completed]")
        print("-"*100)
        print(f"Input Tokens:   {input_tokens:,}")
        print(f"Output Tokens:  {output_tokens:,}")
        print(f"Total Tokens:   {total_tokens:,}")
        print(f"Interactions:   {interaction_count}")

        # Debug: Show available patient IDs if tokens are 0
        if total_tokens == 0:
            print(f"\n[DEBUG] Available patient IDs in doctor.token_usage: {list(doctor.token_usage.keys())}")
            print(f"[DEBUG] Looking for patient_id: {patient_id}")
            if patient_id in doctor.token_usage:
                print(f"[DEBUG] Token data exists: {doctor.token_usage[patient_id]}")

        print("-"*100 + "\n")

    def _conduct_initial_consultation(self, doctor, shared_patient, doctor_index):
        """
        Conduct independent doctor-patient consultation.

        Args:
            doctor: Doctor agent conducting the consultation
            shared_patient: Original patient instance (for profile/records)
            doctor_index: Index for logging

        Returns:
            dict with dialog_history, diagnosis, and metadata
        """
        # Create isolated patient instance for this consultation
        patient = registry.get_class(self.args.patient)(
            self.args,
            patient_profile=shared_patient.profile,
            medical_records=shared_patient.medical_records,
            patient_id=shared_patient.id,
        )

        # Initialize dialog
        dialog_history = [{
            "turn": 0,
            "role": "Doctor",
            "content": doctor.doctor_greet,
            "speaker": "Doctor",
            "recipient": "Patient"
        }]
        doctor.memorize(("assistant", doctor.doctor_greet), patient.id)

        if self.ff_print:
            print(f"############### Dialog - Doctor {doctor.name} <{doctor.engine.model_name}> ###############")
            print("--------------------------------------")
            print(dialog_history[-1]["turn"], f"Doctor {doctor.name} <{doctor.engine.model_name}> -> Patient")
            print(dialog_history[-1]["content"])

        # Consultation loop
        final_turn = 0
        for turn in range(self.max_conversation_turn):
            patient_response = patient.speak(dialog_history[-1]["role"], dialog_history[-1]["content"])

            # Don't add unparsed patient response yet - we'll add parsed version(s) below
            final_turn = turn + 1

            speak_to, patient_response_parsed = patient.parse_role_content(patient_response)

            # Handle dual response (patient speaking to both reporter and doctor)
            if speak_to == "双向":
                # Phase 1: Patient asks Reporter for exam results
                reporter_content = patient_response_parsed["reporter"]
                doctor_content = patient_response_parsed["doctor"]

                if reporter_content:
                    dialog_history.append({
                        "turn": turn+1,
                        "role": "Patient",
                        "content": reporter_content,
                        "speaker": "Patient",
                        "recipient": "Reporter"
                    })

                    if self.ff_print:
                        print("--------------------------------------")
                        print(dialog_history[-1]["turn"], f"Patient {patient.id} <{patient.engine.model_name}> -> Reporter <{self.reporter.engine.model_name}>")
                        print(dialog_history[-1]["content"])

                    # Reporter retrieves and provides results (shown as just "Reporter")
                    reporter_response = self.reporter.speak(patient.medical_records, reporter_content)
                    dialog_history.append({
                        "turn": turn+1,
                        "role": "Reporter",
                        "content": reporter_response
                    })

                    if self.ff_print:
                        print("--------------------------------------")
                        print(dialog_history[-1]["turn"], f"Reporter <{self.reporter.engine.model_name}>")
                        print(dialog_history[-1]["content"])

                # Phase 2: Patient answers Doctor's questions
                if doctor_content:
                    dialog_history.append({
                        "turn": turn+1,
                        "role": "Patient",
                        "content": doctor_content,
                        "speaker": "Patient",
                        "recipient": "Doctor"
                    })

                    if self.ff_print:
                        print("--------------------------------------")
                        print(dialog_history[-1]["turn"], f"Patient {patient.id} <{patient.engine.model_name}> -> Doctor {doctor.name} <{doctor.engine.model_name}>")
                        print(dialog_history[-1]["content"])

                    # Doctor responds based on patient's answer (and has context of reporter's results)
                    # Combine reporter results with patient's answer for doctor's context
                    doctor_input = doctor_content
                    if reporter_content:
                        doctor_input = f"{doctor_content}\n\n[检查结果]\n{reporter_response}"

                    doctor_response = doctor.speak(doctor_input, patient.id)
                    dialog_history.append({
                        "turn": turn+1,
                        "role": "Doctor",
                        "content": doctor_response,
                        "speaker": "Doctor",
                        "recipient": "Patient"
                    })
                    final_turn = turn + 1

                    if self.ff_print:
                        print("--------------------------------------")
                        print(dialog_history[-1]["turn"], f"Doctor {doctor.name} <{doctor.engine.model_name}> -> Patient")
                        print(dialog_history[-1]["content"])

                    # Check if doctor has completed diagnosis
                    if "<诊断完成>" in doctor_response:
                        break

            elif speak_to == "医生":
                # Patient speaks only to doctor
                dialog_history.append({
                    "turn": turn+1,
                    "role": "Patient",
                    "content": patient_response_parsed,
                    "speaker": "Patient",
                    "recipient": "Doctor"
                })

                if self.ff_print:
                    print("--------------------------------------")
                    print(dialog_history[-1]["turn"], f"Patient {patient.id} <{patient.engine.model_name}> -> Doctor {doctor.name} <{doctor.engine.model_name}>")
                    print(dialog_history[-1]["content"])

                doctor_response = doctor.speak(patient_response_parsed, patient.id)
                dialog_history.append({
                    "turn": turn+1,
                    "role": "Doctor",
                    "content": doctor_response,
                    "speaker": "Doctor",
                    "recipient": "Patient"
                })
                final_turn = turn + 1

                if self.ff_print:
                    print("--------------------------------------")
                    print(dialog_history[-1]["turn"], f"Doctor {doctor.name} <{doctor.engine.model_name}> -> Patient")
                    print(dialog_history[-1]["content"])

                # Check if doctor has completed diagnosis (doctor controls when to end)
                if "<诊断完成>" in doctor_response:
                    break

            elif speak_to == "检查员":
                # Patient asks Reporter for exam results only (no doctor question in same turn)
                dialog_history.append({
                    "turn": turn+1,
                    "role": "Patient",
                    "content": patient_response_parsed,
                    "speaker": "Patient",
                    "recipient": "Reporter"
                })

                if self.ff_print:
                    print("--------------------------------------")
                    print(dialog_history[-1]["turn"], f"Patient {patient.id} <{patient.engine.model_name}> -> Reporter <{self.reporter.engine.model_name}>")
                    print(dialog_history[-1]["content"])

                # Reporter retrieves and provides results directly (shown as just "Reporter")
                reporter_response = self.reporter.speak(patient.medical_records, patient_response_parsed)
                dialog_history.append({
                    "turn": turn+1,
                    "role": "Reporter",
                    "content": reporter_response
                })

                if self.ff_print:
                    print("--------------------------------------")
                    print(dialog_history[-1]["turn"], f"Reporter <{self.reporter.engine.model_name}>")
                    print(dialog_history[-1]["content"])

                # Doctor responds based on the exam results
                doctor_response = doctor.speak(reporter_response, patient.id)
                dialog_history.append({
                    "turn": turn+1,
                    "role": "Doctor",
                    "content": doctor_response,
                    "speaker": "Doctor",
                    "recipient": "Patient"
                })
                final_turn = turn + 1

                if self.ff_print:
                    print("--------------------------------------")
                    print(dialog_history[-1]["turn"], f"Doctor {doctor.name} <{doctor.engine.model_name}> -> Patient")
                    print(dialog_history[-1]["content"])

                # Check if doctor has completed diagnosis (doctor controls when to end)
                if "<诊断完成>" in doctor_response:
                    break
            else:
                raise Exception("Wrong!")

        # Get structured diagnosis
        medical_director_summary_query = \
            "【重要】现在需要你提供结构化的诊断总结，用于病历记录。这是数据提取任务，必须使用指定格式，暂时不遵循日常对话规则。严格按照以下格式输出，必须包含 # 标记和编号：\n\n" + \
            "#症状#\n" + \
            "(1) 症状描述1\n(2) 症状描述2\n" + \
            "#辅助检查#\n" + \
            "(1) 检查项目1: 结果\n(2) 检查项目2: 结果\n" + \
            "#诊断结果#\n诊断名称和描述\n" + \
            "#诊断依据#\n" + \
            "(1) 依据1\n(2) 依据2\n" + \
            "#治疗方案#\n" + \
            "(1) 治疗措施1\n" + \
            "(2) 治疗措施2\n\n" + \
            "【格式要求】\n" + \
            "1. 每个章节标题必须使用 #章节名# 格式（两边都有#号）\n" + \
            "2. 每个章节内容必须使用 (1) (2) (3) 编号\n" + \
            "3. 这是病历记录格式，不是日常对话，必须结构化\n" + \
            "4. 不要遗漏任何章节，不要使用其他格式\n" + \
            "5. 完成后在末尾添加 <诊断完成> 标记"

        doctor_response = doctor.speak(medical_director_summary_query, patient.id)
        dialog_history.append({"turn": final_turn+1, "role": "Doctor", "content": doctor_response})

        if self.ff_print:
            print("--------------------------------------")
            print(dialog_history[-1]["turn"], f"Doctor {doctor.name} <{doctor.engine.model_name}> - FINAL DIAGNOSIS")
            print(dialog_history[-1]["content"])
            print("="*100)

        # Parse and store diagnosis
        diagnosis_dict = doctor.parse_diagnosis(doctor_response)

        # Ensure all required diagnosis fields are initialized
        # This prevents issues when diagnosis parsing is incomplete
        required_fields = ["症状", "辅助检查", "诊断结果", "诊断依据", "治疗方案"]
        missing_fields = []
        for field in required_fields:
            if field not in diagnosis_dict or not diagnosis_dict[field]:
                diagnosis_dict[field] = ""
                missing_fields.append(field)

        # Log warning if diagnosis parsing failed
        if missing_fields and self.ff_print:
            print(f"[WARNING] Doctor {doctor.name} diagnosis parsing incomplete. Missing fields: {missing_fields}")
            print(f"[WARNING] Raw response length: {len(doctor_response)} chars")

        doctor.diagnosis[patient.id].update(diagnosis_dict)

        # Print token usage for this doctor's consultation
        # Use patient.id since that's what was used when tracking tokens in doctor.speak()
        self._print_doctor_token_summary(doctor, patient.id)

        return {
            "doctor_id": doctor_index,
            "doctor_name": doctor.name,
            "doctor_class": type(doctor).__name__,
            "doctor_engine_name": doctor.engine.model_name,
            "dialog_history": dialog_history,
            "initial_diagnosis": diagnosis_dict
        }

    def run(self):
        self.remove_processed_patients()
        for patient in tqdm(self.patients):
            self._run(patient)

    def parallel_run(self):
        self.remove_processed_patients()
        st = time.time()
        print("Parallel Run Start")
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 使用 map 来简化提交任务和获取结果的过程
            # executor.map(self._diagnosis, self.patients)
            futures = [executor.submit(self._run, patient) for patient in self.patients]
            # 使用 tqdm 来创建一个进度条
            for _ in tqdm(concurrent.futures.as_completed(futures), total=len(self.patients)):
                pass
        print("duration: ", time.time() - st)

    def _run(self, patient):
        # NEW: Initial consultation phase
        # Generate diagnoses online from each doctor consulting with patient independently
        initial_dialog_histories = []

        # Create a persistent patient instance for the discussion phase
        # This patient will handle queries from the host during discussion
        discussion_patient = registry.get_class(self.args.patient)(
            self.args,
            patient_profile=patient.profile,
            medical_records=patient.medical_records,
            patient_id=patient.id,
        )

        for i, doctor in enumerate(self.doctors):
            # Check if diagnosis already loaded from file
            if patient.id not in doctor.diagnosis or not doctor.diagnosis[patient.id]:
                # Generate diagnosis online through consultation
                consultation_result = self._conduct_initial_consultation(doctor, patient, i)
                initial_dialog_histories.append(consultation_result)
            else:
                # Pre-computed diagnosis already loaded
                initial_dialog_histories.append({
                    "doctor_id": i,
                    "doctor_name": doctor.name,
                    "dialog_history": None,
                    "note": "Pre-computed from file: {}".format(doctor.id)
                })

        # PHASE 1: Host summarizes symptoms and examinations from doctors only
        # Host should NOT access patient dataset directly - only use doctors' diagnoses
        # Get host's initial summary based ONLY on doctors' diagnoses
        initial_summary_result = self.host.get_initial_summary_from_doctors(self.doctors, discussion_patient)

        # If host found inconsistencies, query patient (NOT reporter initially)
        # Generate initial symptom_and_examination for future use if needed
        # This will be updated at the end of discussion to include all new information
        initial_symptom_and_examination = self.host.finalize_symptom_and_examination(
            self.doctors, discussion_patient, initial_summary_result, self.reporter)

        if self.ff_print:
            print("="*100)
            print(f"\n### Collaborative Discussion (STAR Mode - Doctors Don't See Each Other) ###\n")

        # Initialize discussion tracking
        diagnosis_in_discussion = []
        additional_info_gathered = []

        # Initialize final results (will be set when discussion ends)
        final_symptom_and_examination = None
        final_diagnosis = None

        # Turn 1 Phase 1: Use initial diagnoses from consultations as first reports
        if self.ff_print:
            print(f"[Phase 1 - Turn 1]: Doctors report initial diagnoses to host\n")

        # Collect initial diagnoses for Turn 1 Phase 1
        initial_diagnosis_in_turn = []
        for i, doctor in enumerate(self.doctors):
            diagnosis_dict = doctor.get_diagnosis_by_patient_id(discussion_patient.id)
            initial_diagnosis_in_turn.append({
                "doctor_id": i,
                "doctor_engine_name": doctor.engine.model_name,
                "diagnosis": diagnosis_dict
            })
            if self.ff_print:
                diagnosis_result = diagnosis_dict.get("诊断结果", "N/A") if diagnosis_dict else "N/A"
                print(f"  [Doctor {doctor.name}({doctor.engine.model_name})]: {diagnosis_result}")

        # Host checks agreement after initial reports
        if self.ff_print:
            print("\n" + "-"*100)
            print(f"[Host({self.host.engine.model_name}) - Turn 1 Agreement Check]\n")

        host_measurement = self.host.measure_agreement(self.doctors, discussion_patient, discussion_mode=self.discussion_mode, current_turn=1)

        # Print host token usage
        if self.ff_print:
            self._print_host_tokens(current_turn=1)

        # Get detailed analysis from host about initial diagnoses
        initial_analysis = self.host.analyze_discussion_state(
            self.doctors, discussion_patient, self.reporter, current_turn=1)

        # Print host token usage
        if self.ff_print:
            self._print_host_tokens(current_turn=1)

        # Host queries patient when:
        # 1. Doctors reached agreement (host_measurement == '#结束#')
        # 2. analyze_discussion_state indicates we should query patient for missing key information
        turn_1_new_info = None
        query_text = initial_analysis.get('query', '').strip()
        if host_measurement == '#结束#' and initial_analysis.get('action') == 'query_patient' and query_text:
            # Doctors agree, but host identified missing key information
            if self.ff_print:
                print(f"\n[Host Query to Patient - Turn 1]")
                print(f"Reason: Doctors agree but lack key information")
                print(f"Question: {query_text}")

            # Patient responds to the query
            new_info = discussion_patient.speak(
                role="医生",
                content=query_text,
                save_to_memory=True)

            additional_info_gathered.append({
                "turn": 1,
                "type": "patient_query",
                "query": query_text,
                "response": new_info
            })
            turn_1_new_info = f"患者补充信息：{new_info}"

            if self.ff_print:
                print(f"[Patient Response]")
                print(f"{new_info}\n")
        elif host_measurement == '#结束#' and initial_analysis.get('action') == 'query_patient' and not query_text:
            # Host wanted to query but didn't provide question - log warning
            if self.ff_print:
                print(f"\n[WARNING] Host decided to query patient but provided no question at Turn 1.")

        # Determine initial host decision based on agreement and analysis
        if host_measurement == '#结束#':
            if turn_1_new_info:
                # Doctors agreed but got new info from patient, need to update diagnosis
                initial_host_decision = {
                    "action": "update_with_patient_info",
                    "reason": 'Doctors agree but patient provided additional key information. Final diagnosis will incorporate this.',
                    "query": None
                }
            elif initial_analysis.get('action') == 'query_patient':
                # Host wanted to query patient but no query was provided or query failed
                # Begin discussion to resolve the missing information issue
                initial_host_decision = {
                    "action": "begin_discussion",
                    "reason": initial_analysis.get('reason', 'Need additional information. Doctors should discuss to clarify.'),
                    "query": None
                }
            elif initial_analysis.get('action') == 'finalize':
                # Doctors agreed and analysis confirms we can finalize
                initial_host_decision = {
                    "action": "finalize",
                    "reason": initial_analysis.get('reason', 'Doctors have reached agreement after initial consultation.'),
                    "query": None
                }
            else:
                # measure_agreement says consensus but analyze_discussion_state suggests continue
                # Begin discussion to resolve inconsistency
                initial_host_decision = {
                    "action": "begin_discussion",
                    "reason": initial_analysis.get('reason', 'Further discussion needed despite initial agreement.'),
                    "query": None
                }
        else:
            # Doctors have conflicts, begin discussion (no patient query here)
            initial_host_decision = {
                "action": "begin_discussion",
                "reason": initial_analysis.get('reason', 'Doctors have different diagnoses. Discussion begins to reach consensus.'),
                "query": None
            }

        # Add Turn 1 to discussion history with initial reports
        diagnosis_in_discussion.append({
            "turn": 1,
            "diagnosis_in_turn": initial_diagnosis_in_turn,
            "host_critique": host_measurement,
            "host_decision": initial_host_decision,
            "new_information": turn_1_new_info,
            "host_analysis": initial_analysis  # Store detailed analysis for Phase 2 use
        })

        if self.ff_print:
            print(f"  Agreement Status: {host_measurement}")
            print(f"  Host Decision: {initial_host_decision['action']}")
            print("-"*100)

        # Turn 1 Phase 2: If discussion begins OR need to update with patient info, doctors revise
        if host_measurement != '#结束#' and initial_host_decision['action'] == 'begin_discussion':
            # Doctors have conflicts, they revise based on discussion
            # STAR MODE: Doctors revise based ONLY on host's critique, not other doctors' opinions
            if self.ff_print:
                print(f"\n[Phase 2 - Turn 1]: Doctors revise diagnosis based on host's critique (STAR Mode - no other doctors' diagnoses)\n")

            # Prepare host's analysis as critique for doctors to consider
            # Use the detailed analysis from analyze_discussion_state instead of just measurement marker
            host_critique_for_revision = initial_analysis.get('reason', '')

            # Doctors revise their diagnoses
            turn_1_revised_diagnoses = []
            for i, doctor in enumerate(self.doctors):
                # STAR MODE: Pass empty list for other_doctors
                # Doctors revise based ONLY on host's analysis, not on other doctors' opinions
                doctor.revise_diagnosis_by_others(
                    discussion_patient,
                    [],  # STAR MODE: Empty list - doctors don't see other doctors' diagnoses
                    host_critique=host_critique_for_revision,
                    discussion_mode=self.discussion_mode,
                    current_turn=1)

                # Print token usage for this revision
                if self.ff_print:
                    self._print_doctor_tokens(doctor, discussion_patient.id, current_turn=1)

                revised_diagnosis = doctor.get_diagnosis_by_patient_id(discussion_patient.id)
                turn_1_revised_diagnoses.append({
                    "doctor_id": i,
                    "doctor_engine_name": doctor.engine.model_name,
                    "diagnosis": revised_diagnosis,
                    "received_from": ["host"]  # STAR MODE: only receives host's critique, not other doctors
                })

                if self.ff_print:
                    diagnosis_result = revised_diagnosis.get("诊断结果", "N/A") if revised_diagnosis else "N/A"
                    print(f"  [Doctor {doctor.name}({doctor.engine.model_name})]: {diagnosis_result}")

            # Update Turn 1 with revised diagnoses (these will be used in Turn 2 Phase 1)
            diagnosis_in_discussion[0]["revised_diagnoses"] = turn_1_revised_diagnoses

        elif host_measurement == '#结束#' and initial_host_decision['action'] == 'update_with_patient_info':
            # Doctors agreed but got new patient info, update their diagnoses
            if self.ff_print:
                print(f"\n[Phase 2 - Turn 1]: Doctors update diagnosis with patient's additional information\n")

            turn_1_revised_diagnoses = []
            for i, doctor in enumerate(self.doctors):
                # Update diagnosis with new patient information
                doctor.revise_diagnosis_with_new_info(
                    discussion_patient, turn_1_new_info, "Patient provided additional key information", current_turn=1)

                # Print token usage
                if self.ff_print:
                    self._print_doctor_tokens(doctor, discussion_patient.id, current_turn=1)

                revised_diagnosis = doctor.get_diagnosis_by_patient_id(discussion_patient.id)
                turn_1_revised_diagnoses.append({
                    "doctor_id": i,
                    "doctor_engine_name": doctor.engine.model_name,
                    "diagnosis": revised_diagnosis,
                    "received_from": ["host", "patient"]  # Updates with patient info
                })

                if self.ff_print:
                    diagnosis_result = revised_diagnosis.get("诊断结果", "N/A") if revised_diagnosis else "N/A"
                    print(f"  [Doctor {doctor.name}({doctor.engine.model_name})]: {diagnosis_result}")

            # Update Turn 1 with revised diagnoses
            diagnosis_in_discussion[0]["revised_diagnoses"] = turn_1_revised_diagnoses

        if host_measurement != '#结束#':
            discussion_ended = False
            final_turn_number = 1
            pending_patient_info = None  # Track patient info from previous turn
            previous_host_critique = None  # Track host critique for next turn's revision

            for k in range(self.max_discussion_turn):
                current_turn = k + 2  # Start from Turn 2 since Turn 1 is already done
                if self.ff_print:
                    print(f"\n[Host({self.host.engine.model_name}) - Turn {current_turn} Discussion Round]")

                # Check if this turn should update with pending patient info from previous turn
                if pending_patient_info:
                    if self.ff_print:
                        print(f"  [Updating diagnoses with patient information from Turn {current_turn - 1}]")

                    # Doctors update with patient info (this is Phase 2 of previous turn's patient query)
                    diagnosis_in_turn = []
                    for i, doctor in enumerate(self.doctors):
                        doctor.revise_diagnosis_with_new_info(
                            discussion_patient, pending_patient_info,
                            "Incorporating additional information from patient", current_turn=current_turn)

                        # Print token usage
                        if self.ff_print:
                            self._print_doctor_tokens(doctor, discussion_patient.id, current_turn=current_turn)

                        diagnosis_in_turn.append({
                            "doctor_id": i,
                            "doctor_engine_name": doctor.engine.model_name,
                            "diagnosis": doctor.get_diagnosis_by_patient_id(discussion_patient.id),
                            "received_from": ["host", "patient"]  # STAR MODE: updated with patient info
                        })

                        if self.ff_print:
                            diagnosis_dict = doctor.get_diagnosis_by_patient_id(discussion_patient.id)
                            diagnosis_result = diagnosis_dict.get("诊断结果", "N/A") if diagnosis_dict else "N/A"
                            print(f"  Turn {current_turn} - Doctor {doctor.name}({doctor.engine.model_name}): {diagnosis_result}")

                    # After incorporating patient info, finalize
                    host_measurement = '#结束#'
                    turn_decision = {
                        "action": "finalize_with_patient_info",
                        "reason": "Doctors updated diagnosis with patient information. Finalizing.",
                        "query": None
                    }

                    diagnosis_in_discussion.append({
                        "turn": current_turn,
                        "diagnosis_in_turn": diagnosis_in_turn,
                        "host_critique": "#结束#",
                        "host_decision": turn_decision,
                        "new_information": None
                    })

                    discussion_ended = True
                    final_turn_number = current_turn + 1
                    pending_patient_info = None

                    if self.ff_print:
                        print(f"\n[Host({self.host.engine.model_name}) - Turn {current_turn} Result]")
                        print(f"  Agreement Status: {host_measurement}")
                        print("-"*100)
                    # Will break at the end of loop check
                else:
                    # Normal discussion turn
                    # Host analyzes discussion state and decides next action
                    host_decision = self.host.analyze_discussion_state(
                        self.doctors, discussion_patient, self.reporter, current_turn=current_turn)

                    # Print host token usage
                    if self.ff_print:
                        self._print_host_tokens(current_turn=current_turn)

                    if self.ff_print:
                        print(f"  Decision: {host_decision['action']}")
                        print(f"  Reason: {host_decision['reason']}")

                    # Check if host wants to finalize
                    if host_decision["action"] == "finalize":
                        # Host decides diagnosis can be finalized
                        if self.ff_print:
                            print("\n[Host Decision]: Finalize diagnosis - will add final reporting round\n")
                        discussion_ended = True
                        final_turn_number = current_turn

                    # Doctors revise diagnoses (Phase 2)
                    # STAR MODE: Doctors revise based ONLY on host's critique
                    diagnosis_in_turn = []
                    for i, doctor in enumerate(self.doctors):
                        # STAR MODE: Pass empty list for other_doctors
                        # Doctors revise based ONLY on host's current analysis
                        doctor.revise_diagnosis_by_others(
                            discussion_patient,
                            [],  # STAR MODE: Empty list - doctors don't see other doctors' diagnoses
                            host_critique=host_decision.get('reason', ''),  # Use current detailed analysis
                            discussion_mode=self.discussion_mode,
                            current_turn=current_turn)

                        # Print token usage
                        if self.ff_print:
                            self._print_doctor_tokens(doctor, discussion_patient.id, current_turn=current_turn)

                        diagnosis_in_turn.append({
                            "doctor_id": i,
                            "doctor_engine_name": doctor.engine.model_name,
                            "diagnosis": doctor.get_diagnosis_by_patient_id(discussion_patient.id),
                            "received_from": ["host"]  # STAR MODE: only receives host's critique
                        })
                        if self.ff_print:
                            diagnosis_dict = doctor.get_diagnosis_by_patient_id(discussion_patient.id)
                            diagnosis_result = diagnosis_dict.get("诊断结果", "N/A") if diagnosis_dict else "N/A"
                            print(f"  Turn {current_turn} - Doctor {doctor.name}({doctor.engine.model_name}): {diagnosis_result}")

                    # Host measures agreement after revision
                    # In "Parallel_with_Critique" mode: returns "#结束#" or critique like "(a) xxx\n(b) xxx"
                    # In "Parallel" mode: returns "#结束#" or "#继续#"
                    host_measurement = self.host.measure_agreement(self.doctors, discussion_patient, discussion_mode=self.discussion_mode, current_turn=current_turn)

                    # Print host token usage
                    if self.ff_print:
                        self._print_host_tokens(current_turn=current_turn)

                    # Determine if consensus was reached
                    consensus_reached = "#结束#" in host_measurement or host_measurement == "#结束#"

                    # Extract the critique for storing and for next turn
                    if self.discussion_mode == "Parallel_with_Critique" and not consensus_reached:
                        # host_measurement contains the critique like "(a) xxx\n(b) xxx"
                        current_host_critique = host_measurement
                    else:
                        # In Parallel mode or when consensus reached, no detailed critique
                        current_host_critique = host_measurement

                    # Save critique for next turn's doctor revision
                    previous_host_critique = current_host_critique

                    # If doctors reached consensus, check if key information is missing
                    turn_new_info = None
                    if consensus_reached:
                        # Doctors now agree, but check if we're missing key information
                        consensus_analysis = self.host.analyze_discussion_state(
                            self.doctors, discussion_patient, self.reporter, current_turn=current_turn)

                        # Print host token usage
                        if self.ff_print:
                            self._print_host_tokens(current_turn=current_turn)

                        # Check if host wants to query patient
                        query_text = consensus_analysis.get('query', '').strip()
                        if consensus_analysis.get('action') == 'query_patient' and query_text:
                            # Doctors agree but lack key info, query patient
                            if self.ff_print:
                                print(f"\n[Host Query to Patient - Turn {current_turn}]")
                                print(f"Reason: Doctors reached consensus but lack key information")
                                print(f"Question: {query_text}")

                            # Patient responds to the query
                            patient_response = discussion_patient.speak(
                                role="医生",
                                content=query_text,
                                save_to_memory=True)

                            # Parse patient response to handle potential reporter interactions
                            speak_to, patient_response_parsed = discussion_patient.parse_role_content(patient_response)

                            reporter_dialog = []
                            if speak_to == "双向":
                                # Patient speaking to both reporter and doctor
                                reporter_content = patient_response_parsed.get("reporter", "")
                                doctor_content = patient_response_parsed.get("doctor", "")

                                if reporter_content:
                                    # Patient asking reporter for tests
                                    if self.ff_print:
                                        print(f"  [Patient {discussion_patient.id} -> Reporter {self.reporter.engine.model_name}]")
                                        print(f"    {reporter_content}")

                                    reporter_response = self.reporter.speak(discussion_patient.medical_records, reporter_content)

                                    reporter_dialog.append({
                                        "role": "Patient",
                                        "recipient": "Reporter",
                                        "content": reporter_content
                                    })
                                    reporter_dialog.append({
                                        "role": "Reporter",
                                        "recipient": "Patient",
                                        "content": reporter_response
                                    })

                                    if self.ff_print:
                                        print(f"  [Reporter {self.reporter.engine.model_name} -> Patient {discussion_patient.id}]")
                                        print(f"    {reporter_response}\n")

                                    # Use doctor content as the final patient response
                                    new_info = doctor_content if doctor_content else patient_response
                                else:
                                    new_info = patient_response

                            elif speak_to == "检查员":
                                # Patient only asking reporter
                                if self.ff_print:
                                    print(f"  [Patient {discussion_patient.id} -> Reporter {self.reporter.engine.model_name}]")
                                    print(f"    {patient_response_parsed}")

                                reporter_response = self.reporter.speak(discussion_patient.medical_records, patient_response_parsed)

                                reporter_dialog.append({
                                    "role": "Patient",
                                    "recipient": "Reporter",
                                    "content": patient_response_parsed
                                })
                                reporter_dialog.append({
                                    "role": "Reporter",
                                    "recipient": "Patient",
                                    "content": reporter_response
                                })

                                if self.ff_print:
                                    print(f"  [Reporter {self.reporter.engine.model_name} -> Patient {discussion_patient.id}]")
                                    print(f"    {reporter_response}\n")

                                new_info = f"患者请求检查结果：{patient_response_parsed}\n检查员回复：{reporter_response}"
                            else:
                                # Patient speaking only to doctor
                                new_info = patient_response


                            additional_info_gathered.append({
                                "turn": current_turn,
                                "type": "patient_query",
                                "query": query_text,
                                "response": new_info
                            })
                            turn_new_info = f"患者补充信息：{new_info}"

                            if self.ff_print:
                                print(f"[Patient Response]")
                                print(f"{new_info}\n")

                            # Save for next turn
                            pending_patient_info = turn_new_info
                        elif consensus_analysis.get('action') == 'query_patient' and not query_text:
                            # Host wants to query patient but didn't provide a question
                            # This shouldn't happen, but if it does, log warning and continue discussion
                            if self.ff_print:
                                print(f"\n[WARNING] Host decided to query patient but provided no question. Continuing discussion.")
                            # Don't set turn_new_info, will be handled in decision logic below

                    # Determine next host decision for this turn
                    if consensus_reached:
                        if turn_new_info:
                            # Reached consensus but got new patient info, need one more revision
                            turn_decision = {
                                "action": "update_with_patient_info",
                                "reason": "Doctors reached consensus but patient provided additional key information. Need to update diagnosis.",
                                "query": None
                            }
                            # Don't end discussion yet, need one more turn to incorporate patient info
                            discussion_ended = False
                        elif consensus_analysis.get('action') == 'query_patient':
                            # Host wanted to query patient but no query was provided or query failed
                            # Continue discussion to try to resolve missing information through doctor discussion
                            turn_decision = {
                                "action": "continue_discussion",
                                "reason": consensus_analysis.get("reason", "Need additional information but unable to query patient. Doctors should discuss further."),
                                "query": None
                            }
                            discussion_ended = False
                            consensus_reached = False  # Override to continue discussion
                        elif consensus_analysis.get('action') == 'finalize':
                            # Consensus confirmed by both measure_agreement and analyze_discussion_state
                            turn_decision = {
                                "action": "finalize_after_discussion",
                                "reason": consensus_analysis.get("reason", "Doctors have reached consensus after discussion."),
                                "query": None
                            }
                            discussion_ended = True
                            final_turn_number = current_turn + 1
                        else:
                            # measure_agreement says consensus, but analyze_discussion_state suggests continue_discussion
                            # This can happen if LLM responses are inconsistent or there are remaining issues
                            turn_decision = {
                                "action": "continue_discussion",
                                "reason": consensus_analysis.get("reason", "Further discussion needed to resolve remaining issues."),
                                "query": None
                            }
                            discussion_ended = False
                            # Override consensus_reached to continue the discussion
                            consensus_reached = False
                    else:
                        turn_decision = {
                            "action": "continue_discussion",
                            "reason": host_decision["reason"],
                            "query": None
                        }

                    diagnosis_in_discussion.append({
                        "turn": current_turn,
                        "diagnosis_in_turn": diagnosis_in_turn,
                        "host_critique": current_host_critique,  # Store the current critique
                        "host_decision": turn_decision,
                        "new_information": turn_new_info
                    })

                    if self.ff_print:
                        print(f"\n[Host({self.host.engine.model_name}) - Turn {current_turn} Result]")
                        print(f"  Agreement Status: {host_measurement}")
                        print("-"*100)

                # Check if discussion should end or continue with patient info
                if discussion_ended:
                    # discussion_ended is False if we need to incorporate patient info
                    # discussion_ended is True if consensus reached and no patient info needed
                    if self.ff_print:
                        print(f"[Host({self.host.engine.model_name})]: Discussion ending - finalizing consultation\n")

                    # Add final reporting round (Phase 1 only, no Phase 2)
                    final_diagnosis_in_turn = []
                    for i, doctor in enumerate(self.doctors):
                        final_diagnosis_in_turn.append({
                            "doctor_id": i,
                            "doctor_engine_name": doctor.engine.model_name,
                            "diagnosis": doctor.get_diagnosis_by_patient_id(discussion_patient.id)
                        })

                    # Host generates final diagnosis dict (includes症状, 辅助检查, 诊断结果, 诊断依据, 治疗方案)
                    # This ensures all information gathered during discussion is included
                    final_diagnosis = self.host.finalize_consultation(
                        self.doctors, discussion_patient, self.reporter,
                        initial_summary_result, additional_info_gathered)

                    if self.ff_print:
                        print(f"[Host({self.host.engine.model_name}) - Final Diagnosis (Complete)]:")
                        for key, value in final_diagnosis.items():
                            if value:
                                print(f"\n{key}:")
                                print(f"{value}")
                        print()

                    final_host_decision = {
                        "action": "finalize",
                        "reason": "Discussion ends. Doctors have reached consensus or sufficient information has been gathered.",
                        "query": None
                    }

                    diagnosis_in_discussion.append({
                        "turn": final_turn_number,
                        "diagnosis_in_turn": final_diagnosis_in_turn,
                        "host_critique": "#结束#",
                        "host_decision": final_host_decision,
                        "new_information": None,
                        "final_diagnosis_by_host": final_diagnosis  # Host's final summary
                    })

                    if self.ff_print:
                        print(f"[Host({self.host.engine.model_name}) - Final Round {final_turn_number}]")
                        print(f"  Host Decision: Discussion ends")
                        print("-"*100)
                    break
                elif turn_new_info:
                    # Got patient info, need one more turn to incorporate it
                    # Continue loop to next iteration (Turn N+1)
                    if self.ff_print:
                        print(f"[Host({self.host.engine.model_name})]: Patient provided additional info - doctors will update in next turn\n")
                    # The next iteration will be Turn N+1 where doctors update with patient info
                    continue
        else:
            # No discussion needed - doctors already agreed after initial consultation
            if self.ff_print:
                print(f"[Host({self.host.engine.model_name})]: Doctors already reached agreement after initial consultation - finalizing directly\n")
            final_turn_number = 1

            # Host generates final diagnosis dict (includes all fields)
            final_diagnosis = self.host.finalize_consultation(
                self.doctors, discussion_patient, self.reporter,
                initial_summary_result, additional_info_gathered)

            if self.ff_print:
                print(f"[Host({self.host.engine.model_name}) - Final Diagnosis (Complete, No Discussion Needed)]:")
                for key, value in final_diagnosis.items():
                    if value:
                        print(f"\n{key}:")
                        print(f"{value}")
                print()

            # Add final reporting round to diagnosis_in_discussion
            final_diagnosis_in_turn = []
            for i, doctor in enumerate(self.doctors):
                final_diagnosis_in_turn.append({
                    "doctor_id": i,
                    "doctor_engine_name": doctor.engine.model_name,
                    "diagnosis": doctor.get_diagnosis_by_patient_id(discussion_patient.id)
                })

            final_host_decision = {
                "action": "finalize",
                "reason": "Doctors have reached consensus after initial consultation without discussion.",
                "query": None
            }

            diagnosis_in_discussion.append({
                "turn": final_turn_number,
                "diagnosis_in_turn": final_diagnosis_in_turn,
                "host_critique": "#结束#",
                "host_decision": final_host_decision,
                "new_information": None,
                "final_diagnosis_by_host": final_diagnosis
            })

        # Fallback: If final results weren't set (shouldn't happen, but safety check)
        if final_diagnosis is None:
            if self.ff_print:
                print(f"[WARNING] Final diagnosis not set - generating now as fallback\n")

            final_diagnosis = self.host.finalize_consultation(
                self.doctors, discussion_patient, self.reporter,
                initial_summary_result, additional_info_gathered)

            if self.ff_print:
                print(f"[Host({self.host.engine.model_name}) - Final Diagnosis (Complete)]:")
                for key, value in final_diagnosis.items():
                    if value:
                        print(f"\n{key}:")
                        print(f"{value}")
                print()

        if self.ff_print:
            print("="*100)

        # Aggregate token usage from all agents during discussion phase
        token_usage_summary = {
            "initial_consultation_phase": {
                "doctors": {}
            },
            "discussion_phase": {
                "doctors": {},
                "host": self.host.token_usage.copy()
            }
        }

        # Collect doctor token usage from initial consultations
        for i, doctor in enumerate(self.doctors):
            doctor_name = doctor.name
            token_usage_summary["initial_consultation_phase"]["doctors"][doctor_name] = {
                "total_input_tokens": doctor.token_usage[patient.id]["total_input_tokens"],
                "total_output_tokens": doctor.token_usage[patient.id]["total_output_tokens"],
                "interaction_count": len(doctor.token_usage[patient.id]["interactions"]),
                "interactions": doctor.token_usage[patient.id]["interactions"]
            }

        # Collect doctor token usage from discussion phase
        for i, doctor in enumerate(self.doctors):
            doctor_name = doctor.name
            # Get total tokens for this doctor
            doctor_total_tokens = doctor.token_usage.get(discussion_patient.id, {})

            if doctor_name not in token_usage_summary["discussion_phase"]["doctors"]:
                token_usage_summary["discussion_phase"]["doctors"][doctor_name] = {
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "interaction_count": 0,
                    "interactions": []
                }

            # Calculate discussion phase tokens using last accumulated values from discussion turns
            if doctor_total_tokens and doctor_total_tokens.get("interactions"):
                all_interactions = doctor_total_tokens.get("interactions", [])

                # Filter interactions that have turn info (discussion phase interactions are marked with turn >= 1)
                # Turn 0 is initial consultation, Turn 1+ are discussion turns
                discussion_interactions = [i for i in all_interactions if i.get("turn") and i.get("turn") >= 1]

                # Get the last accumulated values from discussion phase
                if discussion_interactions:
                    # Calculate accumulated tokens up to the last discussion interaction
                    last_turn = max(i.get("turn", 0) for i in discussion_interactions)
                    accumulated_interactions = [i for i in all_interactions if i.get("turn") and i.get("turn") <= last_turn]

                    disc_input = sum(i.get('input_tokens', 0) for i in accumulated_interactions)
                    disc_output = sum(i.get('output_tokens', 0) for i in accumulated_interactions)
                else:
                    # No discussion interactions found, discussion phase input/output = 0
                    disc_input = 0
                    disc_output = 0

                token_usage_summary["discussion_phase"]["doctors"][doctor_name] = {
                    "total_input_tokens": disc_input,
                    "total_output_tokens": disc_output,
                    "interaction_count": len(discussion_interactions),
                    "interactions": doctor_total_tokens.get("interactions", [])
                }

        # Calculate discussion phase totals: sum of each doctor's last accumulated + host's accumulated
        discussion_total_input = 0
        discussion_total_output = 0

        # Sum each doctor's discussion tokens
        for doctor_name, tokens in token_usage_summary["discussion_phase"]["doctors"].items():
            discussion_total_input += tokens.get("total_input_tokens", 0)
            discussion_total_output += tokens.get("total_output_tokens", 0)

        # Add host's accumulated tokens from discussion phase
        host_tokens = token_usage_summary["discussion_phase"]["host"]
        if host_tokens and host_tokens.get("interactions"):
            all_host_interactions = host_tokens.get("interactions", [])
            # Get host's discussion interactions (turn >= 1)
            host_discussion_interactions = [i for i in all_host_interactions if i.get("turn") and i.get("turn") >= 1]

            if host_discussion_interactions:
                last_host_turn = max(i.get("turn", 0) for i in host_discussion_interactions)
                host_accumulated_interactions = [i for i in all_host_interactions if i.get("turn") and i.get("turn") <= last_host_turn]

                discussion_total_input += sum(i.get('input_tokens', 0) for i in host_accumulated_interactions)
                discussion_total_output += sum(i.get('output_tokens', 0) for i in host_accumulated_interactions)

        # Add reporter tokens if present
        discussion_total_input_for_print = discussion_total_input
        discussion_total_output_for_print = discussion_total_output

        reporter_tokens = token_usage_summary.get("reporter", {})
        if reporter_tokens and reporter_tokens.get("interactions"):
            reporter_interactions = reporter_tokens.get("interactions", [])
            discussion_total_input_for_print += sum(i.get('input_tokens', 0) for i in reporter_interactions)
            discussion_total_output_for_print += sum(i.get('output_tokens', 0) for i in reporter_interactions)

        # Add reporter token usage to summary
        token_usage_summary["reporter"] = self.reporter.token_usage.copy()

        # Add discussion phase total tokens
        token_usage_summary["discussion_phase"]["total_input_tokens"] = discussion_total_input
        token_usage_summary["discussion_phase"]["total_output_tokens"] = discussion_total_output
        token_usage_summary["discussion_phase"]["total_tokens"] = discussion_total_input + discussion_total_output

        # Print token usage summary if ff_print is enabled
        if self.ff_print:
            self._print_token_usage_summary(token_usage_summary, discussion_patient.id)

        diagnosis_info = {
            "patient_id": discussion_patient.id,
            "initial_consultations": initial_dialog_histories,
            "additional_info_gathered": additional_info_gathered,
            "final_turn": final_turn_number,
            "diagnosis": final_diagnosis,  # Now includes症状, 辅助检查, 诊断结果, 诊断依据, 治疗方案
            "diagnosis_in_discussion": diagnosis_in_discussion,
            "doctor_database": self.args.doctor_database,
            "doctor_names": [doctor.name for doctor in self.doctors],
            "doctor_engine_names": [doctor.engine.model_name for doctor in self.doctors],
            "host": self.args.host,
            "host_engine_name": self.host.engine.model_name,
            "patient": self.args.patient,
            "patient_engine_name": patient.engine.model_name,
            "reporter": self.args.reporter,
            "reporter_engine_name": self.reporter.engine.model_name,
            "time": self.start_time,
            "token_usage": token_usage_summary
        }
        self.save_info(diagnosis_info)

    def remove_processed_patients(self):
        processed_patient_ids = {}
        if os.path.exists(self.save_path):
            with jsonlines.open(self.save_path, "r") as f:
                for obj in f:
                    processed_patient_ids[obj["patient_id"]] = 1
            f.close()

        patient_num = len(self.patients)
        for i, patient in enumerate(self.patients[::-1]):
            if processed_patient_ids.get(patient.id) is not None:
                self.patients.pop((patient_num-(i+1)))

        # random.shuffle(self.patients)
        # self.patients = self.patients
        print("To-be-diagnosed Patient Number: ", len(self.patients))

    def save_info(self, dialog_info):
        with jsonlines.open(self.save_path, "a") as f:
            f.write(dialog_info)
        f.close()
