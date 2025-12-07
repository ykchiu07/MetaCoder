import os
import json
import time
from typing import Dict, Any, List
from dataclasses import dataclass
from OllamaClient import OllamaClient

import threading # 新增引用

@dataclass
class GenerationResult:
    structure_file_path: str
    project_root_path: str
    model_entropy: float
    execution_time: float

@dataclass
class ModuleDetailResult:
    spec_file_path: str
    fragment_files: List[str]
    model_entropy: float

class ProjectManager:
    def __init__(self, workspace_dir: str = "./vibe_workspace", ollama_url: str = "http://localhost:11434"):
        self.workspace_dir = workspace_dir
        self.client = OllamaClient(ollama_url)
        if not os.path.exists(workspace_dir):
            os.makedirs(workspace_dir)

    def generateHighStructure(self, project_requirements: str, model_name: str) -> GenerationResult:
        """(Phase 1) 生成專案總架構並建立資料夾結構"""
        print(f"[*] (Phase 1) Generating Architecture with {model_name}...")
        start_time = time.time()

        system_prompt = (
            "You are an expert Python Software Architect. "
            "Design a modular architecture based on the user's requirements. "
            "\n\n"
            "CRITICAL REQUIREMENTS:\n"
            "1. Define a clear entry point (e.g., 'main.py' or 'app.py') that orchestrates the modules.\n"
            "2. Define strict dependencies. If Module A imports Module B, Module A depends on B.\n"
            "3. Avoid circular dependencies.\n"
            "\n"
            "Output strict JSON:\n"
            "{\n"
            "  'project_name': 'str',\n"
            "  'entry_point': 'main.py',\n"  # 新增
            "  'modules': [\n"
            "    {\n"
            "      'name': 'auth',\n"
            "      'description': 'Handles user login/register',\n"
            "      'dependencies': ['database', 'utils'],\n" # 強制填寫
            "      'public_api_summary': ['login(user, pass)', 'logout()']\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        data, entropy, stats = self.client.chat_complete_json(model_name, system_prompt, f"Req: {project_requirements}")

        project_name = data.get("project_name", "vibe_project").replace(" ", "_")
        project_dir = os.path.join(self.workspace_dir, project_name)
        if not os.path.exists(project_dir): os.makedirs(project_dir)

        arch_path = os.path.join(project_dir, "architecture.json")
        with open(arch_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        for mod in data.get('modules', []):
            mod_dir = os.path.join(project_dir, mod['name'])
            if not os.path.exists(mod_dir): os.makedirs(mod_dir)

        return GenerationResult(arch_path, project_dir, entropy, time.time() - start_time)

    def generateModuleDetail(self, architecture_path: str, target_module_name: str, progress_data: Dict[str, Any], model_name: str,cancel_event: threading.Event = None ) -> ModuleDetailResult:
        """
        (Phase 2) 單一模組細化
        **優化重點**：強化參數完整性 Prompt
        """
        print(f"[*] (Phase 2) Refining Module '{target_module_name}' with {model_name}...")

        with open(architecture_path, 'r', encoding='utf-8') as f:
            arch_data = json.load(f)

        # [Fix 4] 提前定義 mod_dir
        project_dir = os.path.dirname(architecture_path)
        mod_dir = os.path.join(project_dir, target_module_name)
        if not os.path.exists(mod_dir): os.makedirs(mod_dir)

        target_mod_info = next((m for m in arch_data.get('modules', []) if m['name'] == target_module_name), None)
        if not target_mod_info: raise ValueError(f"Module '{target_module_name}' not found.")

        declared_deps = target_mod_info.get('dependencies', [])

        # 構建 Context：只提供「被依賴模組」的詳細資訊
        dep_context = "DEPENDENCY CONTEXT (You can use these APIs):\n"
        project_dir = os.path.dirname(architecture_path)

        for dep in declared_deps:
            dep_spec_path = os.path.join(project_dir, dep, "spec.json")
            if os.path.exists(dep_spec_path):
                with open(dep_spec_path, 'r') as f:
                    spec = json.load(f)
                    # 簡化 API 描述
                    funcs = [f"{fn['name']}(...)" for fn in spec.get('functions', [])]
                    dep_context += f"- Module '{dep}': {spec.get('description')}\n  Available: {', '.join(funcs)}\n"
            else:
                dep_context += f"- Module '{dep}': (Spec not generated yet)\n"

        system_prompt = (
            "You are a Senior Python Developer. Define the detailed specification for a module.\n"
            "\n"
            "CRITICAL RULES FOR DEPENDENCIES:\n"
            f"1. This module is architected to depend on: {json.dumps(declared_deps)}.\n"
            "2. You MUST include a 'dependencies' field in the output JSON matching this list.\n"
            "3. In the 'docstring' of each function, explicitly state which external functions it calls (e.g., 'Calls auth.login').\n"
            "\n"
            "Output strict JSON:\n"
            "{\n"
            "  'module_name': 'str',\n"
            "  'dependencies': ['mod_a', 'mod_b'],\n" # 強制欄位
            "  'functions': [\n"
            "    {\n"
            "      'name': 'func_name',\n"
            "      'args': [...],\n"
            "      'return_type': '...',\n"
            "      'docstring': '...'\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        user_prompt = (
            f"PROJECT: {arch_data.get('project_name')}\n"
            f"TARGET MODULE: {target_module_name}\n"
            f"DESCRIPTION: {target_mod_info.get('description')}\n\n"
            f"{dep_context}\n"
            "Generate the full spec.json."
        )

        # 在生成 Spec 之前檢查
        if cancel_event and cancel_event.is_set():
            print("[ProjectManager] Operation Cancelled.")
            return None

        # 呼叫 LLM
        spec_data, entropy, _ = self.client.chat_complete_json(model_name, system_prompt, user_prompt, cancel_event=cancel_event)

        # 強制補全依賴
        if 'dependencies' not in spec_data:
            spec_data['dependencies'] = declared_deps

        # 存檔 (現在 mod_dir 已經定義了)
        spec_path = os.path.join(mod_dir, "spec.json")
        with open(spec_path, 'w', encoding='utf-8') as f:
            json.dump(spec_data, f, indent=4, ensure_ascii=False)

        fragment_paths = []

        for func in spec_data.get('functions', []):
            if cancel_event and cancel_event.is_set():
                print("[ProjectManager] Fragment generation cancelled.")
                break

        # 建立 __init__.py
        init_py_path = os.path.join(mod_dir, "__init__.py")
        with open(init_py_path, 'w', encoding='utf-8') as f:
            f.write(f"# Package marker for {target_module_name}\n")
        fragment_paths.append(init_py_path)

        # [防禦性編程] 強制補全依賴 (以架構定義為準)
        if 'dependencies' not in spec_data:
            spec_data['dependencies'] = declared_deps

        spec_path = os.path.join(mod_dir, "spec.json")
        with open(spec_path, 'w', encoding='utf-8') as f:
            json.dump(spec_data, f, indent=4, ensure_ascii=False)

        # 建立 Stubs
        progress_data['status'] = f"Creating file stubs..."
        for func in spec_data.get('functions', []):
            func_name = func['name']
            filename = "__init_logic__.py" if func_name == "__init__" else f"{func_name}.py"
            file_path = os.path.join(mod_dir, filename)

            args_str = ", ".join([f"{arg['name']}: {arg.get('type', 'Any')}" for arg in func.get('args', [])])
            return_hint = func.get('return_type', 'Any')
            docstring = func.get('docstring', '').replace('\n', '\n    ')

            stub_content = (
                f"from typing import Any, List, Dict, Optional\n\n"
                f"def {func_name}({args_str}) -> {return_hint}:\n"
                f"    \"\"\"\n    {docstring}\n    \"\"\"\n"
                f"    pass\n"
            )

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(stub_content)
            fragment_paths.append(file_path)

        progress_data['status'] = "Refinement Complete"
        return ModuleDetailResult(spec_path, fragment_paths, entropy)
