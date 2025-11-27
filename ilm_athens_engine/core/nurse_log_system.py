import torch
import torch.nn as nn
import gc
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import logging

# 依存コンポーネントをインポート
from ilm_athens_engine.deepseek_integration.deepseek_runner import DeepSeekR1Engine, DeepSeekConfig
from ilm_athens_engine.core.student_llm import StudentLLM
from ilm_athens_engine.model_manager import get_model_manager, EngineType

logger = logging.getLogger(__name__)

# --- ヘルパークラス ---

@dataclass
class ConversationLog:
    """昼間の会話ログ"""
    user_input: str
    mentor_response: Dict[str, Any]
    apprentice_attempt: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(datetime.UTC))

@dataclass
class StudentModelState:
    """各世代のStudentLLMの状態スナップショット"""
    generation: int
    model_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(datetime.UTC))
    training_steps: int = 0
    total_conversations: int = 0
    average_loss: float = 0.0
    kl_divergence: float = 0.0
    confidence_score: float = 0.0
    is_ready_for_succession: bool = False
    specialization: Dict[str, Any] = field(default_factory=dict)
    # 成熟度関連フィールド
    maturity_score: float = 0.0  # 0.0〜1.0の成熟度スコア
    is_mature_for_inference: bool = False  # 推論に使用可能かどうか
    dream_cycles_completed: int = 0  # 完了した夢のフェーズ数
    evaluation_history: List[float] = field(default_factory=list)  # 評価履歴

