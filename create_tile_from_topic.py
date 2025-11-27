import json
import asyncio
import os
import sys

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Phase 0 & 1で作成した各モジュールをインポート
from backend.deepseek_local_client import DeepSeekLocalClient, DeepSeekConfig
from deepseek_prompt_templates import MEDICAL_KNOWLEDGE_GENERATION_PROMPT
from reasoning_chain_extractor import extract_reasoning_chain
from knowledge_tile_generator import create_knowledge_tile
from iath_encoder import IathEncoder
# 修正：新しいパスからCoordinateMapperとDomainManagerをインポート
from ilm_athens_engine.domain.manager import DomainManager
from coordinate_mapper import CoordinateMapper

# --- グローバルオブジェクトの初期化 ---
# DomainManagerとCoordinateMapperは一度だけ初期化する
domain_manager = DomainManager()
# このスクリプトは現在、医療ドメイン専用
medical_schema = domain_manager.get_schema("medical")
if not medical_schema:
    raise RuntimeError("医療ドメインのスキーマを 'domain_schemas.json' から読み込めませんでした。")
mapper = CoordinateMapper(medical_schema)


async def create_knowledge_tile_pipeline(
    topic: str,
    domain_id: str = "medical", # ドメインIDを引数に追加
    audience_level: str = "intermediate",
    output_filename: str = None,
    save_json: bool = True
):
    """
    単一のトピックからDeepSeekで知識を生成し、.iathファイルとして保存するまでの
    完全なパイプラインを実行します。
    """
    print(f"--- パイプライン開始: トピック「{topic}」, ドメイン「{domain_id}」 ---")

    # 1. DeepSeekで知識を生成
    print("ステップ1: DeepSeekによる知識生成...")
    api = DeepSeekLocalClient(config=DeepSeekConfig(
        api_url="http://localhost:11434",
        model_name="deepseek-r1:32b"
    ))
    # ドメインに応じたプロンプトを取得
    from ilm_athens_engine.deepseek_integration.deepseek_runner import DeepSeekR1Engine
    domain_instructions = DeepSeekR1Engine()._get_domain_instructions(domain_id)
    
    prompt = f"{domain_instructions}\n\n【トピック】\n{topic}"
    
    deepseek_response = await api.generate_async(prompt)
    if not deepseek_response or not deepseek_response.get("success"):
        print(f"エラー: DeepSeekモデルからの応答に失敗しました - {deepseek_response.get('error', '不明なエラー')}")
        return None

    # 2. テキストの解析と座標へのマッピング
    print("ステップ2: テキストの解析と座標へのマッピング...")
    reasoning_steps = extract_reasoning_chain(deepseek_response)
    if not reasoning_steps:
        reasoning_steps = [{'sequence': 0, 'text': deepseek_response['response'], 'confidence': 0.7, 'concepts': [], 'depth_level': 2}]
    
    # ドメインスキーマをロードしてマッパーを初期化
    schema = domain_manager.get_schema(domain_id)
    if not schema:
        print(f"エラー: ドメイン '{domain_id}' のスキーマが見つかりません。")
        return None
    mapper = CoordinateMapper(schema)
    coordinates = mapper.map_reasoning_to_domain_space(reasoning_steps)
    print(f"  -> {len(coordinates)}個の推論ステップを座標にマッピングしました。")

    # 3. Knowledge Tileの構造化
    print("ステップ3: Knowledge Tileの構造化...")
    knowledge_tile = create_knowledge_tile(deepseek_response, coordinates, topic)
    print(f"  -> Knowledge Tile ID: {knowledge_tile['metadata']['knowledge_id']}")

    # 4. エンコードとファイルへの保存
    print("ステップ4: エンコードと.iathファイルへの保存...")
    encoder = IathEncoder()
    compressed_binary = encoder.encode_tile(knowledge_tile)

    if not output_filename:
        safe_filename = topic.replace(" ", "_").replace("/", "_").replace("（", "").replace("）", "")[:30]
        output_filename = f"{safe_filename}.iath"
    
    try:
        with open(output_filename, "wb") as f:
            f.write(compressed_binary)
        print(f"  -> 成功: 知識タイルを {output_filename} ({len(compressed_binary)} bytes) に保存しました。")
    except IOError as e:
        print(f"  -> エラー: ファイルの保存に失敗しました - {e}")
        return None

    if save_json:
        json_filename = output_filename.replace(".iath", ".json")
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(knowledge_tile, f, indent=2, ensure_ascii=False)
        print(f"  -> 検証用の {json_filename} も保存しました。")
    
    print("--- パイプライン完了 ---")
    return output_filename


if __name__ == '__main__':
    # --- 実行 ---
    # DBに追加したいトピックを指定してください
    target_topic = "心筋梗塞の急性期診断アルゴリズム"
    
    # パイプラインを実行
    # このスクリプトを直接実行する場合、トップレベルで `await` は使えないため、
    # asyncio.run() を使用します。
    import asyncio
    asyncio.run(create_knowledge_tile_pipeline(topic=target_topic))
