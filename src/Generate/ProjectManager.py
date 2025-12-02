import os
import json
import time
from typing import Dict, Any, List
from dataclasses import dataclass
from OllamaClient import OllamaClient

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

    def generateModuleDetail(self, architecture_path: str, target_module_name: str, progress_data: Dict[str, Any], model_name: str) -> ModuleDetailResult:
        """
        (Phase 2) 單一模組細化
        **優化重點**：強化參數完整性 Prompt
        """
        print(f"[*] (Phase 2) Refining Module '{target_module_name}' with {model_name}...")

        with open(architecture_path, 'r', encoding='utf-8') as f:
            arch_data = json.load(f)

        project_dir = os.path.dirname(architecture_path)
        mod_dir = os.path.join(project_dir, target_module_name)
        if not os.path.exists(mod_dir): os.makedirs(mod_dir)

        target_mod_info = next((m for m in arch_data.get('modules', []) if m['name'] == target_module_name), None)
        if not target_mod_info: raise ValueError(f"Module '{target_module_name}' not found.")

        progress_data['status'] = f"Generating spec for {target_module_name}..."

        context_str = (
            f"Project: {arch_data.get('project_name')}\n"
            f"Module: {target_module_name}\n"
            f"Description: {target_mod_info.get('description')}\n"
            f"Dependencies: {target_mod_info.get('dependencies')}\n"
            f"Suggested APIs: {target_mod_info.get('public_api_summary')}"
        )

        # --- 優化後的 Prompt ---
        system_prompt = (
            "You are a Senior Python Developer. "
            "Define the detailed specification for this module. "
            "The module will be implemented as a Class. "
            "\n\n"
            "CRITICAL INSTRUCTION ON PARAMETERS:\n"
            "1. Do NOT rely on hardcoded strings inside functions. Everything dynamic must be an argument.\n"
            "2. Do NOT abstract away necessary data. If an API key or Database connection is needed, it must be passed in `__init__` or the method itself.\n"
            "3. Be explicit about types (e.g., 'url: str', 'timeout: int', 'api_key: str').\n"
            "\n"
            "Output strict JSON. Format:\n"
            "{\n"
            "  'module_name': 'str',\n"
            "  'class_name': 'str (CamelCase)',\n"
            "  'functions': [\n"
            "    {\n"
            "      'name': '__init__',\n"
            "      'access': 'public',\n"
            "      'args': [{'name': 'config', 'type': 'dict'}, {'name': 'base_url', 'type': 'str'}],\n"
            "      'return_type': 'None',\n"
            "      'docstring': 'Initializes with config and base_url...'\n"
            "    },\n"
            "    {\n"
            "      'name': 'fetch_stock_data',\n"
            "      'access': 'public',\n"
            "      'args': [{'name': 'ticker', 'type': 'str'}, {'name': 'endpoint', 'type': 'str'}],\n"
            "      'return_type': 'dict',\n"
            "      'docstring': 'Fetches data from {base_url}/{endpoint}?ticker={ticker}'\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        spec_data, entropy, _ = self.client.chat_complete_json(model_name, system_prompt, f"Context:\n{context_str}")

        spec_path = os.path.join(mod_dir, "spec.json")
        with open(spec_path, 'w', encoding='utf-8') as f:
            json.dump(spec_data, f, indent=4, ensure_ascii=False)

        fragment_paths = []

        # 建立 __init__.py
        init_py_path = os.path.join(mod_dir, "__init__.py")
        with open(init_py_path, 'w', encoding='utf-8') as f:
            f.write(f"# Package marker for {target_module_name}\n")
        fragment_paths.append(init_py_path)

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
