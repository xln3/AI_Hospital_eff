#!/usr/bin/env python3
"""
Diagnosis History Visualizer
Reads JSONL log files and generates an interactive HTML visualization
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
        return f'<img src="{icons["patient"]}" class="inline-icon"> Patient → <img src="{icons["reporter"]}" class="inline-icon"> Reporter', cleaned_text
    elif role == 'Patient' and recipient == 'Doctor':
        return f'<img src="{icons["patient"]}" class="inline-icon"> Patient → <img src="{icons["doctor"]}" class="inline-icon"> Doctor', cleaned_text
    elif role == 'Doctor' and recipient == 'Patient':
        return f'<img src="{icons["doctor"]}" class="inline-icon"> Doctor → <img src="{icons["patient"]}" class="inline-icon"> Patient', cleaned_text
    elif role == 'Reporter':
        return f'<img src="{icons["reporter"]}" class="inline-icon"> Reporter', cleaned_text
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
    <title>AI Hospital Diagnosis History Visualization</title>
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
            <h1><img src="{icons['collaborate']}" class="header-icon">Multi-LLM-Agent Collaborative Diagnosis Dashboard</h1>
            <div class="stats">
                <div class="stat-item">
                    <span class="stat-number">{len(records)}</span>
                    <span>Total Patients</span>
                </div>
            </div>
        </div>

        <!-- Navigation with Tabs -->
        <div class="navigation">
            <div class="nav-tabs">
                <button class="tab-button active" onclick="switchTab('patients')">📋 Patient History</button>
                <button class="tab-button" onclick="switchTab('about')">ℹ️ About AI Hospital</button>
            </div>
            <div class="patient-selector" id="patient-selector">
                <button class="expand-all-btn" onclick="toggleAllSections()">Expand/Collapse All</button>
                <label for="patient-select">Select Patient:</label>
                <select id="patient-select" class="patient-dropdown" onchange="showPatient(this.value)">
"""

    # Add patient dropdown options
    for i, record in enumerate(records):
        patient_id = record.get('patient_id', i)
        selected = ' selected' if i == 0 else ''
        html_content += f'                    <option value="{i}"{selected}>Patient {patient_id}</option>\n'

    html_content += f"""                </select>
            </div>
        </div>

        <!-- About Section -->
        <div class="about-section" id="about-section">
            <div class="hero-banner">
                <div class="hero-icons">
                    <img src="{icons['diagnose']}" class="hero-icon-large" alt="Diagnose">
                    <img src="{icons['collaborate']}" class="hero-icon-large" alt="Collaborate">
                </div>
                <h1 class="hero-title">AI Hospital: Multi-LLM-Agent Collaborative Diagnosis System</h1>
                <p class="hero-subtitle">A research platform for evaluating Large Language Models as medical diagnostic agents through realistic clinical consultations</p>
            </div>
            <div class="about-content">
                <!-- Roles Section -->
                <div class="role-grid">
                    <div class="role-card">
                        <div class="role-header">
                            <img src="{icons['patient']}">
                            <div class="role-title">Patient</div>
                        </div>
                        <div class="role-description">
                            AI agent simulating a patient with specific medical conditions and symptoms.
                        </div>
                        <ul class="role-responsibilities">
                            <li>Provides symptoms and medical history</li>
                            <li>Responds to doctor's questions</li>
                            <li>Requests examinations through reporter</li>
                            <li>Maintains consistent patient profile</li>
                        </ul>
                    </div>

                    <div class="role-card">
                        <div class="role-header">
                            <img src="{icons['doctor']}">
                            <div class="role-title">Doctor</div>
                        </div>
                        <div class="role-description">
                            LLM-based physician agents (GPT, Qwen, etc.) that diagnose patients through consultation.
                        </div>
                        <ul class="role-responsibilities">
                            <li>Conducts medical consultation</li>
                            <li>Asks diagnostic questions</li>
                            <li>Analyzes symptoms and test results</li>
                            <li>Provides diagnosis and treatment plan</li>
                            <li>Collaborates with other doctors in discussions</li>
                        </ul>
                    </div>

                    <div class="role-card">
                        <div class="role-header">
                            <img src="{icons['reporter']}">
                            <div class="role-title">Reporter</div>
                        </div>
                        <div class="role-description">
                            Medical examination system that provides test results and evaluation.
                        </div>
                        <ul class="role-responsibilities">
                            <li>Provides laboratory test results</li>
                            <li>Conducts imaging examinations</li>
                            <li>Returns examination findings</li>
                            <li>Evaluates final diagnosis accuracy</li>
                        </ul>
                    </div>

                    <div class="role-card">
                        <div class="role-header">
                            <img src="{icons['host']}">
                            <div class="role-title">Host (Chief Doctor)</div>
                        </div>
                        <div class="role-description">
                            Senior physician agent that facilitates collaborative consultations and ensures quality.
                        </div>
                        <ul class="role-responsibilities">
                            <li>Consolidates information from all doctors</li>
                            <li>Identifies conflicts and commonalities</li>
                            <li>Queries patient for missing key information</li>
                            <li>Guides discussion toward consensus</li>
                            <li>Synthesizes final diagnosis</li>
                        </ul>
                    </div>
                </div>

                <!-- Workflow Sections -->
                <div class="workflow-section">
                    <div class="workflow-title">
                        <img src="{icons['diagnose']}" style="width: 32px; height: 32px;">
                        <span>Single Consultation Workflow</span>
                    </div>
                    <div class="workflow-steps">
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                <img src="{icons['patient']}" class="inline-icon">
                                1. Initial Consultation
                            </div>
                            <div class="workflow-step-description">
                                Doctor greets patient and begins consultation. Patient describes symptoms and concerns.
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                <img src="{icons['patient']}" class="inline-icon">
                                2. Information Gathering
                            </div>
                            <div class="workflow-step-description">
                                Doctor asks questions about symptoms, medical history, and current condition. Patient responds with relevant information.
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['patient']}" class="inline-icon">
                                <img src="{icons['reporter']}" class="inline-icon">
                                3. Examination Requests
                            </div>
                            <div class="workflow-step-description">
                                Patient (guided by doctor) requests laboratory tests, imaging, or other examinations from reporter.
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                4. Diagnosis & Treatment
                            </div>
                            <div class="workflow-step-description">
                                Doctor analyzes all information and provides: diagnosis result, diagnostic reasoning, and treatment plan.
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['reporter']}" class="inline-icon">
                                5. Evaluation
                            </div>
                            <div class="workflow-step-description">
                                Reporter evaluates diagnosis against reference diagnosis and provides metrics.
                            </div>
                        </div>
                    </div>
                </div>

                <div class="workflow-section">
                    <div class="workflow-title">
                        <img src="{icons['collaborate']}" style="width: 32px; height: 32px;">
                        <span>Collaborative Consultation Workflow</span>
                    </div>
                    <div class="workflow-steps">
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                <img src="{icons['patient']}" class="inline-icon">
                                Phase 0: Independent Consultations
                            </div>
                            <div class="workflow-step-description">
                                Each doctor independently conducts a full consultation with the patient and generates their initial diagnosis.
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                <img src="{icons['host']}" class="inline-icon">
                                Turn 1 Phase 1: Initial Reports
                            </div>
                            <div class="workflow-step-description">
                                Doctors report their initial diagnoses to host. Host consolidates information and checks for conflicts/commonalities.
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['host']}" class="inline-icon">
                                Host Decision: Finalize or Discuss?
                            </div>
                            <div class="workflow-step-description">
                                <strong>If doctors agree + no missing info:</strong> Finalize diagnosis ✓<br>
                                <strong>If doctors agree + missing key info:</strong> Query patient 💬<br>
                                <strong>If doctors have conflicts:</strong> Begin discussion ↻
                            </div>
                        </div>
                        <div class="flow-arrow">↓ (if discussion needed)</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['doctor']}" class="inline-icon">
                                <img src="{icons['collaborate']}" class="inline-icon">
                                Turn 1 Phase 2: Revision
                            </div>
                            <div class="workflow-step-description">
                                Doctors revise their diagnoses considering: (1) other doctors' opinions, (2) host's critique/guidance.
                            </div>
                        </div>
                        <div class="flow-arrow">↓</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['collaborate']}" class="inline-icon">
                                Turn 2+ Phase 1: Report & Check
                            </div>
                            <div class="workflow-step-description">
                                Doctors report revised diagnoses. Host checks if consensus is reached. If consensus + missing info → query patient.
                            </div>
                        </div>
                        <div class="flow-arrow">↓ (loop until consensus)</div>
                        <div class="workflow-step">
                            <div class="workflow-step-title">
                                <img src="{icons['host']}" class="inline-icon">
                                Final: Consensus Diagnosis
                            </div>
                            <div class="workflow-step-description">
                                Host synthesizes final diagnosis incorporating all doctors' input and any additional patient information.
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
        html_content += f'                <h2 style="color: #667eea; margin-bottom: 25px;"><img src="{icons['patient']}" class="inline-icon"> Patient ID: {patient_id}</h2>\n'

        # Initial Consultations Section
        if 'initial_consultations' in record:
            html_content += f"""                <div class="section">
                    <div class="section-header" onclick="toggleSection(this)">
                        <span><img src="{icons['diagnose']}" class="inline-icon"> Initial Consultations</span>
                        <span class="toggle-icon">▼</span>
                    </div>
                    <div class="section-content">