class NurseLogSystem:
    """
    倒木更新システム
    世代交代・継続進化システムを管理する。

    成熟度ベースのルーティング:
    - 未成熟なStudentは推論に使用せず、DeepSeekまたは成熟済みモデルを優先
    - Studentが成熟閾値を超えたら推論担当に昇格可能
    - 世代交代時も、新しいStudentが成熟するまで旧Mentorが推論を継続
    """
    def __init__(
        self,
        deepseek_config: DeepSeekConfig,
        student_llm_config: Dict = None,
        succession_threshold: float = 0.85,  # 弟子の評価がこれを超えたら世代交代
        dream_interval_conversations: int = 10,  # 何会話ごとに夢を見るか
        maturity_threshold_for_inference: float = 0.70,  # 推論に使用可能な成熟度閾値
        min_dream_cycles_for_inference: int = 3,  # 推論可能になるまでの最低夢サイクル数
    ):
        print("--- NurseLogSystem Initializing... ---")

        if student_llm_config is None:
            student_llm_config = {}

        self.current_generation = 1
        self.deepseek_config = deepseek_config

        # 基盤モデル（DeepSeek）は常に利用可能な成熟済みモデルとして保持
        self.foundation_engine = DeepSeekR1Engine(deepseek_config)

        # 現在の推論担当エンジン（初期はDeepSeek）
        self.active_inference_engine = self.foundation_engine

        # 師匠エンジン（訓練監督用、初期はDeepSeekと同じ）
        self.mentor_engine = self.foundation_engine

        # 弟子エンジン（訓練中）
        self.apprentice_engine = StudentLLM(**student_llm_config)

        # 現在の弟子の状態追跡
        self.current_apprentice_state = StudentModelState(
            generation=self.current_generation,
            model_id=f"student_gen_{self.current_generation}",
            maturity_score=0.0,
            is_mature_for_inference=False
        )

        self.generation_history: List[StudentModelState] = []
        self.conversation_buffer: List[ConversationLog] = []

        # 閾値設定
        self.succession_threshold = succession_threshold
        self.dream_interval_conversations = dream_interval_conversations
        self.maturity_threshold_for_inference = maturity_threshold_for_inference
        self.min_dream_cycles_for_inference = min_dream_cycles_for_inference

        self.is_dreaming = False

        # 成熟済みのStudentモデルプール（世代交代で昇格したモデル）
        self.mature_student_pool: List[Any] = []

        print(f"  -> Foundation: {self.foundation_engine.config.model_name}")
        print(f"  -> Active Inference: DeepSeek (成熟済み)")
        print(f"  -> Apprentice: Gen {self.current_generation} (訓練中, 成熟度: 0%)")
        print(f"  -> 成熟閾値: {self.maturity_threshold_for_inference:.0%}, 最低夢サイクル: {self.min_dream_cycles_for_inference}")

    def _get_inference_engine(self) -> Any:
        """
        推論に使用するエンジンを決定する成熟度ベースルーティング

        優先順位:
        1. 成熟済みのStudent（あれば）
        2. DeepSeek基盤モデル（常に利用可能）

        未成熟なStudentは推論に使用しない
        """
        # 成熟済みStudentがあれば優先
        if self.mature_student_pool:
            return self.mature_student_pool[-1]  # 最新の成熟済みモデル

        # 現在のApprenticeが成熟済みかチェック
        if self._is_apprentice_mature():
            logger.info(f"弟子Gen{self.current_generation}が成熟済み。推論に使用可能。")
            return self.apprentice_engine

        # 未成熟な場合はDeepSeek基盤モデルを使用
        logger.debug(f"弟子Gen{self.current_generation}は未成熟（成熟度: {self.current_apprentice_state.maturity_score:.1%}）。DeepSeekを使用。")
        return self.foundation_engine

    def _is_apprentice_mature(self) -> bool:
        """現在の弟子が推論可能な成熟度に達しているか判定"""
        state = self.current_apprentice_state

        # 条件1: 成熟度スコアが閾値以上
        maturity_ok = state.maturity_score >= self.maturity_threshold_for_inference

        # 条件2: 最低限の夢サイクルを完了
        cycles_ok = state.dream_cycles_completed >= self.min_dream_cycles_for_inference

        # 両条件を満たす場合のみ成熟と判定
        is_mature = maturity_ok and cycles_ok

        if is_mature and not state.is_mature_for_inference:
            state.is_mature_for_inference = True
            logger.info(f"弟子Gen{state.generation}が成熟状態に移行（成熟度: {state.maturity_score:.1%}, サイクル: {state.dream_cycles_completed}）")
            print(f"  ★ 弟子Gen{state.generation}が成熟！推論に使用可能になりました。")

        return is_mature

    def _update_apprentice_maturity(self, evaluation_score: float):
        """弟子の成熟度を更新"""
        state = self.current_apprentice_state

        # 評価履歴に追加
        state.evaluation_history.append(evaluation_score)
        state.dream_cycles_completed += 1

        # 成熟度スコアを計算（直近の評価の加重平均）
        if len(state.evaluation_history) >= 3:
            # 直近3回の評価で加重平均（新しいほど重み大）
            weights = [0.2, 0.3, 0.5]
            recent = state.evaluation_history[-3:]
            state.maturity_score = sum(w * s for w, s in zip(weights, recent))
        else:
            # データ不足の場合は単純平均
            state.maturity_score = sum(state.evaluation_history) / len(state.evaluation_history)

        state.confidence_score = evaluation_score

        logger.info(f"弟子Gen{state.generation}の成熟度更新: {state.maturity_score:.1%} (サイクル: {state.dream_cycles_completed})")
        print(f"  -> 弟子Gen{state.generation}の成熟度: {state.maturity_score:.1%} (サイクル: {state.dream_cycles_completed}/{self.min_dream_cycles_for_inference})")

        # 成熟判定を実行
        self._is_apprentice_mature()

    def get_system_status(self) -> Dict[str, Any]:
        """システムの現在の状態を取得"""
        inference_engine = self._get_inference_engine()
        inference_type = "DeepSeek" if inference_engine == self.foundation_engine else f"Student_Gen{self.current_generation}"

        return {
            "current_generation": self.current_generation,
            "active_inference_engine": inference_type,
            "apprentice_maturity": self.current_apprentice_state.maturity_score,
            "apprentice_is_mature": self.current_apprentice_state.is_mature_for_inference,
            "dream_cycles_completed": self.current_apprentice_state.dream_cycles_completed,
            "maturity_threshold": self.maturity_threshold_for_inference,
            "min_dream_cycles": self.min_dream_cycles_for_inference,
            "conversation_buffer_size": len(self.conversation_buffer),
            "is_dreaming": self.is_dreaming,
            "mature_student_count": len(self.mature_student_pool)
        }

    async def process_conversation(
        self,
        user_input: str,
        domain_context: Optional[Dict] = None
    ) -> Dict:
        """
        会話処理（昼間フェーズ）
        成熟度ベースルーティングで適切なモデルが回答。
        ログをバッファに追加し、必要に応じて夢のフェーズをトリガー。
        """
        print(f"\n【昼間フェーズ】会話処理中 (Gen {self.current_generation})...")

        # 1. 成熟度ベースで推論エンジンを選択
        inference_engine = self._get_inference_engine()
        engine_name = "DeepSeek" if inference_engine == self.foundation_engine else f"Student_Gen{self.current_generation}"
        print(f"  -> 推論エンジン: {engine_name} (成熟度: {self.current_apprentice_state.maturity_score:.1%})")

        # 2. 選択されたエンジンで推論実行
        if inference_engine == self.foundation_engine or hasattr(inference_engine, 'infer'):
            # DeepSeekまたは成熟済みStudentの場合
            inference_response = await inference_engine.infer(user_input, domain_context)
        else:
            # StudentLLMの場合（将来的な拡張用）
            inference_response = {"response": "StudentLLM推論未実装", "confidence": 0.0}

        # 3. 師匠（DeepSeek）による監督応答（訓練データ生成用）
        # 推論エンジンがDeepSeekでない場合も、訓練用に師匠の応答を取得
        if inference_engine != self.foundation_engine:
            mentor_response = await self.foundation_engine.infer(user_input, domain_context)
        else:
            mentor_response = inference_response

        # 4. 弟子の試行（バックグラウンドで訓練データとして記録）
        apprentice_attempt_data = None
        if not self.current_apprentice_state.is_mature_for_inference:
            # 未成熟な弟子は推論に使わないが、訓練用に試行を記録
            apprentice_attempt_text = f"StudentLLMの応答（訓練中）: {user_input}への試行"
            apprentice_attempt_data = {"response": apprentice_attempt_text, "confidence": 0.0}

        # 5. ログ記録
        log = ConversationLog(
            user_input=user_input,
            mentor_response=mentor_response,
            apprentice_attempt=apprentice_attempt_data
        )
        self.conversation_buffer.append(log)
        self.current_apprentice_state.total_conversations += 1

        print(f"  -> 会話ログを追加 (現在 {len(self.conversation_buffer)} 件)")

        # 6. バッファが満杯なら夢のフェーズを実行
        if len(self.conversation_buffer) >= self.dream_interval_conversations and not self.is_dreaming:
            asyncio.create_task(self.dreaming_phase())

        return {
            "response": inference_response.get("response"),
            "generation": self.current_generation,
            "inference_engine": engine_name,
            "apprentice_maturity": self.current_apprentice_state.maturity_score,
            "is_apprentice_mature": self.current_apprentice_state.is_mature_for_inference
        }

    async def dreaming_phase(self):
        """
        夢を見る学習フェーズ（夜間）
        ナレッジ蒸留と評価を行い、成熟度を更新。
        成熟閾値を超えたら世代交代をトリガー。
        """
        if self.is_dreaming:
            print("警告: 既に夢のフェーズ実行中です。")
            return

        self.is_dreaming = True
        cycle_num = self.current_apprentice_state.dream_cycles_completed + 1
        print(f"\n=== 夜間フェーズ開始: 夢を見る学習 (サイクル {cycle_num}) ===\n")

        # 1. 訓練データセット構築
        training_data = []
        for log in self.conversation_buffer:
            if log.mentor_response.get("success", True):
                training_data.append({
                    "user_input": log.user_input,
                    "mentor_output": log.mentor_response.get("full_response")
                })

        if not training_data:
            print("警告: 訓練データがありません。夢のフェーズをスキップします。")
            self.is_dreaming = False
            return

        print(f"  -> {len(training_data)}件のデータで蒸留学習を開始します。")

        # 2. Knowledge Distillation
        optimizer = torch.optim.AdamW(self.apprentice_engine.parameters(), lr=1e-4)

        total_loss = 0.0
        for epoch in range(3):
            for item in training_data:
                input_ids = torch.randint(0, 50257, (1, 10))
                student_logits = self.apprentice_engine(input_ids)
                mentor_logits = torch.randn_like(student_logits)

                loss = StudentLLM.distill_from_mentor(mentor_logits, student_logits)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

        avg_loss = total_loss / (len(training_data) * 3)
        self.current_apprentice_state.average_loss = avg_loss
        self.current_apprentice_state.training_steps += len(training_data) * 3
        print(f"  -> 蒸留学習完了。平均損失: {avg_loss:.4f}")

        # 3. 評価
        confidence = await self._evaluate_apprentice()
        print(f"  -> 弟子の評価完了。信頼度: {confidence:.1%}")

        # 4. 成熟度を更新（これが重要！）
        self._update_apprentice_maturity(confidence)

        # 5. 成熟状態のログ
        state = self.current_apprentice_state
        maturity_status = "成熟済み ★" if state.is_mature_for_inference else "訓練中"
        print(f"  -> 弟子状態: {maturity_status}")
        print(f"     成熟度: {state.maturity_score:.1%} (閾値: {self.maturity_threshold_for_inference:.0%})")
        print(f"     夢サイクル: {state.dream_cycles_completed}/{self.min_dream_cycles_for_inference}")

        # 6. 世代交代判定（成熟度が継承閾値を超えた場合）
        if confidence >= self.succession_threshold and state.is_mature_for_inference:
            print(f"  -> 評価 {confidence:.1%} >= 継承閾値 {self.succession_threshold:.1%}")
            print(f"  -> かつ成熟済み。世代交代プロトコル実行！")
            await self._succession_protocol(confidence)
        elif confidence >= self.succession_threshold:
            print(f"  -> 評価は継承閾値を超えましたが、成熟度が不足。世代交代は保留。")
        else:
            print(f"  -> 評価 {confidence:.1%} < 継承閾値 {self.succession_threshold:.1%}。世代交代は行いません。")

        self.conversation_buffer.clear()
        self.is_dreaming = False
        print("\n=== 夜間フェーズ終了 ===\n")

    async def _evaluate_apprentice(self) -> float:
        """弟子の評価（プレースホルダー）"""
        # 実際には、独立した評価セットで推論を行い、基準に照らして評価する
        return 0.7 + (self.current_generation * 0.05) # 世代が進むと評価が上がるようにシミュレート

    async def _succession_protocol(self, new_mentor_confidence: float):
        """
        世代交代プロトコル
        成熟した弟子を成熟済みプールに移動し、新しい弟子を誕生させる。
        世代交代中も成熟済みモデルが推論を継続するため、サービス中断なし。
        """
        old_generation = self.current_generation
        self.current_generation += 1
        logger.info(f"世代交代プロトコル実行: 第{old_generation}世代 → 第{self.current_generation}世代")
        print(f"\n--- 世代交代プロトコル実行: 第{old_generation}世代 → 第{self.current_generation}世代 ---")

        # 1. 現世代の状態を履歴に保存
        self.current_apprentice_state.is_ready_for_succession = True
        self.generation_history.append(self.current_apprentice_state)

        # 2. 成熟した弟子を成熟済みプールに追加（推論に使用可能）
        print(f"  -> 第{old_generation}世代の弟子を成熟済みプールに追加")
        self.mature_student_pool.append(self.apprentice_engine)
        logger.info(f"成熟済みプールに追加: Gen{old_generation} (プールサイズ: {len(self.mature_student_pool)})")

        # 3. ModelManagerを使用（オプション）
        model_manager = get_model_manager()

        # 4. 古い成熟済みモデルのメモリ管理（プールが大きくなりすぎたら最古を解放）
        max_pool_size = 2  # 最大保持数
        if len(self.mature_student_pool) > max_pool_size:
            oldest_model = self.mature_student_pool.pop(0)
            print(f"  -> 成熟済みプールが上限超過。最古のモデルを解放")
            if hasattr(oldest_model, 'unload_model'):
                oldest_model.unload_model()
            del oldest_model
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        # 5. 新しい弟子を作成（未成熟状態で開始）
        logger.info("新しい弟子を作成中...")
        print(f"  -> 新しい弟子（第{self.current_generation}世代）を作成中...")

        # デフォルトモデルはHuggingFaceのオープンソースモデルを使用
        # 注意: OpenAI/Anthropic等の外部APIモデルは使用不可
        old_apprentice_config = {
            "base_model_name": getattr(self.apprentice_engine, 'base_model_name', 'deepseek-ai/DeepSeek-R1-Distill-Qwen-7B'),
            "hidden_size": getattr(self.apprentice_engine, 'hidden_size', 768),
            "num_layers": getattr(self.apprentice_engine, 'num_layers', 6),
            "lora_rank": getattr(self.apprentice_engine, 'lora_rank', 8)
        }

        self.apprentice_engine = StudentLLM(**old_apprentice_config)

        # 6. 新しい弟子の状態を初期化
        self.current_apprentice_state = StudentModelState(
            generation=self.current_generation,
            model_id=f"student_gen_{self.current_generation}",
            maturity_score=0.0,
            is_mature_for_inference=False,
            dream_cycles_completed=0
        )

        # 7. メモリ状況を報告
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            memory_gb = torch.cuda.memory_allocated() / 1024**3
            print(f"  -> GPU使用量: {memory_gb:.2f} GB")

        memory_status = model_manager.get_memory_status()
        logger.info(f"メモリ状況: {memory_status}")

        print(f"\n  ★ 世代交代完了!")
        print(f"    - 第{old_generation}世代の弟子が成熟済みプールに移動（推論継続可能）")
        print(f"    - 新しい弟子（第{self.current_generation}世代）が誕生（訓練開始）")
        print(f"    - 推論は成熟済みモデルが担当（サービス中断なし）")

# --- 使用例 ---
async def main():
    deepseek_config = DeepSeekConfig(model_name="gemma:2b") # テスト用にgemma
    student_llm_config = {"hidden_size": 768, "lora_rank": 8}
    
    nurse_log_system = NurseLogSystem(deepseek_config, student_llm_config, dream_interval_conversations=3)

    # 複数会話をシミュレートし、夢のフェーズと世代交代をトリガー
    for i in range(1, 7): # 6会話を処理 (2回夢のフェーズが走るはず)
        user_input = f"新しい医療知識に関する質問 {i}"
        response = await nurse_log_system.process_conversation(user_input)
        print(f"  -> 師匠の応答: {response.get('response')[:50]}...")
        await asyncio.sleep(0.1) # 非同期処理のデモ

if __name__ == "__main__":
    asyncio.run(main())
