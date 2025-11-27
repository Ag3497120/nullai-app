"""
NullAI モデルルーター

クロスプラットフォーム対応：Windows、Mac、Linux
サポート形式：MLX (Apple Silicon)、HuggingFace Transformers、GGUF、Ollama

注意: 外部API（OpenAI/Anthropic等）は利用規約上の理由からサポートしていません。
NullAIは独自モデルまたはオープンソースモデルのみをサポートします。
"""
import asyncio
import aiohttp
import logging
import platform
import sys
from typing import Dict, Any, Optional, List, Generator
from datetime import datetime
import hashlib
import json
import os
import threading

from null_ai.config import ConfigManager, ModelConfig, ModelProvider

logger = logging.getLogger(__name__)


# ========================================
# プラットフォーム検出
# ========================================
def detect_platform() -> Dict[str, Any]:
    """実行プラットフォームとハードウェアを検出"""
    system = platform.system()
    machine = platform.machine()

    is_apple_silicon = system == "Darwin" and machine == "arm64"
    is_windows = system == "Windows"
    is_linux = system == "Linux"
    is_macos = system == "Darwin"

    # GPU検出
    has_cuda = False
    has_mps = False

    try:
        import torch
        has_cuda = torch.cuda.is_available()
        has_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    except ImportError:
        pass

    return {
        "system": system,
        "machine": machine,
        "is_apple_silicon": is_apple_silicon,
        "is_windows": is_windows,
        "is_linux": is_linux,
        "is_macos": is_macos,
        "has_cuda": has_cuda,
        "has_mps": has_mps
    }


PLATFORM_INFO = detect_platform()
logger.info(f"Platform detected: {PLATFORM_INFO}")

# グローバルなモデルキャッシュ（重いTransformersモデルの再読み込み防止）
_model_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()


def get_cached_model(model_name: str):
    """キャッシュからモデルを取得"""
    with _cache_lock:
        return _model_cache.get(model_name)


def set_cached_model(model_name: str, model_instance: Any):
    """モデルをキャッシュに保存"""
    with _cache_lock:
        _model_cache[model_name] = model_instance


class GGUFInference:
    """
    GGUF形式モデル推論（llama.cpp）

    全プラットフォーム対応。量子化モデルで低メモリ動作。
    """

    def __init__(self):
        self._llama_cpp = None

    def _ensure_dependencies(self):
        """llama-cpp-pythonの遅延インポート"""
        if self._llama_cpp is None:
            try:
                from llama_cpp import Llama
                self._llama_cpp = Llama
                logger.info("llama-cpp-python initialized successfully")
            except ImportError as e:
                raise ImportError(
                    "GGUFモデルを使用するには llama-cpp-python をインストールしてください: "
                    "pip install llama-cpp-python"
                ) from e

    def load_model(self, model_path: str, **kwargs):
        """GGUFモデルをロード"""
        self._ensure_dependencies()

        cached = get_cached_model(f"gguf_{model_path}")
        if cached:
            logger.info(f"Using cached GGUF model: {model_path}")
            return cached

        logger.info(f"Loading GGUF model: {model_path}")

        # llama.cppでモデルをロード
        # n_gpu_layers: GPUレイヤー数（0=CPU、-1=全GPU）
        n_gpu_layers = kwargs.get("n_gpu_layers", -1 if PLATFORM_INFO["has_cuda"] else 0)

        model = self._llama_cpp(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=kwargs.get("n_ctx", 4096),
            verbose=False
        )

        set_cached_model(f"gguf_{model_path}", model)
        logger.info(f"GGUF model loaded successfully")
        return model

    async def generate(
        self,
        model_path: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """テキスト生成（GGUF）"""
        self._ensure_dependencies()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._generate_sync(model_path, prompt, max_tokens, temperature, **kwargs)
        )
        return result

    def _generate_sync(
        self,
        model_path: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> Dict[str, Any]:
        """同期的なテキスト生成（GGUF）"""
        model = self.load_model(model_path)

        response = model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=kwargs.get("stop", []),
            echo=False
        )

        return {
            "response": response["choices"][0]["text"],
            "model": model_path,
            "provider": "gguf"
        }