"""

            for consultation in record['initial_consultations']:
                doctor_name = consultation.get('doctor_name', 'Unknown')
                doctor_engine = consultation.get('doctor_engine_name', 'Unknown')
                doctor_id = consultation.get('doctor_id', 0)

                # Assign unique color to each doctor
                doctor_color = doctor_colors[doctor_id % len(doctor_colors)]

                html_content += f"""                        <div class="doctor-consultation" style="border-color: {doctor_color};">
                            <div class="doctor-header" style="background: {doctor_color};">
                                <span><img src="{icons['doctor']}" class="inline-icon"> {doctor_name}</span>
                                <span>Engine: {doctor_engine} | ID: {doctor_id}</span>
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
                                    <span class="turn-number">Turn {turn_num}</span>
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
                                <h4 style="color: {doctor_color}; margin-bottom: 15px;"><img src="{icons['doctor']}" class="inline-icon"> {doctor_name}'s Diagnosis</h4>
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
                        <span><img src="{icons['collaborate']}" class="inline-icon"> Discussion Rounds</span>
                        <span class="toggle-icon">▼</span>
                    </div>
                    <div class="section-content">
"""

            for round_idx, round_data in enumerate(record['diagnosis_in_discussion']):
                turn_num = round_data.get('turn', round_idx + 1)  # Turn numbers start at 1 now
                html_content += f"""                        <div class="discussion-round">
                            <div class="round-header">
                                <span><img src="{icons['collaborate']}" class="inline-icon"></span>
                                <span>Turn {turn_num}</span>
                            </div>
