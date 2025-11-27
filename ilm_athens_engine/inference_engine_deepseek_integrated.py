import asyncio
import logging
from typing import Dict, Any, Optional, List

# --- すべての依存コンポーネントをインポート ---
from ilm_athens_engine.deepseek_integration.deepseek_runner import DeepSeekR1Engine, DeepSeekConfig
from ilm_athens_engine.domain.manager import DomainManager
from ilm_athens_engine.config import IlmAthensConfig, InferenceBackend
from ilm_athens_engine.core.dendritic_memory import DendriticMemorySpace, DendriticMemoryNode
from backend.iath_db_interface import IathDBInterface
from layer1_spatial_encoding import SpatialEncodingEngine
from judge_alpha_lobe import AlpheLobe
from judge_beta_lobe_advanced import BetaLobeAdvanced
from judge_correction_flow import JudgeCorrectionFlow
from mock_objects import MockOntology

logger = logging.getLogger(__name__)


class IlmAthensEngine:
    """
    Ilm-Athensの全レイヤーを統括するオーケストレーター。

    機能:
    - 推論パイプライン（空間エンコード → DB検索 → 生成 → 検証）
    - NurseLogSystem統合による継続学習・世代交代
    - ドメイン対応（医療/法学/経済学）
    """
    def __init__(
        self,
        domain_manager: DomainManager,
        db_interface: IathDBInterface,
        deepseek_config: Optional[DeepSeekConfig] = None,
        config: Optional[IlmAthensConfig] = None,
        enable_nurse_log_system: bool = False,
        enable_dendritic_memory: bool = True,
        memory_max_nodes: int = 100000
    ):
        print("--- Ilm-Athens Orchestrator Initializing... ---")
        self.domain_manager = domain_manager
        self.db_interface = db_interface
        self.ontology = MockOntology()
        self.config = config or IlmAthensConfig()

        # Layer 3: DeepSeekエンジン
        self.deepseek_engine = DeepSeekR1Engine(deepseek_config)

        # Layer 4: Judge層のコンポーネント
        self.alpha_lobe = AlpheLobe(self.deepseek_engine)
        self.beta_lobe = BetaLobeAdvanced(self.db_interface, self.ontology)
        self.judge_flow = JudgeCorrectionFlow(self.alpha_lobe, self.beta_lobe)

        # Layer 1: 空間エンコーディング（ドメインごとに動的に生成）
        self.spatial_encoders: Dict[str, SpatialEncodingEngine] = {}

        # Layer 5: 樹木型記憶空間（DendriticMemorySpace）
        self.dendritic_memory: Optional[DendriticMemorySpace] = None
        self.enable_dendritic_memory = enable_dendritic_memory
        if enable_dendritic_memory:
            self._init_dendritic_memory(memory_max_nodes)

        # NurseLogSystem統合（倒木更新システム）
        self.nurse_log_system = None
        self.enable_nurse_log_system = enable_nurse_log_system

        if enable_nurse_log_system:
            self._init_nurse_log_system(deepseek_config)

        print(f"  -> DendriticMemory: {'有効' if enable_dendritic_memory else '無効'}")
        print(f"  -> NurseLogSystem: {'有効' if enable_nurse_log_system else '無効'}")

    def _init_dendritic_memory(self, max_nodes: int):
        """DendriticMemorySpaceを初期化"""
        try:
            self.dendritic_memory = DendriticMemorySpace(
                max_nodes=max_nodes,
                db_interface=self.db_interface
            )
            logger.info(f"DendriticMemorySpace初期化完了 (max_nodes={max_nodes})")
        except Exception as e:
            logger.warning(f"DendriticMemorySpace初期化失敗: {e}")
            self.dendritic_memory = None
            self.enable_dendritic_memory = False

    async def sync_dendritic_memory(self, domain: str = "medical") -> int:
        """
        IathDBからDendriticMemorySpaceに知識を同期する。
        初回起動時や明示的なリフレッシュ時に呼び出す。

        Returns:
            同期されたタイル数
        """
        if not self.dendritic_memory:
            logger.warning("DendriticMemorySpaceが無効です")
            return 0

        print(f"\\n【記憶空間同期開始】ドメイン: {domain}")
        synced_count = await self.dendritic_memory.sync_from_db(domain)

        # 統計情報を表示
        stats = self.dendritic_memory.get_stats()
        print(f"  -> 統計: {stats['total_nodes']}ノード, 利用率: {stats['utilization']:.1%}")

        return synced_count

    async def _retrieve_memory_context(
        self,
        coordinates: List[tuple],
        domain_id: str,
        max_results: int = 5
    ) -> List[DendriticMemoryNode]:
        """
        DendriticMemorySpaceから関連記憶を取得する。
        座標ベースの検索でIathDBを補完。
        """
        if not self.dendritic_memory or not coordinates:
            return []

        all_memories = []
        seen_ids = set()

        for coord in coordinates[:3]:  # 最大3座標
            memories = await self.dendritic_memory.retrieve_by_coordinate(
                coordinate=tuple(coord),
                tolerance=20.0,
                max_results=max_results
            )
            for mem in memories:
                if mem.node_id not in seen_ids:
                    all_memories.append(mem)
                    seen_ids.add(mem.node_id)

        # 重要度でソート
        all_memories.sort(key=lambda m: m.importance, reverse=True)
        return all_memories[:max_results]

    def _init_nurse_log_system(self, deepseek_config: Optional[DeepSeekConfig]):
        """NurseLogSystemを初期化（継続学習・世代交代システム）"""
        try:
            from ilm_athens_engine.core.nurse_log_system import NurseLogSystem

            student_config = {
                "hidden_size": 768,
                "num_layers": 6,
                "lora_rank": 8
            }

            self.nurse_log_system = NurseLogSystem(
                deepseek_config=deepseek_config or DeepSeekConfig(),
                student_llm_config=student_config,
                succession_threshold=self.config.succession_threshold,
                dream_interval_conversations=self.config.dream_interval_conversations,
                maturity_threshold_for_inference=0.70,
                min_dream_cycles_for_inference=3
            )
            logger.info("NurseLogSystem初期化完了")
        except ImportError as e:
            logger.warning(f"NurseLogSystem初期化失敗: {e}")
            self.nurse_log_system = None
            self.enable_nurse_log_system = False

    def get_inference_engine(self):
        """
        現在の推論エンジンを取得。
        NurseLogSystem有効時は成熟度ベースルーティングを使用。
        """
        if self.nurse_log_system and self.enable_nurse_log_system:
            return self.nurse_log_system._get_inference_engine()
        return self.deepseek_engine

    def get_system_status(self) -> Dict[str, Any]:
        """システム全体の状態を取得"""
        status = {
            "domain_count": len(self.domain_manager.schemas) if hasattr(self.domain_manager, 'schemas') else 0,
            "spatial_encoders_cached": len(self.spatial_encoders),
            "dendritic_memory_enabled": self.enable_dendritic_memory,
            "nurse_log_enabled": self.enable_nurse_log_system
        }

        # DendriticMemorySpaceの統計
        if self.dendritic_memory:
            status["dendritic_memory"] = self.dendritic_memory.get_stats()

        # NurseLogSystemの統計
        if self.nurse_log_system:
            status["nurse_log"] = self.nurse_log_system.get_system_status()

        return status

    def _get_spatial_encoder(self, domain_id: str) -> SpatialEncodingEngine:
        """ドメインに応じたSpatialEncodingEngineをキャッシュまたは新規作成"""
        if domain_id not in self.spatial_encoders:
            schema = self.domain_manager.get_schema(domain_id)
            if not schema:
                raise ValueError(f"ドメイン'{domain_id}'のスキーマが見つかりません。")
            self.spatial_encoders[domain_id] = SpatialEncodingEngine(schema, self.ontology)
        return self.spatial_encoders[domain_id]

    async def process_question(
        self,
        question: str,
        session_id: str,
        domain_id: str = "medical",
        session_context: Dict[str, Any] = None,
        use_memory_augmentation: bool = True
    ) -> Dict[str, Any]:
        """
        質問を受け取り、完全な推論・検証パイプラインを実行する。
        ドメイン対応のJudge層で検証を行う。
        DendriticMemorySpaceによるコンテキスト強化も実施。
        """
        print(f"\n【Ilm-Athens推論開始】\n  質問: {question}\n  ドメイン: {domain_id}")

        if session_context is None:
            session_context = {"session_id": session_id, "history": []}

        try:
            # L1: 空間エンコーディング
            spatial_encoder = self._get_spatial_encoder(domain_id)
            coords_info = spatial_encoder.extract_coordinates_from_question(question)
            db_coordinates = [info['coordinate'] for info in coords_info]
            print(f"  -> 空間座標: {db_coordinates[:3]}...")

            # L6: DBからコンテキストを取得
            db_context = {}
            if db_coordinates:
                for coord in db_coordinates[:3]:  # 最大3タイル取得
                    tile = await self.db_interface.fetch_async(coord)
                    if tile:
                        db_context[str(coord)] = tile
            print(f"  -> 取得タイル数: {len(db_context)}")

            # L5: DendriticMemorySpaceからの関連記憶でコンテキスト強化
            memory_context = []
            if use_memory_augmentation and self.dendritic_memory and self.enable_dendritic_memory:
                memory_nodes = await self._retrieve_memory_context(
                    coordinates=db_coordinates,
                    domain_id=domain_id,
                    max_results=3
                )
                for node in memory_nodes:
                    # DB直接取得と重複しないものを追加
                    if node.node_id not in db_context:
                        memory_context.append({
                            "node_id": node.node_id,
                            "content": node.content,
                            "importance": node.importance,
                            "layer": node.layer.value
                        })
                print(f"  -> 記憶空間から追加: {len(memory_context)}件")

                # db_contextに記憶空間からの情報を追加
                for mem in memory_context:
                    db_context[f"memory_{mem['node_id']}"] = {
                        "content": mem["content"],
                        "source": "dendritic_memory",
                        "importance": mem["importance"]
                    }

            # L4: JudgeFlowを実行（ドメイン対応）
            final_result = await self.judge_flow.process_and_correct(
                question=question,
                db_context=db_context,
                session_context=session_context,
                domain_id=domain_id
            )

            # セッション履歴に追加
            session_context["history"].append({
                "question": question,
                "response": final_result.get("response", "")[:200],
                "domain": domain_id
            })

            # メタ情報を追加
            final_result["domain"] = domain_id
            final_result["coordinates_used"] = db_coordinates[:3]
            final_result["memory_augmented"] = len(memory_context) > 0
            final_result["memory_nodes_used"] = len(memory_context)

            # NurseLogSystemへの会話ログ記録（継続学習用）
            if self.nurse_log_system and self.enable_nurse_log_system:
                await self._log_to_nurse_system(question, final_result, domain_id)

            return final_result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e), "domain": domain_id}

    async def _log_to_nurse_system(self, question: str, result: Dict[str, Any], domain_id: str):
        """NurseLogSystemに会話を記録（継続学習用）"""
        try:
            # NurseLogSystemのprocess_conversationを呼び出してログを記録
            # これにより、夢のフェーズがトリガーされる可能性がある
            await self.nurse_log_system.process_conversation(
                user_input=question,
                domain_context={"domain_name": domain_id}
            )
            logger.debug(f"NurseLogSystemに会話を記録: {question[:50]}...")
        except Exception as e:
            logger.warning(f"NurseLogSystemへのログ記録失敗: {e}")

    async def trigger_dreaming_phase(self):
        """手動で夢のフェーズをトリガー（テスト/管理用）"""
        if not self.nurse_log_system:
            return {"status": "error", "message": "NurseLogSystemが無効です"}

        await self.nurse_log_system.dreaming_phase()
        return {
            "status": "completed",
            "system_status": self.nurse_log_system.get_system_status()
        }

