import os
import json
import time
import requests
import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

# --- 1. 通用層：Ollama API 客戶端 (維持不變) ---
class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def _calculate_entropy(self, raw_response: Dict) -> float:
        try:
            logprobs_list = raw_response.get('logprobs')
            if logprobs_list is None and 'message' in raw_response:
                logprobs_list = raw_response['message'].get('logprobs')
            if not logprobs_list: return -1.0
            total_logprob = 0.0
            count = 0
            for item in logprobs_list:
                lp = item.get('logprob')
                if lp is not None:
                    total_logprob += lp
                    count += 1
            if count == 0: return 0.0
            return round(-(total_logprob / count), 4)
        except Exception:
            return -1.0

    def chat_complete_json(self, model: str, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> Tuple[Dict, float, Dict]:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "format": "json", "stream": False, "options": {"temperature": temperature, "num_ctx": 4096}, "logprobs": True
        }
        try:
            response = requests.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            raw_response = response.json()
            content_str = raw_response['message']['content']
            parsed_json = json.loads(content_str)
            entropy = self._calculate_entropy(raw_response)
            stats = {k: v for k, v in raw_response.items() if k not in ['logprobs', 'message']}
            return parsed_json, entropy, stats
        except Exception as e:
            print(f"[OllamaClient Error] {e}")
            raise

# --- 2. 業務層：專案生成管理器 ---

@dataclass
class GenerationResult:
    structure_file_path: str  # architecture.json 的路徑
    project_root_path: str    # 專案根目錄路徑
    model_entropy: float
    execution_time: float

@dataclass
class ModuleDetailResult:
    spec_file_path: str       # 生成的 spec.json 路徑
    fragment_files: List[str] # 生成的碎片檔案路徑列表 (__init_logic__.py, func_a.py ...)
    model_entropy: float

