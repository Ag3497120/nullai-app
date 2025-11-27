import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock

# --- 必要なモジュールをインポート ---
# NOTE: 実際のテストでは、これらのモジュールがPythonのimportパス上にある必要があります。
from judge_alpha_lobe import AlpheLobe
from judge_beta_lobe_advanced import BetaLobeAdvanced # Advanced版を使用
from judge_correction_flow import JudgeCorrectionFlow
from hallucination_detector import calculate_hallucination_risk_score
from mock_objects import MockRunner, MockOntology, MockDBInterface


class TestJudgeComprehensive(unittest.TestCase):

    def setUp(self):
        # α-Lobeのセットアップ
        self.mock_alpha_lobe = AsyncMock(spec=AlpheLobe)
        
        # β-Lobeのセットアップ (Advanced版を使用)
        self.beta_lobe = BetaLobeAdvanced(MockDBInterface(), None)
        
        # Correction Flow Controllerのセットアップ
        self.controller = JudgeCorrectionFlow(self.mock_alpha_lobe, self.beta_lobe)

    def test_medical_validity_check(self):
        """β-Lobe(Advanced)が医学的妥当性を検証できるか"""
        async def run_test():
            # ケース1: 妥当な治療法
            response_valid = "心筋梗塞の治療にはアスピリンが使われます。"
            check1 = await self.beta_lobe._check_medical_context(response_valid, {})
            self.assertTrue(check1["passed"])

            # ケース2: 未知または妥当でない治療法
            response_invalid = "心筋梗塞の治療には謎のハーブが良いとされます。"
            check2 = await self.beta_lobe._check_medical_context(response_invalid, {})
            self.assertFalse(check2["passed"])
            self.assertEqual(check2["issues"][0]["type"], "unknown_treatment")
        
        asyncio.run(run_test())

    def test_logical_consistency_check(self):
        """β-Lobe(Advanced)が論理エラーを検出できるか"""
        async def run_test():
            # ケース: 偽の二者択一
            response_dichotomy = "治療法はAかBのいずれかしかない。"
            alpha_res = {"main_response": response_dichotomy, "key_points":[]}
            check = await self.beta_lobe._check_logical_consistency("q", alpha_res)
            
            self.assertFalse(check["passed"])
            self.assertEqual(check["logical_errors"][0]["type"], "false_dichotomy")

        asyncio.run(run_test())
    
    def test_correction_flow_approve(self):
        """Correction Flowが問題ない回答を「承認」できるか"""
        async def run_test():
            # α-Lobeが正しい回答を返すと仮定
            self.mock_alpha_lobe.generate_response.return_value = {
                "main_response": "心筋梗塞は冠動脈の閉塞が原因です。", "confidence": 0.9,
                "key_points": [], "uncertainties": [], "sources_cited": ["JCS Guideline"]
            }
            # β-Lobeの検証はすべてパスすると仮定
            self.beta_lobe.validate_response = AsyncMock(return_value={
                "has_contradictions": False, "severity": "none", "checks": {}
            })
            
            result = await self.controller.process_and_correct("質問", db_context={})
            self.assertEqual(result["status"], "approved")

        asyncio.run(run_test())

    def test_correction_flow_regenerate(self):
        """Correction Flowが重大な問題を持つ回答を「再生成」できるか"""
        async def run_test():
            # α-Lobeが最初に間違った回答を返す
            self.mock_alpha_lobe.generate_response.side_effect = [
                {"main_response": "心筋梗塞は脳の病気です。", "confidence": 0.8}, # 初回
                {"main_response": "心筋梗塞は心臓の病気です。", "confidence": 0.9}  # 再生成後
            ]
            
            # β-Lobeは、初回の回答に対して重大な矛盾を検出する
            self.beta_lobe.validate_response = AsyncMock(side_effect=[
                {"has_contradictions": True, "severity": "critical", "checks": {"anchor_facts": {"contradictions":[{"type":"anchor_fact_contradiction"}]}}},
                {"has_contradictions": False, "severity": "none", "checks": {}} # 2回目はパス
            ])

            result = await self.controller.process_and_correct("質問", db_context={})
            
            # 最終的なステータスは'approve'または'corrected'になるはず（再生成が成功し、2回目の検証でパスするため）
            # ここでは再生成が試みられたことを確認
            self.assertEqual(self.mock_alpha_lobe.generate_response.call_count, 2)
            # 最終結果はapproveになるはず
            self.assertEqual(result['status'], 'approved')


        asyncio.run(run_test())

    def test_hallucination_risk_score_calculation(self):
        """ハルシネーションリスクスコアが正しく計算されるか"""
        # 安全なケース
        alpha_res_safe = {"confidence": 0.9, "uncertainties": ["可能性"], "sources_cited": ["ref1"]}
        val_res_safe = {"checks": {"anchor_facts": {"passed": True}, "logic": {"passed": True}}}
        risk_safe = calculate_hallucination_risk_score(alpha_res_safe, val_res_safe)
        self.assertLess(risk_safe["hallucination_risk_score"], 0.3)

        # 危険なケース
        alpha_res_risky = {"confidence": 0.9, "uncertainties": [], "sources_cited": []}
        val_res_risky = {"checks": {"anchor_facts": {"passed": False}, "logic": {"passed": True}}}
        risk_risky = calculate_hallucination_risk_score(alpha_res_risky, val_res_risky)
        self.assertGreater(risk_risky["hallucination_risk_score"], 0.5)

if __name__ == '__main__':
    unittest.main()
