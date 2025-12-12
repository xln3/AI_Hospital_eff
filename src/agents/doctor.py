from .base_agent import Agent
from utils.register import register_class, registry
from collections import defaultdict
import re
import jsonlines
from abc import abstractmethod


@register_class(alias="Agent.Doctor.Base")
class Doctor(Agent):
    def __init__(self, engine=None, doctor_info=None, name="A"):
        if doctor_info is None:
            self.system_message = \
                "你是一个专业且高效的医生，正在与患者对话进行诊断。你必须在有限的对话轮次内完成诊断。\n\n" + \
                "## 对话流程（严格遵守）\n" + \
                "(1) 第1轮：询问主诉、病史、主要症状（简短提问，1-2个问题）\n" + \
                "(2) 第2-3轮：根据症状直接要求必要检查。说'让我们做XXX检查'，患者会找检查员获取结果。\n" + \
                "    【重要】此时绝不能说<诊断完成>，必须等待检查结果\n" + \
                "(3) 第4-5轮：收到检查结果后，立即分析并给出诊断，或补充1-2项关键检查\n" + \
                "(4) 第6轮开始：必须给出明确诊断和治疗方案\n" + \
                "(5) 【关键】只有在以下情况才能说<诊断完成>：\n" + \
                "    - 你已经收到并分析了检查员给出的检查结果\n" + \
                "    - 你已经给出了完整的诊断结果和治疗建议\n" + \
                "    - 绝不能在要求检查后立即说<诊断完成>，必须等到下一轮收到结果并分析完成\n\n" + \
                "## 重要禁令\n" + \
                "- 禁止重复请求已经完成的检查项目（即使结果是'无异常'，也说明已经查过了）\n" + \
                "- 禁止建议患者转院、换医院、找专家，除非病情确实超出诊断能力\n" + \
                "- 禁止提供预约服务、随访安排等非诊断内容，专注于当前诊断\n" + \
                "- 禁止说'您可以去XXX医院'、'我帮您安排XXX'等推诿性话语\n" + \
                "- 禁止在收到检查结果后不分析、不诊断，而是继续问无关问题\n" + \
                "- 禁止自问自答（如'需要准备什么？通常不需要...'），这不是自然对话\n" + \
                "- 【严禁】禁止告诉患者如何准备检查、去哪个科室、带什么材料、检查流程等后勤信息\n" + \
                "- 【严禁】禁止说'下面把准备要点给你讲清楚'、'需要带的材料'、'现场要点'等非医学内容\n" + \
                "- 【严禁】你的角色是医生，不是导诊员或行政人员，只谈医学诊断和治疗\n\n" + \
                "## 检查结果处理规则\n" + \
                "- 检查员回复了检查项目（无论结果是数值、'无异常'、'无数据'），都说明该检查已完成\n" + \
                "- 收到检查结果后，必须立即分析结果并推进诊断，不要再重复请求同一检查\n" + \
                "- 如果检查结果'无异常'，说明该项正常，应综合其他信息做诊断，不是重新要求检查\n\n" + \
                "## 说话方式（极其重要）\n" + \
                "你必须像真实医生面对面交流一样自然说话，严禁使用以下格式：\n" + \
                "❌ 禁止使用编号：1. 2. 3. 或 (1) (2) (3) 或 一、二、三\n" + \
                "❌ 禁止使用项目符号：- 或 • 或 √\n" + \
                "❌ 禁止列清单式回答（如'以下是建议：1...2...3...'）\n" + \
                "❌ 禁止使用'##'、'###'等标题格式\n" + \
                "❌ 禁止写成报告或文档格式\n" + \
                "❌ 禁止自问自答（不要说'需要什么？答：XXX'，患者会问的）\n" + \
                "❌ 禁止在一句话里既提问又回答（等患者回答）\n\n" + \
                "✅ 正确方式：用自然流畅的句子说话，像面对面聊天\n" + \
                "✅ 例如：'听起来像是脑梗死的可能性比较大。你这个左边手脚无力，结合CT看到的右侧病灶，是典型的表现。我们需要用阿司匹林来预防，同时控制好血压和血糖。'\n" + \
                "✅ 可以用'首先'、'另外'、'还有'这样的连接词，但不要编号\n" + \
                "✅ 即使提出多个建议，也要用自然的句子连接，不要列表\n" + \
                "✅ 问患者问题就停下，等患者回答，不要自己继续往下说\n" + \
                "✅ 要求检查时简单说'让我们做XXX检查'即可，患者自己会去办理\n\n" + \
                "你必须在8轮对话内完成诊断，高效推进对话，避免重复和无效沟通。记住：像真人医生一样说话，只谈医学诊断，不谈后勤安排。"

        else: self.system_message = doctor_info

        self.name = name

        self.doctor_greet = "您好，有哪里不舒服？"
        self.engine = engine
        def default_value_factory():
            return [("system", self.system_message)]
        
        self.memories = defaultdict(default_value_factory) 

        def default_diagnosis_factory():
            return {}
        self.diagnosis = defaultdict(default_diagnosis_factory)

        # Token tracking for each patient consultation
        def default_tokens_factory():
            return {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "interactions": []  # List of individual turn token counts
            }
        self.token_usage = defaultdict(default_tokens_factory)

    def get_response(self, messages):
        response = self.engine.get_response(messages)
        return response

    def get_response_with_tokens(self, messages):
        """Get response and track token usage if engine supports it."""
        if hasattr(self.engine, 'get_response_with_tokens'):
            content, tokens = self.engine.get_response_with_tokens(messages)
            return content, tokens
        else:
            # Fallback for engines that don't support token tracking
            content = self.engine.get_response(messages)
            return content, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def get_diagnosis_by_patient_id(self, patient_id, key="ALL"):
        if key == "ALL":
            return self.diagnosis[patient_id]
        else:
            assert key in ["症状", "辅助检查", "诊断结果", "诊断依据", "治疗方案"]
            return self.diagnosis[patient_id].get(key)
    
    def load_diagnosis(
            self, 
            diagnosis=None, 
            patient_id=None, 
            diagnosis_filepath=None, 
            evaluation_filepath=None,
            doctor_key=None
        ):
        if diagnosis is not None and patient_id is not None:
            if isinstance(diagnosis, dict):
                self.diagnosis[patient_id].update(diagnosis)
            else:
                self.diagnosis[patient_id].update(self.parse_diagnosis(diagnosis))
        elif diagnosis_filepath is not None:
            self.id = diagnosis_filepath
            if diagnosis_filepath.endswith("jsonl"):
                with jsonlines.open(diagnosis_filepath, "r") as fr:
                    for line in fr:
                        diagnosis = line["dialog_history"][-1]["content"]
                        self.load_diagnosis(diagnosis=diagnosis, patient_id=line["patient_id"])
                fr.close()
        elif evaluation_filepath is not None:
            assert doctor_key is not None
            self.id = (evaluation_filepath, doctor_key)
            if diagnosis_filepath.endswith("jsonl"):
                with jsonlines.open(evaluation_filepath, "r") as fr:
                    for line in fr:
                        assert line["doctor_name"] == doctor_key
                        diagnosis = line["doctor_diagnosis"]["diagnosis"]
                        self.load_diagnosis(diagnosis=diagnosis, patient_id=line["patient_id"])
                fr.close()
        else:
            raise Exception("Wrong!")

    def parse_diagnosis(self, diagnosis):
        struct_diagnosis = {}
        diagnosis = diagnosis + "\n#"

        for key in ["症状", "辅助检查", "诊断结果", "诊断依据", "治疗方案"]:
            diagnosis_part = re.findall(r"\#{}\#(.*?)\n\#".format(key), diagnosis, re.S)
            if len(diagnosis_part) > 0:
                diagnosis_part = diagnosis_part[0].strip()
                diagnosis_part = re.sub(r"\#{}\#".format(key), '', diagnosis_part)
                diagnosis_part = re.sub(r"\#", '', diagnosis_part)
                diagnosis_part = diagnosis_part.strip()
                struct_diagnosis[key] = diagnosis_part
        return struct_diagnosis

    @staticmethod
    def add_parser_args(parser):
        pass

    def memorize(self, message, patient_id):
        self.memories[patient_id].append(message)

    def forget(self, patient_id=None):
        def default_value_factory():
            return [("system", self.system_message)]
        if patient_id is None:
            self.memories = defaultdict(default_value_factory) 
        else:
            self.memories.pop(patient_id)

    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})

        # Get response with token tracking
        response, tokens = self.get_response_with_tokens(messages)

        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", response), patient_id)

        # Debug: Print before accumulation
        # print(f"\n[DEBUG Doctor.speak] patient_id={patient_id}, tokens before accumulation: {self.token_usage[patient_id]}")
        # print(f"[DEBUG Doctor.speak] Received tokens from API: {tokens}")

        # Track tokens for this interaction
        self.token_usage[patient_id]["total_input_tokens"] += tokens["prompt_tokens"]
        self.token_usage[patient_id]["total_output_tokens"] += tokens["completion_tokens"]
        self.token_usage[patient_id]["interactions"].append({
            "input_tokens": tokens["prompt_tokens"],
            "output_tokens": tokens["completion_tokens"]
        })

        # Debug: Print after accumulation
        print(f"[DEBUG Doctor.speak] tokens after accumulation: {self.token_usage[patient_id]}\n")

        # Debug: Print token info if both are 0 (indicates potential API issue)
        if tokens["prompt_tokens"] == 0 and tokens["completion_tokens"] == 0:
            import sys
            print(f"[WARNING] Doctor {self.name}: Zero tokens returned from API. Response length: {len(response)} chars", file=sys.stderr)

        return response

    def revise_diagnosis_by_symptom_and_examination(self, patient, symptom_and_examination, current_turn=None):
        # load the symptom and examination from the host
        self.load_diagnosis(
            diagnosis=symptom_and_examination,
            patient_id=patient.id
        )
        # revise the diagnosis
        # build the system message
        system_message = "你是一个专业的医生。\n" + \
            "你正在为患者做诊断，患者的症状和辅助检查如下：\n" + \
            "#症状#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="症状")) + \
            "#辅助检查#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="辅助检查")) + \
            "下面你将收到一份初步的医疗意见，其中包含诊断结果、诊断依据和治疗方案。\n" + \
            "(1) 这份医疗意见中可能是正确的，也可能存在谬误，仅供参考。\n" + \
            "(2) 你需要根据患者的症状和辅助检查的结果，来给出更正确合理的诊断结果、诊断依据和治疗方案。\n" + \
            "(3) 请你按照下面的格式来输出。\n" + \
            "#诊断结果#\n(1) xxx\n(2) xxx\n\n" + \
            "#诊断依据#\n(1) xxx\n(2) xxx\n\n" + \
            "#治疗方案#\n(1) xxx\n(2) xxx\n"
        # build the content
        content = "#诊断结果#\n{}\n\n#诊断依据#\n{}\n\n#治疗方案#\n{}".format(
            self.get_diagnosis_by_patient_id(patient.id, key="诊断结果"),
            self.get_diagnosis_by_patient_id(patient.id, key="诊断依据"),
            self.get_diagnosis_by_patient_id(patient.id, key="治疗方案")
        )
        # get the revised diagnosis from the doctor
        diagnosis, tokens = self.get_response_with_tokens([
            {"role": "system", "content": system_message},
            {"role": "user", "content": content}
        ])

        # Track tokens for this revision
        self.token_usage[patient.id]["total_input_tokens"] += tokens["prompt_tokens"]
        self.token_usage[patient.id]["total_output_tokens"] += tokens["completion_tokens"]
        self.token_usage[patient.id]["interactions"].append({
            "input_tokens": tokens["prompt_tokens"],
            "output_tokens": tokens["completion_tokens"],
            "type": "revision_by_symptom_and_examination",
            "turn": current_turn
        })

        # update the diagnosis of doctor for patient with "patient_id"
        self.load_diagnosis(
            diagnosis=diagnosis,
            patient_id=patient.id
        )

    def revise_diagnosis_by_others(self, patient, doctors, host_critique=None, discussion_mode="Parallel", current_turn=None):
        # revise_mode in ["Parallel", "Parallel_with_Critique"]
        if discussion_mode == "Parallel":
            self.revise_diagnosis_by_others_in_parallel(patient, doctors, host_critique=host_critique, current_turn=current_turn)
        elif discussion_mode == "Parallel_with_Critique":
            self.revise_diagnosis_by_others_in_parallel_with_critique(patient, doctors, host_critique, current_turn=current_turn)
        else:
            raise Exception("Wrong discussion_mode: {}".format(discussion_mode))

    def revise_diagnosis_by_others_in_parallel(self, patient, doctors, host_critique=None, current_turn=None):
        # load the symptom and examination from the host
        system_message = "你是一个专业的医生。\n" + \
            "你正在为患者做诊断，患者的症状和辅助检查如下：\n" + \
            "#症状#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="症状")) + \
            "#辅助检查#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="辅助检查")) + \
            "针对患者的病情，你给出了初步的诊断意见：\n" + \
            "#诊断结果#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="诊断结果")) + \
            "#诊断依据#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="诊断依据")) + \
            "#治疗方案#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="治疗方案"))

        # Build prompt based on whether other doctors are present
        if doctors:
            # Regular mode: doctors review each other's opinions
            system_message += \
                "(1) 下面你将收到来自其他医生的诊断意见，其中也包含诊断结果、诊断依据和治疗方案。你需要批判性地梳理并分析其他医生的诊断意见。\n" + \
                "(2) 如果你发现其他医生给出的诊断意见有比你的更合理的部分，请吸纳进你的诊断意见中进行改进。\n" + \
                "(3) 如果你认为你的诊断意见相对于其他医生的更科学合理，请坚持自己的意见保持不变。\n" + \
                "(4) 请你按照下面的格式来输出。\n" + \
                "#诊断结果#\n(1) xxx\n(2) xxx\n\n" + \
                "#诊断依据#\n(1) xxx\n(2) xxx\n\n" + \
                "#治疗方案#\n(1) xxx\n(2) xxx\n"
        else:
            # STAR mode: no other doctors, only review host's critique
            system_message += \
                "(1) 下面你将收到来自会诊主持医生的分析意见和建议。\n" + \
                "(2) 基于主持医生的分析，请对你的诊断意见进行审视和可能的改进。\n" + \
                "(3) 请你按照下面的格式来输出。\n" + \
                "#诊断结果#\n(1) xxx\n(2) xxx\n\n" + \
                "#诊断依据#\n(1) xxx\n(2) xxx\n\n" + \
                "#治疗方案#\n(1) xxx\n(2) xxx\n"

        # build the content
        content = ""
        for i, doctor in enumerate(doctors):
            content += "##医生{}##\n\n#诊断结果#\n{}\n\n#诊断依据#\n{}\n\n#治疗方案#\n{}\n\n".format(
                doctor.name,
                doctor.get_diagnosis_by_patient_id(patient.id, key="诊断结果"),
                doctor.get_diagnosis_by_patient_id(patient.id, key="诊断依据"),
                doctor.get_diagnosis_by_patient_id(patient.id, key="治疗方案")
            )

        # Add host's critique if available (even in Parallel mode)
        if host_critique and host_critique not in ['#继续#', '#结束#']:
            content += "\n##会诊主持医生的分析##\n{}".format(host_critique)

        response, tokens = self.get_response_with_tokens([
            {"role": "system", "content": system_message},
            {"role": "user", "content": content}
        ])

        # Track tokens for this revision
        self.token_usage[patient.id]["total_input_tokens"] += tokens["prompt_tokens"]
        self.token_usage[patient.id]["total_output_tokens"] += tokens["completion_tokens"]
        self.token_usage[patient.id]["interactions"].append({
            "input_tokens": tokens["prompt_tokens"],
            "output_tokens": tokens["completion_tokens"],
            "type": "revision_by_others_in_parallel",
            "turn": current_turn
        })

        self.load_diagnosis(
            diagnosis=response,
            patient_id=patient.id
        )

    def revise_diagnosis_by_others_in_parallel_with_critique(self, patient, doctors, host_critique=None, current_turn=None):
        # load the symptom and examination from the host
        system_message = "你是一个专业的医生{}。\n".format(self.name) + \
            "你正在为患者做诊断，患者的症状和辅助检查如下：\n" + \
            "#症状#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="症状")) + \
            "#辅助检查#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="辅助检查")) + \
            "针对患者的病情，你给出了初步的诊断意见：\n" + \
            "#诊断结果#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="诊断结果")) + \
            "#诊断依据#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="诊断依据")) + \
            "#治疗方案#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="治疗方案"))

        # Build prompt based on whether other doctors are present
        if doctors:
            # Regular mode: doctors review each other's opinions with critique
            system_message += \
                "(1) 下面你将收到来自其他医生的诊断意见，其中也包含诊断结果、诊断依据和治疗方案。你需要批判性地梳理并分析其他医生的诊断意见。\n" + \
                "(2) 在这个过程中，请你注意主治医生给出的争议点。\n" + \
                "(3) 如果你发现其他医生给出的诊断意见有比你的更合理的部分，请吸纳进你的诊断意见中进行改进。\n" + \
                "(4) 如果你认为你的诊断意见相对于其他医生的更科学合理，请坚持自己的意见保持不变。\n" + \
                "(5) 请你按照下面的格式来输出。\n" + \
                "#诊断结果#\n(1) xxx\n(2) xxx\n\n" + \
                "#诊断依据#\n(1) xxx\n(2) xxx\n\n" + \
                "#治疗方案#\n(1) xxx\n(2) xxx\n"
        else:
            # STAR mode: no other doctors, only review host's critique with specific focus points
            system_message += \
                "(1) 下面你将收到来自会诊主持医生的分析意见和建议。主持医生指出了一些需要关注的争议点。\n" + \
                "(2) 请你仔细审视主持医生指出的问题，考虑这些观点对你的诊断的影响。\n" + \
                "(3) 基于这些分析，请对你的诊断意见进行审视和可能的改进。\n" + \
                "(4) 请你按照下面的格式来输出。\n" + \
                "#诊断结果#\n(1) xxx\n(2) xxx\n\n" + \
                "#诊断依据#\n(1) xxx\n(2) xxx\n\n" + \
                "#治疗方案#\n(1) xxx\n(2) xxx\n"

        # build the content
        content = ""
        for i, doctor in enumerate(doctors):
            content += "##医生{}##\n\n#诊断结果#\n{}\n\n#诊断依据#\n{}\n\n#治疗方案#\n{}\n\n".format(
                doctor.name,
                doctor.get_diagnosis_by_patient_id(patient.id, key="诊断结果"),
                doctor.get_diagnosis_by_patient_id(patient.id, key="诊断依据"),
                doctor.get_diagnosis_by_patient_id(patient.id, key="治疗方案")
            )

        # Add host's critique with appropriate label
        if doctors:
            content += "##主任医生##\n{}".format(host_critique)
        else:
            content += "##会诊主持医生的分析##\n{}".format(host_critique)

        response, tokens = self.get_response_with_tokens([
            {"role": "system", "content": system_message},
            {"role": "user", "content": content}
        ])

        # Track tokens for this revision
        self.token_usage[patient.id]["total_input_tokens"] += tokens["prompt_tokens"]
        self.token_usage[patient.id]["total_output_tokens"] += tokens["completion_tokens"]
        self.token_usage[patient.id]["interactions"].append({
            "input_tokens": tokens["prompt_tokens"],
            "output_tokens": tokens["completion_tokens"],
            "type": "revision_by_others_in_parallel_with_critique",
            "turn": current_turn
        })

        self.load_diagnosis(
            diagnosis=response,
            patient_id=patient.id
        )

    def _format_diagnosis(self, diagnosis_dict):
        """
        Format diagnosis dictionary for display in prompts.

        Args:
            diagnosis_dict: Dictionary with diagnosis fields

        Returns:
            Formatted string representation
        """
        formatted = ""
        for key in ["症状", "辅助检查", "诊断结果", "诊断依据", "治疗方案"]:
            value = diagnosis_dict.get(key, "")
            if value:
                formatted += f"#{key}#\n{value}\n\n"
        return formatted.rstrip()

    def revise_diagnosis_with_new_info(self, patient, new_information, context, current_turn=None):
        """
        Revise diagnosis when host provides new information from patient/reporter.

        Args:
            patient: Patient object
            new_information: New data from patient query or examination
            context: Host's explanation of why this info was gathered
            current_turn: Current discussion turn number (optional, for token tracking)
        """
        current_diagnosis = self.get_diagnosis_by_patient_id(patient.id)

        system_message = f"""你是一个专业的医生。

你之前的诊断：
{self._format_diagnosis(current_diagnosis)}

会诊主持人提供了新的信息：
{new_information}

原因：{context}

请根据这个新信息，重新评估你的诊断。如果需要修改，请更新诊断结果、诊断依据和治疗方案。

按照以下格式输出：
#诊断结果#
...

#诊断依据#
...

#治疗方案#
...
"""

        revised_diagnosis, tokens = self.get_response_with_tokens([
            {"role": "system", "content": system_message},
            {"role": "user", "content": "请提供你更新后的诊断。"}
        ])

        # Track tokens for this revision
        self.token_usage[patient.id]["total_input_tokens"] += tokens["prompt_tokens"]
        self.token_usage[patient.id]["total_output_tokens"] += tokens["completion_tokens"]
        self.token_usage[patient.id]["interactions"].append({
            "input_tokens": tokens["prompt_tokens"],
            "output_tokens": tokens["completion_tokens"],
            "type": "revision_with_new_info",
            "turn": current_turn
        })

        # Parse and update
        diagnosis_dict = self.parse_diagnosis(revised_diagnosis)
        self.diagnosis[patient.id].update(diagnosis_dict)


