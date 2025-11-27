"""
ローカルDeepSeekモデルへの接続

警告: このモジュールは非推奨です。
新規実装では null_ai/model_router.py (HuggingFace Transformers) を使用してください。

OpenAI/Anthropic等の外部APIは利用規約上の理由からサポートされていません。
"""

import requests
import json
import warnings
from typing import Optional, Dict, AsyncGenerator
import asyncio
from dataclasses import dataclass

# 非推奨警告
warnings.warn(
    "deepseek_local_client.pyは非推奨です。"
    "null_ai/model_router.py (HuggingFace Transformers) の使用を推奨します。",
    DeprecationWarning,
    stacklevel=2
)

@dataclass
class DeepSeekConfig:
    """DeepSeekローカル設定"""
    api_url: str = "http://localhost:8000"  # デフォルト
    model_name: str = "deepseek-r1"
    thinking_length_tokens: int = 8000
    max_tokens: int = 2000
    temperature: float = 0.7
    timeout: int = 300

class DeepSeekLocalClient:
    """ローカルDeepSeekへのAPI呼び出し"""
    
    def __init__(self, config: Optional[DeepSeekConfig] = None):
        self.config = config or DeepSeekConfig()
        self.api_url = self.config.api_url
        # 起動時に接続を試みるのではなく、最初の呼び出し時に確認する方が柔軟
        # self._validate_connection() 
    
    def _validate_connection(self):
        """DeepSeekサーバーへの接続を確認"""
        # Note: text-generation-webuiやollamaには/healthエンドポイントがない場合があるため、
        # より汎用的なエンドポイント（例：/v1/models）を試す方が良いかもしれない。
        # ここでは設計書通りに実装するが、実用上は要調整。
        try:
            # 多くのローカルサーバーは /v1/models を持つ
            response = requests.get(
                f"{self.api_url}/v1/models",
                timeout=5
            )
            if response.status_code == 200:
                print(f"✓ DeepSeek互換サーバーへの接続を確認: {self.api_url}")
                return True
            else:
                # /healthも試す
                response = requests.get(f"{self.api_url}/health", timeout=5)
                response.raise_for_status()
                print(f"✓ DeepSeek互換サーバーへの接続を確認: {self.api_url}")
                return True

        except Exception as e:
            print(f"⚠️  DeepSeek互換サーバーへの接続に失敗: {e}")
            print(f"   確認事項:")
            print(f"   1. ollama/llama.cpp/text-generation-webui等が起動しているか？")
            print(f"   2. APIエンドポイントは正しいか？ (例: http://localhost:8000)")
            return False
            
    def generate(
        self,
        prompt: str,
        thinking_length: Optional[int] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict:
        import time
        start = time.time()
        
        # ollamaなどのOpenAI互換API用のペイロード
        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature or self.config.temperature,
                "num_predict": max_tokens or self.config.max_tokens,
            }
        }
        
        # text-generation-webuiなどのAPIは 'max_tokens' をトップレベルに要求する
        # payload['max_tokens'] = max_tokens or self.config.max_tokens
        
        try:
            # ollamaの /api/generate エンドポイントを想定
            response = requests.post(
                f"{self.api_url}/api/generate",
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            elapsed_ms = int((time.time() - start) * 1000)
            
            full_text = result.get("response", "")
            thinking_text = ""
            final_response = full_text

            # 設計通り、<thinking>タグを解析して思考プロセスを抽出
            if "<thinking>" in full_text and "</thinking>" in full_text:
                thinking_start = full_text.find("<thinking>") + len("<thinking>")
                thinking_end = full_text.find("</thinking>")
                thinking_text = full_text[thinking_start:thinking_end].strip()
                final_response = full_text[thinking_end + len("</thinking>"):].strip()

            return {
                "thinking": thinking_text,
                "response": final_response,
                "success": True,
                "tokens_used": result.get("eval_count", 0),
                "latency_ms": elapsed_ms,
                "raw_response": result
            }
        
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
    
    async def generate_async(self, prompt: str, **kwargs) -> Dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate, prompt, **kwargs)
    
    async def generate_streaming(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        # このストリーミング実装は、ollamaのAPIを想定
        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "stream": True,
        }
        try:
            with requests.post(f"{self.api_url}/api/generate", json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        yield data.get("response", "")
                        if data.get("done"):
                            break
        except Exception as e:
            raise Exception(f"Streaming generation failed: {e}")


class DeepSeekTestHelper:
    @staticmethod
    def test_basic_connection(config: Optional[DeepSeekConfig] = None):
        print("\n【テスト】基本接続")
        try:
            client = DeepSeekLocalClient(config)
            if not client._validate_connection(): return False

            test_prompt = "1+1は何ですか？簡潔に答えてください。"
            print(f"プロンプト: {test_prompt}")
            
            result = client.generate(test_prompt)
            
            print("\n結果:")
            print(f"  ✓ 成功: {result['success']}")
            if result['success']:
                print(f"  レイテンシ: {result['latency_ms']}ms")
                print(f"  応答: {result['response'][:100].strip()}...")
            else:
                print(f"  ✗ エラー: {result['error']}")
            return result['success']
        except Exception as e:
            print(f"  ✗ テスト中に例外発生: {e}")
            return False

if __name__ == "__main__":
    config = DeepSeekConfig(
        api_url="http://localhost:11434",  # 環境に応じて変更
        model_name="deepseek-r1:32b",
    )
    
    print("="*60)
    print("Ilm-Athens DeepSeekLocalClient 接続テスト")
    print("="*60)
    print("注意: このテストを実行するには、バックグラウンドでOllama等が\n"          f"      `{config.model_name}` モデルをロードして実行中である必要があります。")
    print(f"      テスト対象エンドポイント: {config.api_url}")