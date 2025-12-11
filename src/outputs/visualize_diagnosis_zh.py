#!/usr/bin/env python3
"""
诊断历史可视化工具（中文版）
读取 JSONL 日志文件并生成交互式 HTML 可视化
"""

import json
import argparse
import re
import base64
from pathlib import Path


def load_icon_as_base64(icon_path):
    """Load an icon file and convert it to base64 data URI"""
    try:
        with open(icon_path, 'rb') as f:
            icon_data = base64.b64encode(f.read()).decode('utf-8')
            return f'data:image/png;base64,{icon_data}'
    except FileNotFoundError:
        print(f"Warning: Icon file not found: {icon_path}")
        return ''


def clean_content(content):
    """Remove conversation markers and format content"""
    # Remove markers like <对医生讲>, <对检查员讲>, etc.
    content = re.sub(r'<对.*?讲>\s*', '', content)
    # Remove #检查项目# header
    content = re.sub(r'#检查项目#\s*', '', content)
    # Remove <诊断完成> marker
    content = re.sub(r'<诊断完成>\s*$', '', content)
    return content.strip()


def is_diagnosis_turn(content):
    """Check if this turn contains the diagnosis"""
    markers = ['#症状#', '#辅助检查#', '#诊断结果#', '#诊断依据#', '#治疗方案#']
    return any(marker in content for marker in markers)


def format_message_flow(role, recipient, content, icons):
    """Format message with visual flow indicators"""
    cleaned_text = clean_content(content)

    # Detect if this is a request to reporter/exam
    if role == 'Patient' and recipient == 'Reporter':
        return f'<img src="{icons["patient"]}" class="inline-icon"> 患者 → <img src="{icons["reporter"]}" class="inline-icon"> 检查员', cleaned_text
    elif role == 'Patient' and recipient == 'Doctor':
        return f'<img src="{icons["patient"]}" class="inline-icon"> 患者 → <img src="{icons["doctor"]}" class="inline-icon"> 医生', cleaned_text
    elif role == 'Doctor' and recipient == 'Patient':
        return f'<img src="{icons["doctor"]}" class="inline-icon"> 医生 → <img src="{icons["patient"]}" class="inline-icon"> 患者', cleaned_text
    elif role == 'Reporter':
        return f'<img src="{icons["reporter"]}" class="inline-icon"> 检查员', cleaned_text
    else:
        return f'{role}', cleaned_text


