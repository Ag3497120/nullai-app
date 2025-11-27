import unittest
import asyncio

# 実装したモジュールをインポート
from judge_alpha_lobe import AlpheLobe
from judge_beta_lobe_basic import BetaLobeBasic
from runner_engine import RunnerEngine
from layer1_spatial_encoding import SpatialEncodingEngine, MockOntology
from runner_engine import MockLLMClient, MockDBInterface
from web_search_autonomy import WebSearchAutonomySystem

class TestJudgeBasic(unittest.TestCase):

    def setUp(self):
        """テストのセットアップ: 各コンポーネントを初期化"""
        # α-Lobeの依存コンポーネント
        spatial_encoder = SpatialEncodingEngine(MockOntology())
        runner = RunnerEngine(MockLLMClient(), MockDBInterface(), WebSearchAutonomySystem())
        self.alpha_lobe = AlpheLobe(runner, spatial_encoder)
        
        # β-Lobeの依存コンポーネント
        self.beta_lobe = BetaLobeBasic(MockDBInterface(), MockOntology())

    def test_alpha_lobe_generation(self):
        """α-Lobeが構造化された回答を生成できるかテスト"""
        async def run_test():
            question = "心筋梗塞の診断について"
            response = await self.alpha_lobe.generate_response(question)
            
            # 必須キーが存在するかチェック
            self.assertIn("is_complete", response)
            self.assertIn("main_response", response)
            self.assertIn("thinking_process", response)
            self.assertIn("key_points", response)
            self.assertTrue(response["is_complete"])
            self.assertGreater(len(response["main_response"]), 0)
        
        asyncio.run(run_test())

    def test_beta_lobe_anchor_fact_contradiction(self):
        """β-LobeがAnchor事実との明確な矛盾を検出できるかテスト"""
        async def run_test():
            # セットアップ: α-Lobeが意図的に誤った回答を生成したと仮定
            alpha_response = {
                "main_response": "心筋梗塞は脳の血流が悪くなることで発生します。これが原因です。"
            }
            db_context = {
                (28, 55, 15): { # 心筋梗塞の機序の座標
                    "anchor_facts": [
                        {"text": "心筋梗塞は心臓の冠動脈が詰まることで起こる", "type": "causal"}
                    ]
                }
            }
            
            # 検証実行
            validation_result = await self.beta_lobe.validate_response_basic(alpha_response, db_context)
            
            # アサーション
            self.assertTrue(validation_result["has_contradictions"])
            self.assertEqual(validation_result["severity"], "critical")
            self.assertEqual(validation_result["checks"]["anchor_facts"]["contradiction_count"], 1)
            contradiction_detail = validation_result["checks"]["anchor_facts"]["contradictions"][0]
            self.assertEqual(contradiction_detail["type"], "anchor_fact_contradiction")
            self.assertIn("脳の血流", contradiction_detail["response_excerpt"])

        asyncio.run(run_test())

    def test_beta_lobe_no_contradiction(self):
        """β-Lobeが矛盾のない回答を正しく承認できるかテスト"""
        async def run_test():
            # セットアップ: 正確な回答
            alpha_response = {
                "main_response": "心筋梗塞は心臓の冠動脈の血流が途絶えることで発生します。"
            }
            db_context = {
                (28, 55, 15): {
                    "anchor_facts": [
                        {"text": "心筋梗塞は心臓の冠動脈が詰まることで起こる", "type": "causal"}
                    ]
                }
            }
            
            # 検証実行
            validation_result = await self.beta_lobe.validate_response_basic(alpha_response, db_context)
            
            # アサーション
            self.assertFalse(validation_result["has_contradictions"])
            self.assertEqual(validation_result["severity"], "none")
            self.assertTrue(validation_result["checks"]["anchor_facts"]["passed"])

        asyncio.run(run_test())
        
    def test_beta_lobe_numerical_contradiction(self):
        """β-Lobeが数値の矛盾を検出できるかテスト"""
        async def run_test():
            alpha_response = {
                "main_response": "正常な体温はだいたい40.0度です。"
            }
            db_context = {
                (1,1,1): {
                     "anchor_facts": [
                        {"text": "正常なヒトの体温は36.5度から37.5度の範囲", "type": "numerical"}
                    ]
                }
            }
            validation_result = await self.beta_lobe.validate_response_basic(alpha_response, db_context)
            self.assertTrue(validation_result["has_contradictions"])
            self.assertEqual(validation_result["checks"]["anchor_facts"]["contradiction_count"], 1)

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
