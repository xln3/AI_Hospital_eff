import argparse
import os
import json
from typing import List
import jsonlines
from tqdm import tqdm
import time
import concurrent
import random
from utils.register import register_class, registry


@register_class(alias="Scenario.Consultation")
class Consultation:
    def __init__(self, args):
        patient_database = json.load(open(args.patient_database))
        self.args = args
        self.doctor = registry.get_class(args.doctor)(
            args,
        )
        
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

        self.medical_director_summary_query = \
            "您能分别总结一下病人的症状和辅助检查的结果，然后给出您的诊断结果、诊断依据和治疗方案吗？" + \
            "按照下面的格式给出。\n\n" + \
            "#症状#\n(1)xx\n(2)xx\n\n" + \
            "#辅助检查#\n(1)xx\n(2)xx\n\n" + \
            "#诊断结果#\nxx\n\n" + \
            "#诊断依据#\n(1)xx\n(2)xx\n\n" + \
            "#治疗方案#\n(1)xx\n(2)xx" 

        self.max_conversation_turn = args.max_conversation_turn
        self.delay_between_tasks = args.delay_between_tasks
        self.max_workers = args.max_workers
        self.save_path = args.save_path
        self.ff_print = args.ff_print
        self.start_time = time.strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def add_parser_args(parser: argparse.ArgumentParser):
        parser.add_argument("--patient_database", default="patients.json", type=str)
        parser.add_argument("--patient", default="Agent.Patient.GPT", help="registry name of patient agent")
        parser.add_argument("--doctor", default="Agent.Doctor.GPT", help="registry name of doctor agent")
        parser.add_argument("--reporter", default="Agent.Reporter.GPT", help="registry name of reporter agent")

        parser.add_argument("--max_conversation_turn", default=10, type=int, help="max conversation turn between doctor and patient")
        parser.add_argument("--max_workers", default=4, type=int, help="max workers for parallel diagnosis")
        parser.add_argument("--delay_between_tasks", default=10, type=int, help="delay between tasks")
        parser.add_argument("--save_path", default="dialog_history.jsonl", help="save path for dialog history")
        parser.add_argument("--ff_print", default=False, action="store_true", help="print dialog history")
        parser.add_argument("--parallel", default=False, action="store_true", help="parallel diagnosis")

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
            
        random.shuffle(self.patients)
        print("To-be-diagnosed Patient Number: ", len(self.patients))

    def run(self):
        self.remove_processed_patients()
        # st = time.time()
        for patient in tqdm(self.patients):
            self._diagnosis(patient)
            # patient.forget()
            # self.doctor.forget()
        # print("duration: ", time.time() - st)

    def parallel_run(self):
        self.remove_processed_patients()

        st = time.time()
        print("Parallel Diagnosis Start")
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 使用 map 来简化提交任务和获取结果的过程
            # executor.map(self._diagnosis, self.patients)
            futures = [executor.submit(self._diagnosis, patient) for patient in self.patients]
            # 使用 tqdm 来创建一个进度条
            for _ in tqdm(concurrent.futures.as_completed(futures), total=len(self.patients)):
                pass

        print("duration: ", time.time() - st)
        
    def _diagnosis(self, patient):
        dialog_history = [{
            "turn": 0,
            "role": "Doctor",
            "content": self.doctor.doctor_greet,
            "speaker": "Doctor",
            "recipient": "Patient"
        }]
        self.doctor.memorize(("assistant", self.doctor.doctor_greet), patient.id)
        if self.ff_print:
            print("############### Dialog ###############")
            print("--------------------------------------")
            print(dialog_history[-1]["turn"], "Doctor -> Patient")
            print(dialog_history[-1]["content"])
        for turn in range(self.max_conversation_turn):
            patient_response = patient.speak(dialog_history[-1]["role"], dialog_history[-1]["content"])

            if "<结束>" in patient_response:
                break

            speak_to, patient_response_parsed = patient.parse_role_content(patient_response)

            # Handle dual response (patient speaking to both reporter and doctor)
            if speak_to == "双向":
                reporter_content = patient_response_parsed["reporter"]
                doctor_content = patient_response_parsed["doctor"]

                if reporter_content:
                    # Patient asks Reporter for exam results
                    dialog_history.append({
                        "turn": turn+1,
                        "role": "Patient",
                        "content": reporter_content,
                        "speaker": "Patient",
                        "recipient": "Reporter"
                    })

                    if self.ff_print:
                        print("--------------------------------------")
                        print(dialog_history[-1]["turn"], "Patient -> Reporter")
                        print(dialog_history[-1]["content"])

                    # Reporter provides results
                    reporter_response = self.reporter.speak(patient.medical_records, reporter_content)
                    dialog_history.append({
                        "turn": turn+1,
                        "role": "Reporter",
                        "content": reporter_response
                    })

                    if self.ff_print:
                        print("--------------------------------------")
                        print(dialog_history[-1]["turn"], "Reporter")
                        print(dialog_history[-1]["content"])

                if doctor_content:
                    # Patient answers Doctor's questions
                    dialog_history.append({
                        "turn": turn+1,
                        "role": "Patient",
                        "content": doctor_content,
                        "speaker": "Patient",
                        "recipient": "Doctor"
                    })

                    if self.ff_print:
                        print("--------------------------------------")
                        print(dialog_history[-1]["turn"], "Patient -> Doctor")
                        print(dialog_history[-1]["content"])

                    # Doctor responds with context of exam results if available
                    doctor_input = doctor_content
                    if reporter_content:
                        doctor_input = f"{doctor_content}\n\n[检查结果]\n{reporter_response}"

                    doctor_response = self.doctor.speak(doctor_input, patient.id)
                    dialog_history.append({
                        "turn": turn+1,
                        "role": "Doctor",
                        "content": doctor_response,
                        "speaker": "Doctor",
                        "recipient": "Patient"
                    })

                    if self.ff_print:
                        print("--------------------------------------")
                        print(dialog_history[-1]["turn"], "Doctor -> Patient")
                        print(dialog_history[-1]["content"])

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
                    print(dialog_history[-1]["turn"], "Patient -> Doctor")
                    print(dialog_history[-1]["content"])

                doctor_response = self.doctor.speak(patient_response_parsed, patient.id)
                dialog_history.append({
                    "turn": turn+1,
                    "role": "Doctor",
                    "content": doctor_response,
                    "speaker": "Doctor",
                    "recipient": "Patient"
                })

                if self.ff_print:
                    print("--------------------------------------")
                    print(dialog_history[-1]["turn"], "Doctor -> Patient")
                    print(dialog_history[-1]["content"])

            elif speak_to == "检查员":
                # Patient asks Reporter for exam results only
                dialog_history.append({
                    "turn": turn+1,
                    "role": "Patient",
                    "content": patient_response_parsed,
                    "speaker": "Patient",
                    "recipient": "Reporter"
                })

                if self.ff_print:
                    print("--------------------------------------")
                    print(dialog_history[-1]["turn"], "Patient -> Reporter")
                    print(dialog_history[-1]["content"])

                reporter_response = self.reporter.speak(patient.medical_records, patient_response_parsed)
                dialog_history.append({
                    "turn": turn+1,
                    "role": "Reporter",
                    "content": reporter_response
                })

                if self.ff_print:
                    print("--------------------------------------")
                    print(dialog_history[-1]["turn"], "Reporter")
                    print(dialog_history[-1]["content"])

                doctor_response = self.doctor.speak(reporter_response, patient.id)
                dialog_history.append({
                    "turn": turn+1,
                    "role": "Doctor",
                    "content": doctor_response,
                    "speaker": "Doctor",
                    "recipient": "Patient"
                })

                if self.ff_print:
                    print("--------------------------------------")
                    print(dialog_history[-1]["turn"], "Doctor -> Patient")
                    print(dialog_history[-1]["content"])
            else:
                raise Exception("Wrong!")
        
        doctor_response = self.doctor.speak(self.medical_director_summary_query, patient.id)
        dialog_history.append({"turn": turn+1, "role": "Doctor", "content": doctor_response})
        if self.ff_print:
            print("--------------------------------------")
            print(dialog_history[-1]["turn"], dialog_history[-1]["role"])
            print(dialog_history[-1]["content"])
            # self.evaluate(patient_profile, doctor_response)

        dialog_info = {
            "patient_id": patient.id,
            "doctor": self.args.doctor,
            "doctor_engine_name": self.doctor.engine.model_name,
            "patient": self.args.patient,
            "patient_engine_name": patient.engine.model_name,
            "reporter": self.args.reporter,
            "reporter_engine_name": self.reporter.engine.model_name,
            "dialog_history": dialog_history,
            "time": self.start_time,
        }
        self.save_dialog_info(dialog_info)
    
    def save_dialog_info(self, dialog_info):
        with jsonlines.open(self.save_path, "a") as f:
            f.write(dialog_info)
        f.close()