@register_class(alias="Agent.Doctor.GPT")
class GPTDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.GPT")(
            openai_api_key=args.doctor_openai_api_key, 
            openai_api_base=args.doctor_openai_api_base,
            openai_model_name=args.doctor_openai_model_name, 
            temperature=args.doctor_temperature, 
            max_tokens=args.doctor_max_tokens,
            top_p=args.doctor_top_p,
            frequency_penalty=args.doctor_frequency_penalty,
            presence_penalty=args.doctor_presence_penalty
        )
        super(GPTDoctor, self).__init__(engine, doctor_info, name=name)
        # elf.engine = build_engine(engine_name=model)
        # print(self.memories[0][1])

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument('--doctor_openai_api_key', type=str, help='API key for OpenAI')
        parser.add_argument('--doctor_openai_api_base', type=str, help='API base for OpenAI')
        parser.add_argument('--doctor_openai_model_name', type=str, help='API model name for OpenAI')
        parser.add_argument('--doctor_temperature', type=float, default=0.0, help='temperature')
        parser.add_argument('--doctor_max_tokens', type=int, default=2048, help='max tokens')
        parser.add_argument('--doctor_top_p', type=float, default=1, help='top p')
        parser.add_argument('--doctor_frequency_penalty', type=float, default=0, help='frequency penalty')
        parser.add_argument('--doctor_presence_penalty', type=float, default=0, help='presence penalty')                

    def get_response(self, messages):
        response = self.engine.get_response(messages)
        return response

    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})

        response = self.get_response(messages)

        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", response), patient_id)

        return response


