import unittest
import asyncio
from unittest.mock import patch, AsyncMock

# 依存コンポーネントをインポート
from ilm_athens_engine.core.nurse_log_system import NurseLogSystem
from ilm_athens_engine.deepseek_integration.deepseek_runner import DeepSeekConfig

class TestWeek2Integration(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """テストのセットアップ"""
        print("\n--- Setting up Week 2 Integration Test (Generational System) ---")
        
        # テスト用のコンフィグ
        self.config = DeepSeekConfig(api_url="http://localhost:11434", model_name="gemma:2b")
        
        # NurseLogSystemを初期化
        # 夢のフェーズが2回の会話でトリガーされるように設定
        self.nurse_log_system = NurseLogSystem(
            deepseek_config=self.config,
            dream_interval_conversations=2
        )
        
        # 師匠エンジン（DeepSeek）の推論メソッドをモックに置き換え、実際のAPIコールを防ぐ
        self.nurse_log_system.mentor_engine.infer = AsyncMock(
            return_value={"response": "師匠の応答", "success": True}
        )

    async def test_dream_phase_trigger(self):
        """
        会話ログが閾値に達した際に、夢のフェーズ（学習）が
        バックグラウンドで正しくトリガーされることをテストする。
        """
        print("\n[Test] Verifying Dream Phase trigger...")
        
        # 初期状態では夢のフェーズは実行されていない
        self.assertFalse(self.nurse_log_system.is_dreaming)

        # 1回目の会話
        await self.nurse_log_system.process_conversation("質問1")
        self.assertFalse(self.nurse_log_system.is_dreaming, "1回目の会話ではまだトリガーされないはず")

        # 2回目の会話（ここで閾値に達する）
        await self.nurse_log_system.process_conversation("質問2")
        
        # dreaming_phaseはバックグラウンドタスクとして生成されるため、
        # is_dreamingフラグがTrueに変わるのを少し待つ
        await asyncio.sleep(0.1)
        
        self.assertTrue(self.nurse_log_system.is_dreaming, "2回目の会話後、夢のフェーズがトリガーされるはず")
        
        # 実行中のタスクをクリーンアップ
        # dreaming_phaseが完了するまで待機（テストを安定させるため）
        while self.nurse_log_system.is_dreaming:
            await asyncio.sleep(0.1)

        print("  -> ✓ Dream Phase was triggered correctly.")


    @patch('ilm_athens_engine.core.nurse_log_system.NurseLogSystem._evaluate_apprentice', new_callable=AsyncMock)
    async def test_succession_protocol_trigger(self, mock_evaluate):
        """
        弟子の評価スコアが閾値を超えた場合に、世代交代プロトコルが
        正しく実行されることをテストする。
        """
        print("\n[Test] Verifying Succession Protocol trigger...")
        
        # 弟子の評価スコアが閾値(0.85)を超えるようにモックを設定
        mock_evaluate.return_value = 0.90
        
        # 初期世代は1
        self.assertEqual(self.nurse_log_system.current_generation, 1)

        # 夢のフェーズがトリガーされるまで会話を処理
        await self.nurse_log_system.process_conversation("質問A")
        await self.nurse_log_system.process_conversation("質問B")
        
        # 夢のフェーズが完了するまで待機
        while self.nurse_log_system.is_dreaming:
            await asyncio.sleep(0.1)
        
        # 世代交代が実行され、世代がインクリメントされたことを確認
        self.assertEqual(self.nurse_log_system.current_generation, 2, "世代交代が実行され、世代が2になるはず")
        print("  -> ✓ Succession Protocol was triggered correctly.")
        print(f"  -> New Generation: {self.nurse_log_system.current_generation}")

if __name__ == '__main__':
    unittest.main()
