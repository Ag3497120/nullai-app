from datetime import datetime
from collections import Counter

class EpisodePalace:
    """セッション固有のエピソード宮殿を管理"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.rooms = []
        self.spatial_coordinates = []
        self.reasoning_paths = []

    def _calculate_room_position(self, turn_number: int) -> tuple:
        """ターン数から宮殿内の位置を計算"""
        x = min(100, (turn_number - 1) * 25)
        y = 50 if turn_number > 1 else 0
        z = 0
        return (x, y, z)

    def add_turn(self, user_input: str, llm_response: str, metadata: dict):
        """ターンを宮殿に追加"""
        turn_number = len(self.rooms) + 1
        room_coordinate = self._calculate_room_position(turn_number)
        
        turn_record = {
            "turn_number": turn_number,
            "room_coordinate": room_coordinate,
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "llm_response": llm_response,
            "referenced_db_coordinates": metadata.get("referenced_coords", []),
            "referenced_web_results": metadata.get("web_results", []),
            "reasoning_path": metadata.get("reasoning_path", []),
            "confidence_scores": metadata.get("confidence_scores", [])
        }
        
        self.rooms.append(turn_record)
        self.spatial_coordinates.append(room_coordinate)
        self.reasoning_paths.append(metadata.get("reasoning_path", []))
        
        return room_coordinate

    def _aggregate_referenced_coords(self, turns: list) -> list:
        """ターンから参照座標を集約"""
        all_coords = [tuple(c) for turn in turns for c in turn["referenced_db_coordinates"]]
        coord_counts = Counter(all_coords)
        sorted_coords = sorted(coord_counts.items(), key=lambda x: x[1], reverse=True)
        return [coord for coord, count in sorted_coords[:5]]

    def _extract_key_concepts(self, turns: list) -> list:
        """ターンから主要概念を抽出"""
        concepts = set()
        for turn in turns:
            response_text = turn["llm_response"]
            words = response_text.split()
            for word in words:
                if len(word) > 2:
                    concepts.add(word)
        return list(concepts)[:10]

    def _construct_trajectory(self, turns: list) -> list:
        # このメソッドの具体的な実装は設計書にないため、プレースホルダーとします
        return [turn.get("reasoning_path", []) for turn in turns]


    def get_recent_context(self, num_turns: int = 5) -> dict:
        """最近のターンから文脈を取得"""
        recent_turns = self.rooms[-num_turns:]
        
        context = {
            "recent_turns": recent_turns,
            "referenced_coordinates": self._aggregate_referenced_coords(recent_turns),
            "key_concepts": self._extract_key_concepts(recent_turns),
            "reasoning_trajectory": self._construct_trajectory(recent_turns)
        }
        return context

class EpisodeDBReferenceTracker:
    """エピソード宮殿がグローバルDB空間を参照するのを追跡"""
    
    def __init__(self, episode_palace, db_interface):
        self.episode_palace = episode_palace
        self.db_interface = db_interface
        self.reference_map = {}

    def record_reference(self, turn_number: int, db_coordinates: list, confidence: float):
        """参照を記録"""
        if turn_number > len(self.episode_palace.rooms):
            return

        room_coord = self.episode_palace.rooms[turn_number - 1]["room_coordinate"]
        
        if room_coord not in self.reference_map:
            self.reference_map[room_coord] = []
        
        reference_record = {
            "timestamp": datetime.now().isoformat(),
            "db_coordinates": db_coordinates,
            "confidence": confidence,
        }
        self.reference_map[room_coord].append(reference_record)

    def build_trust_chain(self, turn_number: int) -> list:
        """参照チェーンから信頼度チェーンを構築"""
        if turn_number > len(self.episode_palace.rooms):
            return []

        room_coord = self.episode_palace.rooms[turn_number - 1]["room_coordinate"]
        
        if room_coord not in self.reference_map:
            return []
        
        references = self.reference_map[room_coord]
        trust_chain = []

        for ref in references:
            db_coords_list = ref["db_coordinates"]
            for db_coord in db_coords_list:
                db_certainty = self.db_interface.get_certainty(db_coord)
                trust_record = {
                    "db_coordinates": db_coord,
                    "reference_confidence": ref["confidence"],
                    "db_certainty": db_certainty,
                    "combined_trust": ref["confidence"] * db_certainty
                }
                trust_chain.append(trust_record)
        
        return trust_chain

if __name__ == '__main__':
    # --- モックDBインターフェース ---
    class MockDB:
        def get_certainty(self, db_coordinates):
            certainty_map = {(28, 35, 15): 0.95, (28, 55, 15): 0.85}
            rounded_coords = (int(db_coordinates[0]), int(db_coordinates[1]), int(db_coordinates[2]))
            return certainty_map.get(rounded_coords, 0.5)

    # --- 実行例 ---
    palace = EpisodePalace("session-001")
    tracker = EpisodeDBReferenceTracker(palace, MockDB())

    # ターン1
    palace.add_turn("心筋梗塞とは？", "心臓の筋肉に血流が...", {"referenced_coords": [(28, 55, 15)]})
    tracker.record_reference(turn_number=1, db_coordinates=[(28, 55, 15)], confidence=0.9)
    
    # ターン2
    palace.add_turn("診断方法は？", "心電図や血液検査で...", {"referenced_coords": [(28, 35, 15)]})
    tracker.record_reference(turn_number=2, db_coordinates=[(28, 35, 15)], confidence=0.95)

    print("\n--- Context for next turn (after 2 turns) ---")
    print(palace.get_recent_context())

    print("\n--- Trust chain for turn 2 ---")
    print(tracker.build_trust_chain(turn_number=2))