@register_class(alias="Agent.Doctor.ChatGLM")
class ChatGLMDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.ChatGLM")(
            chatglm_api_key=args.doctor_chatglm_api_key, 
            model_name=args.doctor_chatglm_model_name, 
            temperature=args.doctor_temperature, 
            top_p=args.doctor_top_p, 
            incremental=args.doctor_incremental,
        )
        super(ChatGLMDoctor, self).__init__(engine, doctor_info, name=name)

        def default_value_factory():
            return [("assistant", self.system_message)]
        self.memories = defaultdict(default_value_factory) 

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_chatglm_api_key", type=str)
        parser.add_argument("--doctor_chatglm_model_name", type=str, default="chatglm_pro")
        parser.add_argument("--doctor_temperature", type=float, default=0.5)
        parser.add_argument("--doctor_top_p", type=float, default=0.9)
        parser.add_argument("--doctor_incremental", type=bool, default=True)

    def forget(self, patient_id=None):
        def default_value_factory():
            return [("assistant", self.system_message)]
        if patient_id is None:
            self.memories = defaultdict(default_value_factory) 
        else:
            self.memories.pop(patient_id)
            

@register_class(alias="Agent.Doctor.Minimax")
class MinimaxDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.MiniMax")(
            minimax_api_key=args.doctor_minimax_api_key, 
            minimax_group_id=args.doctor_minimax_group_id, 
            minimax_model_name=args.doctor_minimax_model_name, 
            tokens_to_generate=args.doctor_tokens_to_generate,
            temperature=args.doctor_temperature, 
            top_p=args.doctor_top_p, 
            stream=args.doctor_stream,
        )

        super(MinimaxDoctor, self).__init__(engine, doctor_info, name=name)

        def default_value_factory():
            return []
        self.memories = defaultdict(default_value_factory) 

        self.bot_setting = [{
            "bot_name": "医生",
            "content": self.system_message
        }]

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_minimax_group_id", type=str)
        parser.add_argument("--doctor_minimax_api_key", type=str)
        parser.add_argument("--doctor_minimax_model_name", type=str, default="abab5.5-chat")
        parser.add_argument("--doctor_tokens_to_generate", type=int, default=1024)
        parser.add_argument("--doctor_temperature", type=float, default=0.5)
        parser.add_argument("--doctor_top_p", type=float, default=1.0)
        parser.add_argument("--doctor_stream", type=bool, default=False)

    def forget(self, patient_id=None):
        def default_value_factory():
            return []
        if patient_id is None:
            self.memories = defaultdict(default_value_factory)  
        else:
             self.memories.pop(patient_id)

    @staticmethod
    def translate_role_to_sender_type(role):
        if role == "user":
            return "USER"
        elif role == "assistant":
            return "BOT"
        else:
            raise Exception("Unknown role: {}".format(role))
    
    @staticmethod
    def translate_role_to_sender_name(role):
        if role == "user":
            return "患者"
        elif role == "assistant":
            return "医生"
        else:
            raise Exception("Unknown role: {}".format(role))
        
    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]
        messages = []
        for memory in memories:
            sender_type = self.translate_role_to_sender_type(memory[0])
            sender_name = self.translate_role_to_sender_name(memory[0])
            messages.append({"sender_type": sender_type, "sender_name": sender_name, "text": memory[1]})
        messages.append({"sender_type": "USER", "sender_name": "患者",  "text": content})

        responese = self.engine.get_response(messages, self.bot_setting)

        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", responese), patient_id)

        return responese


