import asyncio
from typing import Dict, Any

# --- これまでに実装した全コンポーネントをインポート ---
from domain_manager import DomainManager
from backend.iath_db_interface import IathDBInterface
from backend.deepseek_local_client import DeepSeekLocalClient, DeepSeekConfig
from layer1_spatial_encoding import SpatialEncodingEngine
from layer2_episodic_binding import EpisodePalace
from judge_alpha_lobe import AlpheLobe
from judge_beta_lobe_advanced import BetaLobeAdvanced
from judge_correction_flow import JudgeCorrectionFlow
from layer5_state_management import ExternalState, LayerResetManager
from hallucination_detector import calculate_hallucination_risk_score

# --- モックオブジェクト（テスト用） ---
from mock_objects import MockOntology

class InferenceEngine:
    """
    Ilm-Athensの全推論レイヤーを統合し、単一のインターフェースを提供するクラス。
    """
    def __init__(self, deepseek_config: DeepSeekConfig, db_path: str):
        """
        推論エンジンの初期化。すべてのコアコンポーネントをロードします。

        Args:
            deepseek_config (DeepSeekConfig): DeepSeekローカルクライアントの設定。
            db_path (str): .iath データベースファイルのパス。
        """
        print("--- Ilm-Athens Unified Inference Engine Initializing... ---")
        # 外部クライアントの初期化
        self.llm_client = DeepSeekLocalClient(config=deepseek_config)
        self.db_interface = IathDBInterface(db_file_path=db_path)
        
        # マネージャーと汎用コンポーネントの初期化
        self.domain_manager = DomainManager()
        self.ontology = MockOntology() # オントロジーはまだモックを使用
        
        # セッション管理用のストレージ
        self.sessions: Dict[str, Dict[str, Any]] = {}

        # DBのロード
        if not self.db_interface.load_db():
            print(f"警告: DBファイル '{db_path}' のロードに失敗しました。DBコンテキストなしで動作します。")
        
        print("--- Initialization Complete. ---")

    def _get_or_create_session(self, session_id: str) -> Dict[str, Any]:
        """セッションIDに対応するオブジェクトを取得または新規作成する。"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "episode_palace": EpisodePalace(session_id),
                "external_state": ExternalState(),
                "reset_manager": LayerResetManager(self.llm_client)
            }
        return self.sessions[session_id]

    async def process_question(
        self,
        question: str,
        session_id: str,
        domain_id: str = "medical"
    ) -> Dict[str, Any]:
        """
        単一の質問を受け取り、推論から検証までの完全なパイプラインを実行します。

        Args:
            question (str): ユーザーからの質問。
            session_id (str): 現在の会話セッションを識別するID。
            domain_id (str): 使用する知識ドメイン (例: "medical", "legal")。

        Returns:
            dict: 最終的な処理結果を含む辞書。
        """
        print(f"\n--- Processing question in session '{session_id}' for domain '{domain_id}' ---")
        
        # 1. セッションオブジェクトを取得
        session = self._get_or_create_session(session_id)
        episode_palace: EpisodePalace = session["episode_palace"]
        external_state: ExternalState = session["external_state"]
        reset_manager: LayerResetManager = session["reset_manager"]

        # 2. ドメインスキーマと、それに基づくコンポーネントをロード
        domain_schema = self.domain_manager.get_schema(domain_id)
        if not domain_schema:
            return {"status": "error", "message": f"ドメイン '{domain_id}' が見つかりません。"}
        
        spatial_encoder = SpatialEncodingEngine(domain_schema, self.ontology)
        
        # 3. パイプラインの実行
        try:
            # L5: ターン開始時にリセット
            reset_manager.reset_layer24_for_new_turn()
            
            # L5: 前のターンまでのコンテキストを取得
            session_context = external_state.get_context_for_next_turn()
            
            # L1: 質問から座標を抽出
            coords_info = spatial_encoder.extract_coordinates_from_question(question)
            db_coordinates = [info['coordinate'] for info in coords_info]
            
            # DBからコンテキストを取得
            db_context = {}
            if db_coordinates:
                 tile = await self.db_interface.fetch_async(db_coordinates[0])
                 if tile:
                     db_context = {db_coordinates[0]: tile}

            # L4: JudgeFlowをセットアップ
            # Note: α-LobeはRunnerEngineなどを内包する概念だが、ここでは直接llm_clientを渡す
            beta_lobe = BetaLobeAdvanced(self.db_interface, self.ontology)
            judge_flow = JudgeCorrectionFlow(AlpheLobe(None, None), beta_lobe)
            # JudgeFlowのalpha_lobeを実際のLLMクライアントに差し替え
            judge_flow.alpha_lobe.generate_response = self.llm_client.generate_response
            
            # JudgeFlowを実行して、生成・検証・修正/再生成を行う
            final_result = await judge_flow.process_and_correct(
                question, db_context, session_context
            )
            
            # L2 & L5: ターン結果を記録
            if final_result.get("status") in ["approved", "corrected"]:
                response_text = final_result["response"]
                episode_palace.add_turn(question, response_text, {'referenced_coords': db_coordinates})
                external_state.add_turn_summary(len(episode_palace.rooms), question, response_text, db_coordinates)

            return final_result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

# --- 使用例 ---
async def main():
    # --- 前提条件 ---
    # 1. `create_tile_from_topic.py` を実行して、`sample.iath` を作成しておく
    # 2. バックグラウンドでOllama等のLLMサーバーが起動している
    
    # 1. DeepSeekクライアントの設定
    # ご自身のLLM環境に合わせてURLとモデル名を修正してください
    config = DeepSeekConfig(
        api_url="http://localhost:11434",
        model_name="phi4-finetuned:f16",
    )
    
    # 2. 推論エンジンを初期化
    try:
        engine = InferenceEngine(
            deepseek_config=config,
            db_path="心筋梗塞の急性期診断アルゴリズム.iath" # 事前に生成したファイル名
        )
    except Exception as e:
        print(f"エンジンの初期化に失敗しました: {e}")
        return

    # 3. 複数ターンの会話をシミュレート
    session_id = "user123_session_xyz"
    
    # ターン1
    question1 = "心筋梗塞の主な原因は何ですか？"
    response1 = await engine.process_question(question1, session_id, "medical")
    print("\n--- Turn 1 Final Output ---")
    print(json.dumps(response1, indent=2, ensure_ascii=False))

    # ターン2
    question2 = "その治療法について教えてください"
    response2 = await engine.process_question(question2, session_id, "medical")
    print("\n--- Turn 2 Final Output ---")
    print(json.dumps(response2, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    # このスクリプトを実行する前に、
    # .venv/bin/python3 create_tile_from_topic.py を実行して、
    # 「心筋梗塞の急性期診断アルゴリズム.iath」というファイルを作成しておく必要があります。
    asyncio.run(main())