def generate_html(jsonl_file, output_html):
    """Generate an interactive HTML visualization from JSONL diagnosis log"""

    # Load icons as base64 data URIs
    icons_dir = Path(__file__).parent / 'icons'
    icons = {
        'diagnose': load_icon_as_base64(icons_dir / 'icon_diagnose-removebg-preview.png'),
        'doctor': load_icon_as_base64(icons_dir / 'icon_doctor-removebg-preview.png'),
        'patient': load_icon_as_base64(icons_dir / 'icon_patient-removebg-preview.png'),
        'host': load_icon_as_base64(icons_dir / 'icon_host-removebg-preview.png'),
        'reporter': load_icon_as_base64(icons_dir / 'icon_reporter-removebg-preview.png'),
        'collaborate': load_icon_as_base64(icons_dir / 'icon_collaborate-removebg-preview.png'),
    }

    # Read all patient records
    records = []
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    # Generate color palette for doctors
    doctor_colors = [
        '#667eea',  # Purple
        '#f093fb',  # Pink
        '#4facfe',  # Blue
        '#43e97b',  # Green
        '#fa709a',  # Rose
        '#30cfd0',  # Cyan
        '#a8edea',  # Mint
        '#feca57',  # Yellow
    ]

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 医院多智能体协同诊疗系统</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .stats {{
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 20px;
            font-size: 1.1em;
        }}

        .stat-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        .stat-number {{
            font-size: 2em;
            font-weight: bold;
        }}

        .navigation {{
            background: #f8f9fa;
            padding: 20px;
            border-bottom: 2px solid #e0e0e0;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        .nav-tabs {{
            display: flex;
            gap: 15px;
            align-items: center;
            justify-content: center;
            margin-bottom: 15px;
        }}

        .tab-button {{
            padding: 10px 25px;
            background: white;
            border: 2px solid #667eea;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1em;
            color: #667eea;
            font-weight: bold;
            transition: all 0.3s;
        }}

        .tab-button:hover {{
            background: #667eea;
            color: white;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        }}

        .tab-button.active {{
            background: #667eea;
            color: white;
        }}

        .patient-selector {{
            display: flex;
            gap: 15px;
            align-items: center;
            justify-content: center;
        }}

        .patient-selector label {{
            font-weight: bold;
            color: #667eea;
            font-size: 1em;
        }}

        .patient-dropdown {{
            padding: 10px 15px;
            background: white;
            border: 2px solid #667eea;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1em;
            color: #333;
            min-width: 200px;
            transition: all 0.3s;
        }}

        .patient-dropdown:hover {{
            border-color: #764ba2;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        }}

        .patient-dropdown:focus {{
            outline: none;
            border-color: #764ba2;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
        }}

        .content {{
            padding: 30px;
        }}

        .patient-record {{
            display: none;
        }}

        .patient-record.active {{
            display: block;
            animation: fadeIn 0.5s;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .section {{
            margin-bottom: 30px;
            background: #f8f9fa;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #e0e0e0;
        }}

        .section-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: bold;
            font-size: 1.1em;
        }}

        .section-header:hover {{
            opacity: 0.9;
        }}

        .section-content {{
            padding: 20px;
            background: white;
        }}

        .section-content.collapsed {{
            display: none;
        }}

        .toggle-icon {{
            transition: transform 0.3s;
        }}

        .toggle-icon.collapsed {{
            transform: rotate(-90deg);
        }}

        .doctor-consultation {{
            margin-bottom: 25px;
            border: 2px solid #667eea;
            border-radius: 8px;
            overflow: hidden;
        }}

        .doctor-header {{
            background: #667eea;
            color: white;
            padding: 12px 20px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
        }}

        .dialog-turn {{
            padding: 15px;
            border-bottom: 1px solid #e0e0e0;
        }}

        .dialog-turn:last-child {{
            border-bottom: none;
        }}

        .role-doctor {{
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
        }}

        .role-patient {{
            background: #fff3e0;
            border-left: 4px solid #ff9800;
        }}

        .role-reporter {{
            background: #f3e5f5;
            border-left: 4px solid #9c27b0;
        }}

        .message-flow {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
            padding: 8px 12px;
            background: rgba(102, 126, 234, 0.1);
            border-radius: 6px;
            border-left: 3px solid #667eea;
        }}

        .turn-label {{
            font-weight: bold;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .turn-number {{
            background: #667eea;
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.85em;
        }}

        .diagnosis-box {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-top: 15px;
            border-left: 4px solid #4caf50;
        }}

        .diagnosis-section {{
            margin-bottom: 15px;
        }}

        .diagnosis-label {{
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}

        .discussion-round {{
            background: #fff;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            border: 2px solid #e0e0e0;
        }}

        .round-header {{
            font-weight: bold;
            color: #667eea;
            margin-bottom: 20px;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.2em;
        }}

        .discussion-flow {{
            display: flex;
            align-items: center;
            justify-content: space-around;
            margin: 20px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            position: relative;
        }}

        .discussion-participant {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            min-width: 100px;
        }}

        .participant-icon {{
            font-size: 2.5em;
        }}

        .participant-name {{
            font-weight: bold;
            font-size: 0.9em;
        }}

        .flow-arrow {{
            font-size: 2em;
            color: #667eea;
        }}

        .doctor-opinion {{
            padding: 15px;
            margin: 15px 0;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}

        .opinion-header {{
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 1.05em;
        }}

        .host-message {{
            background: #fff8e1;
            border-left: 4px solid #ffa726;
            padding: 20px;
            margin: 15px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .host-header {{
            font-weight: bold;
            color: #f57c00;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.1em;
            padding-bottom: 10px;
            border-bottom: 2px solid #ffa726;
        }}

        .final-diagnosis {{
            background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
            color: white;
            padding: 25px;
            border-radius: 8px;
            margin-top: 20px;
        }}

        .final-diagnosis h3 {{
            margin-bottom: 15px;
            font-size: 1.5em;
        }}

        .expand-all-btn {{
            padding: 8px 20px;
            background: #4caf50;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.95em;
            transition: all 0.3s;
        }}

        .expand-all-btn:hover {{
            background: #45a049;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(76, 175, 80, 0.3);
        }}

        pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
            font-family: inherit;
        }}

        .inline-icon {{
            width: 64px;
            height: 32px;
            object-fit: contain;
            vertical-align: middle;
            display: inline-block;
            margin: 0 2px;
        }}

        .header-icon {{
            width: 280px;
            height: 140px;
            object-fit: contain;
            vertical-align: middle;
            margin-right: 15px;
        }}

        .participant-icon img {{
            width: 140px;
            height: 70px;
            object-fit: contain;
        }}

        .about-section {{
            display: none;
            padding: 0;
        }}

        .about-section.active {{
            display: block;
            animation: fadeIn 0.5s;
        }}

        .hero-banner {{
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.95) 0%, rgba(118, 75, 162, 0.95) 100%);
            padding: 60px 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 15px 40px rgba(0,0,0,0.2);
            position: relative;
            overflow: hidden;
        }}

        .hero-icons {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 40px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}

        .hero-icon-large {{
            width: 560px;
            height: 280px;
            object-fit: contain;
            filter: drop-shadow(0 10px 20px rgba(0,0,0,0.3));
            transition: transform 0.3s ease;
        }}

        .hero-icon-large:hover {{
            transform: scale(1.1);
        }}

        .hero-title {{
            text-align: center;
            color: white;
            font-size: 2.5em;
            font-weight: bold;
            text-shadow: 0 4px 10px rgba(0,0,0,0.3);
            margin-bottom: 15px;
        }}

        .hero-subtitle {{
            text-align: center;
            color: rgba(255, 255, 255, 0.95);
            font-size: 1.3em;
            max-width: 800px;
            margin: 0 auto;
            line-height: 1.6;
        }}

        .about-content {{
            background: white;
            padding: 30px;
            border-radius: 10px;
        }}

        .role-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .role-card {{
            background: rgba(255, 255, 255, 0.95);
            color: #333;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}

        .role-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #667eea;
        }}

        .role-header img {{
            width: 128px;
            height: 64px;
            object-fit: contain;
        }}

        .role-title {{
            font-size: 1.3em;
            font-weight: bold;
            color: #667eea;
        }}

        .role-description {{
            line-height: 1.6;
            color: #555;
            margin-bottom: 10px;
        }}

        .role-responsibilities {{
            margin-top: 12px;
            padding-left: 20px;
        }}

        .role-responsibilities li {{
            margin-bottom: 8px;
            color: #666;
        }}

        .workflow-section {{
            background: rgba(255, 255, 255, 0.95);
            color: #333;
            padding: 25px;
            border-radius: 10px;
            margin-top: 20px;
        }}

        .workflow-title {{
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .workflow-steps {{
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}

        .workflow-step {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}

        .workflow-step-title {{
            font-weight: bold;
            color: #667eea;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .workflow-step-description {{
            color: #666;
            line-height: 1.6;
        }}

        .flow-arrow {{
            text-align: center;
            color: #667eea;
            font-size: 2em;
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><img src="{icons['collaborate']}" class="header-icon">多智能体协同诊疗历史看板</h1>
            <div class="stats">
                <div class="stat-item">
                    <span class="stat-number">{len(records)}</span>
                    <span>患者总数</span>
                </div>
            </div>
        </div>

        <!-- Navigation with Tabs -->
        <div class="navigation">
            <div class="nav-tabs">
                <button class="tab-button active" onclick="switchTab('patients')">📋 患者历史</button>
                <button class="tab-button" onclick="switchTab('about')">ℹ️ 关于 AI 医院</button>
            </div>
            <div class="patient-selector" id="patient-selector">
                <button class="expand-all-btn" onclick="toggleAllSections()">全部展开/折叠</button>
                <label for="patient-select">选择患者：</label>
                <select id="patient-select" class="patient-dropdown" onchange="showPatient(this.value)">
"""

    # Add patient dropdown options
    for i, record in enumerate(records):
        patient_id = record.get('patient_id', i)
        selected = ' selected' if i == 0 else ''
        html_content += f'                    <option value="{i}"{selected}>患者 {patient_id}</option>\n'

    html_content += f"""                </select>
            </div>
        </div>

        <!-- About Section -->
        <div class="about-section" id="about-section">
            <div class="hero-banner">
                <div class="hero-icons">
                    <img src="{icons['diagnose']}" class="hero-icon-large" alt="诊断">
                    <img src="{icons['collaborate']}" class="hero-icon-large" alt="协作">
                </div>
                <h1 class="hero-title">AI 医院诊断系统</h1>
                <p class="hero-subtitle">通过真实的临床会诊场景评估大型语言模型作为医疗诊断智能体的研究平台</p>
            </div>
            <div class="about-content">
                <!-- Roles Section -->
                <div class="role-grid">
                    <div class="role-card">
                        <div class="role-header">
                            <img src="{icons['patient']}">
                            <div class="role-title">患者</div>
                        </div>
                        <div class="role-description">
                            模拟具有特定医疗状况和症状的患者的 AI 智能体。
                        </div>
                        <ul class="role-responsibilities">
                            <li>提供症状和病史</li>
                            <li>回答医生的问题</li>
                            <li>通过检查员请求检查</li>
                            <li>维持一致的患者画像</li>
                        </ul>
                    </div>

                    <div class="role-card">
                        <div class="role-header">
                            <img src="{icons['doctor']}">
                            <div class="role-title">医生</div>
                        </div>
                        <div class="role-description">
                            基于大语言模型的医生智能体（GPT、Qwen 等），通过会诊对患者进行诊断。
                        </div>
                        <ul class="role-responsibilities">
                            <li>进行医疗会诊</li>
                            <li>询问诊断性问题</li>
                            <li>分析症状和检查结果</li>
                            <li>提供诊断和治疗方案</li>
                            <li>在讨论中与其他医生协作</li>
                        </ul>
                    </div>

                    <div class="role-card">
                        <div class="role-header">
                            <img src="{icons['reporter']}">
                            <div class="role-title">检查员</div>
                        </div>
                        <div class="role-description">
                            提供检查结果和评估的医疗检查系统。
                        </div>
                        <ul class="role-responsibilities">
                            <li>提供实验室检查结果</li>
                            <li>进行影像学检查</li>
                            <li>返回检查发现</li>
                            <li>评估最终诊断的准确性</li>
                        </ul>
                    </div>

                    <div class="role-card">
                        <div class="role-header">
                            <img src="{icons['host']}">
                            <div class="role-title">主任医师</div>
                        </div>
                        <div class="role-description">
                            高级医生智能体，促进协作会诊并确保质量。
                        </div>
                        <ul class="role-responsibilities">
                            <li>整合所有医生的信息</li>
                            <li>识别冲突和共识</li>
                            <li>向患者询问缺失的关键信息</li>
                            <li>引导讨论达成共识</li>
                            <li>综合最终诊断</li>
                        </ul>
                    </div>
                </div>

                <!-- Workflow Sections -->
                <div class="workflow-section">
                    <div class="workflow-title">
                        <img src="{icons['diagnose']}" style="width: 32px; height: 32px;">
                        <span>单人会诊流程</span>
                    </div>
                    <div class="workflow-steps">
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                <img src="{icons['patient']}" class="inline-icon">
                                1. 初始会诊
                            </div>
                            <div class="workflow-step-description">
                                医生问候患者并开始会诊。患者描述症状和顾虑。
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                <img src="{icons['patient']}" class="inline-icon">
                                2. 信息收集
                            </div>
                            <div class="workflow-step-description">
                                医生询问有关症状、病史和当前状况的问题。患者提供相关信息。
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['patient']}" class="inline-icon">
                                <img src="{icons['reporter']}" class="inline-icon">
                                3. 检查请求
                            </div>
                            <div class="workflow-step-description">
                                患者（在医生的指导下）向检查员请求实验室检查、影像学检查或其他检查。
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                4. 诊断与治疗
                            </div>
                            <div class="workflow-step-description">
                                医生分析所有信息并提供：诊断结果、诊断依据和治疗方案。
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['reporter']}" class="inline-icon">
                                5. 评估
                            </div>
                            <div class="workflow-step-description">
                                检查员根据参考诊断评估诊断并提供指标。
                            </div>
                        </div>
                    </div>
                </div>

                <div class="workflow-section">
                    <div class="workflow-title">
                        <img src="{icons['collaborate']}" style="width: 32px; height: 32px;">
                        <span>协作会诊流程</span>
                    </div>
                    <div class="workflow-steps">
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                <img src="{icons['patient']}" class="inline-icon">
                                阶段 0：独立会诊
                            </div>
                            <div class="workflow-step-description">
                                每位医生独立地与患者进行完整会诊并生成初步诊断。
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                <img src="{icons['host']}" class="inline-icon">
                                回合 1 阶段 1：初步报告
                            </div>
                            <div class="workflow-step-description">
                                医生向主任医师报告初步诊断。主任医师整合信息并检查冲突/共识。
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['host']}" class="inline-icon">
                                主任医师决策：结束还是讨论？
                            </div>
                            <div class="workflow-step-description">
                                <strong>如果医生达成一致 + 无缺失信息：</strong>完成诊断 ✓<br>
                                <strong>如果医生达成一致 + 有缺失关键信息：</strong>询问患者 💬<br>
                                <strong>如果医生有冲突：</strong>开始讨论 ↻
                            </div>
                        </div>
                        <div class="flow-arrow">↓ (如需讨论)</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                <img src="{icons['collaborate']}" class="inline-icon">
                                回合 1 阶段 2：修订
                            </div>
                            <div class="workflow-step-description">
                                医生修订诊断，考虑：(1) 其他医生的意见，(2) 主任医师的批评/指导。
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['collaborate']}" class="inline-icon">
                                回合 2+ 阶段 1：报告与检查
                            </div>
                            <div class="workflow-step-description">
                                医生报告修订后的诊断。主任医师检查是否达成共识。如果达成共识 + 有缺失信息 → 询问患者。
                            </div>
                        </div>
                        <div class="flow-arrow">↓ (循环直到达成共识)</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['host']}" class="inline-icon">
                                最终：共识诊断
                            </div>
                            <div class="workflow-step-description">
                                主任医师综合所有医生的意见和任何额外的患者信息，形成最终诊断。
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Content Section (Patient History) -->
        <div class="content" id="patients-section">
"""

    # Generate content for each patient
    for idx, record in enumerate(records):
        patient_id = record.get('patient_id', idx)
        html_content += f'            <div class="patient-record{" active" if idx == 0 else ""}" id="patient-{idx}">\n'
        html_content += f'                <h2 style="color: #667eea; margin-bottom: 25px;"><img src="{icons['patient']}" class="inline-icon"> 患者编号：{patient_id}</h2>\n'

        # Initial Consultations Section
        if 'initial_consultations' in record:
            html_content += f"""                <div class="section">
                    <div class="section-header" onclick="toggleSection(this)">
                        <span><img src="{icons['diagnose']}" class="inline-icon"> 初步会诊</span>
                        <span class="toggle-icon">▼</span>
                    </div>
                    <div class="section-content">
"""

            for consultation in record['initial_consultations']:
                doctor_name = consultation.get('doctor_name', '未知')
                doctor_engine = consultation.get('doctor_engine_name', '未知')
                doctor_id = consultation.get('doctor_id', 0)

                # Assign unique color to each doctor
                doctor_color = doctor_colors[doctor_id % len(doctor_colors)]

                html_content += f"""                        <div class="doctor-consultation" style="border-color: {doctor_color};">
                            <div class="doctor-header" style="background: {doctor_color};">
                                <span><img src="{icons['doctor']}" class="inline-icon"> {doctor_name}</span>
                                <span>模型：{doctor_engine} | 编号：{doctor_id}</span>
                            </div>
"""

                # Dialog History - skip if turn contains diagnosis
                if 'dialog_history' in consultation:
                    for turn in consultation['dialog_history']:
                        role = turn.get('role', 'Unknown')
                        recipient = turn.get('recipient', '')
                        content = turn.get('content', '')
                        turn_num = turn.get('turn', '')

                        # Skip if this is the diagnosis turn (will be shown in Initial Diagnosis section)
                        if role == 'Doctor' and is_diagnosis_turn(content):
                            continue

                        role_class = f"role-{role.lower()}"

                        # Format message with flow indicators
                        flow_label, cleaned_text = format_message_flow(role, recipient, content, icons)

                        # Custom color for doctor turns
                        border_color = doctor_color if role == 'Doctor' else ''
                        style = f'border-left-color: {border_color};' if border_color else ''

                        html_content += f"""                            <div class="dialog-turn {role_class}" style="{style}">
                                <div class="turn-label">
                                    <span class="turn-number">回合 {turn_num}</span>
                                </div>
                                <div class="message-flow" style="{'color: ' + doctor_color + '; border-left-color: ' + doctor_color + ';' if role == 'Doctor' else ''}">
                                    {flow_label}
                                </div>
                                <pre>{cleaned_text}</pre>
                            </div>
"""

                # Initial Diagnosis - now displayed inline
                if 'initial_diagnosis' in consultation:
                    diag = consultation['initial_diagnosis']
                    html_content += f"""                            <div class="diagnosis-box" style="border-left-color: {doctor_color};">
                                <h4 style="color: {doctor_color}; margin-bottom: 15px;"><img src="{icons['doctor']}" class="inline-icon"> {doctor_name} 的诊断</h4>
"""

                    if isinstance(diag, dict):
                        for key, value in diag.items():
                            if value:
                                cleaned_value = clean_content(str(value))
                                html_content += f"""                                <div class="diagnosis-section">
                                    <div class="diagnosis-label" style="color: {doctor_color};">{key}:</div>
                                    <pre>{cleaned_value}</pre>
                                </div>
"""
                    else:
                        cleaned_diag = clean_content(str(diag))
                        html_content += f"""                                <pre>{cleaned_diag}</pre>
"""

                    html_content += "                            </div>\n"

                html_content += "                        </div>\n"

            html_content += """                    </div>
                </div>
"""

        # Discussion Rounds Section
        if 'diagnosis_in_discussion' in record and record['diagnosis_in_discussion']:
            html_content += f"""                <div class="section">
                    <div class="section-header" onclick="toggleSection(this)">
                        <span><img src="{icons['collaborate']}" class="inline-icon"> 讨论回合</span>
                        <span class="toggle-icon">▼</span>
                    </div>
                    <div class="section-content">
"""

            for round_idx, round_data in enumerate(record['diagnosis_in_discussion']):
                turn_num = round_data.get('turn', round_idx + 1)  # Turn numbers start at 1 now
                html_content += f"""                        <div class="discussion-round">
                            <div class="round-header">
                                <span><img src="{icons['collaborate']}" class="inline-icon"></span>
                                <span>回合 {turn_num}</span>
                            </div>
"""

                num_doctors = len(record.get('initial_consultations', []))

                # ===== PHASE 1: Doctors Report to Host =====
                # For Turn 1, initial reports are already in diagnosis_in_turn (from initial consultations)
                # For Turn 2+, show previous round's revised diagnoses as reports
                html_content += """                            <div style="margin: 25px 0; padding: 20px; background: #f0f4ff; border-radius: 10px; border: 2px solid #667eea;">
                                <h4 style="color: #667eea; margin-bottom: 20px; font-size: 1.2em; display: flex; align-items: center; gap: 10px;">
                                    <span style="background: #667eea; color: white; padding: 5px 15px; border-radius: 20px; font-size: 0.9em;">阶段 1</span>
                                    <span>报告</span>
                                </h4>
"""

                # Determine which diagnoses to show in Phase 1
                if turn_num == 1:
                    # Turn 1: Show initial diagnoses (diagnosis_in_turn contains initial reports)
                    phase1_diagnoses = []
                    if 'diagnosis_in_turn' in round_data:
                        for doctor_diag in round_data['diagnosis_in_turn']:
                            doctor_id = doctor_diag.get('doctor_id', 0)
                            doctor_name = record['initial_consultations'][doctor_id].get('doctor_name', f'Doctor {doctor_id}') if doctor_id < len(record.get('initial_consultations', [])) else f'Doctor {doctor_id}'
                            phase1_diagnoses.append({
                                'doctor_id': doctor_id,
                                'doctor_name': doctor_name,
                                'doctor_engine_name': doctor_diag.get('doctor_engine_name', 'Unknown'),
                                'diagnosis': doctor_diag.get('diagnosis', {}),
                                'is_initial': True
                            })
                else:
                    # Turn 2+: Show previous round's revised/discussed diagnoses as reports
                    prev_round = record['diagnosis_in_discussion'][round_idx - 1]
                    phase1_diagnoses = []

                    # Check if previous round has revised_diagnoses (Turn 1 Phase 2) or diagnosis_in_turn (Turn 2+ Phase 2)
                    source_diagnoses = prev_round.get('revised_diagnoses') or prev_round.get('diagnosis_in_turn', [])

                    for doctor_diag in source_diagnoses:
                        doctor_id = doctor_diag.get('doctor_id', 0)
                        doctor_name = record['initial_consultations'][doctor_id].get('doctor_name', f'Doctor {doctor_id}') if doctor_id < len(record.get('initial_consultations', [])) else f'Doctor {doctor_id}'
                        phase1_diagnoses.append({
                            'doctor_id': doctor_id,
                            'doctor_name': doctor_name,
                            'doctor_engine_name': doctor_diag.get('doctor_engine_name', 'Unknown'),
                            'diagnosis': doctor_diag.get('diagnosis', {}),
                            'is_initial': False
                        })

                # Show each doctor's diagnosis to host
                if phase1_diagnoses:
                    html_content += """                                <div style="margin: 15px 0;">
"""
                    for diag_info in phase1_diagnoses:
                        doctor_id = diag_info['doctor_id']
                        doctor_color = doctor_colors[doctor_id % len(doctor_colors)]
                        doctor_name = diag_info['doctor_name']
                        doctor_engine = diag_info['doctor_engine_name']

                        # Show data flow: Doctor → Host
                        html_content += f"""                                    <div style="margin: 15px 0; padding: 12px; background: white; border-left: 4px solid {doctor_color}; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                                        <div style="display: flex; align-items: center; gap: 10px; font-weight: bold; margin-bottom: 8px;">
                                            <span style="color: {doctor_color};"><img src="{icons['doctor']}" class="inline-icon"> {doctor_name} ({doctor_engine})</span>
                                            <span style="font-size: 1.3em; color: #667eea;">→</span>
                                            <span style="color: #ffa726;"><img src="{icons['host']}" class="inline-icon"> Host</span>
                                        </div>
                                        <div style="font-size: 0.9em; color: #666; font-style: italic;">向主任医师报告{'初步诊断' if diag_info['is_initial'] else '修订诊断'}</div>
                                    </div>
"""

                    html_content += """                                </div>
"""


                # Show host's analysis of conflicts/commonalities
                has_detailed_summary = False

                # First check if there's a summary in host_decision.reason
                if 'host_decision' in round_data and round_data['host_decision'] and round_data['host_decision'].get('reason'):
                    reason = clean_content(str(round_data['host_decision'].get('reason', '')))
                    html_content += f"""                                <div style="margin: 20px 0; padding: 20px; background: #fff8e1; border-left: 4px solid #ffa726; border-radius: 8px;">
                                    <div style="font-weight: bold; color: #f57c00; margin-bottom: 15px; display: flex; align-items: center; gap: 10px; font-size: 1.1em;">
                                        <span><img src="{icons['host']}" class="inline-icon"></span>
                                        <span>主任医师分析（冲突与共识）</span>
                                    </div>
                                    <pre style="background: white; padding: 15px; border-radius: 6px; border: 1px solid #ffd54f;">{reason}</pre>
                                </div>
"""
                    has_detailed_summary = True
                # Otherwise check host_critique for detailed analysis
                elif 'host_critique' in round_data and round_data['host_critique']:
                    critique = clean_content(str(round_data['host_critique']))
                    # Only show if it's not just a marker
                    if critique not in ['#继续#', '#结束#']:
                        html_content += f"""                                <div style="margin: 20px 0; padding: 20px; background: #fff8e1; border-left: 4px solid #ffa726; border-radius: 8px;">
                                    <div style="font-weight: bold; color: #f57c00; margin-bottom: 15px; display: flex; align-items: center; gap: 10px; font-size: 1.1em;">
                                        <span><img src="{icons['host']}" class="inline-icon"></span>
                                        <span>主任医师分析（冲突与共识）</span>
                                    </div>
                                    <pre style="background: white; padding: 15px; border-radius: 6px; border: 1px solid #ffd54f;">{critique}</pre>
                                </div>
"""
                        has_detailed_summary = True

                # Host Decision
                if 'host_decision' in round_data and round_data['host_decision']:
                    decision = round_data['host_decision']
                    action = decision.get('action', 'N/A')
                    query = clean_content(str(decision.get('query', '')))

                    # Determine decision status text
                    if action in ['finalize', 'finalize_after_discussion', 'finalize_with_patient_info']:
                        decision_status = '讨论结束'
                        icon = '<span style="color: #4caf50; font-size: 1.5em;">✓</span>'
                        bg_color = '#e8f5e9'
                        border_color = '#4caf50'
                    elif action == 'begin_discussion':
                        decision_status = '讨论开始'
                        icon = '<span style="color: #2196f3; font-size: 1.5em;">↻</span>'
                        bg_color = '#e3f2fd'
                        border_color = '#2196f3'
                    elif action == 'update_with_patient_info':
                        decision_status = '更新患者信息'
                        icon = '<span style="color: #ff9800; font-size: 1.5em;">💬</span>'
                        bg_color = '#fff3e0'
                        border_color = '#ff9800'
                    elif action in ['continue_discussion', 'query_patient']:
                        decision_status = '讨论继续'
                        icon = '<span style="color: #2196f3; font-size: 1.5em;">↻</span>'
                        bg_color = '#e3f2fd'
                        border_color = '#2196f3'
                    else:
                        decision_status = f'操作：{action}'
                        icon = '<span style="color: #ff9800; font-size: 1.5em;">?</span>'
                        bg_color = '#fff3e0'
                        border_color = '#ff9800'

                    html_content += f"""                                <div style="background: {bg_color}; border-left: 4px solid {border_color}; padding: 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <div style="font-weight: bold; color: {border_color}; margin-bottom: 10px; display: flex; align-items: center; gap: 10px; font-size: 1.1em;">
                                        <span style="font-size: 1.5em;">{icon}</span>
                                        <span>主任医师决策：{decision_status}</span>
                                    </div>
"""

                    # Show query to patient if exists
                    if query and action == 'query_patient':
                        html_content += f"""                                    <div style="margin-top: 15px;">
                                        <strong style="color: #ff9800;">询问患者：</strong>
                                        <pre style="background: white; padding: 15px; border-radius: 6px; border: 1px solid #e0e0e0; margin-top: 8px;">{query}</pre>
                                    </div>
"""

                    html_content += """                                </div>
"""

                # Patient Response (if host queried)
                if 'new_information' in round_data and round_data['new_information']:
                    new_info = clean_content(str(round_data['new_information']))
                    html_content += f"""                                <div style="margin: 15px 0; padding: 15px; background: #fff3e0; border-left: 4px solid #ff9800; border-radius: 8px;">
                                    <div style="font-weight: bold; color: #f57c00; margin-bottom: 10px; display: flex; align-items: center; gap: 10px;">
                                        <span><img src="{icons['patient']}" class="inline-icon"></span>
                                        <span>患者回应 → 主任医师</span>
                                    </div>
                                    <pre style="background: white; padding: 15px; border-radius: 6px; border: 1px solid #ffd54f;">{new_info}</pre>
                                </div>
"""

                html_content += """                            </div>
"""

                # ===== PHASE 2: Revision (if discussion continues) =====
                # Only show Phase 2 if host decision is begin_discussion, continue_discussion, or update_with_patient_info
                if 'host_decision' in round_data:
                    decision = round_data.get('host_decision', {})
                    action = decision.get('action', '') if decision else ''

                    # Only show Phase 2 if discussion begins/continues or updating with patient info
                    if action in ['begin_discussion', 'continue_discussion', 'update_with_patient_info', 'finalize_with_patient_info']:
                        # Get the revisions for Phase 2
                        # For Turn 1: use revised_diagnoses if it exists
                        # For Turn 2+: use diagnosis_in_turn from current round
                        if turn_num == 1:
                            phase2_diagnoses = round_data.get('revised_diagnoses', [])
                        else:
                            phase2_diagnoses = round_data.get('diagnosis_in_turn', [])

                        if phase2_diagnoses:
                            html_content += """                            <div style="margin: 25px 0; padding: 20px; background: #f0fff4; border-radius: 10px; border: 2px solid #4caf50;">
                                <h4 style="color: #4caf50; margin-bottom: 20px; font-size: 1.2em; display: flex; align-items: center; gap: 10px;">
                                    <span style="background: #4caf50; color: white; padding: 5px 15px; border-radius: 20px; font-size: 0.9em;">阶段 2</span>
                                    <span>修订</span>
                                </h4>
"""

                            # For each doctor, show what they receive and their revision
                            for doctor_diag in phase2_diagnoses:
                                doctor_id = doctor_diag.get('doctor_id', 0)
                                doctor_color = doctor_colors[doctor_id % len(doctor_colors)]
                                doctor_name = record['initial_consultations'][doctor_id].get('doctor_name', f'Doctor {doctor_id}') if doctor_id < len(record.get('initial_consultations', [])) else f'Doctor {doctor_id}'
                                doctor_engine = doctor_diag.get('doctor_engine_name', 'Unknown')
                                diagnosis = doctor_diag.get('diagnosis', {})

                                # Show what this doctor receives
                                html_content += f"""                                <div style="margin: 20px 0; padding: 15px; background: white; border: 2px solid {doctor_color}; border-radius: 8px;">
                                    <div style="font-weight: bold; color: {doctor_color}; margin-bottom: 15px; font-size: 1.05em; padding-bottom: 10px; border-bottom: 2px solid {doctor_color};">
                                        <img src="{icons['doctor']}" class="inline-icon"> {doctor_name} 的修订回合
                                    </div>

                                    <div style="margin: 15px 0; padding: 12px; background: #f8f9fa; border-radius: 6px;">
                                        <div style="font-weight: bold; color: #667eea; margin-bottom: 10px; font-size: 0.95em;">接收输入来自：</div>
"""

                                # Show input from host
                                html_content += f"""                                        <div style="margin: 8px 0; padding: 8px; background: white; border-left: 3px solid #ffa726; border-radius: 4px;">
                                            <div style="display: flex; align-items: center; gap: 8px; font-size: 0.9em;">
                                                <span style="color: #ffa726; font-weight: bold;"><img src="{icons['host']}" class="inline-icon"> 主任医师</span>
                                                <span style="font-size: 1.2em; color: #667eea;">→</span>
                                                <span style="color: {doctor_color}; font-weight: bold;"><img src="{icons['doctor']}" class="inline-icon"> {doctor_name}</span>
                                            </div>
                                            <div style="font-size: 0.85em; color: #666; margin-top: 4px; font-style: italic;">主任医师的总结和批评</div>
                                        </div>
"""

                                # Show input from other doctors
                                for other_idx in range(num_doctors):
                                    if other_idx != doctor_id:
                                        other_color = doctor_colors[other_idx % len(doctor_colors)]
                                        other_name = record['initial_consultations'][other_idx].get('doctor_name', f'Doctor {other_idx}') if other_idx < len(record.get('initial_consultations', [])) else f'Doctor {other_idx}'

                                        html_content += f"""                                        <div style="margin: 8px 0; padding: 8px; background: white; border-left: 3px solid {other_color}; border-radius: 4px;">
                                            <div style="display: flex; align-items: center; gap: 8px; font-size: 0.9em;">
                                                <span style="color: {other_color}; font-weight: bold;"><img src="{icons['doctor']}" class="inline-icon"> {other_name}</span>
                                                <span style="font-size: 1.2em; color: #667eea;">→</span>
                                                <span style="color: {doctor_color}; font-weight: bold;"><img src="{icons['doctor']}" class="inline-icon"> {doctor_name}</span>
                                            </div>
                                            <div style="font-size: 0.85em; color: #666; margin-top: 4px; font-style: italic;">{other_name} 的诊断</div>
                                        </div>
"""

                                html_content += """                                    </div>
"""

                                # Show revised diagnosis
                                html_content += f"""                                    <div style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid {doctor_color};">
                                        <div style="font-weight: bold; color: {doctor_color}; margin-bottom: 12px; font-size: 1em;">
                                            <img src="{icons['doctor']}" class="inline-icon"> 修订后的诊断（{doctor_engine}）
                                        </div>
"""

                                if isinstance(diagnosis, dict):
                                    for key, value in diagnosis.items():
                                        if value:
                                            cleaned_value = clean_content(str(value))
                                            html_content += f"""                                        <div style="margin-bottom: 12px;">
                                            <div style="font-weight: bold; color: {doctor_color}; font-size: 0.95em; margin-bottom: 4px;">{key}:</div>
                                            <pre style="background: white; padding: 12px; border-radius: 4px; border: 1px solid #e0e0e0; font-size: 0.9em;">{cleaned_value}</pre>
                                        </div>
"""
                                else:
                                    cleaned_diag = clean_content(str(diagnosis))
                                    html_content += f"""                                        <pre style="background: white; padding: 12px; border-radius: 4px; border: 1px solid #e0e0e0;">{cleaned_diag}</pre>
"""

                                html_content += """                                    </div>
                                </div>
"""

                            html_content += """                            </div>
"""

                # ===== HOST'S FINAL DIAGNOSIS (if present in this round) =====
                # Show the host's final consensus diagnosis if this is the final round
                if 'final_diagnosis_by_host' in round_data:
                    host_final_diag = round_data['final_diagnosis_by_host']
                    final_color = '#4caf50'  # Green for final diagnosis

                    html_content += f"""                            <div style="margin: 25px 0; padding: 20px; background: linear-gradient(135deg, #f8f9fa 0%, #e8f5e9 100%); border-radius: 10px; border: 3px solid {final_color};">
                                <h4 style="color: {final_color}; margin-bottom: 20px; font-size: 1.3em; display: flex; align-items: center; gap: 10px;">
                                    <span style="font-size: 1.8em;"><img src="{icons['host']}" class="inline-icon"></span>
                                    <span>主任医师的最终共识诊断</span>
                                </h4>
                                <div style="padding: 15px; background: white; border-radius: 8px; border-left: 5px solid {final_color};">
"""

                    if isinstance(host_final_diag, dict):
                        for key, value in host_final_diag.items():
                            if value:
                                cleaned_value = clean_content(str(value))
                                html_content += f"""                                    <div style="margin-bottom: 15px;">
                                        <div style="font-weight: bold; color: {final_color}; font-size: 1.05em; margin-bottom: 6px;">{key}:</div>
                                        <pre style="background: #f8f9fa; padding: 12px; border-radius: 4px; border: 1px solid #e0e0e0; font-size: 0.95em;">{cleaned_value}</pre>
                                    </div>
"""
                    else:
                        cleaned_diag = clean_content(str(host_final_diag))
                        html_content += f"""                                    <pre style="background: #f8f9fa; padding: 15px; border-radius: 6px; border: 1px solid #e0e0e0;">{cleaned_diag}</pre>
"""

                    html_content += """                                </div>
                            </div>
"""

                html_content += "                        </div>\n"

            html_content += """                    </div>
                </div>
"""

        # Final Diagnosis Section (using same style as doctor diagnosis boxes)
        if 'diagnosis' in record:
            final_diag = record['diagnosis']
            final_diag_color = '#4caf50'  # Green for final/consensus diagnosis
            html_content += f"""                <div class="diagnosis-box" style="border-left-color: {final_diag_color}; background: #f8f9fa; padding: 25px; border-radius: 8px; margin-top: 20px; border-left-width: 5px;">
                    <h3 style="color: {final_diag_color}; margin-bottom: 20px; font-size: 1.5em;"><img src="{icons['collaborate']}" class="inline-icon"> 最终诊断</h3>
"""

            if isinstance(final_diag, dict):
                for key, value in final_diag.items():
                    if value:
                        cleaned_value = clean_content(str(value))
                        html_content += f"""                    <div class="diagnosis-section">
                            <div class="diagnosis-label" style="color: {final_diag_color}; font-size: 1.1em;">{key}:</div>
                            <pre>{cleaned_value}</pre>
                        </div>
"""
            else:
                cleaned_diag = clean_content(str(final_diag))
                html_content += f"""                    <pre>{cleaned_diag}</pre>
"""

            html_content += "                </div>\n"

        html_content += "            </div>\n"

    html_content += """        </div>
    </div>

    <script>
        function switchTab(tabName) {
            // Update tab buttons
            const tabButtons = document.querySelectorAll('.tab-button');
            tabButtons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            // Switch content
            const patientsSection = document.getElementById('patients-section');
            const aboutSection = document.getElementById('about-section');
            const patientSelector = document.getElementById('patient-selector');

            if (tabName === 'about') {
                patientsSection.style.display = 'none';
                aboutSection.classList.add('active');
                patientSelector.style.display = 'none';
            } else {
                patientsSection.style.display = 'block';
                aboutSection.classList.remove('active');
                patientSelector.style.display = 'flex';
            }

            // Scroll to top
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function showPatient(index) {
            // Hide all patient records
            const records = document.querySelectorAll('.patient-record');
            records.forEach(record => record.classList.remove('active'));

            // Show selected patient
            document.getElementById('patient-' + index).classList.add('active');

            // Update dropdown selection
            document.getElementById('patient-select').value = index;

            // Scroll to top
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function toggleSection(header) {
            const content = header.nextElementSibling;
            const icon = header.querySelector('.toggle-icon');

            content.classList.toggle('collapsed');
            icon.classList.toggle('collapsed');
        }

        function toggleAllSections() {
            const activeRecord = document.querySelector('.patient-record.active');
            const sections = activeRecord.querySelectorAll('.section-content');
            const icons = activeRecord.querySelectorAll('.toggle-icon');

            // Check if any section is open
            const hasOpen = Array.from(sections).some(s => !s.classList.contains('collapsed'));

            sections.forEach(section => {
                if (hasOpen) {
                    section.classList.add('collapsed');
                } else {
                    section.classList.remove('collapsed');
                }
            });

            icons.forEach(icon => {
                if (hasOpen) {
                    icon.classList.add('collapsed');
                } else {
                    icon.classList.remove('collapsed');
                }
            });
        }
    </script>
</body>
</html>
"""

    # Write HTML file
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"[✓] Visualization generated successfully!")
    print(f"[📊] Total patients processed: {len(records)}")
    print(f"[📄] Output file: {output_html}")
    print(f"\n[🌐] Open the file in your browser to view the visualization")


def main():
    parser = argparse.ArgumentParser(
        description='Visualize AI Hospital diagnosis history from JSONL logs'
    )
    parser.add_argument(
        'input',
        nargs='?',
        default='test_online_named_doctors_full.jsonl',
        help='Input JSONL file path (default: test_online_named_doctors_full.jsonl)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output HTML file path (default: input_filename.html)'
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.exists():
        print(f"❌ Error: Input file not found: {input_file}")
        return

    if args.output:
        output_file = Path(args.output)
    else:
        output_file = input_file.with_suffix('.html')

    print(f"📖 Reading from: {input_file}")
    print(f"📝 Writing to: {output_file}")
    print(f"⏳ Generating visualization...")

    generate_html(input_file, output_file)


if __name__ == '__main__':
    main()