class OllamaInference:
    """
    Ollama API推論

    全プラットフォーム対応。ローカルOllamaサーバーを使用。
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    async def generate(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """テキスト生成（Ollama）"""
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "response": data.get("response", ""),
                            "model": model_name,
                            "provider": "ollama"
                        }
                    else:
                        error_text = await resp.text()
                        raise Exception(f"Ollama API error: {resp.status} - {error_text}")
        except Exception as e:
            logger.error(f"Ollama inference failed: {e}")
            raise


class MLXInference:
    """
    Apple Silicon専用MLXを使用した高速推論

    MLXはApple Siliconに最適化されており、メモリ効率と速度が大幅に向上。
    """

    def __init__(self):
        self._mlx_lm = None

    def _ensure_dependencies(self):
        """MLX依存ライブラリの遅延インポート"""
        if self._mlx_lm is None:
            try:
                import mlx.core as mx
                import mlx_lm
                self._mlx_lm = mlx_lm
                self._mx = mx
                logger.info("MLX initialized successfully for Apple Silicon")
            except ImportError as e:
                raise ImportError(
                    "MLXを使用するには mlx と mlx-lm をインストールしてください: "
                    "pip install mlx mlx-lm"
                ) from e

    def load_model(self, model_name: str, **kwargs):
        """MLXモデルをロード（キャッシュ対応）"""
        self._ensure_dependencies()

        cached = get_cached_model(f"mlx_{model_name}")
        if cached:
            logger.info(f"Using cached MLX model: {model_name}")
            return cached

        logger.info(f"Loading MLX model: {model_name}")

        # mlx_lmでモデルとトークナイザーをロード
        # trust_remote_code=Trueで互換性問題を回避
        model, tokenizer = self._mlx_lm.load(
            model_name,
            tokenizer_config={"trust_remote_code": True}
        )

        result = {"model": model, "tokenizer": tokenizer}
        set_cached_model(f"mlx_{model_name}", result)

        logger.info(f"MLX model loaded successfully: {model_name}")
        return result

    async def generate(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """テキスト生成（MLX）"""
        self._ensure_dependencies()

        # 別スレッドで実行（非同期化）
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._generate_sync(model_name, prompt, max_tokens, temperature, **kwargs)
        )
        return result

    def _generate_sync(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> Dict[str, Any]:
        """同期的なテキスト生成（MLX）"""
        model_data = self.load_model(model_name)
        model = model_data["model"]
        tokenizer = model_data["tokenizer"]

        # MLXで生成
        response = self._mlx_lm.generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            verbose=False
        )

        return {
            "response": response,
            "model": model_name,
            "provider": "mlx"
        }


class HuggingFaceInference:
    """
    HuggingFace Transformersを使用したローカル推論

    モデルはダウンロード後ローカルで実行される。
    GPUが利用可能な場合は自動的にGPU推論を使用。
    """

    def __init__(self):
        self._transformers = None
        self._torch = None
        self._device = None

    def _ensure_dependencies(self):
        """依存ライブラリの遅延インポート"""
        if self._transformers is None:
            try:
                import transformers
                import torch
                self._transformers = transformers
                self._torch = torch

                # デバイス選択
                if torch.cuda.is_available():
                    self._device = "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    self._device = "mps"  # Apple Silicon
                else:
                    self._device = "cpu"

                logger.info(f"HuggingFace Transformers initialized with device: {self._device}")
            except ImportError as e:
                raise ImportError(
                    "HuggingFace Transformersを使用するには transformers と torch をインストールしてください: "
                    "pip install transformers torch"
                ) from e

    def load_model(self, model_name: str, use_4bit: bool = True, **kwargs):
        """モデルをロード（キャッシュ対応、Apple Silicon最適化）"""
        self._ensure_dependencies()

        cached = get_cached_model(model_name)
        if cached:
            logger.info(f"Using cached model: {model_name}")
            return cached

        logger.info(f"Loading model: {model_name} on device: {self._device}")

        # AutoModelForCausalLM + AutoTokenizerを使用
        tokenizer = self._transformers.AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True
        )

        # Apple Silicon (MPS) の場合は特別な設定
        if self._device == "mps":
            logger.info("Apple Silicon detected - using MPS-optimized configuration")
            logger.info("Loading with float16, max_memory, and disk offload for 64GB memory")

            # MPSではbitsandbytesが使えないため、float16 + メモリ最適化 + ディスクオフロードを使用
            # 64GBメモリの場合、MPSに最大40GB、CPUに15GB割り当て
            max_memory = {
                "mps": "40GiB",
                "cpu": "15GiB"
            }

            # オフロードフォルダを作成
            offload_folder = os.path.join(os.path.dirname(__file__), "..", "model_offload")
            os.makedirs(offload_folder, exist_ok=True)

            logger.info(f"Max memory allocation: MPS=40GB, CPU=15GB, Offload to: {offload_folder}")

            model = self._transformers.AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=self._torch.float16,
                low_cpu_mem_usage=True,
                device_map="auto",
                max_memory=max_memory,
                offload_folder=offload_folder,
                offload_state_dict=True,
                trust_remote_code=True,
                **kwargs
            )
            logger.info("Model loaded successfully with memory optimization and disk offload")

        # CUDA (NVIDIA GPU) の場合は4bit量子化を試みる
        elif use_4bit and self._device == "cuda":
            try:
                from transformers import BitsAndBytesConfig

                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=self._torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )

                logger.info("Using 4-bit quantization (CUDA) to reduce memory usage (~75% reduction)")

                model = self._transformers.AutoModelForCausalLM.from_pretrained(
                    model_name,
                    quantization_config=quantization_config,
                    device_map="auto",
                    trust_remote_code=True,
                    **kwargs
                )
            except (ImportError, Exception) as e:
                logger.warning(f"4-bit quantization failed: {e}, falling back to float16")
                model = self._transformers.AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=self._torch.float16,
                    device_map="auto",
                    trust_remote_code=True,
                    **kwargs
                )
        else:
            # CPU または量子化なし
            model = self._transformers.AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=self._torch.float16 if self._device != "cpu" else self._torch.float32,
                device_map="auto" if self._device != "cpu" else None,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
                **kwargs
            )

            if self._device == "cpu":
                model = model.to("cpu")

        result = {"model": model, "tokenizer": tokenizer}
        set_cached_model(model_name, result)

        return result

    async def generate(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """テキスト生成"""
        self._ensure_dependencies()

        # 別スレッドで実行（非同期化）
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._generate_sync(model_name, prompt, max_tokens, temperature, **kwargs)
        )
        return result

    def _generate_sync(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> Dict[str, Any]:
        """同期的なテキスト生成"""
        model_data = self.load_model(model_name)
        model = model_data["model"]
        tokenizer = model_data["tokenizer"]

        # チャット形式のプロンプト構築
        if hasattr(tokenizer, "apply_chat_template"):
            messages = [{"role": "user", "content": prompt}]
            input_text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        else:
            input_text = prompt

        inputs = tokenizer(input_text, return_tensors="pt")
        if self._device != "cpu":
            inputs = {k: v.to(model.device) for k, v in inputs.items()}

        # 生成パラメータ
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "do_sample": temperature > 0,
            "pad_token_id": tokenizer.eos_token_id,
            **kwargs
        }

        if temperature == 0:
            gen_kwargs.pop("temperature", None)
            gen_kwargs["do_sample"] = False

        with self._torch.no_grad():
            outputs = model.generate(**inputs, **gen_kwargs)

        # 入力部分を除いた生成テキストを取得
        generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
        response = tokenizer.decode(generated_ids, skip_special_tokens=True)

        # DeepSeek-R1スタイルの思考プロセス抽出
        thinking = ""
        final_response = response

        if "<think>" in response and "</think>" in response:
            think_start = response.find("<think>") + len("<think>")
            think_end = response.find("</think>")
            thinking = response[think_start:think_end].strip()
            final_response = response[think_end + len("</think>"):].strip()

        return {
            "response": final_response,
            "thinking": thinking,
            "raw_response": response
        }


class HuggingFaceAPIInference:
    """
    HuggingFace Inference APIを使用したリモート推論

    モデルをダウンロードせずにHuggingFaceのサーバーで推論を実行。
    無料枠あり（レート制限あり）。
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("HF_API_KEY", "")
        self.base_url = "https://api-inference.huggingface.co/models"

    async def generate(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """HuggingFace Inference APIで推論"""
        url = f"{self.base_url}/{model_name}"

        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status == 503:
                    # モデルがロード中の場合
                    data = await response.json()
                    estimated_time = data.get("estimated_time", 60)
                    raise Exception(f"Model is loading, estimated time: {estimated_time}s")

                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"HuggingFace API error: {error_text}")

                data = await response.json()

                if isinstance(data, list):
                    text = data[0].get("generated_text", "")
                else:
                    text = data.get("generated_text", "")

                return {
                    "response": text,
                    "thinking": "",
                    "raw_response": data
                }