async def main():
    """テスト用の実行ブロック"""
    # 1. 依存関係を初期化
    domain_manager = DomainManager("domain_schemas.json")
    db_interface = IathDBInterface("ilm_athens_medical_db.iath")
    if not db_interface.load_db():
        print("DBファイルのロードに失敗。テストを中断します。")
        return

    config = DeepSeekConfig(api_url="http://localhost:11434", model_name="deepseek-r1:32b")

    # 2. 新しいオーケストレーターエンジンを初期化（記憶空間有効）
    engine = IlmAthensEngine(
        domain_manager=domain_manager,
        db_interface=db_interface,
        deepseek_config=config,
        enable_dendritic_memory=True,
        memory_max_nodes=50000
    )

    # 3. 記憶空間をDBと同期
    synced = await engine.sync_dendritic_memory(domain="medical")
    print(f"\n【記憶空間同期完了】{synced}件のタイルを統合")

    # 4. システム状態を確認
    status = engine.get_system_status()
    print(f"\n【システム状態】")
    print(json.dumps(status, indent=2, ensure_ascii=False))

    # 5. 推論を実行（記憶空間強化あり）
    result = await engine.process_question(
        question="心筋梗塞の急性期治療について教えてください。",
        session_id="test_session",
        domain_id="medical",
        use_memory_augmentation=True
    )

    print("\n--- 最終推論結果 ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    import json
    # このテストを実行するには、`ilm_athens_medical_db.iath` と Ollama が必要です。
    asyncio.run(main())