@register_class(alias="Agent.Doctor.WenXin")
class WenXinDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.WenXin")(
            wenxin_api_key=args.doctor_wenxin_api_key, 
            wenxin_sercet_key=args.doctor_wenxin_sercet_key,
            temperature=args.doctor_temperature, 
            top_p=args.doctor_top_p,
            penalty_score=args.doctor_penalty_score,
        )
        super(WenXinDoctor, self).__init__(engine, doctor_info, name=name)

        def default_value_factory():
            return []
        self.memories = defaultdict(default_value_factory) 
        # self.memories = []

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_wenxin_api_key", type=str)
        parser.add_argument("--doctor_wenxin_sercet_key", type=str)
        parser.add_argument("--doctor_temperature", type=float, default=0.95)
        parser.add_argument("--doctor_top_p", type=float, default=0.8)
        parser.add_argument("--doctor_penalty_score", type=float, default=1.0)

    def forget(self, patient_id=None):
        def default_value_factory():
            return []
        if patient_id is None:
            self.memories = defaultdict(default_value_factory) 
        else:
            self.memories.pop(patient_id)
        
    def get_response(self, messages):
        if messages[0]["role"] == "system":
            system_message = messages.pop(0)["content"]
        else: system_message = self.system_message
        if messages[0]["role"] == "assistant":
            messages.pop(0)
        response = self.engine.get_response(messages, system=system_message)
        return response

    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]
        # if memories[0][0] == "assistant":
        #     memories.pop(0)
        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})
        responese = self.engine.get_response(messages, system=self.system_message)

        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", responese), patient_id)
        return responese


