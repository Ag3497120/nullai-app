import re
from typing import Dict, Any, List

class SpatialEncodingEngine:
    """
    質問テキストを、動的に読み込まれたドメインスキーマに基づいて
    ドメイン固有の空間座標に変換する汎用エンジン。
    """
    
    def __init__(self, domain_schema: Dict[str, Any], ontology_interface):
        """
        特定のドメインスキーマを元にエンジンを初期化します。

        Args:
            domain_schema (Dict[str, Any]): 対象ドメインのスキーマ。
            ontology_interface: ドメインのオントロジーを検索するためのインターフェース。
        """
        if not domain_schema:
            raise ValueError("ドメインスキーマが提供されていません。")
        self.schema = domain_schema
        self.ontology = ontology_interface
        self.keyword_map = self.schema.get("keyword_map", {})

    def _extract_keywords(self, text: str) -> List[str]:
        """スキーマのキーワードマップに存在するキーワードをテキストから抽出する。"""
        found_keywords = [kw for kw in self.keyword_map.keys() if kw in text]
        return found_keywords

    def extract_coordinates_from_question(self, question: str, default_coord=(50, 50, 50)) -> List[Dict[str, Any]]:
        """
        質問から関連座標を抽出します。このメソッドはドメインに依存しない汎用的なロジックです。
        """
        keywords = self._extract_keywords(question)
        
        if not keywords:
            # キーワードが見つからない場合はデフォルト座標を返す
            return [{"keyword": "default", "concept": "default", "coordinate": default_coord, "confidence": 0.5}]

        # 質問全体のコンテキストから各軸の主要な値を決定する
        # 各軸について、最も頻繁に出現したキーワードの座標を採用する
        coord = list(default_coord)
        axis_map = {'x': 0, 'y': 1, 'z': 2}

        for axis_name, axis_index in axis_map.items():
            axis_keywords = [kw for kw in keywords if self.keyword_map[kw]['axis'] == axis_name]
            if axis_keywords:
                # ここでは単純に最初に見つかったキーワードを採用
                coord[axis_index] = self.keyword_map[axis_keywords[0]]['coord']
        
        # この実装では、質問から単一の代表的な座標を生成する
        final_coord = tuple(coord)

        # TODO: オントロジー検索と信頼度計算のロジックを統合
        # 現状は、抽出された主要な座標のみを返す
        return [{
            "keywords_found": keywords,
            "concept": "inferred_concept", # オントロジー検索で決定
            "coordinate": final_coord,
            "confidence": 0.75 # 信頼度は別途計算
        }]


# --- 使用例 ---
if __name__ == '__main__':
    from domain_manager import DomainManager
    from mock_objects import MockOntology
    # --- 実行例 ---
    coord_system = MedicalSpaceCoordinateSystem()
    ontology = MockOntology()
    engine = SpatialEncodingEngine(coord_system, ontology)
    
    question = "心筋梗塞の急性期診断について"
    coords_info = engine.extract_coordinates_from_question(question)
    print(f"質問: '{question}'")
    print("抽出された座標情報:")
    import json
    print(json.dumps(coords_info, indent=2, ensure_ascii=False))

    if coords_info:
        palace_rep = MemoryPalaceRepresentation()
        location = palace_rep.coordinate_to_palace_location(coords_info[0]['coordinate'])
        print("\n宮殿内の場所:")
        print(json.dumps(location, indent=2, ensure_ascii=False))