# runner_engine.py

import asyncio
from hot_cache import LRUCache
from web_search_autonomy import WebSearchAutonomySystem

# NOTE: The mock objects previously in this file have been moved to `mock_objects.py`
# for centralized test management. The main `RunnerEngine` class below is the
# actual implementation.



class RunnerEngine:
    """推論実行エンジン（Layer 3）"""
    
    def __init__(self, llm_client, db_interface, web_search_system):
        self.llm = llm_client
        self.db = db_interface
        self.web_search_system = web_search_system
        self.hot_cache = LRUCache(max_size=20)

    async def _fetch_db_coordinates(self, db_coordinates: list) -> dict:
        """DB座標から知識を取得（ホットキャッシュ利用）"""
        results = {}
        for coord in db_coordinates[:5]:
            if coord in self.hot_cache:
                print(f"Cache: Hit for {coord}")
                results[coord] = self.hot_cache[coord]
                continue
            
            print(f"Cache: Miss for {coord}")
            tile = await self.db.fetch_async(coord)
            if tile:
                self.hot_cache[coord] = tile
                results[coord] = tile
        return results

    def _build_context(self, question: str, db_results: dict, session_context) -> str:
        """LLMプロンプト用のコンテキストを構築"""
        context_parts = []
        if session_context: # この例では未使用
            context_parts.append(f"セッション履歴: {session_context}")
        
        if db_results:
            for coord, tile in db_results.items():
                context_parts.append(f"【確実性{tile['certainty']}%】{tile['content']}")
        
        return "\n\n".join(context_parts)

    def _format_prompt(self, question: str, context: str) -> str:
        return f"情報: {context}\n\n質問: {question}\n\n指示: 提供された情報に基づき回答してください。"

    async def generate_response_streaming(self, question: str, db_coordinates: list, session_context=None):
        """ストリーミング形式での回答生成と動的なWeb検索判断"""
        web_decision = self.web_search_system.should_search(question)
        
        db_task = asyncio.create_task(self._fetch_db_coordinates(db_coordinates))
        web_task = asyncio.create_task(mock_web_search_api(question)) if web_decision["should_search"] else None

        try:
            db_results = await asyncio.wait_for(db_task, timeout=0.5)
        except asyncio.TimeoutError:
            db_results = {}
        
        context = self._build_context(question, db_results, session_context)
        prompt = self._format_prompt(question, context)
        
        partial_response = ""
        final_metadata = {}
        
        async for result in self.llm.generate_streaming(prompt):
            if result['type'] == 'response_token':
                token = result['token']
                partial_response += token
                yield result # トークンをそのまま中継
                
                # 推論中の動的Web検索判定
                if len(partial_response) > 5 and len(partial_response) % 20 == 0 and not web_task:
                    class MockInferenceState: partial_response = ""
                    inference_state = MockInferenceState()
                    inference_state.partial_response = partial_response
                    dynamic_decision = self.web_search_system.should_search(question, inference_state=inference_state)
                    if dynamic_decision["should_search"]:
                        print("\n*** Dynamic Web Search Triggered! ***\n")
                        web_task = asyncio.create_task(mock_web_search_api(question))
            
            elif result['type'] == 'completion':
                # Judge層で必要となる構造化されたメタデータを準備
                final_metadata = result['metadata']

        web_results_content = []
        if web_task:
            try:
                web_results_content = await asyncio.wait_for(web_task, timeout=2.0)
                yield {"type": "web_results", "results": web_results_content}
            except asyncio.TimeoutError:
                yield {"type": "web_results", "results": [], "error": "timeout"}

        # 最終的なメタデータを生成して終了
        final_metadata["referenced_coords"] = db_coordinates
        final_metadata["web_results"] = web_results_content
        yield {
            "type": "final_structured_response",
            "is_complete": True,
            "main_response": partial_response, 
            **final_metadata # thinking_process, key_pointsなどを展開
        }

# --- 実行例 ---
async def main():
    # モックコンポーネントの初期化
    llm = MockLLMClient()
    db = MockDBInterface()
    web_search = WebSearchAutonomySystem()
    
    runner = RunnerEngine(llm, db, web_search)
    
    question = "最新の心筋梗塞の診断について"
    # Layer 1で抽出された想定の座標
    db_coordinates = [(28, 35, 15)] 

    print(f"--- Running pipeline for question: '{question}' ---")
    final_response = {}
    async for event in runner.generate_response_streaming(question, db_coordinates):
        if event['type'] == 'response_token':
            print(event['token'], end='', flush=True)
        elif event['type'] == 'web_results':
            print(f"\n\n--- Web Results Received ---")
            print(event['results'])
        elif event['type'] == 'final_structured_response':
            final_response = event
    
    print("\n\n--- Final Structured Response (for Judge Layer) ---")
    import json
    print(json.dumps(final_response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
