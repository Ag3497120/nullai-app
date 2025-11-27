import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock

# --- リファクタリングされたアーキテクチャのコンポーネントをインポート ---
from domain_manager import DomainManager
from layer1_spatial_encoding import SpatialEncodingEngine
from coordinate_mapper import CoordinateMapper
from reasoning_chain_extractor import extract_reasoning_chain
from knowledge_tile_generator import create_knowledge_tile
from judge_alpha_lobe import AlpheLobe
from judge_beta_lobe_advanced import BetaLobeAdvanced
from judge_correction_flow import JudgeCorrectionFlow
from layer2_episodic_binding import EpisodePalace
from layer5_state_management import ExternalState, LayerResetManager
from hallucination_detector import calculate_hallucination_risk_score

from mock_objects import MockOntology, MockDBInterface, MockLLMClient

class TestRefactoredIntegration(unittest.TestCase):
    
    def setUp(self):
        self.domain_manager = DomainManager()
        self.ontology = MockOntology()

    async def run_full_pipeline_for_domain(self, domain_id: str, question: str, mock_responses: list):
        print(f"\n--- Testing Pipeline for Domain: '{domain_id}' ---")

        # 1. ドメインスキーマをロード
        schema = self.domain_manager.get_schema(domain_id)
        self.assertIsNotNone(schema)

        # 2. ドメイン固有のコンポーネントを初期化
        spatial_encoder = SpatialEncodingEngine(schema, self.ontology)
        db_interface = MockDBInterface(schema['domain_id'])
        mock_llm = MockLLMClient(mock_responses)

        # α-Lobe, β-Lobe, JudgeFlow を初期化
        mock_alpha_lobe = AsyncMock(spec=AlpheLobe)
        mock_alpha_lobe.generate_response.side_effect = mock_llm.generate_response
        beta_lobe = BetaLobeAdvanced(db_interface, self.ontology)
        judge_flow = JudgeCorrectionFlow(mock_alpha_lobe, beta_lobe)
        
        # 3. パイプラインを実行
        coords_info = spatial_encoder.extract_coordinates_from_question(question)
        db_context = {coords_info[0]['coordinate']: await db_interface.fetch_async(coords_info[0]['coordinate'])}
        
        final_result = await judge_flow.process_and_correct(question, db_context)
        
        # 4. 結果を検証
        self.assertIn(final_result['status'], ['approved', 'corrected'])
        print(f"  -> Question: '{question}'")
        print(f"  -> Final Status: {final_result['status']}")
        print(f"  -> Final Response: {final_result['response'][:50]}...")
        
        return final_result

    def test_medical_and_legal_domains(self):
        async def run_tests():
            # 医学ドメインのテスト
            await self.run_full_pipeline_for_domain(
                domain_id="medical",
                question="心筋梗塞の原因は？",
                mock_responses=[{"text": "心筋梗塞は心臓の冠動脈が詰まることで起こります。", "confidence": 0.95}]
            )

            # 法学ドメインのテスト
            await self.run_full_pipeline_for_domain(
                domain_id="legal",
                question="契約の成立要件は？",
                mock_responses=[{"text": "契約は当事者間の申込みと承諾が合致することで成立します。", "confidence": 0.98}]
            )
            
            # 矛盾を発生させるテスト（医学）
            await self.run_full_pipeline_for_domain(
                domain_id="medical",
                question="心筋梗塞の原因は？",
                mock_responses=[{"text": "心筋梗塞は脳の血管が詰まることで起こります。", "confidence": 0.9}]
            )

        asyncio.run(run_tests())

if __name__ == '__main__':
    unittest.main()