class GGUFInference:
    """
    GGUF形式モデルの推論（llama-cpp-python使用）

    量子化モデルを使用した軽量推論。CPU環境に適している。
    """

    def __init__(self):
        self._llama = None

    def _ensure_dependencies(self):
        """依存ライブラリの遅延インポート"""
        if self._llama is None:
            try:
                from llama_cpp import Llama
                self._llama = Llama
            except ImportError as e:
                raise ImportError(
                    "GGUF推論を使用するには llama-cpp-python をインストールしてください: "
                    "pip install llama-cpp-python"
                ) from e

    def load_model(self, model_path: str, **kwargs):
        """GGUFモデルをロード"""
        self._ensure_dependencies()

        cached = get_cached_model(model_path)
        if cached:
            return cached

        logger.info(f"Loading GGUF model: {model_path}")

        model = self._llama(
            model_path=model_path,
            n_ctx=4096,
            n_gpu_layers=-1,  # GPUが利用可能なら全レイヤーをGPUで実行
            **kwargs
        )

        set_cached_model(model_path, model)
        return model

    async def generate(
        self,
        model_path: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """GGUF推論"""
        self._ensure_dependencies()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._generate_sync(model_path, prompt, max_tokens, temperature, **kwargs)
        )
        return result

    def _generate_sync(
        self,
        model_path: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> Dict[str, Any]:
        """同期的なGGUF推論"""
        model = self.load_model(model_path)

        output = model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )

        text = output["choices"][0]["text"]

        return {
            "response": text,
            "thinking": "",
            "raw_response": output
        }


