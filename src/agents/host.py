import re
from .base_agent import Agent
from utils.register import register_class, registry


@register_class(alias="Agent.Host.GPT")
class Host(Agent):
    def __init__(self, args, host_info=None):
        engine = registry.get_class("Engine.GPT")(
            openai_api_key=args.host_openai_api_key, 
            openai_api_base=args.host_openai_api_base,
            openai_model_name=args.host_openai_model_name, 
            temperature=args.host_temperature, 
            max_tokens=args.host_max_tokens,
            top_p=args.host_top_p,
            frequency_penalty=args.host_frequency_penalty,
            presence_penalty=args.host_presence_penalty
        )

        if host_info is None:
            self.system_message = \
                "你是医院的数据库管理员，负责收集、汇总和整理病人的病史和检查数据。\n"
        else: self.system_message = host_info

        super(Host, self).__init__(engine)

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument('--host_openai_api_key', type=str, help='API key for OpenAI')
        parser.add_argument('--host_openai_api_base', type=str, help='API base for OpenAI')
        parser.add_argument('--host_openai_model_name', type=str, help='API model name for OpenAI')
        parser.add_argument('--host_temperature', type=float, default=0.0, help='temperature')
        parser.add_argument('--host_max_tokens', type=int, default=16384, help='max tokens (higher for reasoning models like gpt-5-nano)')
        parser.add_argument('--host_top_p', type=float, default=1, help='top p')
        parser.add_argument('--host_frequency_penalty', type=float, default=0, help='frequency penalty')
        parser.add_argument('--host_presence_penalty', type=float, default=0, help='presence penalty')

    def memorize(self, message):
        self.memories.append(message)

    def forget(self):
        self.memories = [("system", self.system_message)]

    def speak(self, content):
        system_message = self.system_message
        
        messages = [{"role": "system", "content": system_message},
                    {"role": "user", "content": "您好，我需要做基因组测序，能否告诉我这些检查结果？"},
                    {"role": "assistant", "content": "#检查项目#\n-基因组测序: 无异常"},
                    {"role": "user", "content": content}]
        responese = self.engine.get_response(messages)
        return responese
    
    def summarize_diagnosis(self, doctors, patient):
        # build query message
        diagnosis_by_different_doctors = ""
        for i, doctor in enumerate(doctors):
            diagnosis_by_different_doctors += \
                "##医生{}##\n\n".format(doctor.name) + \
                "#诊断结果#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="诊断结果")) + \
                "#诊断依据#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="诊断依据")) + \
                "#治疗方案#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="治疗方案"))
        # build system message
        doctor_names = ["##医生{}##".format(doctor.name) for doctor in doctors]
        if len(doctor_names) > 2:
            doctor_names = "、".join(doctor_names[:-2]) + "、" + doctor_names[-2] + "和" + doctor_names[-1]
        else: doctor_names = doctor_names[0] + "和" + doctor_names[1]
        system_message = "你是一个资深的#主任医生#。\n" + \
            "你正在主持一场医生针对患者病情的会诊，参与的医生有{}。\n".format(doctor_names) + \
            "病人的基本情况如下：\n#症状#\n{}\n\n#辅助检查#\n{}\n\n".format(
                doctors[0].get_diagnosis_by_patient_id(patient.id, key="症状"),
                doctors[0].get_diagnosis_by_patient_id(patient.id, key="辅助检查")
            ) + \
            "(1) 你需要听取每个医生的诊断报告，其中包含对病人的#诊断结果#、#诊断依据#和#治疗方案#。\n" + \
            "(2) 你需要汇总每个医生的信息，给出对病人的最终诊断。\n\n" + \
            "(3) 请你按照下面的格式来进行输出。\n" + \
            "#诊断结果#\n(1) xxx\n(2) xxx\n\n" + \
            "#诊断依据#\n(1) xxx\n(2) xxx\n\n" + \
            "#治疗方案#\n(1) xxx\n(2) xxx\n"
        # run engine
        messages = [{"role": "system", "content": system_message},
            {"role": "user", "content": diagnosis_by_different_doctors}]
        diagnosis = self.engine.get_response(messages)
        return diagnosis

    def finalize_consultation(self, doctors, patient, reporter, initial_summary_result, additional_info_gathered):
        """
        Finalize the consultation by generating both symptom_and_examination AND final diagnosis together.
        This ensures that any additional information gathered during discussion is incorporated into both outputs.

        Args:
            doctors: List of doctor agents with their final diagnoses
            patient: Patient instance
            reporter: Reporter instance
            initial_summary_result: Result from get_initial_summary_from_doctors
            additional_info_gathered: List of dicts with information gathered during discussion

        Returns:
            dict with complete diagnosis including症状 and 辅助检查 as top-level keys
        """
        # Build comprehensive symptom and examination summary including all gathered info
        # Start with initial summary
        initial_summary = initial_summary_result.get('initial_summary', '')

        # Build list of all additional information
        additional_info_text = ""
        if additional_info_gathered:
            for info in additional_info_gathered:
                if info.get('type') == 'patient_query':
                    additional_info_text += f"\n\n[补充询问 - 轮次{info.get('turn', 'N/A')}]\n"
                    additional_info_text += f"问题：{info.get('query', 'N/A')}\n"
                    additional_info_text += f"患者回答：{info.get('response', 'N/A')}"

        # Get all doctors' final symptom and examination
        doctors_final_symptoms_and_exams = ""
        for i, doctor in enumerate(doctors):
            doctors_final_symptoms_and_exams += f"##医生{doctor.name}##\n"
            doctors_final_symptoms_and_exams += f"#症状#\n{doctor.get_diagnosis_by_patient_id(patient.id, key='症状')}\n\n"
            doctors_final_symptoms_and_exams += f"#辅助检查#\n{doctor.get_diagnosis_by_patient_id(patient.id, key='辅助检查')}\n\n"

        # Generate final consolidated symptom_and_examination
        doctor_names = [doctor.name for doctor in doctors]
        if len(doctor_names) > 2:
            doctor_names_str = "、".join(doctor_names[:-1]) + "和" + doctor_names[-1]
        else:
            doctor_names_str = doctor_names[0] + "和" + doctor_names[1]

        symptom_exam_messages = [
            {
                "role": "system",
                "content": f"你是一个资深的主任医生，负责主持会诊。\n"
                          f"参与的医生有{doctor_names_str}。\n\n"
                          f"会诊已经结束，现在需要生成最终的症状和辅助检查汇总。\n\n"
                          f"【重要】你需要整合以下所有信息源：\n"
                          f"(1) 医生们在初步诊断中收集的症状和检查\n"
                          f"(2) 讨论过程中向患者补充询问获得的信息\n"
                          f"(3) 医生们在讨论后更新的症状和检查记录\n\n"
                          f"请生成完整、准确的最终症状和辅助检查汇总，确保包含所有相关信息。\n\n"
                          f"请按照以下格式输出：\n"
                          f"##症状##\n(1) xxx\n(2) xxx\n\n"
                          f"##辅助检查##\n(1) xxx\n(2) xxx\n"
            },
            {
                "role": "user",
                "content": f"【初步汇总】\n{initial_summary}\n\n"
                          f"【讨论中补充询问的信息】\n{additional_info_text if additional_info_text else '无'}\n\n"
                          f"【医生们讨论后的最终记录】\n{doctors_final_symptoms_and_exams}"
            }
        ]

        final_symptom_and_examination_text = self.engine.get_response(symptom_exam_messages)

        # Generate final diagnosis (using existing method)
        final_diagnosis_text = self.summarize_diagnosis(doctors, patient)

        # Parse both into structured dicts
        symptom_exam_dict = self.parse_symptom_and_examination(final_symptom_and_examination_text)
        diagnosis_dict = self.parse_diagnosis(final_diagnosis_text)

        # Combine into single complete diagnosis dict
        complete_diagnosis = {
            "症状": symptom_exam_dict.get("症状", ""),
            "辅助检查": symptom_exam_dict.get("辅助检查", ""),
            "诊断结果": diagnosis_dict.get("诊断结果", ""),
            "诊断依据": diagnosis_dict.get("诊断依据", ""),
            "治疗方案": diagnosis_dict.get("治疗方案", "")
        }

        return complete_diagnosis

    def measure_agreement(self, doctors, patient, discussion_mode="Parallel"):
        # revise_mode in ["Parallel_with_Critique", "Parallel"]
        # build query message
        # int_to_char = {0: "A", 1: "B", 2: "C", 3: "D"}
        diagnosis_by_different_doctors = ""
        for i, doctor in enumerate(doctors):
            diagnosis_by_different_doctors += \
                "##医生{}##\n\n".format(doctor.name) + \
                "#诊断结果#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="诊断结果")) + \
                "#诊断依据#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="诊断依据")) + \
                "#治疗方案#\n{}\n\n".format(doctor.get_diagnosis_by_patient_id(patient.id, key="治疗方案")) 
        # build system message
        doctor_names = ["##医生{}##".format(doctor.name) for i, doctor in enumerate(doctors)]
        if len(doctor_names) > 2:
            doctor_names = "、".join(doctor_names[:-2]) + "、" + doctor_names[-2] + "和" + doctor_names[-1]        
        else: doctor_names = doctor_names[0] + "和" + doctor_names[1] 

        system_message = "你是一个资深的主任医生。\n" + \
            "你正在主持一场医生针对患者病情的会诊，参与的医生有{}。\n".format(doctor_names) + \
            "病人的基本情况如下：\n#症状#\n{}\n\n#辅助检查#\n{}\n\n".format(
                doctors[0].get_diagnosis_by_patient_id(patient.id, key="症状"),
                doctors[0].get_diagnosis_by_patient_id(patient.id, key="辅助检查")
            )
        system_message += "你需要听取每个医生的诊断报告，其中包含对病人的#诊断结果#、#诊断依据#和#治疗方案#。\n\n" + \
            "请判断医生们是否已达成一致。只有在以下所有条件都满足时才认为达成一致：\n" + \
            "(1) 所有医生的#诊断结果#完全相同或只有措辞差异\n" + \
            "(2) 所有医生的#诊断依据#基本一致，没有重大分歧\n" + \
            "(3) 所有医生的#治疗方案#兼容，没有冲突的建议\n\n" + \
            "如果有任何以下情况，必须输出#继续#：\n" + \
            "- 诊断结果不同（如一个说'脑梗死'，另一个说'TIA'）\n" + \
            "- 诊断依据有重大差异或矛盾\n" + \
            "- 治疗方案有冲突（如一个说手术，另一个说保守治疗）\n" + \
            "- 诊断还不够明确，需要进一步讨论\n\n" + \
            "请你按照下面的格式来进行输出。\n" + \
            "(1) 如果医生之间已经完全达成一致，请你输出：\n" + \
            "#结束#\n\n" + \
            "(2) 如果医生之间没有完全达成一致，请你输出：\n" + \
            "#继续#"
        # run engine
        messages = [{"role": "system", "content": system_message},
            {"role": "user", "content": diagnosis_by_different_doctors}]
        judgement = self.engine.get_response(messages)
        # parse response
        if "#结束#" in judgement:
            judgement = "#结束#"
            return judgement
        elif "#继续#" in judgement:
            if discussion_mode == "Parallel":
                judgement = "#继续#"
                return judgement
            elif discussion_mode == "Parallel_with_Critique":
                system_message = "你是一个资深的主任医生。\n" + \
                    "你正在主持一场医生针对患者病情的会诊，参与的医生有{}。\n".format(doctor_names) + \
                    "病人的基本情况如下：\n#症状#\n{}\n\n#辅助检查#\n{}\n\n".format(
                        doctors[0].get_diagnosis_by_patient_id(patient.id, key="症状"),
                        doctors[0].get_diagnosis_by_patient_id(patient.id, key="辅助检查")
                    )
                system_message += "(1) 你需要听取每个医生的诊断报告，其中包含对病人的#诊断结果#、#诊断依据#和#治疗方案#。\n" + \
                    "(2) 请你按照重要性列出最多3个需要讨论的争议点，按照下面的格式输出：\n" + \
                    "(a) xxx\n" + \
                    "(b) xxx\n"
                messages = [{"role": "system", "content": system_message},
                    {"role": "user", "content": diagnosis_by_different_doctors}]
                judgement = self.engine.get_response(messages)
                judgement = re.sub(r'.*\(a\)', '(a)', judgement, flags=re.DOTALL)
                return judgement
        else: raise Exception("{}".format(judgement))
        
    def get_initial_summary_from_doctors(self, doctors, patient):
        """
        Phase 1: Get initial summary based ONLY on doctors' diagnoses.
        Host should NOT access patient dataset directly.
        Host identifies inconsistencies and decides whether to ask patient for clarification.

        Args:
            doctors: List of doctor agents
            patient: Patient instance (only used for ID, not medical records)

        Returns:
            dict with keys:
                - initial_summary: merged symptoms and examinations from doctors
                - inconsistencies: description of inconsistencies found (if any)
                - query_to_patient: question to ask patient (if needed)
        """
        # Build query message from doctors' diagnoses ONLY
        symptom_and_examination_by_diff_doctors = ""
        for i, doctor in enumerate(doctors):
            symptom_and_examination_by_diff_doctors += "##医生{}##\n".format(doctor.name)
            for key in ["症状", "辅助检查"]:
                value = doctor.get_diagnosis_by_patient_id(patient.id, key=key)
                if value is not None:
                    symptom_and_examination_by_diff_doctors += "#{}#\n{}\n\n".format(key, value)

        doctor_names = ["医生{}".format(doctor.name) for doctor in doctors]
        if len(doctor_names) > 2:
            doctor_names = "、".join(doctor_names[:-2]) + "、" + doctor_names[-2] + "和" + doctor_names[-1]
        else:
            doctor_names = doctor_names[0] + "和" + doctor_names[1]

        # Phase 1: Get initial summary and identify inconsistencies
        messages = [
            {
                "role": "system",
                "content": "你是一个资深的主任医生，负责主持会诊。\n" + \
                    "你正在主持一场医生针对患者病情的会诊，参与的有{}。\n".format(doctor_names) + \
                    "【重要】你只能使用医生们提供的信息，不能直接查看患者病历或检查结果。\n\n" + \
                    "你的任务：\n" + \
                    "(1) 汇总所有医生提到的#症状#和#辅助检查#信息\n" + \
                    "(2) 识别医生之间的一致信息和不一致信息\n" + \
                    "(3) 如果存在不一致或遗漏，决定是否需要向患者询问\n\n" + \
                    "请按照以下格式输出：\n" + \
                    "#初步汇总#\n" + \
                    "##症状##\n(1) xxx\n(2) xxx\n\n" + \
                    "##辅助检查##\n(1) xxx\n(2) xxx\n\n" + \
                    "#一致性分析#\n" + \
                    "[描述医生之间的一致之处和不一致之处。如果所有信息一致，输出\"医生们的信息完全一致\"]\n\n" + \
                    "#是否需要询问患者#\n" + \
                    "[如果需要询问患者以澄清不一致或补充信息，输出具体问题；如果不需要，输出\"不需要\"]\n"
            },
            {"role": "user", "content": symptom_and_examination_by_diff_doctors},
        ]

        response = self.engine.get_response(messages)

        # Parse response
        initial_summary = ""
        inconsistencies = ""
        query_to_patient = None

        response = response.strip() + '\n\n'

        # Extract initial summary
        summary_match = re.findall(r"#初步汇总#(.*?)(?:#一致性分析#|$)", response, re.S)
        if summary_match:
            initial_summary = summary_match[0].strip()

        # Extract inconsistencies analysis
        inconsistencies_match = re.findall(r"#一致性分析#(.*?)(?:#是否需要询问患者#|$)", response, re.S)
        if inconsistencies_match:
            inconsistencies = inconsistencies_match[0].strip()
            if "完全一致" in inconsistencies or "没有不一致" in inconsistencies:
                inconsistencies = None

        # Extract query to patient
        query_match = re.findall(r"#是否需要询问患者#(.*?)(?:#|$)", response, re.S)
        if query_match:
            query_text = query_match[0].strip()
            if "不需要" not in query_text and len(query_text) > 5:
                query_to_patient = query_text

        return {
            "initial_summary": initial_summary if initial_summary else response,
            "inconsistencies": inconsistencies,
            "query_to_patient": query_to_patient,
            "raw_response": response
        }

    def finalize_symptom_and_examination(self, doctors, patient, initial_summary_result, reporter):
        """
        Phase 1 finalization: Query patient if needed, then finalize symptom and examination summary.

        Args:
            doctors: List of doctor agents
            patient: Patient instance
            initial_summary_result: Result from get_initial_summary_from_doctors
            reporter: Reporter instance (only used if examination clarification needed)

        Returns:
            Final symptom_and_examination string
        """
        # If no patient query needed, return initial summary
        if not initial_summary_result.get('query_to_patient'):
            # Extract and format the symptom and examination
            summary_text = initial_summary_result['initial_summary']

            # Try to extract structured format
            symptom_match = re.findall(r"##症状##(.*?)(?:##辅助检查##|$)", summary_text, re.S)
            exam_match = re.findall(r"##辅助检查##(.*?)(?:##|$)", summary_text, re.S)

            if symptom_match and exam_match:
                return "##症状##\n{}\n\n##辅助检查##\n{}".format(
                    symptom_match[0].strip(), exam_match[0].strip())
            else:
                return summary_text

        # Query patient for clarification
        patient_response = patient.speak(
            role="医生",
            content=initial_summary_result['query_to_patient'],
            save_to_memory=False)

        # Integrate patient's response into the summary
        messages = [
            {
                "role": "system",
                "content": "你是一个资深的主任医生。\n" + \
                    "根据患者的回答，修正和完善症状和辅助检查的汇总。\n\n" + \
                    "请按照以下格式输出：\n" + \
                    "##症状##\n(1) xxx\n(2) xxx\n\n" + \
                    "##辅助检查##\n(1) xxx\n(2) xxx\n"
            },
            {
                "role": "user",
                "content": "初步汇总：\n{}\n\n向患者询问的问题：\n{}\n\n患者的回答：\n{}".format(
                    initial_summary_result['initial_summary'],
                    initial_summary_result['query_to_patient'],
                    patient_response
                )
            }
        ]

        final_summary = self.engine.get_response(messages)
        return final_summary

    def summarize_symptom_and_examination_DEPRECATED(self, doctors, patient, reporter):
        """
        DEPRECATED: This old method is kept for reference but should NOT be used.
        Use get_initial_summary_from_doctors() and finalize_symptom_and_examination() instead.

        This method had a data leakage bug where it accessed patient.medical_records directly.
        """
        raise NotImplementedError(
            "This method is deprecated. Use get_initial_summary_from_doctors() and "
            "finalize_symptom_and_examination() instead to prevent data leakage."
        )
        ## host summarizes the symptom and examination from different doctors
        # build query message
        symptom_and_examination_by_diff_doctors = ""
        for i, doctor in enumerate(doctors):
            symptom_and_examination_by_diff_doctors += "##医生{}##\n".format(doctor.name)
            for key in ["症状", "辅助检查"]:
                value = doctor.get_diagnosis_by_patient_id(patient.id, key=key)
                if value is not None:
                    symptom_and_examination_by_diff_doctors += "#{}#\n{}\n\n".format(key, value)

        doctor_names = ["##医生{}##".format(doctor.name) for doctor in doctors]
        if len(doctor_names) > 2:
            doctor_names = "、".join(doctor_names[:-2]) + "、" + doctor_names[-2] + "和" + doctor_names[-1]
        else: doctor_names = doctor_names[0] + "和" + doctor_names[1]   
        messages = [
            {
            "role": "system",
            "content": "你是一个资深的主任医生。\n" + \
                "你正在主持一场医生针对患者病情的会诊，参与的有{}。".format(doctor_names) + \
                "你需要听取每个医生的诊断报告，总结患者的症状并汇总检查结果。\n\n" + \
                    "(1) 每个医生说话时都会以##xx##开始。例如，##医生A##开始讲话时，则会出现##医生A##的字样。每个医生的诊断报告当中都会包含#症状#和#辅助检查#。\n" + \
                    "(2) 请你汇总医生们掌握的#症状#和#辅助检查#的信息，无论是医生们都提及的信息，还是某个医生提及而其他医生遗漏的信息。\n" + \
                    "(3) 如果不同医生提供的信息存在相互矛盾的部分，请按照下面的方式指出来。\n" + \
                        "(3.1) 如果是#症状#上的不一致，请向病人询问，以#询问病人#开头。\n" + \
                        "(3.2) 如果是#辅助检查#，请向检查员询问，以#询问检查员#开头。\n" + \
                        "(3.3) 如果没有问题，则输出“无”。\n\n" + \
                    "请你按照下面的格式来进行输出。\n" + \
                        "#症状#\n(1) xx\n(2) xx\n\n" + \
                        "#询问病人#\n(1) xx\n(2) xx\n\n" + \
                        "#辅助检查#\n(1) xx\n(2) xx\n\n" + \
                        "#询问检查员#\n(1) xx\n(2) xx\n"
            },
            # {
            # "role": "user",
            # "content": "##医生A##\n#症状#\n(1) 发烧，体温时高时低，最高达到39度\n(2) 咳嗽，有痰\n(3) 头痛\n(4) 感到冷\n(5) 晕眩\n(6) 全身乏力\n(7) 食欲不振\n(8) 睡眠不好\n\n#辅助检查#\n(1) 血常规：\n   - 白细胞计数：10.02×10^9/L（升高）\n   - 血小板计数：366×10^9/L（升高）\n   - 红细胞计数：4.98×10^12/L\n   - 血红蛋白：134g/L\n(2) 胸部X光：心肺膈未见异常\n\n##医生B##\n#症状#\n(1)发烧，体温时高时低\n(2)感到冷\n(3)头痛得厉害，有时候会晕\n(4)咳嗽，咳出来的痰很多\n(5)全身没劲儿\n(6)吃不下饭\n(7)睡不好觉\n\n#辅助检查#\n(1)全血细胞计数（CBC）显示白细胞计数10.02×10^9/L（升高），血小板计数366×10^9/L（升高）\n(2)痰液培养无异常\n(3)胸部X光检查心肺膈未见异常"
            # },
            # {
            # "role": "assistant",
            # "content": "#症状#\n(1) 发烧，体温时高时低，最高达到39度\n(2) 咳嗽，有痰\n(3) 头痛\n(4) 感到冷\n(5) 晕眩\n(6) 全身乏力\n(7) 食欲不振\n(8) 睡眠不好\n\n#询问病人#\n无\n\n#辅助检查#\n(1) 血常规：\n   - 白细胞计数：10.02×10^9/L（升高）\n   - 血小板计数：366×10^9/L（升高）\n   - 红细胞计数：4.98×10^12/L\n   - 血红蛋白：134g/L\n(2) 痰液培养无异常\n(3) 胸部X光：心肺膈未见异常\n\n#询问检查员#\n无"
            # },
            {"role": "user", "content": "{}".format(symptom_and_examination_by_diff_doctors)},
        ]
        responese = self.engine.get_response(messages)
        structure_result = self.parse_symptom_and_examination(responese)
        if structure_result.get("query_to_patient") is None and \
                structure_result.get("query_to_reporter") is None:
            return structure_result.get("symptom_and_examination")
        ## host asks patient and reporter to edit the symptom and examination 
        # if some misalignments exist among different doctos
        if structure_result.get("query_to_patient") is not None:
            # role, content, save_to_memory=True
            structure_result["patient_response"] = patient.speak(
                role="医生", content=structure_result.get("query_to_patient"), save_to_memory=False)
        if structure_result.get("query_to_reporter") is not None:
            structure_result["reporter_response"] = reporter.speak(
                patient.medical_records, structure_result.get("query_to_reporter"), save_to_memory=False)
        # edit the symptom and examination accoring to the response from patient and reporter
        symptom_and_examination = self.edit_symptom_and_examination(structure_result)
        return symptom_and_examination
    
    def parse_symptom_and_examination(self, response):
        values = {}
        response = response.strip() + '\n\n'
        for key in ["症状", "辅助检查", "询问病人", "询问检查员"]:
            value = re.findall(r"\#{}\#(.*?)\n\n".format(key), response, re.S)
            if len(value) >= 1:
                value = value[0]
                value = re.sub(r"\#{}\#".format(key), '', value)
                value = re.sub(r"\#", '', value)
                value = value.strip()
                values[key] = value
            else:
                if key in ["症状", "辅助检查"]:
                    # Try alternative format with ## markers
                    value = re.findall(r"\#\#{}\#\#(.*?)(?:\#\#|$)".format(key), response, re.S)
                    if len(value) >= 1:
                        values[key] = value[0].strip()
                    else:
                        values[key] = ""

        symptom_and_examination = "##症状##\n{}\n\n##辅助检查##\n{}".format(
            values.get("症状", ""), values.get("辅助检查", ""))
        query_to_patient = values.get("询问病人")
        query_to_reporter = values.get("询问检查员")

        if query_to_patient is None or len(query_to_patient) < 5:
            query_to_patient = None
        else: query_to_patient = query_to_patient.strip()

        if query_to_reporter is None or len(query_to_reporter) < 5:
            query_to_reporter = None
        else: query_to_reporter = query_to_reporter.strip()

        structure_result = {
            "symptom_and_examination": symptom_and_examination,
            "症状": values.get("症状", ""),
            "辅助检查": values.get("辅助检查", ""),
            "query_to_patient": query_to_patient,
            "query_to_reporter": query_to_reporter
        }
        return structure_result

    def parse_diagnosis(self, response):
        """Parse diagnosis response into structured dict format"""
        values = {}
        response = response.strip() + '\n\n'

        # Extract each diagnosis section
        for key in ["诊断结果", "诊断依据", "治疗方案"]:
            value = re.findall(r"\#{}\#(.*?)(?:\#|$)".format(key), response, re.S)
            if len(value) >= 1:
                value = value[0]
                value = re.sub(r"\#{}\#".format(key), '', value)
                value = value.strip()
                # Remove any trailing markers
                value = re.sub(r'<诊断完成>\s*$', '', value).strip()
                values[key] = value
            else:
                values[key] = ""

        return values

    def parse_symptom_and_examination_DEPRECATED(self, response):
        values = {}
        response = response.strip() + '\n\n'
        for key in ["症状", "辅助检查", "询问病人", "询问检查员"]:
            value = re.findall(r"\#{}\#(.*?)\n\n".format(key), response, re.S)
            if len(value) >= 1:
                value = value[0]
                value = re.sub(r"\#{}\#".format(key), '', value)
                value = re.sub(r"\#", '', value)
                value = value.strip()
                values[key] = value
            else:
                if key in ["症状", "辅助检查"]:
                    raise Exception("{}".format(response))

        symptom_and_examination = "##症状##\n{}\n\n##辅助检查##\n{}".format(
            values.get("症状"), values.get("辅助检查"))        
        query_to_patient = values.get("询问病人")
        query_to_reporter = values.get("询问检查员")

        if query_to_patient is None or len(query_to_patient) < 5:
            query_to_patient = None
        else: query_to_patient = query_to_patient.strip()

        if query_to_reporter is None or len(query_to_reporter) < 5:
            query_to_reporter = None
        else: query_to_reporter = query_to_reporter.strip()

        structure_result = {
            "symptom_and_examination": symptom_and_examination,
            "query_to_patient": query_to_patient,
            "query_to_reporter": query_to_reporter
        }
        return structure_result

    def edit_symptom_and_examination(self, structure_result):
        # build system message for different situations
        if structure_result.get("query_to_patient") is not None and structure_result.get("query_to_doctor") is not None:
            system_message = "你是一个资深的主任医生。\n" + \
                "你现在需要根据##询问病人##中的#问题#与#回答#，来修正病人##症状##中的歧义与错误。" + \
                "然后根据##询问检查员##中的#问题#与#回答#，来修正病人##辅助检查##中的歧义与错误。\n\n" + \
                "请你按照下面的格式来进行输出。\n#症状#\n(1) xx\n(2) xx\n\n#辅助检查#\n(1) xx\n(2) xx\n"
        elif structure_result.get("query_to_patient") is not None:
            system_message = "你是一个资深的主任医生。\n" + \
                "你现在需要根据##询问病人##中的#问题#与#回答#，来修正病人##症状##中的歧义与错误。\n\n" + \
                "请你按照下面的格式来进行输出。\n#症状#\n(1) xx\n(2) xx\n\n#辅助检查#\n(1) xx\n(2) xx\n"
        elif structure_result.get("query_to_reporter") is not None:
            system_message = "你是一个资深的主任医生。\n" + \
                "你现在需要根据##询问检查员##中的#问题#与#回答#，来修正病人##辅助检查##中的歧义与错误。\n\n" + \
                "请你按照下面的格式来进行输出。\n#症状#\n(1) xx\n(2) xx\n\n#辅助检查#\n(1) xx\n(2) xx\n"
        # build content for user in different situations
        content = "{}\n\n".format(structure_result.get("symptom_and_examination").strip())
        if structure_result.get("query_to_patient") is not None:
            content += "##询问病人##\n#问题#\n{}\n#回答#\n{}\n\n".format(
                structure_result.get("query_to_patient"), structure_result["patient_response"])
        if structure_result.get("query_to_reporter") is not None:
            content += "##询问检查员##\n#问题#\n{}\n#回答#\n{}".format(
                structure_result.get("query_to_repoter"), structure_result["reporter_response"])
        # run engine
        messages = [{"role": "system", "content": system_message},
            {"role": "user", "content": content}]
        symptom_and_examination = self.engine.get_response(messages)
        return symptom_and_examination

    def _build_diagnosis_summary(self, doctors, patient_id):
        """
        Build a summary of all doctors' current diagnoses for analysis.

        Args:
            doctors: List of doctor agents
            patient_id: ID of the patient being discussed

        Returns:
            Formatted string with all diagnoses
        """
        diagnosis_summary = ""
        for i, doctor in enumerate(doctors):
            diagnosis_summary += "##医生{}##\n\n".format(doctor.name)
            diagnosis_summary += "#诊断结果#\n{}\n\n".format(
                doctor.get_diagnosis_by_patient_id(patient_id, key="诊断结果"))
            diagnosis_summary += "#诊断依据#\n{}\n\n".format(
                doctor.get_diagnosis_by_patient_id(patient_id, key="诊断依据"))
            diagnosis_summary += "#治疗方案#\n{}\n\n".format(
                doctor.get_diagnosis_by_patient_id(patient_id, key="治疗方案"))
        return diagnosis_summary

    def _parse_host_decision(self, response):
        """
        Parse host's decision response from LLM.

        Returns:
            dict with keys: action, reason, query, target
        """
        decision = {
            "action": "continue_discussion",
            "reason": "",
            "query": "",
            "target": ""
        }

        response = response.strip()

        # Parse action
        if "询问患者" in response or "查询患者" in response:
            decision["action"] = "query_patient"
            decision["target"] = "patient"
        elif "结束诊断" in response or "结束" in response or "可以得出最终诊断" in response:
            decision["action"] = "finalize"
        else:
            decision["action"] = "continue_discussion"

        # Extract reason (between #理由# markers)
        reason_match = re.findall(r"#理由#(.*?)(?=#|$)", response, re.S)
        if reason_match:
            decision["reason"] = reason_match[0].strip()

        # Extract query (between #问题# markers)
        query_match = re.findall(r"#问题#(.*?)(?=#|$)", response, re.S)
        if query_match:
            decision["query"] = query_match[0].strip()

        return decision

    def analyze_discussion_state(self, doctors, patient, reporter):
        """
        Analyzes current discussion state and decides next action.

        Determines whether host should:
        - Query patient for clarification or new symptoms
        - Request new examinations from reporter
        - Continue discussion among doctors
        - Finalize diagnosis

        Args:
            doctors: List of doctor agents
            patient: Patient agent instance
            reporter: Reporter agent instance

        Returns:
            dict with keys:
                "action": "query_patient" | "request_exam" | "continue_discussion" | "finalize"
                "reason": explanation of decision
                "query": question to ask (if action is query/request)
                "target": "patient" | "reporter" (if action is query/request)
        """
        # Build diagnosis summary
        diagnosis_summary = self._build_diagnosis_summary(doctors, patient.id)

        # Get doctor names
        doctor_names = [doctor.name for doctor in doctors]
        if len(doctor_names) > 2:
            doctor_names_str = "、".join(doctor_names[:-1]) + "和" + doctor_names[-1]
        else:
            doctor_names_str = doctor_names[0] + "和" + doctor_names[1]

        # Build analysis prompt
        analysis_prompt = f"""你是会诊主持人。请分析当前诊断情况，决定下一步行动。

参与会诊的医生有：{doctor_names_str}

当前所有医生的诊断：
{diagnosis_summary}

患者的症状：
{doctors[0].get_diagnosis_by_patient_id(patient.id, key="症状")}

患者的辅助检查：
{doctors[0].get_diagnosis_by_patient_id(patient.id, key="辅助检查")}

【重要规则】
1. 你只能向患者询问，不能要求新的检查。检查只能由各位医生在他们与患者的初步诊断阶段完成。
2. 【限制】每次向患者询问时，最多只能问1-3个问题。请优先选择最关键、最能帮助医生达成一致诊断的问题。

请判断：
1. 是否存在诊断冲突？
2. 医生们的诊断中是否有矛盾或不一致的地方？
3. 是否有关键症状信息不清楚，需要向患者确认？
4. 是否可以得出最终诊断？

请选择一个行动：
- 如果需要询问患者以澄清症状、确认病史、或获取医生遗漏的信息，返回：行动=询问患者，问题=[1-3个具体问题，按优先级排序]
- 如果需要继续让医生讨论但不需要新信息，返回：行动=继续讨论
- 如果可以得出最终诊断（医生们已基本达成一致），返回：行动=结束诊断

【禁止】
- 不要问超过3个问题
- 不要说"行动=要求检查"或要求新的检查项目

按照以下格式返回：

#理由#
[你的分析和理由，说明为什么选择这些问题]

#行动#
[行动类型：询问患者 / 继续讨论 / 结束诊断]

#问题#
[如果选择询问患者，写出1-3个最关键的问题，每行一个问题，用"- "开头]
"""

        # Get host's decision from LLM
        response = self.engine.get_response([
            {"role": "system", "content": "你是一个资深的会诊主持医生。"},
            {"role": "user", "content": analysis_prompt}
        ])

        # Parse response
        decision = self._parse_host_decision(response)

        return decision
