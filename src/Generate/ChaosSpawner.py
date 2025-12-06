import os
import json
import time
from typing import Dict, List, Any, Tuple
from OllamaClient import OllamaClient

class ChaosSpawner:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.client = OllamaClient(ollama_url)

    def _extract_json(self, text: str) -> Dict:
        """嘗試從 LLM 回應中提取 JSON"""
        import re
        try:
            # 優先尋找 markdown json block
            match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            # 其次嘗試直接解析
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"[ChaosSpawner] JSON Parse Error. Raw text: {text[:100]}...")
            return {}

    def generateWeaknessAnalysis(
        self,
        module_name: str,
        project_root: str,  # 傳入專案根目錄以便尋找模組
        model_name: str = "gemma3:12b"
    ) -> Tuple[str, float]:
        """
        [Phase 1] 弱點掃描：分析模組內函式的職責，評估崩潰風險。
        """
        module_dir = os.path.join(project_root, module_name)
        spec_path = os.path.join(module_dir, "spec.json")

        if not os.path.exists(spec_path):
            return f"Error: Spec not found at {spec_path}", 0.0

        print(f"[*] [ChaosSpawner] Analyzing weakness for '{module_name}'...")

        # 1. 讀取規格
        with open(spec_path, 'r', encoding='utf-8') as f:
            spec_data = json.load(f)

        # 2. 構建 Prompt
        # 我們只提供函式簽名與描述，不提供程式碼，讓模型從架構層面判斷
        funcs_summary = []
        for f in spec_data.get('functions', []):
            funcs_summary.append({
                "name": f['name'],
                "args": [a['name'] for a in f.get('args', [])],
                "desc": f.get('docstring', '')
            })

        system_prompt = (
            "You are a Chaos Engineering Architect. "
            "Analyze the provided functions and estimate their 'Vulnerability Level' to faults "
            "(e.g., IO failures, timeout, bad input).\n"
            "\n"
            "RATING CRITERIA:\n"
            "- HIGH: Functions involving File IO, Network, DB, or Complex State Mutation.\n"
            "- MEDIUM: Functions with complex logic loops or conditional branches.\n"
            "- LOW: Pure utility functions, simple getters/setters.\n"
            "\n"
            "Output strictly valid JSON format:\n"
            "{\n"
            "  'module_name': 'str',\n"
            "  'analysis': [\n"
            "    {'function': 'func_name', 'level': 'High/Medium/Low', 'reason': 'Brief explanation'}\n"
            "  ]\n"
            "}"
        )

        user_prompt = (
            f"MODULE: {module_name}\n"
            f"FUNCTIONS: {json.dumps(funcs_summary, indent=2)}\n\n"
            "Perform vulnerability analysis."
        )

        # 3. 呼叫 LLM
        content_str, entropy = self.client.chat_complete_json(model_name, system_prompt, user_prompt)

        # 4. 存檔
        output_path = os.path.join(module_dir, "weakness_analysis.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(content_str, f, indent=4, ensure_ascii=False)

        return output_path, entropy

    def generateChaosPlan(
        self,
        weakness_path: str,
        focus_level: int,  # 1=Low, 2=Med, 3=High
        model_name: str = "gemma3:12b"
    ) -> Tuple[str, float]:
        """
        [Phase 2] 制定計畫：針對篩選出的函式，讀取原始碼並設計注入策略。
        """
        if not os.path.exists(weakness_path):
            return f"Error: Analysis not found at {weakness_path}", 0.0

        module_dir = os.path.dirname(weakness_path)

        print(f"[*] [ChaosSpawner] Generating Chaos Plan (Level >= {focus_level})...")

        # 1. 讀取分析報告
        with open(weakness_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)

        # 等級對照表
        level_map = {"low": 1, "medium": 2, "high": 3}

        # 2. 篩選目標函式並讀取原始碼
        target_funcs_context = []

        for item in analysis_data.get('analysis', []):
            lvl_str = item.get('level', 'Low').lower()
            lvl_int = level_map.get(lvl_str, 1)

            if lvl_int >= focus_level:
                func_name = item['function']
                # 推導實作檔案路徑
                filename = "__init_logic__.py" if func_name == "__init__" else f"{func_name}.py"
                file_path = os.path.join(module_dir, filename)

                code_content = "<missing>"
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code_content = f.read()

                target_funcs_context.append({
                    "name": func_name,
                    "vulnerability": lvl_str,
                    "source_code": code_content
                })

        if not target_funcs_context:
            return "No functions match the focus level.", 0.0

        # 3. 構建 Prompt：要求生成具體參數
        system_prompt = (
            "You are a Gremlin Chaos Engineer. "
            "Create a specific 'Fault Injection Plan' for the provided Python functions. "
            "For each function, design 3 specific experiments.\n"
            "\n"
            "INJECTION TYPES:\n"
            "1. Exception: Force the function to raise an error (e.g., ValueError, TimeoutError).\n"
            "2. Latency: Inject sleep() to simulate lag.\n"
            "3. DataCorruption: Pass None, empty strings, or huge numbers as arguments.\n"
            "\n"
            "Output strictly valid JSON format:\n"
            "{\n"
            "  'plan_id': 'timestamp',\n"
            "  'experiments': [\n"
            "    {\n"
            "      'target_function': 'func_name',\n"
            "      'injections': [\n"
            "        {'type': 'Exception', 'details': 'Raise FileNotFoundError'},\n"
            "        {'type': 'DataCorruption', 'arg_name': 'x', 'value': 'None'}\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        user_prompt = (
            f"TARGETS (Level >= {focus_level}):\n"
            f"{json.dumps(target_funcs_context, indent=2)}\n\n"
            "Design a chaos test plan based on the source code logic."
        )

        # 4. 呼叫 LLM
        content_str, entropy = self.client.chat_complete_json(model_name, system_prompt, user_prompt)

        # 5. 存檔
        output_path = os.path.join(module_dir, "chaos_plan.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(content_str, f, indent=4, ensure_ascii=False)

        return output_path, entropy
