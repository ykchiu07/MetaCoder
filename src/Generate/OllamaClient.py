import requests
import json
import os
import base64
from typing import Dict, Tuple, Optional, List, Any

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def chat_complete_json(self, model: str, system_prompt: str, user_prompt: str, temperature: float = 0.2, cancel_event=None) -> Tuple[Dict, float, Dict]:
        """
        支援 cancel_event 的 JSON 請求
        """
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "format": "json",
            "stream": True,
            "options": {"temperature": temperature, "num_ctx": 4096},
            "logprobs": True # [Fix] 啟用 logprobs
        }

        full_content = ""
        total_logprob = 0.0
        token_count = 0

        try:
            with requests.post(f"{self.base_url}/api/chat", json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if cancel_event and cancel_event.is_set():
                        print("[Ollama] Request cancelled by user.")
                        raise InterruptedError("Task Cancelled")

                    if line:
                        try:
                            chunk = json.loads(line)
                            if 'message' in chunk:
                                content = chunk['message'].get('content', '')
                                full_content += content

                            # [Fix] 收集 Logprobs
                            # 根據文件，它可能在 root level (如 /api/generate) 或 message level
                            logs = chunk.get('logprobs')
                            if not logs and 'message' in chunk:
                                logs = chunk['message'].get('logprobs')

                            if logs:
                                for item in logs:
                                    lp = item.get('logprob')
                                    if lp is not None:
                                        total_logprob += lp
                                        token_count += 1
                        except: pass

            # 解析 JSON
            try:
                parsed_json = json.loads(full_content)
            except:
                parsed_json = {}

            # 計算熵值
            entropy = 0.0
            if token_count > 0:
                avg_logprob = total_logprob / token_count
                entropy = round(-avg_logprob, 4)

            return parsed_json, entropy, {}

        except InterruptedError:
            raise
        except Exception as e:
            print(f"[OllamaClient JSON Error] {e}")
            return {}, -1.0, {}

    def chat_complete_raw(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        images: Optional[List[str]] = None,
        cancel_event=None
    ) -> Tuple[str, float]:
        """
        支援 cancel_event 的原始文字請求 (Stream Mode)
        """
        b64_images = []
        if images:
            for img_path in images:
                if os.path.exists(img_path):
                    try:
                        with open(img_path, "rb") as image_file:
                            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                            b64_images.append(encoded_string)
                    except Exception as e:
                        print(f"[OllamaClient] Failed to encode image {img_path}: {e}")

        user_msg = {"role": "user", "content": user_prompt}
        if b64_images: user_msg["images"] = b64_images

        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, user_msg],
            "stream": True,
            "options": {"temperature": temperature},
            "logprobs": True # [Fix] 根據您的文件，啟用 logprobs
        }

        full_content = ""
        total_logprob = 0.0
        token_count = 0

        try:
            with requests.post(f"{self.base_url}/api/chat", json=payload, stream=True, timeout=60) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if cancel_event and cancel_event.is_set():
                        print("[Ollama] Request cancelled by user.")
                        raise InterruptedError("Task Cancelled")

                    if line:
                        try:
                            chunk = json.loads(line)
                            if 'message' in chunk:
                                content = chunk['message'].get('content', '')
                                full_content += content

                            # [Fix] 收集 Logprobs
                            # 優先檢查 root，其次檢查 message 內部 (相容不同 API 版本)
                            logs = chunk.get('logprobs')
                            if not logs and 'message' in chunk:
                                logs = chunk['message'].get('logprobs')

                            if logs:
                                for item in logs:
                                    lp = item.get('logprob')
                                    if lp is not None:
                                        total_logprob += lp
                                        token_count += 1
                        except: pass

            # 計算熵值 (Entropy = - Average Log Probability)
            entropy = 0.0
            if token_count > 0:
                avg_logprob = total_logprob / token_count
                entropy = round(-avg_logprob, 4)

            return full_content, entropy

        except InterruptedError:
            raise
        except Exception as e:
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Task Cancelled")
            print(f"[OllamaClient Raw Error] {e}")
            return f"Error: {str(e)}", -1.0
