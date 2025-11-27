from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime, UTC
import asyncio

# 依存コンポーネントをインポート
# DeepSeekR1Engineは実際の推論エンジンとして使用
from ilm_athens_engine.deepseek_integration.deepseek_runner import DeepSeekR1Engine, DeepSeekConfig

# --- ヘルパークラス ---

@dataclass
class LocalSapNode:
    """ローカルメモリに蓄積される個々の記憶（樹液）"""
    node_id: str = field(default_factory=lambda: f"sap_{datetime.now(UTC).timestamp()}")
    content: str = ""
    memory_type: str = "episodic"  # episodic, insight, critique
    source: str = ""
    importance: float = 0.5

class LocalMemoryBuffer:
    """会話中に蓄積される樹液（短期記憶）のバッファ"""
    def __init__(self, engine_name: str):
        self.sap: List[LocalSapNode] = []
        self.engine_name = engine_name

    def add(self, content: str, memory_type: str, source: str, importance: float = 0.5):
        node = LocalSapNode(content=content, memory_type=memory_type, source=source, importance=importance)
        self.sap.append(node)

    def get_conversation_log(self) -> List[Dict]:
        return [n.__dict__ for n in self.sap if n.source in ["user_input", "engine_output"]]

    def get_insights(self) -> List[str]:
        return [n.content for n in self.sap if n.memory_type == "insight"]

    def clear(self):
        self.sap = []

# --- メインクラス ---

class SymbioticTwinEngineSystem:
    """
    双子エンジン（連理の木）協働システム
    Engine A (Active) と Engine B (Passive) を管理する。
    """
    def __init__(self, config: Optional[DeepSeekConfig] = None):
        print("--- Symbiotic Twin-Engine System Initializing... ---")
        # 2つの独立したエンジンインスタンスを作成
        self.engine_a = DeepSeekR1Engine(config)
        self.engine_b = DeepSeekR1Engine(config)
        
        # それぞれの短期記憶バッファ
        self.memory_a = LocalMemoryBuffer("EngineA")
        self.memory_b = LocalMemoryBuffer("EngineB")

        # 役割を定義
        self.active_engine = self.engine_a
        self.passive_engine = self.engine_b
        self.active_memory = self.memory_a
        self.passive_memory = self.memory_b
        
        self.turn_count = 0
        self.l0_reset_threshold = 5  # 5ターンごとにL0リセットを発動
        print(f"  -> Engines A and B initialized. L0 Reset threshold set to {self.l0_reset_threshold} turns.")

    async def _passive_analysis(self, user_input: str) -> str:
        """裏エンジンが行う隠れた分析（プレースホルダー）"""
        analysis_prompt = f"以下のユーザー入力について、関連する医学的概念、潜在的なリスク、追加で検索すべきキーワードを3つ挙げてください。\n\n入力: '{user_input}'"
        result = await self.passive_engine.infer(analysis_prompt, domain_context={"domain_name": "medical"})
        # 実際にはより構造化されたデータを返す
        return result.get("response", "分析結果なし")

    def _merge_memories(self) -> str:
        """記憶の融合（L0リセット時に実行）"""
        print("\n--- Merging memories from both engines... ---")
        active_log = self.active_memory.get_conversation_log()
        passive_insights = self.passive_memory.get_insights()
        
        # 簡易的なマージ：会話ログと洞察をテキスト化
        merged_context = "【会話ログ】\n"
        for entry in active_log:
            merged_context += f"- {entry['source']}: {entry['content'][:50]}...\n"
        
        merged_context += "\n【裏エンジンの分析結果】\n"
        for insight in passive_insights:
            merged_context += f"- {insight[:80]}...\n"
            
        print("  -> Memory merge complete.")
        return merged_context

    async def l0_reset_and_swap(self):
        """L0リセットを実行し、エンジンの役割を交代する"""
        print("\n" + "="*20 + " L0 RESET & SWAP " + "="*20)
        
        # 1. 記憶の融合
        merged_context = self._merge_memories()
        
        # 2. メモリのクリア
        self.active_memory.clear()
        self.passive_memory.clear()
        
        # 3. 役割交代
        self.active_engine, self.passive_engine = self.passive_engine, self.active_engine
        self.active_memory, self.passive_memory = self.passive_memory, self.active_memory
        
        print(f"  -> Roles swapped. New Active Engine is '{self.active_memory.engine_name}'.")
        print("="*55 + "\n")
        
        # 4. 新しいActive Engineに融合したコンテキストを渡して要約させる（概念実証）
        summary_prompt = f"以下の会話ログと分析結果を要約し、次の会話の出発点となる重要なコンテキストを抽出してください。\n\n{merged_context}"
        await self.active_engine.infer(summary_prompt)

    async def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """ユーザー入力を処理し、分離稼働とL0リセットを実行する"""
        
        # --- Phase 1: 分離稼働 ---
        
        # Active Engine: ユーザーへの応答を生成
        active_task = self.active_engine.infer(user_input, domain_context={"domain_name": "medical"})
        
        # Passive Engine: 裏で隠れた分析を実行
        passive_task = self._passive_analysis(user_input)
        
        # 両方のタスクを並行して実行
        results = await asyncio.gather(active_task, passive_task)
        active_response, passive_insights = results
        
        # それぞれのメモリに結果を記録
        self.active_memory.add(user_input, "episodic", "user_input")
        self.active_memory.add(active_response.get("response", ""), "episodic", "engine_output")
        self.passive_memory.add(passive_insights, "insight", "hidden_analysis")
        
        self.turn_count += 1
        print(f"\n--- Turn {self.turn_count} processed. Active: {self.active_memory.engine_name} ---")

        # --- L0リセット判定 ---
        if self.turn_count % self.l0_reset_threshold == 0:
            await self.l0_reset_and_swap()
        
        return active_response

# --- 使用例 ---
async def main():
    config = DeepSeekConfig(api_url="http://localhost:11434", model_name="gemma:2b") # テスト用にgemmaを使用
    twin_engine_system = SymbioticTwinEngineSystem(config)

    # 接続確認
    if not await twin_engine_system.engine_a.validate_connection():
        print("\nテストを中止します。Ollamaが起動しているか確認してください。")
        return

    # 複数ターンの会話をシミュレート
    for i in range(1, 8):
        user_input = f"心筋梗塞に関する質問 {i}"
        response = await twin_engine_system.process_user_input(user_input)
        print(f"  -> User: '{user_input}'")
        print(f"  -> Response: '{response.get('response', '')[:50].strip()}...'")

if __name__ == "__main__":
    asyncio.run(main())
