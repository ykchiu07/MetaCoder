import requests
import json
from typing import Dict, Tuple, Optional, Any
import subprocess

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def _calculate_entropy(self, raw_response: Dict) -> float:
        """從 Logprobs 計算生成熵 (信心指標)"""
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
        """發送請求並強制回傳 JSON"""
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "format": "json",
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 4096},
            "logprobs": True
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

    # 修改此方法簽名與實作
    def chat_complete_raw(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        images: Optional[List[str]] = None # 新增 images 參數
    ) -> Tuple[str, float]:
        """發送請求並回傳原始字串"""

        # 構建 User Message
        user_msg = {"role": "user", "content": user_prompt}
        if images:
            user_msg["images"] = images  # Ollama API 支援此格式

        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, user_msg],
            "stream": False,
            "logprobs": True,
            "options": {"temperature": temperature}
        }

        try:
            response = requests.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            raw_response = response.json()

            content_str = raw_response['message']['content']
            entropy = self._calculate_entropy(raw_response)
            return content_str, entropy
        except Exception as e:
            print(f"[OllamaClient Error] {e}")
            raise
