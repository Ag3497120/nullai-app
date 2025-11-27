import unittest
import asyncio
from typing import Dict

# 本日実装したコンポーネントをインポート
from ilm_athens_engine.core.dendritic_memory import DendriticMemorySpace
from ilm_athens_engine.core.symbiotic_engine import SymbioticTwinEngineSystem
from ilm_athens_engine.deepseek_integration.deepseek_runner import DeepSeekConfig

class TestWeek1Integration(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """テストのセットアップ"""
        print("\n--- Setting up Week 1 Integration Test ---")
        
        # テスト用のコンフィグ
        self.config = DeepSeekConfig(api_url="http://localhost:11434", model_name="deepseek-r1:32b")
        
        # 1. 樹木型記憶空間を初期化
        self.memory_space = DendriticMemorySpace()
        
        # 2. 連理の木エンジンシステムを初期化
        self.twin_engine_system = SymbioticTwinEngineSystem(self.config)
        # テストのため、L0リセットの閾値を3ターンに短縮
        self.twin_engine_system.l0_reset_threshold = 3

    async def test_full_cycle_integration(self):
        """
        会話サイクルと記憶統合のテスト:
        1. 連理の木エンジンが会話を処理する。
        2. 各ターンの結果が樹木型記憶に統合される。
        3. L0リセットが正常に発生する。
        4. 蓄積された記憶が検索できることを確認する。
        """
        
        # --- 4ターンの会話をシミュレート ---
        # (3ターン目でL0リセットがトリガーされるはず)
        conversation_topics = ["心筋梗塞の原因", "高血圧の診断基準", "糖尿病の食事療法", "COPDの治療"]
        
        for i, topic in enumerate(conversation_topics):
            # 1. 連理の木エンジンがユーザー入力を処理
            response_data = await self.twin_engine_system.process_user_input(topic)
            self.assertTrue(response_data.get("success", True), f"Engine inference failed on turn {i+1}")

            # 2. 応答からダミーの知識タイルを作成
            #    (実際のパイプラインでは、より多くの情報を持つタイルが生成される)
            mock_tile = self._create_mock_tile_from_response(topic, response_data, i)

            # 3. 知識タイルを樹木型記憶に統合
            self.memory_space.integrate_tile(mock_tile)
            
            # 記憶にノードが追加されたことを確認
            self.assertIn(mock_tile["metadata"]["knowledge_id"], self.memory_space.nodes)

        # --- 検証フェーズ ---

        # 4. L0リセットが発生したか確認
        # 4ターン実行したので、turn_countは4。閾値3を超えているため、リセットが1回実行されたはず。
        # ActiveエンジンがEngineBに切り替わっていることを確認
        self.assertEqual(self.twin_engine_system.active_memory.engine_name, "EngineB", "L0リセット後のエンジン役割交代が失敗しました。")

        # 5. 蓄積された記憶が検索できるか確認
        # 最初の質問「心筋梗塞の原因」に近いトピックで検索
        query_coord = self.memory_space.nodes["tile_0"].coordinate
        retrieved_nodes = await self.memory_space.retrieve_memories(query_coord.theta)
        
        self.assertGreater(len(retrieved_nodes), 0, "樹木型記憶から関連ノードを検索できませんでした。")
        
        # 検索結果に最初のタイルが含まれていることを確認
        retrieved_ids = [node.node_id for node in retrieved_nodes]
        self.assertIn("tile_0", retrieved_ids, "検索結果に期待したノードが含まれていません。")
        
        print("\n--- Integration Test Passed ---")
        print("  ✓ Conversation simulation complete.")
        print("  ✓ Knowledge integration into Dendritic Memory successful.")
        print("  ✓ L0 Reset and Engine Swap successful.")
        print("  ✓ Memory retrieval successful.")


    def _create_mock_tile_from_response(self, topic: str, response: Dict, index: int) -> Dict:
        """応答データからテスト用の簡易知識タイルを作成するヘルパー"""
        # 座標は、テスト用に簡易的に生成
        x = 20 + index * 10
        y = 30 + index * 5
        z = 15
        
        return {
            "metadata": {"knowledge_id": f"tile_{index}", "topic": topic},
            "content": {"final_response": response.get("response", "")},
            "coordinates": {
                "medical_space": [x, y, z], 
                "meta_space": [response.get("confidence", 0.5) * 100, 100, 80]
            }
        }

if __name__ == '__main__':
    # 非同期テストを実行
    # `python -m unittest test_week1_integration.py` でも実行可能
    unittest.main()