@register_class(alias="Agent.Doctor.Qwen")
class QwenDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.Qwen")(
            api_key=args.doctor_qwen_api_key, 
            model_name=args.doctor_qwen_model_name, 
            seed=1,
        )
        super(QwenDoctor, self).__init__(engine, doctor_info, name=name)

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_qwen_api_key", type=str)
        parser.add_argument(
            "--doctor_qwen_model_name", type=str, 
            choices=["qwen-max", "qwen-max-1201", "qwen-plus-gamma", "qwen-plus", "qwen-turbo", "baichuan2-7b-chat-v1", "baichuan2-13b-chat-v1"], default="qwen-max")
        parser.add_argument("--doctor_seed", type=int, default=1)
    
    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})
        if messages[1].get("role") == "assistant":
            messages.pop(1)
        responese = self.engine.get_response(messages)
        
        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", responese), patient_id)
        return responese


@register_class(alias="Agent.Doctor.HuatuoGPT")
class HuatuoGPTDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None):
        engine = registry.get_class("Engine.HuatuoGPT")(
            model_name_or_path=args.doctor_huatuogpt_model_name_or_path, 
        )
        super(HuatuoGPTDoctor, self).__init__(engine, doctor_info)

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_huatuogpt_model_name_or_path", type=str)
    
    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})
        # if messages[1].get("role") == "assistant":
        #     messages.pop(1)
        responese = self.engine.get_response(messages)
        
        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", responese), patient_id)
        return responese


