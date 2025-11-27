import uuid
from datetime import datetime

def generate_unique_id():
    """一意のナレッジIDを生成します。"""
    return f"ktile-{uuid.uuid4()}"

def extract_references(text: str) -> list:
    """
    テキストから参考文献を抽出します。
    これはダミー実装です。実際には正規表現などを使用します。
    """
    references = []
    if "ガイドライン" in text:
        references.append("日本循環器学会ガイドライン2023")
    if "文献" in text:
        references.append(text[text.find("文献"):].split()[0])
    return references

def create_knowledge_tile(
    deepseek_response: dict,
    coordinates: list,
    topic: str,
    audience_level: str = "intermediate"
) -> dict:
    """
    DeepSeekのレスポンスと座標データから、完全なKnowledge Tileオブジェクトを生成します。
    
    Args:
        deepseek_response (dict): 'thinking'と'response'キーを含むAPIレスポンス。
        coordinates (list): coordinate_mapper.pyで生成された座標情報のリスト。
        topic (str): このナレッジタイルのトピック。
        audience_level (str): 対象読者レベル。

    Returns:
        dict: Ilm-Athensのスキーマに準拠したKnowledge Tile。
    """
    if not coordinates:
        raise ValueError("座標リストが空です。推論プロセスから座標を生成できませんでした。")

    # メインの座標は最初の推論ステップのものを使用
    main_coordinate = coordinates[0]["coordinate"]

    tile = {
        # 基本情報
        "metadata": {
            "knowledge_id": generate_unique_id(),
            "topic": topic,
            "domain": "medical",
            "audience_level": audience_level,
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        
        # コンテンツ
        "content": {
            "thinking_process": deepseek_response.get("thinking", ""),
            "final_response": deepseek_response.get("response", ""),
            "references": extract_references(deepseek_response.get("response", ""))
        },
        
        # 座標情報
        "coordinates": {
            "medical_space": main_coordinate["medical_space"],
            "meta_space": main_coordinate["meta_space"],
            "reasoning_path": coordinates  # 全推論ステップの座標
        },
        
        # 検証状態
        "verification": {
            "status": "pending_review",
            "initial_certainty": main_coordinate["meta_space"][0],
            "reviewers": [],
            "modifications": [],
            "external_sources": []
        },
        
        # メタ情報
        "source": {
            "generator": "deepseek-r1",
            "generation_prompt": topic,
            "thinking_depth": len(coordinates)
        },
        
        # トレーサビリティ
        "history": [
            {
                "timestamp": datetime.now().isoformat(),
                "action": "created",
                "by": "deepseek-r1",
                "details": f"初期生成：確実性{coordinates[0]['confidence']:.0%}"
            }
        ]
    }
    
    return tile

if __name__ == "__main__":
    # --- ダミーデータによる使用例 ---
    from reasoning_chain_extractor import extract_reasoning_chain
    from coordinate_mapper import map_reasoning_to_medical_space
    
    dummy_response = {
        'thinking': 'まず、心筋梗塞の定義から始めます。これは心筋への血流が途絶えることで心筋が壊死する状態です。次に、診断のゴールドスタンダードであるトロポニン測定について考慮します。これは～という理由で重要です。さらに心電図の変化も重要な所見です。ST上昇が見られる場合、急性期と判断されます。',
        'response': '急性心筋梗塞は、迅速な診断と治療が求められる救急疾患です。診断は主に、臨床症状（胸痛など）、心電図変化（ST上昇など）、心筋逸脱酵素（特にトロポニン）の上昇を三本柱として行われます。アルゴリズムとしては、まず疑いがあれば直ちに12誘導心電図を記録し、バイタルサインを確認します。ST上昇があれば、緊急カテーテル治療の適応を考慮します。<参考資料> 日本循環器学会ガイドライン2023',
    }
    
    topic = "心筋梗塞の急性期診断"

    # Week 2のモジュールを使って中間データを生成
    reasoning = extract_reasoning_chain(dummy_response)
    coordinates = map_reasoning_to_medical_space(reasoning)

    # Knowledge Tileを生成
    knowledge_tile = create_knowledge_tile(dummy_response, coordinates, topic)

    import json
    print("--- 生成されたKnowledge Tile (JSON) ---")
    print(json.dumps(knowledge_tile, indent=2, ensure_ascii=False))
