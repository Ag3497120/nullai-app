# --- テスト用のモック（ダミー）クラス ---

class MockOntology:
    """オントロジーのモック"""
    def search(self, keyword):
        if "心筋梗塞" in keyword:
            return [{"name": "心筋梗塞", "default_coordinate": (28, 55, 15), "relevance_score": 0.9}]
        if "契約" in keyword:
             return [{"name": "契約", "default_coordinate": (25, 45, 20), "relevance_score": 0.9}]
        return []

class MockDBInterface:
    """DBインターフェースのモック"""
    def __init__(self, domain_id="medical"):
        self.domain_id = domain_id
        self.anchor_facts = {
            "medical": [{"text": "心筋梗塞は心臓の冠動脈が詰まることで起こる", "type": "causal"}],
            "legal": [{"text": "契約は申込みと承諾によって成立する", "type": "causal"}]
        }

    async def fetch_async(self, coord):
        if self.domain_id in self.anchor_facts:
            return {
                "content": f"【DB情報:{self.domain_id}】...",
                "certainty": 98,
                "anchor_facts": self.anchor_facts[self.domain_id]
            }
        return None
    async def search_treatment(self, name):
        if name == "アスピリン":
            return {"is_validated": True}
        if name == "謎のハーブ":
            return None # 未知の治療法
        return {"is_validated": False} # その他の検証されていない治療法
    async def search_diagnosis_criteria(self, name): return True

class MockLLMClient:
    """LLMクライアントのモック"""
    def __init__(self, responses=None):
        self._responses = responses or [{"text": "デフォルトの応答です。", "confidence": 0.9}]
        self._call_count = 0

    async def generate_response(self, prompt, db_context, session_context):
        response_data = self._responses[self._call_count % len(self._responses)]
        self._call_count += 1
        return {
            "is_complete": True,
            "main_response": response_data["text"], "thinking_process": "思考中...", 
            "key_points": [], "confidence": response_data["confidence"],
            "sources_cited": [], "uncertainties": []
        }

class MockRunner:
    """RunnerEngineのモック"""
    async def generate_response_streaming(self, q, db_coords, session_ctx):
        yield {
            "type": "final_structured_response",
            "is_complete": True,
            "main_response": "心筋梗塞は心臓の冠動脈が詰まることで発生します。",
            "thinking_process": "...", "key_points": [], "confidence": 0.9,
            "sources_cited": [], "uncertainties": []
        }
