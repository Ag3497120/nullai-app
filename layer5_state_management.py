from datetime import datetime
import json
from collections import Counter

class LayerResetManager:
    """
    Layer 24（LLMの最終層）のリセットを管理するクラス（概念的な実装）。
    """
    def __init__(self, llm_model_mock):
        self.llm = llm_model_mock
        self.reset_history = []

    def reset_layer24_for_new_turn(self):
        """
        新しいターンのためにLayer 24のKVキャッシュをクリアする操作をシミュレートします。
        """
        # 実際のLLMモデルの `clear_kv_cache` メソッドを呼び出す想定
        if hasattr(self.llm, 'clear_kv_cache') and callable(self.llm.clear_kv_cache):
            self.llm.clear_kv_cache(layer=24)
        
        print("Simulating: KV cache for Layer 24 has been reset.")
        self.reset_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "layer24_reset"
        })

class ExternalState:
    """
    セッションの外部状態を管理し、メモリ使用量を約10KBに制限します。
    """
    def __init__(self, max_size_bytes=10240):
        self.conversation_summary = []
        self.coordinate_trail = []
        self.max_size_bytes = max_size_bytes
        self.current_size = 0

    def _extract_keywords(self, text: str, max_words=3) -> list:
        """テキストから簡易的にキーワードを抽出する。"""
        words = re.findall(r'\b\w+\b', text.lower())
        # 簡単なストップワード除去
        stopwords = {"です", "ます", "が", "は", "を", "に", "と", "の"}
        words = [word for word in words if word not in stopwords]
        return [word for word, freq in Counter(words).most_common(max_words)]

    def _compress_turn(self, user_input: str, llm_response: str, db_coords: list) -> dict:
        """ターン情報を要約・圧縮する。"""
        return {
            "user_keywords": self._extract_keywords(user_input),
            "response_summary": llm_response[:100] + "..." if len(llm_response) > 100 else llm_response,
            "db_coords_used": db_coords[:3],
            "turn_length": len(llm_response)
        }

    def _compress_old_turns(self):
        """古いターンを圧縮（この実装では単純に削除）してサイズを管理する。"""
        if len(self.conversation_summary) > 20:
            print("State size limit exceeded, compressing old turns...")
            # 最も古いターンから削除していく
            while self.current_size > self.max_size_bytes and self.conversation_summary:
                removed_turn = self.conversation_summary.pop(0)
                self.current_size -= removed_turn.get("size_bytes", 0)

    def add_turn_summary(self, turn_num: int, user_input: str, llm_response: str, db_coords: list):
        """ターンの要約をExternalStateに追加する。"""
        summary = self._compress_turn(user_input, llm_response, db_coords)
        summary_size = len(json.dumps(summary, ensure_ascii=False).encode('utf-8'))
        
        turn_data = {
            "turn": turn_num,
            "summary": summary,
            "size_bytes": summary_size
        }
        
        self.conversation_summary.append(turn_data)
        self.current_size += summary_size
        if db_coords:
            self.coordinate_trail.extend(db_coords)

        self._compress_old_turns()

    def _extract_key_coordinates(self) -> list:
        """座標軌跡から主要な座標を抽出する。"""
        if not self.coordinate_trail:
            return []
        coord_freq = Counter([tuple(c) for c in self.coordinate_trail])
        return [list(coord) for coord, count in coord_freq.most_common(5)]

    def get_context_for_next_turn(self) -> dict:
        """次のターンのLLM推論用に文脈を構築する。"""
        recent_turns = self.conversation_summary[-3:] # 直近3ターン
        return {
            "recent_conversation_summary": [
                f"Turn {t['turn']}: User asked about '{', '.join(t['summary']['user_keywords'])}' -> Response: '{t['summary']['response_summary']}'"
                for t in recent_turns
            ],
            "key_coordinates": self._extract_key_coordinates(),
            "context_size_bytes": self.current_size
        }

# --- 使用例 ---
if __name__ == '__main__':
    import re

    # LayerResetManager のデモ
    class MockLLM:
        def clear_kv_cache(self, layer):
            pass #何もしない
    
    print("--- LayerResetManager Demo ---")
    reset_manager = LayerResetManager(MockLLM())
    reset_manager.reset_layer24_for_new_turn()

    # ExternalState のデモ
    print("\n--- ExternalState Demo ---")
    external_state = ExternalState(max_size_bytes=500) # デモ用にサイズを小さく設定

    # ターンを追加
    external_state.add_turn_summary(1, "心筋梗塞の原因は？", "冠動脈の閉塞が主な原因です...", [[28, 55, 15]])
    external_state.add_turn_summary(2, "治療法は？", "カテーテル治療やバイパス手術があります...", [[28, 35, 20]])
    external_state.add_turn_summary(3, "予防について", "食生活の改善、運動、禁煙が重要です...", [[28, 35, 85]])

    print(f"\nCurrent state size: {external_state.current_size} bytes")
    print("Context for next turn:", json.dumps(external_state.get_context_for_next_turn(), indent=2, ensure_ascii=False))

    # さらにターンを追加して圧縮（削除）をトリガー
    print("\nAdding more turns to trigger compression...")
    for i in range(4, 10):
        external_state.add_turn_summary(i, f"質問{i}", f"回答{i}...", [[i, i, i]])
    
    print(f"Final state size after compression: {external_state.current_size} bytes")
    print("Final context:", json.dumps(external_state.get_context_for_next_turn(), indent=2, ensure_ascii=False))