"""

                num_doctors = len(record.get('initial_consultations', []))

                # ===== PHASE 1: Doctors Report to Host =====
                # For Turn 1, initial reports are already in diagnosis_in_turn (from initial consultations)
                # For Turn 2+, show previous round's revised diagnoses as reports
                html_content += """                            <div style="margin: 25px 0; padding: 20px; background: #f0f4ff; border-radius: 10px; border: 2px solid #667eea;">
                                <h4 style="color: #667eea; margin-bottom: 20px; font-size: 1.2em; display: flex; align-items: center; gap: 10px;">
                                    <span style="background: #667eea; color: white; padding: 5px 15px; border-radius: 20px; font-size: 0.9em;">Phase 1</span>
                                    <span>Report</span>
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
                                        <div style="font-size: 0.9em; color: #666; font-style: italic;">Reports {'initial diagnosis' if diag_info['is_initial'] else 'revised diagnosis'} to host</div>
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
                                        <span>Host's Analysis (Conflicts & Commonalities)</span>
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
                                        <span>Host's Analysis (Conflicts & Commonalities)</span>
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
                        decision_status = 'Discussion ends'
                        icon = '<span style="color: #4caf50; font-size: 1.5em;">✓</span>'
                        bg_color = '#e8f5e9'
                        border_color = '#4caf50'
                    elif action == 'begin_discussion':
                        decision_status = 'Discussion begins'
                        icon = '<span style="color: #2196f3; font-size: 1.5em;">↻</span>'
                        bg_color = '#e3f2fd'
                        border_color = '#2196f3'
                    elif action == 'update_with_patient_info':
                        decision_status = 'Update with patient information'
                        icon = '<span style="color: #ff9800; font-size: 1.5em;">💬</span>'
                        bg_color = '#fff3e0'
                        border_color = '#ff9800'
                    elif action in ['continue_discussion', 'query_patient']:
                        decision_status = 'Discussion continues'
                        icon = '<span style="color: #2196f3; font-size: 1.5em;">↻</span>'
                        bg_color = '#e3f2fd'
                        border_color = '#2196f3'
                    else:
                        decision_status = f'Action: {action}'
                        icon = '<span style="color: #ff9800; font-size: 1.5em;">?</span>'
                        bg_color = '#fff3e0'
                        border_color = '#ff9800'

                    html_content += f"""                                <div style="background: {bg_color}; border-left: 4px solid {border_color}; padding: 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <div style="font-weight: bold; color: {border_color}; margin-bottom: 10px; display: flex; align-items: center; gap: 10px; font-size: 1.1em;">
                                        <span style="font-size: 1.5em;">{icon}</span>
                                        <span>Host Decision: {decision_status}</span>
                                    </div>
"""

                    # Show query to patient if exists
                    if query and action == 'query_patient':
                        html_content += f"""                                    <div style="margin-top: 15px;">
                                        <strong style="color: #ff9800;">Query to Patient:</strong>
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
                                        <span>Patient Response → Host</span>
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
                                    <span style="background: #4caf50; color: white; padding: 5px 15px; border-radius: 20px; font-size: 0.9em;">Phase 2</span>
                                    <span>Revision</span>
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
                                        <img src="{icons['doctor']}" class="inline-icon"> {doctor_name}'s Turn to Revise
                                    </div>

                                    <div style="margin: 15px 0; padding: 12px; background: #f8f9fa; border-radius: 6px;">
                                        <div style="font-weight: bold; color: #667eea; margin-bottom: 10px; font-size: 0.95em;">Receives input from:</div>
"""

                                # Show input from host
                                html_content += f"""                                        <div style="margin: 8px 0; padding: 8px; background: white; border-left: 3px solid #ffa726; border-radius: 4px;">
                                            <div style="display: flex; align-items: center; gap: 8px; font-size: 0.9em;">
                                                <span style="color: #ffa726; font-weight: bold;"><img src="{icons['host']}" class="inline-icon"> Host</span>
                                                <span style="font-size: 1.2em; color: #667eea;">→</span>
                                                <span style="color: {doctor_color}; font-weight: bold;"><img src="{icons['doctor']}" class="inline-icon"> {doctor_name}</span>
                                            </div>
                                            <div style="font-size: 0.85em; color: #666; margin-top: 4px; font-style: italic;">Host's summary and critique</div>
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
                                            <div style="font-size: 0.85em; color: #666; margin-top: 4px; font-style: italic;">{other_name}'s diagnosis</div>
                                        </div>
"""

                                html_content += """                                    </div>
"""

                                # Show revised diagnosis
                                html_content += f"""                                    <div style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid {doctor_color};">
                                        <div style="font-weight: bold; color: {doctor_color}; margin-bottom: 12px; font-size: 1em;">
                                            <img src="{icons['doctor']}" class="inline-icon"> Revised Diagnosis ({doctor_engine})
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
                                    <span>Host's Final Consensus Diagnosis</span>
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
                    <h3 style="color: {final_diag_color}; margin-bottom: 20px; font-size: 1.5em;"><img src="{icons['collaborate']}" class="inline-icon"> Final Diagnosis</h3>
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