class OllamaInference:
    """
    Ollama推論エンジン

    Ollamaローカルサーバーと通信して推論を実行。
    多様なオープンソースモデルをサポート。
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    async def generate(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Ollamaで推論"""
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error: {error_text}")

                    data = await response.json()

                    return {
                        "response": data.get("response", ""),
                        "thinking": "",
                        "raw_response": data
                    }
        except aiohttp.ClientConnectorError:
            raise Exception(
                "Ollamaサーバーに接続できません。Ollamaが起動しているか確認してください: "
                "http://localhost:11434"
            )

    async def generate_stream(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Generator[str, None, None]:
        """Ollamaでストリーミング推論"""
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error: {error_text}")

                    async for line in response.content:
                        if line:
                            data = json.loads(line.decode('utf-8'))
                            if "response" in data:
                                yield data["response"]
        except aiohttp.ClientConnectorError:
            raise Exception(
                "Ollamaサーバーに接続できません。Ollamaが起動しているか確認してください: "
                "http://localhost:11434"
            )


class ModelRouter:
    """
    マルチモデル対応の推論ルーター

    - MLX（Apple Silicon専用、最高速度）
    - HuggingFace Transformers（ローカル推論）
    - HuggingFace Inference API（リモート推論）
    - GGUF形式（llama.cpp互換）
    - Ollama（ローカル推論サーバー）
    - ドメインに応じた最適モデル選択
    - 推論結果の自動保存機能

    注意: OpenAI/Anthropic等の競合APIはサポートしていません。
    """

    def __init__(self, config_manager: ConfigManager, ollama_url: str = "http://localhost:11434"):
        self.config = config_manager
        self.memory_space = None  # DendriticMemorySpace (後で注入)
        self.db_interface = None  # IathDBInterface (後で注入)

        # 推論エンジン
        self._hf_inference = HuggingFaceInference()
        self._hf_api_inference = HuggingFaceAPIInference()
        self._gguf_inference = GGUFInference()
        self._ollama_inference = OllamaInference(base_url=ollama_url)
        self._mlx_inference = MLXInference() if PLATFORM_INFO["is_apple_silicon"] else None

    def set_memory_space(self, memory_space):
        """樹木型記憶空間を設定"""
        self.memory_space = memory_space

    def set_db_interface(self, db_interface):
        """DBインターフェースを設定"""
        self.db_interface = db_interface

    def get_model_for_domain(self, domain_id: str) -> ModelConfig:
        """ドメインに最適なモデルを取得"""
        # ドメイン設定からデフォルトモデルを取得
        domain = self.config.get_domain(domain_id)
        if domain and domain.default_model_id:
            model = self.config.get_model(domain.default_model_id)
            if model:
                return model

        # ドメインをサポートするモデルを検索
        models = self.config.list_models(domain_id=domain_id)
        if models:
            return models[0]

        # フォールバック：デフォルトモデル
        return self.config.get_default_model()

    async def infer(
        self,
        prompt: str,
        domain_id: str = "general",
        model_id: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        save_to_memory: bool = True,
        coordinate: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        推論を実行し、結果を返す

        Args:
            prompt: 入力プロンプト
            domain_id: ドメインID
            model_id: 使用するモデルID（省略時はドメインのデフォルト）
            temperature: 温度パラメータ
            max_tokens: 最大トークン数
            save_to_memory: 結果を記憶空間に保存するか
            coordinate: 保存時の座標（省略時は自動計算）

        Returns:
            推論結果の辞書
        """
        # モデル選択
        if model_id:
            model = self.config.get_model(model_id)
            if not model:
                raise ValueError(f"Model not found: {model_id}")
        else:
            model = self.get_model_for_domain(domain_id)

        if not model:
            raise ValueError("No available model")

        logger.info(f"Using model: {model.display_name} for domain: {domain_id}")

        # プロバイダー別の推論実行
        start_time = datetime.now()

        if model.provider == ModelProvider.MLX:
            result = await self._infer_mlx(model, prompt, temperature, max_tokens)
        elif model.provider == ModelProvider.HUGGINGFACE:
            result = await self._infer_huggingface(model, prompt, temperature, max_tokens)
        elif model.provider == ModelProvider.HUGGINGFACE_API:
            result = await self._infer_huggingface_api(model, prompt, temperature, max_tokens)
        elif model.provider == ModelProvider.LOCAL:
            result = await self._infer_local(model, prompt, temperature, max_tokens)
        elif model.provider == ModelProvider.GGUF:
            result = await self._infer_gguf(model, prompt, temperature, max_tokens)
        elif model.provider == ModelProvider.OLLAMA:
            result = await self._infer_ollama(model, prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {model.provider}")

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        result["latency_ms"] = elapsed_ms
        result["model_id"] = model.model_id
        result["model_name"] = model.display_name
        result["domain_id"] = domain_id

        # 信頼度推定
        confidence = self._estimate_confidence(result.get("response", ""), domain_id)
        result["confidence"] = confidence

        # 自動保存
        if save_to_memory and self.config.system_config.auto_save_to_memory:
            if confidence >= self.config.system_config.memory_save_threshold:
                tile_id = await self._save_to_memory(
                    prompt=prompt,
                    response=result.get("response", ""),
                    domain_id=domain_id,
                    confidence=confidence,
                    coordinate=coordinate
                )
                result["saved_to_memory"] = True
                result["tile_id"] = tile_id
            else:
                result["saved_to_memory"] = False
                result["save_skipped_reason"] = f"Confidence {confidence:.2f} below threshold {self.config.system_config.memory_save_threshold}"

        return result

    async def _infer_huggingface(
        self,
        model: ModelConfig,
        prompt: str,
        temperature: Optional[float],
        max_tokens: Optional[int]
    ) -> Dict[str, Any]:
        """HuggingFace Transformersでの推論"""
        return await self._hf_inference.generate(
            model_name=model.model_name,
            prompt=prompt,
            max_tokens=max_tokens or model.max_tokens,
            temperature=temperature or model.temperature
        )

    async def _infer_huggingface_api(
        self,
        model: ModelConfig,
        prompt: str,
        temperature: Optional[float],
        max_tokens: Optional[int]
    ) -> Dict[str, Any]:
        """HuggingFace Inference APIでの推論"""
        return await self._hf_api_inference.generate(
            model_name=model.model_name,
            prompt=prompt,
            max_tokens=max_tokens or model.max_tokens,
            temperature=temperature or model.temperature
        )

    async def _infer_local(
        self,
        model: ModelConfig,
        prompt: str,
        temperature: Optional[float],
        max_tokens: Optional[int]
    ) -> Dict[str, Any]:
        """ローカルモデル（Transformers）での推論"""
        # HuggingFace Transformersと同じ実装
        return await self._hf_inference.generate(
            model_name=model.model_name,
            prompt=prompt,
            max_tokens=max_tokens or model.max_tokens,
            temperature=temperature or model.temperature
        )

    async def _infer_gguf(
        self,
        model: ModelConfig,
        prompt: str,
        temperature: Optional[float],
        max_tokens: Optional[int]
    ) -> Dict[str, Any]:
        """GGUF形式モデルでの推論"""
        # model_nameはGGUFファイルパスを想定
        return await self._gguf_inference.generate(
            model_path=model.model_name,
            prompt=prompt,
            max_tokens=max_tokens or model.max_tokens,
            temperature=temperature or model.temperature
        )

    async def _infer_ollama(
        self,
        model: ModelConfig,
        prompt: str,
        temperature: Optional[float],
        max_tokens: Optional[int]
    ) -> Dict[str, Any]:
        """Ollamaでの推論"""
        return await self._ollama_inference.generate(
            model_name=model.model_name,
            prompt=prompt,
            max_tokens=max_tokens or model.max_tokens,
            temperature=temperature or model.temperature
        )

    async def _infer_mlx(
        self,
        model: ModelConfig,
        prompt: str,
        temperature: Optional[float],
        max_tokens: Optional[int]
    ) -> Dict[str, Any]:
        """MLX（Apple Silicon専用）での推論"""
        if not PLATFORM_INFO["is_apple_silicon"]:
            raise ValueError("MLX is only supported on Apple Silicon")
        if self._mlx_inference is None:
            raise ValueError("MLX inference engine not initialized")
        return await self._mlx_inference.generate(
            model_name=model.model_name,
            prompt=prompt,
            max_tokens=max_tokens or model.max_tokens,
            temperature=temperature or model.temperature
        )

    def _estimate_confidence(self, response: str, domain_id: str) -> float:
        """応答の信頼度を推定"""
        if not response:
            return 0.0

        confidence = 0.5

        # 長さボーナス
        if len(response) > 200:
            confidence += 0.1
        if len(response) > 500:
            confidence += 0.1

        # 不確実性マーカーによる減点
        uncertainty_markers = [
            "かもしれません", "可能性があります", "不確実",
            "わかりません", "専門家に相談", "確認が必要"
        ]
        for marker in uncertainty_markers:
            if marker in response:
                confidence -= 0.05

        # ドメイン固有のエビデンスキーワード
        evidence_keywords = {
            "medical": ["エビデンス", "臨床研究", "ガイドライン", "システマティックレビュー"],
            "legal": ["判例", "条文", "最高裁", "法令"],
            "economics": ["統計", "データ", "研究", "分析"]
        }

        for keyword in evidence_keywords.get(domain_id, []):
            if keyword in response:
                confidence += 0.05

        return max(0.0, min(1.0, confidence))

    async def _save_to_memory(
        self,
        prompt: str,
        response: str,
        domain_id: str,
        confidence: float,
        coordinate: Optional[List[float]] = None
    ) -> str:
        """推論結果を樹木型記憶空間に保存"""
        # タイルIDを生成
        content_hash = hashlib.md5(f"{prompt}{response}".encode()).hexdigest()[:12]
        tile_id = f"auto_{domain_id}_{content_hash}"

        # 座標が指定されていない場合はダミー座標を使用
        # 実際には空間エンコーディングを使用すべき
        if coordinate is None:
            coordinate = [50.0, 50.0, 50.0]

        # タイル形式で保存
        tile = {
            "metadata": {
                "knowledge_id": tile_id,
                "domain": domain_id,
                "created_at": datetime.utcnow().isoformat(),
                "source": "auto_generated",
                "original_question": prompt[:200]
            },
            "content": {
                "final_response": response,
                "question": prompt
            },
            "coordinates": {
                f"{domain_id}_space": coordinate,
                "meta_space": [confidence * 100, 0, 0]
            }
        }

        # 記憶空間に統合
        if self.memory_space:
            self.memory_space.integrate_tile(tile, domain_id)
            logger.info(f"Saved to memory: {tile_id}")

        # DBにも保存（オプション）
        if self.db_interface:
            try:
                # IathDBの形式で保存
                self.db_interface.store_tile(tile_id, tile)
                logger.info(f"Saved to DB: {tile_id}")
            except Exception as e:
                logger.warning(f"Failed to save to DB: {e}")

        return tile_id

    async def list_available_models(self, domain_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """利用可能なモデル一覧を取得"""
        models = self.config.list_models(domain_id=domain_id)
        return [
            {
                "model_id": m.model_id,
                "display_name": m.display_name,
                "provider": m.provider.value,
                "supported_domains": m.supported_domains,
                "is_default": m.is_default,
                "description": m.description
            }
            for m in models
        ]

    def get_provider_info(self) -> Dict[str, Any]:
        """サポートされているプロバイダー情報を取得"""
        return {
            "supported_providers": [
                {
                    "id": "huggingface",
                    "name": "HuggingFace Transformers",
                    "description": "ローカルでモデルをダウンロードして実行。GPU推奨。",
                    "requires_api_key": False,
                    "requires_gpu": True
                },
                {
                    "id": "huggingface_api",
                    "name": "HuggingFace Inference API",
                    "description": "HuggingFaceのサーバーで推論。無料枠あり。",
                    "requires_api_key": False,  # オプション
                    "requires_gpu": False
                },
                {
                    "id": "local",
                    "name": "Local Model",
                    "description": "ローカルにダウンロード済みのモデルを使用。",
                    "requires_api_key": False,
                    "requires_gpu": True
                },
                {
                    "id": "gguf",
                    "name": "GGUF (llama.cpp)",
                    "description": "量子化モデル。CPU環境でも動作可能。",
                    "requires_api_key": False,
                    "requires_gpu": False
                }
            ],
            "unsupported_providers": [
                {
                    "id": "openai",
                    "reason": "利用規約上、競合モデル作成への使用が禁止されているため削除されました。"
                },
                {
                    "id": "anthropic",
                    "reason": "利用規約上、競合モデル作成への使用が禁止されているため削除されました。"
                },
                {
                    "id": "ollama",
                    "reason": "HuggingFaceでの公開を考慮し、直接Transformersを使用する方式に変更されました。"
                }
            ]
        }
