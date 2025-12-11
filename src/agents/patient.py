from .base_agent import Agent
from utils.register import register_class, registry


@register_class(alias="Agent.Patient.GPT")
class Patient(Agent):
    def __init__(self, args, patient_profile, medical_records, patient_id=0):
        engine = registry.get_class("Engine.GPT")(
            openai_api_key=args.patient_openai_api_key, 
            openai_api_base=args.patient_openai_api_base,
            openai_model_name=args.patient_openai_model_name, 
            temperature=args.patient_temperature, 
            max_tokens=args.patient_max_tokens,
            top_p=args.patient_top_p,
            frequency_penalty=args.patient_frequency_penalty,
            presence_penalty=args.patient_presence_penalty
        )
        self.system_message = "你是一个病人。这是你的基本资料。\n" + \
            "{}\n".format(patient_profile)

        if "现病史" in medical_records:
            self.system_message += "<现病史> {}\n".format(medical_records["现病史"].strip())        
        if "既往史" in medical_records:
            self.system_message += "<既往史> {}\n".format(medical_records["既往史"].strip())
        if "个人史" in medical_records:
            self.system_message += "<个人史> {}\n".format(medical_records["个人史"].strip())
        self.system_message += "\n"

        self.system_message += \
            "下面会有<医生>来对你的身体状况进行诊断，你需要：\n" + \
            "(1) 按照病历和基本资料的设定进行对话。\n" + \
            "(2) 在每次对话时，你都要明确对话的对象是<医生>还是<检查员>。当你对医生说话时，你要在句子开头说<对医生讲>；如果对象是<检查员>，你要在句子开头说<对检查员讲>。\n" + \
            "(3) 每次回复只能对一个对象说话，不要在同一次回复中同时对医生和检查员说话。\n" + \
            "(4) 首先按照主诉进行回复。\n" + \
            "(5) 当<医生>询问你的现病史、既往史、个人史时，要按照相关内容进行回复。\n" + \
            "(6) 当<医生>提到要做检查时（如'让我们做XXX检查'、'需要做XXX检查'），你的下一次回复必须是向<检查员>询问这些检查结果。例如：<对检查员讲> 医生让我做XXX检查，结果是什么？不要说'我去做检查'或'我安排检查'，而是直接问检查员要结果。\n" + \
            "(7) 从<检查员>那里收到检查结果后，在下一次回复中将结果简要复述给<医生>。\n" + \
            "(8) 【重要】当医生给出诊断和治疗建议时：\n" + \
            "    - 只需简单表示理解或感谢：'好的，谢谢医生' 或 '明白了，我会照做的'\n" + \
            "    - 【严禁】不要重复医生说的治疗方案或医学术语\n" + \
            "    - 【严禁】不要说'我会按你们的计划执行：...（然后列举一大堆医学细节）'\n" + \
            "    - 【严禁】不要像医学生一样复述药物名称、剂量、用法\n" + \
            "    - 【严禁】普通患者听不懂也记不住那么多专业内容，只会简单点头\n\n" + \
            "## 重要：说话方式（必须遵守）\n" + \
            "你是普通患者，没有医学背景，说话要符合这个身份：\n\n" + \
            "❌ 禁止主动、详细地汇报其他医院的检查结果，除非医生明确问'之前做过什么检查'\n" + \
            "❌ 禁止使用医学术语，要用老百姓的大白话（如'脖子肿了'而不是'颈部肿物'、'头晕'而不是'眩晕'）\n" + \
            "❌ 禁止像医学生或医生助手那样有条理地列举症状\n" + \
            "❌ 禁止显得比医生还专业，不要主动提供医学分析或诊断建议\n" + \
            "❌ 禁止复述医生的治疗方案，普通人记不住那么多专业内容\n" + \
            "❌ 禁止使用编号 1. 2. 3. 或项目符号 - •\n" + \
            "❌ 禁止说得太全面、太系统，普通人不会这样说话\n\n" + \
            "✅ 正确方式：\n" + \
            "- 说话零散、口语化，像和朋友聊天：'我从昨天开始就头痛，还有点发烧，嘴巴很干'\n" + \
            "- 可能遗漏细节，需要医生追问才想起来\n" + \
            "- 用简单、朴素的词汇，不要太书面化\n" + \
            "- 回答简短自然，不要像写病历一样详细\n" + \
            "- 对医学不了解，可能说不清楚具体位置或症状特点\n" + \
            "- 医生说完治疗方案后，只说'好的'、'明白了'、'谢谢医生'，不要重复复杂的医学内容\n\n" + \
            "你必须像真实病人一样口语化地说话，严禁使用以下格式：\n" + \
            "❌ 禁止使用编号：1. 2. 3. 或 (1) (2) (3)\n" + \
            "❌ 禁止使用项目符号：- 或 •\n" + \
            "❌ 禁止列清单式的回答\n" + \
            "❌ 禁止使用正式文档格式\n" + \
            "✅ 正确：用自然的句子连接，像正常人说话一样。例如：'我从昨天开始就头痛，还有点发烧，大概38度多。嘴巴很干，便秘。'\n" + \
            "✅ 病人是普通人，说话简单直白，不会像医生那样组织严谨，会有口语化的表达。"
    
        super(Patient, self).__init__(engine)
        self.id = patient_id
        self.profile = patient_profile
        self.medical_records = medical_records

    @staticmethod
    def add_parser_args(parser):
        # group = parser.add_argument_group('Agent.Patient.GPT Arguments')
        parser.add_argument('--patient_openai_api_key', type=str, help='API key for OpenAI')
        parser.add_argument('--patient_openai_api_base', type=str, help='API base for OpenAI')
        parser.add_argument('--patient_openai_model_name', type=str, help='API model name for OpenAI')
        parser.add_argument('--patient_temperature', type=float, default=0.0, help='temperature')
        parser.add_argument('--patient_max_tokens', type=int, default=16384, help='max tokens (higher for reasoning models like gpt-5-nano)')
        parser.add_argument('--patient_top_p', type=float, default=1, help='top p')
        parser.add_argument('--patient_frequency_penalty', type=float, default=0, help='frequency penalty')
        parser.add_argument('--patient_presence_penalty', type=float, default=0, help='presence penalty')

    def speak(self, role, content, save_to_memory=True):
        messages = [{"role": memory[0], "content": memory[1]} for memory in self.memories]
        messages.append({"role": "user", "content": f"<{role}> {content}"})

        responese = self.engine.get_response(messages)
        
        if save_to_memory:
            self.memorize(("user", f"<{role}> {content}"))
            self.memorize(("assistant", responese))

        return responese
    
    @staticmethod
    def parse_role_content(responese):
        """
        Parse patient response to determine who they're speaking to.

        Returns:
            If single target: (speak_to, content)
            If dual target: ("双向", {"reporter": content1, "doctor": content2})
        """
        responese = responese.strip()

        # Check if response contains BOTH tags (patient addressing both reporter and doctor)
        if "<对检查员讲>" in responese and "<对医生讲>" in responese:
            # Extract both parts
            parts = responese.split("<对检查员讲>")
            before_reporter = parts[0].strip()
            after_reporter = parts[1] if len(parts) > 1 else ""

            # Further split by doctor tag
            if "<对医生讲>" in after_reporter:
                reporter_and_doctor = after_reporter.split("<对医生讲>")
                reporter_content = reporter_and_doctor[0].strip()
                doctor_content = reporter_and_doctor[1].strip() if len(reporter_and_doctor) > 1 else ""
            elif "<对医生讲>" in before_reporter:
                doctor_and_reporter = before_reporter.split("<对医生讲>")
                doctor_content = doctor_and_reporter[1].strip() if len(doctor_and_reporter) > 1 else ""
                reporter_content = after_reporter.strip()
            else:
                reporter_content = after_reporter.strip()
                doctor_content = ""

            return "双向", {"reporter": reporter_content, "doctor": doctor_content}

        # Check if response contains ONLY <对检查员讲> (patient asking reporter for exams)
        elif "<对检查员讲>" in responese:
            speak_to = "检查员"
            responese = responese.replace("<对检查员讲>", "").strip()
        # Default to speaking to doctor
        else:
            speak_to = "医生"
            responese = responese.replace("<对医生讲>", "").strip()

        return speak_to, responese
