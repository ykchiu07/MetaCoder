import requests
import json
import os
import base64
from typing import Dict, Tuple, Optional, List, Any

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def _calculate_entropy(self, raw_response: Dict) -> float:
        # (保持原有的 entropy 計算邏輯不變)
        try:
            # 如果是 stream 模式，logprobs 可能分散在不同 chunks，這裡簡化處理
            # 針對非 stream 的完整回應計算
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

    def chat_complete_json(self, model: str, system_prompt: str, user_prompt: str, temperature: float = 0.2, cancel_event=None) -> Tuple[Dict, float, Dict]:
        """
        [修正] 支援 cancel_event 的 JSON 請求
        """
        # 為了支援中斷，我們必須用 stream=True，然後自己組裝字串
        # 但 JSON 模式通常比較快，且 Ollama 支援 format='json'
        # 這裡示範如何用 stream 攔截

        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "format": "json",
            "stream": True, # [關鍵] 開啟串流
            "options": {"temperature": temperature, "num_ctx": 4096},
            "logprobs": False # Stream 模式下 logprobs 處理較複雜，暫時關閉以提升穩定性
        }

        full_content = ""
        try:
            with requests.post(f"{self.base_url}/api/chat", json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    # [關鍵] 每次讀取一行都檢查取消旗標
                    if cancel_event and cancel_event.is_set():
                        print("[Ollama] Request cancelled by user.")
                        raise InterruptedError("Task Cancelled")

                    if line:
                        chunk = json.loads(line)
                        if 'message' in chunk:
                            content = chunk['message'].get('content', '')
                            full_content += content

            # 嘗試解析最後組裝好的 JSON
            parsed_json = json.loads(full_content)
            return parsed_json, 0.0, {} # Stream 模式暫不計算 Entropy

        except InterruptedError:
            raise # 拋出給上層處理
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
        cancel_event=None # [新增] 接收取消事件
    ) -> Tuple[str, float]:
        """
        [修正] 支援 cancel_event 的原始文字請求 (Stream Mode)
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
            "stream": True, # [關鍵] 開啟串流
            "options": {"temperature": temperature}
        }

        full_content = ""
        try:
            with requests.post(f"{self.base_url}/api/chat", json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    # [關鍵] 檢查取消
                    if cancel_event and cancel_event.is_set():
                        print("[Ollama] Request cancelled by user.")
                        raise InterruptedError("Task Cancelled")

                    if line:
                        chunk = json.loads(line)
                        if 'message' in chunk:
                            content = chunk['message'].get('content', '')
                            full_content += content
                            # 這裡其實可以做即時 UI 輸出 (Streaming Output)，未來可擴充

            return full_content, 0.0

        except InterruptedError:
            raise
        except Exception as e:
            print(f"[OllamaClient Raw Error] {e}")
            return f"Error: {str(e)}", -1.0