class ProjectManager:
    def __init__(self, workspace_dir: str = "./vibe_workspace", ollama_url: str = "http://localhost:11434"):
        self.workspace_dir = workspace_dir
        self.client = OllamaClient(ollama_url)
        if not os.path.exists(workspace_dir):
            os.makedirs(workspace_dir)

    def generateHighStructure(self, project_requirements: str, model_name: str) -> GenerationResult:
        """
        (Phase 1) 生成專案總架構並建立資料夾結構
        """
        print(f"[*] (Phase 1) Generating Architecture with {model_name}...")
        start_time = time.time()

        system_prompt = (
            "You are an expert Python Software Architect. "
            "Break down the user's requirement into a high-level modular architecture. "
            "Output strict JSON. Format: "
            "{\n"
            "  'project_name': 'str',\n"
            "  'modules': [\n"
            "    {\n"
            "      'name': 'module_name',\n"
            "      'description': 'Brief responsibility',\n"
            "      'dependencies': ['dep1', 'dep2'],\n"
            "      'public_api_summary': ['func1', 'func2']\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        data, entropy, stats = self.client.chat_complete_json(model_name, system_prompt, f"Req: {project_requirements}")

        # 1. 建立專案根目錄
        project_name = data.get("project_name", "vibe_project").replace(" ", "_")
        project_dir = os.path.join(self.workspace_dir, project_name)
        if not os.path.exists(project_dir): os.makedirs(project_dir)

        # 2. 儲存架構檔 (architecture.json)
        arch_path = os.path.join(project_dir, "architecture.json")
        with open(arch_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # 3. 建立模組資料夾 (Empty Structure)
        modules = data.get('modules', [])
        for mod in modules:
            mod_name = mod['name']
            mod_dir = os.path.join(project_dir, mod_name)
            if not os.path.exists(mod_dir):
                os.makedirs(mod_dir)
                print(f"    + Created directory: {mod_name}/")

        return GenerationResult(arch_path, project_dir, entropy, time.time() - start_time)

    def generateModuleDetail(self, architecture_path: str, target_module_name: str, progress_data: Dict[str, Any], model_name: str) -> ModuleDetailResult:
        """
        (Phase 2) 單一模組細化：生成 Spec 和 函式碎片檔案 (Stub)
        """
        print(f"[*] (Phase 2) Refining Module '{target_module_name}' with {model_name}...")

        # 1. 讀取架構與定位
        with open(architecture_path, 'r', encoding='utf-8') as f:
            arch_data = json.load(f)

        project_dir = os.path.dirname(architecture_path)
        mod_dir = os.path.join(project_dir, target_module_name)

        if not os.path.exists(mod_dir):
            os.makedirs(mod_dir) # 容錯：如果 Phase 1 沒建到

        # 2. 尋找目標模組的 Context
        target_mod_info = next((m for m in arch_data.get('modules', []) if m['name'] == target_module_name), None)
        if not target_mod_info:
            raise ValueError(f"Module '{target_module_name}' not found in architecture.")

        progress_data['status'] = f"Generating spec for {target_module_name}..."

        # 3. LLM 生成 Spec
        context_str = (
            f"Project: {arch_data.get('project_name')}\n"
            f"Module: {target_module_name}\n"
            f"Description: {target_mod_info.get('description')}\n"
            f"Dependencies: {target_mod_info.get('dependencies')}\n"
            f"Suggested APIs: {target_mod_info.get('public_api_summary')}"
        )

        system_prompt = (
            "You are a Senior Python Developer. "
            "Define the detailed specification for this module. "
            "The module will be implemented as a Class. "
            "1. Define the '__init__' method (initialization). "
            "2. Define other Public/Private methods. "
            "Output strict JSON. Format:\n"
            "{\n"
            "  'module_name': 'str',\n"
            "  'class_name': 'str (CamelCase)',\n"
            "  'functions': [\n"
            "    {\n"
            "      'name': '__init__',\n"
            "      'access': 'public',\n"
            "      'args': [{'name': 'self', 'type': 'Any'}, {'name': 'config', 'type': 'dict'}],\n"
            "      'return_type': 'None',\n"
            "      'docstring': 'Initializes the module...'\n"
            "    },\n"
            "    {\n"
            "      'name': 'do_something',\n"
            "      'access': 'public',\n"
            "      'args': [...],\n"
            "      'return_type': 'bool',\n"
            "      'docstring': '...'\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        spec_data, entropy, _ = self.client.chat_complete_json(model_name, system_prompt, f"Context:\n{context_str}")

        # 4. 存檔 Spec
        spec_path = os.path.join(mod_dir, "spec.json")
        with open(spec_path, 'w', encoding='utf-8') as f:
            json.dump(spec_data, f, indent=4, ensure_ascii=False)

        # 5. 生成檔案碎片 (Fragments)
        fragment_paths = []
        functions = spec_data.get('functions', [])

        # 5.1 建立 __init__.py (Python Package Marker)
        init_py_path = os.path.join(mod_dir, "__init__.py")
        with open(init_py_path, 'w', encoding='utf-8') as f:
            f.write(f"# Package marker for {target_module_name}\n")
        fragment_paths.append(init_py_path)

        # 5.2 建立各個函式的空檔案
        progress_data['status'] = f"Creating file stubs for {target_module_name}..."

        for func in functions:
            func_name = func['name']

            # 處理特殊名稱
            if func_name == "__init__":
                filename = "__init_logic__.py"
            else:
                filename = f"{func_name}.py"

            file_path = os.path.join(mod_dir, filename)

            # 組裝簡單的 Stub 內容 (僅含 def 和 docstring，無實作)
            args_str = ", ".join([f"{arg['name']}: {arg.get('type', 'Any')}" for arg in func.get('args', [])])
            return_hint = func.get('return_type', 'Any')
            docstring = func.get('docstring', '').replace('\n', '\n    ')

            stub_content = (
                f"from typing import Any, List, Dict, Optional\n\n"
                f"def {func_name}({args_str}) -> {return_hint}:\n"
                f"    \"\"\"\n    {docstring}\n    \"\"\"\n"
                f"    pass  # Implementation pending\n"
            )

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(stub_content)

            fragment_paths.append(file_path)

        progress_data['status'] = "Refinement Complete"
        return ModuleDetailResult(spec_path, fragment_paths, entropy)

# --- Wrapper Functions ---
def generateHighStructure(project_requirements: str, model_name: str) -> Dict[str, Any]:
    pm = ProjectManager()
    res = pm.generateHighStructure(project_requirements, model_name)
    return {
        "structure_path": res.structure_file_path,
        "project_root": res.project_root_path,
        "entropy": res.model_entropy,
        "duration": res.execution_time
    }

def generateModuleDetail(architecture_path: str, target_module_name: str, progress_data: Dict, model_name: str) -> Dict[str, Any]:
    pm = ProjectManager()
    res = pm.generateModuleDetail(architecture_path, target_module_name, progress_data, model_name)
    return {
        "spec_path": res.spec_file_path,
        "fragments": res.fragment_files,
        "entropy": res.model_entropy
    }

import os
import json
import time
from LLMGenerate import generateHighStructure, generateModuleDetail

def test_granular_vibe():
    # model_name = "llama3.2:3b" # 建議使用小模型以求速度
    model_name = "gemma3:12b"
    req = "Develop a Python stock analyzer with 3 modules: DataFetcher, Calculator, and Reporter."

    print("=== Step 1: Generate High Structure ===")
    arch_res = generateHighStructure(req, model_name)
    arch_path = arch_res['structure_path']
    print(f"Structure saved: {arch_path}")

    # 讀取剛剛生成的架構，看看有哪些模組
    with open(arch_path, 'r') as f:
        arch_data = json.load(f)
    modules = [m['name'] for m in arch_data['modules']]
    print(f"Modules found: {modules}")

    # 假設使用者選擇了第一個模組進行細化
    target_mod = modules[0]
    print(f"\n=== Step 2: Refining Single Module '{target_mod}' ===")

    progress = {'status': 'Init'}
    detail_res = generateModuleDetail(arch_path, target_mod, progress, model_name)

    print(f"Spec saved: {detail_res['spec_path']}")
    print("Generated Fragments:")
    for path in detail_res['fragments']:
        print(f"  - {os.path.basename(path)}")

    print(f"\nModel Entropy: {detail_res['entropy']}")

if __name__ == "__main__":
    test_granular_vibe()
