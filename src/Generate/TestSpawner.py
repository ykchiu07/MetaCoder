import os
import json
import time
import re
from typing import List, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from OllamaClient import OllamaClient

@dataclass
class TestGenerationResult:
    target_name: str  # 測試目標 (函式名、模組對、或劇本名)
    test_file_path: str
    model_entropy: float
    duration: float
    skipped: bool = False

class TestSpawner:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.client = OllamaClient(ollama_url)

    def _extract_python_code(self, text: str) -> str:
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if match: return match.group(1)
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match: return match.group(1)
        return text

    def _should_generate_test(self, return_type: str) -> bool:
        """判斷是否需要生成單元測試 (有無回傳值)"""
        if not return_type: return False
        normalized = return_type.lower().strip()
        return normalized not in ['none', 'void', 'noreturn', 'nothing']

    def _generate_single_test(self, spec_data: Dict, func_name: str, tests_dir: str, model_name: str = "gemma3:12b") -> TestGenerationResult:
        start_time = time.time()

        # 1. 獲取函式規格
        target_func_spec = next((f for f in spec_data.get('functions', []) if f['name'] == func_name), None)
        if not target_func_spec:
            return TestGenerationResult(func_name, "", -1.0, 0.0, True)

        # 2. 檢查回傳值
        return_type = target_func_spec.get('return_type', 'None')
        if not self._should_generate_test(return_type):
            print(f"    > Skipping test for {func_name} (Return type: {return_type})")
            return TestGenerationResult(func_name, "", 0.0, 0.0, True)

        print(f"    > Generating Unit Test for {func_name}...")

        # 3. 準備檔案路徑
        test_filename = f"test_{func_name}.py"
        test_file_path = os.path.join(tests_dir, test_filename)

        # 4. 準備 Prompt
        module_name = spec_data.get('module_name', 'unknown_module')

        system_prompt = (
            "You are a QA Engineer Expert in Python unittest. "
            "Write a comprehensive unit test for the specified function. "
            "1. Import `unittest`. "
            "2. Assume the function is available to import (e.g., `from ..{func_name} import {func_name}`). "
            "3. Cover at least 2-3 scenarios (normal case, edge case). "
            "4. Assert the return value matches expectation. "
            "5. Output ONLY the python code."
        )

        func_info = (
            f"Module: {module_name}\n"
            f"Function: {func_name}\n"
            f"Arguments: {target_func_spec.get('args')}\n"
            f"Return Type: {return_type}\n"
            f"Description: {target_func_spec.get('docstring')}"
        )

        user_prompt = (
            f"Target Function Info:\n{func_info}\n\n"
            "Generate the unittest code now:"
        )

        try:
            content_str, entropy = self.client.chat_complete_raw(model_name, system_prompt, user_prompt)
            code_body = self._extract_python_code(content_str)

            # 加入 sys.path hack 讓測試在碎片化狀態下也能跑 (可選，視您如何執行測試而定)
            # 這裡簡單加上標準 import 頭
            if "import unittest" not in code_body:
                code_body = "import unittest\n" + code_body

            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(code_body)

            return TestGenerationResult(func_name, test_file_path, entropy, time.time() - start_time, False)

        except Exception as e:
            print(f"[!] Error generating test for {func_name}: {e}")
            return TestGenerationResult(func_name, "", -1.0, 0.0, True)

    def generateUnitTest(self, spec_path: str, target_function_names: List[str], model_name: str= "gemma3:12b") -> List[TestGenerationResult]:
        """
        批次生成單元測試
        """
        if not os.path.exists(spec_path):
            raise FileNotFoundError(f"Spec file not found: {spec_path}")

        with open(spec_path, 'r', encoding='utf-8') as f:
            spec_data = json.load(f)

        module_dir = os.path.dirname(spec_path)
        tests_dir = os.path.join(module_dir, "tests")
        if not os.path.exists(tests_dir):
            os.makedirs(tests_dir)

        results = []
        print(f"[*] Spawning tests for {len(target_function_names)} functions...")

        # 同樣支援並行生成
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_name = {
                executor.submit(self._generate_single_test, spec_data, name, tests_dir, model_name): name
                for name in target_function_names
            }

            for future in as_completed(future_to_name):
                res = future.result()
                results.append(res)
                if not res.skipped:
                    print(f"    [Test Created] {res.test_file_path} (Entropy: {res.model_entropy})")

        return results

