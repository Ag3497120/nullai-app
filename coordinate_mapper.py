import math
from typing import Dict, Any, List

# 既存のモジュールをインポート
# calculate_granularity は粒度を計算するもので、ドメインに依存しないためそのまま利用
from certainty_calculation_formula import calculate_granularity

def assign_verification_score(concepts: list, sources: list) -> float:
    """検証スコアを割り当てるダミー関数"""
    score = 50.0
    if sources:
        score += len(sources) * 5.0
    return score

class CoordinateMapper:
    """
    LLMの思考プロセス（推論ステップ）を、動的に読み込まれたドメインスキーマに
    基づいてドメイン固有の空間座標に変換する汎用マッパー。
    """
    def __init__(self, domain_schema: Dict[str, Any]):
        """
        特定のドメインスキーマを元にマッパーを初期化します。

        Args:
            domain_schema (Dict[str, Any]): 対象ドメインのスキーマ。
        """
        if not domain_schema:
            raise ValueError("ドメインスキーマが提供されていません。")
        self.schema = domain_schema
        self.keyword_map = self.schema.get("keyword_map", {})

    def map_reasoning_to_domain_space(self, reasoning_steps: List[Dict]) -> List[Dict]:
        """
        抽出された推論ステップを、当マッパーに設定されたドメインの空間座標に変換します。

        Args:
            reasoning_steps (List[Dict]): reasoning_chain_extractor.pyから得られる推論ステップのリスト。

        Returns:
            List[Dict]: 座標情報が付与された辞書のリスト。
        """
        coordinates = []
        full_text = " ".join(step["text"] for step in reasoning_steps)
        
        # 全体のテキストから主要な座標を推定（デフォルト値として使用）
        default_coord = [50, 50, 50]
        axis_map = {'x': 0, 'y': 1, 'z': 2}
        for axis_name, axis_index in axis_map.items():
             axis_keywords = [kw for kw in self.keyword_map if self.keyword_map[kw]['axis'] == axis_name and kw in full_text]
             if axis_keywords:
                 default_coord[axis_index] = self.keyword_map[axis_keywords[0]]['coord']

        for step in reasoning_steps:
            coord = list(default_coord)
            # ステップ内のキーワードで座標を上書き
            step_keywords = [kw for kw in self.keyword_map if kw in step["text"]]
            for kw in step_keywords:
                axis_name = self.keyword_map[kw]['axis']
                axis_index = axis_map[axis_name]
                coord[axis_index] = self.keyword_map[kw]['coord']
            
            # メタ軸の計算
            c = int(step["confidence"] * 100)
            word_count = len(step["text"].split())
            g = calculate_granularity(word_count)
            v = assign_verification_score(step["concepts"], [])
            
            coordinates.append({
                "step_sequence": step["sequence"],
                "reasoning_text": step["text"],
                "coordinate": {
                    "medical_space": tuple(coord), # スキーマ名に合わせて変更が必要だが、ここでは固定
                    "meta_space": (c, g, v)
                },
                "concept_tags": step["concepts"],
                "confidence": step["confidence"]
            })
        
        return coordinates

# --- 使用例 ---
if __name__ == "__main__":
    from domain_manager import DomainManager
    from reasoning_chain_extractor import extract_reasoning_chain

    # 1. ドメインマネージャを初期化
    domain_manager = DomainManager()

    # 2. ダミーの推論ステップを用意
    dummy_reasoning_chain = [
        {'sequence': 0, 'text': 'まず、民法における契約の定義から始めます。', 'confidence': 0.9, 'concepts': ['民法', '契約']},
        {'sequence': 1, 'text': '次に、具体的な判例を元に解釈を深めます。', 'confidence': 0.8, 'concepts': ['判例', '解釈']}
    ]

    # 3. 法学ドメイン用のマッパーを生成して実行
    print("--- Case: Legal Domain ---")
    legal_schema = domain_manager.get_schema("legal")
    legal_mapper = CoordinateMapper(legal_schema)
    
    legal_coordinates = legal_mapper.map_reasoning_to_domain_space(dummy_reasoning_chain)

    import json
    print(json.dumps(legal_coordinates, indent=2, ensure_ascii=False))