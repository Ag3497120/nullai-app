#!/usr/bin/env python3
"""
NullAI 推論CLI - OllamaとTransformersを簡単に切り替え
"""
import sys
import os
import argparse
import asyncio
from typing import Optional

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from null_ai.model_router import ModelRouter
from null_ai.config import ConfigManager


async def run_inference(
    question: str,
    provider: str = "auto",
    model: Optional[str] = None,
    domain: str = "general",
    temperature: float = 0.7,
    max_tokens: int = 2048
):
    """推論を実行"""

    # 設定マネージャー初期化
    config_manager = ConfigManager()

    # モデル選択
    if model:
        model_config = config_manager.get_model(model)
        if not model_config:
            print(f"❌ モデル '{model}' が見つかりません")
            print("\n利用可能なモデル一覧:")
            for m_id, m_cfg in config_manager.models.items():
                print(f"  - {m_id}: {m_cfg.display_name} ({m_cfg.provider})")
            return
    else:
        # プロバイダーに基づいてモデルを選択
        if provider == "ollama":
            # Ollamaモデルを優先
            model_config = next(
                (m for m in config_manager.models.values()
                 if m.provider == "ollama" and domain in m.supported_domains),
                None
            )
            if not model_config:
                print("❌ Ollamaモデルが見つかりません")
                return
        elif provider == "transformers":
            # Transformersモデルを優先
            model_config = next(
                (m for m in config_manager.models.values()
                 if m.provider == "huggingface" and domain in m.supported_domains),
                None
            )
            if not model_config:
                print("❌ Transformersモデルが見つかりません")
                return
        else:
            # デフォルトモデルを使用
            model_config = config_manager.get_default_model()

    print(f"🤖 モデル: {model_config.display_name}")
    print(f"📦 プロバイダー: {model_config.provider}")
    print(f"🏷️  ドメイン: {domain}")
    print(f"❓ 質問: {question}")
    print("-" * 60)

    # ModelRouter初期化
    router = ModelRouter(
        config_manager=config_manager,
        ollama_url="http://localhost:11434"
    )

    try:
        # 推論実行
        result = await router.infer(
            model_id=model_config.model_id,
            prompt=question,
            temperature=temperature,
            max_tokens=max_tokens
        )

        print("\n💬 回答:")
        print(result.get("response", "回答が得られませんでした"))

        if result.get("thinking"):
            print("\n🧠 思考過程:")
            print(result["thinking"])

        print(f"\n✅ 推論完了")

    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()


def list_models(config_manager: ConfigManager, provider_filter: Optional[str] = None):
    """モデル一覧を表示"""
    print("\n📋 利用可能なモデル一覧:\n")

    # プロバイダーごとにグループ化
    ollama_models = []
    transformers_models = []
    other_models = []

    for model_id, model_config in config_manager.models.items():
        if provider_filter and model_config.provider != provider_filter:
            continue

        model_info = f"  🔹 {model_id}\n" \
                    f"      名前: {model_config.display_name}\n" \
                    f"      プロバイダー: {model_config.provider}\n" \
                    f"      ドメイン: {', '.join(model_config.supported_domains)}\n"

        if model_config.provider == "ollama":
            ollama_models.append(model_info)
        elif model_config.provider == "huggingface":
            transformers_models.append(model_info)
        else:
            other_models.append(model_info)

    if ollama_models:
        print("🚀 Ollamaモデル:")
        print("\n".join(ollama_models))

    if transformers_models:
        print("\n🤗 Transformersモデル:")
        print("\n".join(transformers_models))

    if other_models:
        print("\nその他のモデル:")
        print("\n".join(other_models))


def main():
    parser = argparse.ArgumentParser(
        description="NullAI 推論CLI - OllamaとTransformersを簡単に切り替え",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # Ollamaで推論
  %(prog)s --provider ollama --question "心筋梗塞とは？" --domain medical

  # Transformersで推論
  %(prog)s --provider transformers --question "AIとは？" --domain general

  # 特定のモデルを指定
  %(prog)s --model ollama-deepseek-r1-32b --question "法律について" --domain legal

  # モデル一覧表示
  %(prog)s --list-models
  %(prog)s --list-models --provider ollama
        """
    )

    parser.add_argument(
        "-q", "--question",
        type=str,
        help="質問文"
    )

    parser.add_argument(
        "-p", "--provider",
        type=str,
        choices=["ollama", "transformers", "auto"],
        default="auto",
        help="プロバイダーを選択 (ollama/transformers/auto)"
    )

    parser.add_argument(
        "-m", "--model",
        type=str,
        help="使用するモデルID（例: ollama-deepseek-r1-32b）"
    )

    parser.add_argument(
        "-d", "--domain",
        type=str,
        default="general",
        help="ドメインID（例: medical, legal, general）"
    )

    parser.add_argument(
        "-t", "--temperature",
        type=float,
        default=0.7,
        help="Temperature（0.0-1.0）"
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        help="最大トークン数"
    )

    parser.add_argument(
        "--list-models",
        action="store_true",
        help="利用可能なモデル一覧を表示"
    )

    args = parser.parse_args()

    # 設定マネージャー初期化
    config_manager = ConfigManager()

    # モデル一覧表示
    if args.list_models:
        provider_filter = None
        if args.provider != "auto":
            provider_filter = "ollama" if args.provider == "ollama" else "huggingface"
        list_models(config_manager, provider_filter)
        return

    # 質問が必須
    if not args.question:
        parser.error("--question が必要です（または --list-models を使用）")

    # 推論実行
    asyncio.run(run_inference(
        question=args.question,
        provider=args.provider,
        model=args.model,
        domain=args.domain,
        temperature=args.temperature,
        max_tokens=args.max_tokens
    ))


if __name__ == "__main__":
    main()