# --- 新增功能 1: 整合測試 ---
    def generateIntegrationTest(
        self,
        caller_spec_path: str,
        callee_spec_path: str,
        tests_dir: str,
        model_name: str
    ) -> TestGenerationResult:
        """
        生成整合測試：測試 Caller 模組與 Callee 模組之間的互動。
        """
        start_time = time.time()

        # 1. 讀取雙方規格
        if not os.path.exists(caller_spec_path) or not os.path.exists(callee_spec_path):
            return TestGenerationResult("Integration", "", -1.0, 0.0, True)

        with open(caller_spec_path, 'r') as f: caller_data = json.load(f)
        with open(callee_spec_path, 'r') as f: callee_data = json.load(f)

        caller_mod = caller_data['module_name']
        callee_mod = callee_data['module_name']

        filename = f"test_integration_{caller_mod}_v_{callee_mod}.py"
        target_path = os.path.join(tests_dir, filename)

        print(f"[*] Generating Integration Test: {caller_mod} -> {callee_mod}...")

        # 2. 構建 Context：讓 LLM 看到雙方的 Public API
        # 我們只提供簽名 (Signature)，不提供實作，迫使 LLM 關注「介面」
        def extract_public_api(data):
            return [
                f"{f['name']}({', '.join([a['name'] for a in f.get('args', [])])}) -> {f.get('return_type')}"
                for f in data.get('functions', [])
                if f.get('access') == 'public' or f['name'] == '__init__'
            ]

        context_str = (
            f"--- Caller Module: {caller_mod} ---\n"
            f"Description: {caller_data.get('description')}\n"
            f"Public APIs: {json.dumps(extract_public_api(caller_data), indent=2)}\n\n"
            f"--- Callee Module: {callee_mod} ---\n"
            f"Description: {callee_data.get('description')}\n"
            f"Public APIs: {json.dumps(extract_public_api(callee_data), indent=2)}\n"
        )

        # 3. Prompt 設計：防止 Mock 依賴
        system_prompt = (
            "You are a Senior Python QA Engineer specializing in Integration Testing. "
            "Your goal is to verify the contract (handshake) between two specific modules.\n"
            "\n"
            "CRITICAL RULES (To avoid Unit-Test style):\n"
            "1. DO NOT MOCK the Callee Module. You must import and instantiate the REAL class/functions of the Callee.\n"
            "2. You MAY mock external systems (Database, Network, Filesystem) if the Callee uses them.\n"
            "3. Verify that the Caller correctly handles the return values or exceptions from the Callee.\n"
            "4. Structure the test to setup the Callee first, then inject it into the Caller (Dependency Injection pattern).\n"
            "5. Output ONLY Python code."
        )

        user_prompt = (
            f"INTEGRATION CONTEXT:\n{context_str}\n\n"
            f"Task: Write a unittest case where '{caller_mod}' calls '{callee_mod}'. "
            "Ensure data flows correctly between them."
        )

        # 4. 生成與存檔
        try:
            content, entropy = self.client.chat_complete_raw(model_name, system_prompt, user_prompt)
            code = self._extract_python_code(content)

            # 加入必要的 import 修正 (假設專案結構)
            header = "import unittest\nimport sys\nimport os\nsys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))\n"
            if "import unittest" not in code:
                code = header + code
            else:
                # 插入 sys.path hack 在 import unittest 之後
                code = code.replace("import unittest", header)

            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(code)

            return TestGenerationResult(f"{caller_mod}->{callee_mod}", target_path, entropy, time.time() - start_time, False)

        except Exception as e:
            print(f"[!] Integration Test Gen Error: {e}")
            return TestGenerationResult("Integration", "", -1.0, 0.0, True)


    # --- 新增功能 2: 模擬系統測試 (End-to-End Mock) ---
    def generateMockSystemTest(
        self,
        architecture_path: str,
        scenario_description: str,
        tests_dir: str,
        model_name: str
    ) -> TestGenerationResult:
        """
        生成模擬系統測試：根據使用者劇本，串接多個模組。
        """
        start_time = time.time()

        # 1. 讀取架構圖 (God View)
        with open(architecture_path, 'r') as f: arch_data = json.load(f)

        filename = f"test_system_scenario_{int(time.time())}.py"
        target_path = os.path.join(tests_dir, filename)

        print(f"[*] Generating System Test for Scenario: {scenario_description[:30]}...")

        # 2. 構建 Context：提供所有模組的簡介，讓 LLM 知道有哪些積木可用
        modules_overview = []
        for m in arch_data.get('modules', []):
            modules_overview.append(f"- Module '{m['name']}': {m.get('description')}")
            # 若有 API summary 也可加入，但保持簡短以免 context 爆炸

        context_str = "\n".join(modules_overview)

        # 3. Prompt 設計：強調狀態流轉 (State Propagation)
        system_prompt = (
            "You are a System Architect writing an End-to-End System Test. "
            "Your goal is to simulate a complete user workflow using multiple internal modules.\n"
            "\n"
            "CRITICAL RULES:\n"
            "1. NO ISOLATION: Do not test functions in vacuum. Connect them.\n"
            "2. STATE PROPAGATION: The output of Step 1 MUST be passed as input to Step 2. (e.g., `user = auth.login(); profile = db.get_profile(user.id)`)\n"
            "3. MOCK BOUNDARIES ONLY: Use `unittest.mock` ONLY for IO (Network, Disk, API). Do NOT mock internal logic classes.\n"
            "4. Write a script that executes the scenario from start to finish.\n"
            "5. Output ONLY Python code."
        )

        user_prompt = (
            f"SYSTEM ARCHITECTURE:\n{context_str}\n\n"
            f"TARGET SCENARIO: \"{scenario_description}\"\n\n"
            "Write a python script (using unittest) to verify this scenario."
        )

        # 4. 生成與存檔
        try:
            content, entropy = self.client.chat_complete_raw(model_name, system_prompt, user_prompt)
            code = self._extract_python_code(content)

            header = "import unittest\nimport sys\nimport os\nsys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))\n"
            if "import unittest" not in code:
                code = header + code
            else:
                code = code.replace("import unittest", header)

            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(code)

            return TestGenerationResult("SystemScenario", target_path, entropy, time.time() - start_time, False)

        except Exception as e:
            print(f"[!] System Test Gen Error: {e}")
            return TestGenerationResult("SystemScenario", "", -1.0, 0.0, True)
