import unittest
import json
import hashlib

# Ilm-Athens DB層の各モジュールをインポート
from deepseek_prompt_templates import MEDICAL_KNOWLEDGE_GENERATION_PROMPT, DeepSeekLocalAPI
from reasoning_chain_extractor import extract_reasoning_chain
from coordinate_mapper import map_reasoning_to_medical_space
from knowledge_tile_generator import create_knowledge_tile
from iath_encoder import IathEncoder
from iath_decoder import IathDecoder

class EndToEndPipelineTest(unittest.TestCase):

    def test_full_pipeline_for_single_topic(self):
        """
        単一トピックに対して、プロンプト生成から圧縮・復号まで、
        パイプライン全体がエラーなく動作することを検証する。
        """
        # --- セットアップ ---
        topic = "心筋梗塞の急性期診断"
        
        # DeepSeek APIは実際に呼び出さず、ダミーレスポンスを使用
        dummy_response = {
            'thinking': 'まず、心筋梗塞の定義から始めます。これは心筋への血流が途絶えることで心筋が壊死する状態です。次に、診断のゴールドスタンダードであるトロポニン測定について考慮します。これは～という理由で重要です。さらに心電図の変化も重要な所見です。ST上昇が見られる場合、急性期と判断されます。',
            'response': '急性心筋梗塞は、迅速な診断と治療が求められる救急疾患です。診断は主に、臨床症状（胸痛など）、心電図変化（ST上昇など）、心筋逸脱酵素（特にトロポニン）の上昇を三本柱として行われます。アルゴリズムとしては、まず疑いがあれば直ちに12誘導心電図を記録し、バイタルサインを確認します。ST上昇があれば、緊急カテーテル治療の適応を考慮します。<参考資料> 日本循環器学会ガイドライン2023',
        }

        # --- パイプライン実行 ---

        # ステップ1: プロンプト生成 (テストでは直接使用しないが、形式を確認)
        prompt = MEDICAL_KNOWLEDGE_GENERATION_PROMPT.format(topic=topic, audience_level="intermediate")
        self.assertIn(topic, prompt)

        # ステップ2: 推論抽出
        reasoning = extract_reasoning_chain(dummy_response)
        self.assertIsInstance(reasoning, list)
        self.assertGreater(len(reasoning), 0, "推論チェーンが抽出されませんでした。")

        # ステップ3: 座標マッピング
        coordinates = map_reasoning_to_medical_space(reasoning)
        self.assertIsInstance(coordinates, list)
        self.assertEqual(len(coordinates), len(reasoning))

        # ステップ4: Knowledge Tile生成
        tile = create_knowledge_tile(dummy_response, coordinates, topic)
        self.assertIsInstance(tile, dict)
        self.assertEqual(tile['metadata']['topic'], topic)

        # ステップ5: 圧縮 (エンコード)
        encoder = IathEncoder()
        compressed_data = encoder.encode_tile(tile)
        self.assertIsInstance(compressed_data, bytes)
        self.assertGreater(len(compressed_data), 0)

        # ステップ6: 復号 (デコード)
        decoder = IathDecoder()
        restored_tile = decoder.decode_tile(compressed_data)
        self.assertIsInstance(restored_tile, dict)

        # ステップ7: 可逆性検証
        def get_comparable_hash(tile_data: dict) -> str:
            keys_to_compare = ["metadata", "content", "coordinates", "verification"]
            comparable_data = {key: tile_data.get(key) for key in keys_to_compare}
            serialized = json.dumps(comparable_data, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

        original_hash = get_comparable_hash(tile)
        restored_hash = get_comparable_hash(restored_tile)

        self.assertEqual(original_hash, restored_hash, "エンコード・デコードの可逆性が損なわれています。")
        
        print(f"\n--- E2E Test for '{topic}' Passed ---")
        print(f"  - Generated Tile ID: {tile['metadata']['knowledge_id']}")
        print(f"  - Reasoning Steps: {len(reasoning)}")
        print(f"  - Compressed Size: {len(compressed_data)} bytes")
        print("  - Lossless Verification: OK")


if __name__ == '__main__':
    print("Ilm-Athens DB Layer End-to-End Pipeline Test")
    unittest.main()