@register_class(alias="Agent.Doctor.HF")
class HFDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None):
        engine = registry.get_class("Engine.HF")(
            model_name_or_path=args.doctor_hf_model_name_or_path, 
        )
        super(HFDoctor, self).__init__(engine, doctor_info)

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_hf_model_name_or_path", type=str)
    
    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})
        # if messages[1].get("role") == "assistant":
        #     messages.pop(1)
        responese = self.engine.get_response(messages)
        
        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", responese), patient_id)
        return responese


@register_class(alias="Agent.Doctor.AiHubMix")
class AiHubMixDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.AiHubMix")(
            aihubmix_api_key=args.doctor_aihubmix_api_key,
            aihubmix_model_name=args.doctor_aihubmix_model_name,
            temperature=args.doctor_temperature,
            max_tokens=args.doctor_max_tokens,
            top_p=args.doctor_top_p,
            frequency_penalty=args.doctor_frequency_penalty,
            presence_penalty=args.doctor_presence_penalty
        )
        super(AiHubMixDoctor, self).__init__(engine, doctor_info, name=name)

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument('--doctor_aihubmix_api_key', type=str, help='API key for AiHubMix')
        parser.add_argument('--doctor_aihubmix_model_name', type=str, default='gpt-5-nano', help='Model name for AiHubMix')
        parser.add_argument('--doctor_temperature', type=float, default=0.3, help='temperature (slightly higher for more natural conversation)')
        parser.add_argument('--doctor_max_tokens', type=int, default=16384, help='max tokens (higher for reasoning models like gpt-5-nano)')
        parser.add_argument('--doctor_top_p', type=float, default=1, help='top p')
        parser.add_argument('--doctor_frequency_penalty', type=float, default=0, help='frequency penalty')
        parser.add_argument('--doctor_presence_penalty', type=float, default=0, help='presence penalty')

    def speak(self, content, patient_id, save_to_memory=True):
        # Use parent's speak() method which includes token tracking and debug output
        return super().speak(content, patient_id, save_to_memory)
