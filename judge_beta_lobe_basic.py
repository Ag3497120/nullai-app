from datetime import datetime
import re

class BetaLobeBasic:
    """
    検証院（β-Lobe）の基本機能：Anchor事実との矛盾検出を実装。
    """
    def __init__(self, db_interface, medical_ontology):
        self.db = db_interface
        self.ontology = medical_ontology
        self.validation_history = []

    def _is_mentioned(self, fact: str, response: str) -> bool:
        """事実に関連するキーワードが回答に含まれているか簡易的に判定"""
        # 事実から主要な名詞を抽出（簡易的な実装）
        fact_keywords = [word for word in fact.split() if len(word) > 1]
        if not fact_keywords: return False
        
        mentioned_count = sum(1 for kw in fact_keywords if kw in response)
        return (mentioned_count / len(fact_keywords)) > 0.5

    def _detect_numerical_contradiction(self, fact: str, response: str) -> bool:
        """数値の矛盾を検出"""
        fact_numbers = re.findall(r'[-+]?\d*\.\d+|\d+', fact)
        if not fact_numbers: return False
        fact_value = float(fact_numbers[0])

        response_numbers = re.findall(r'[-+]?\d*\.\d+|\d+', response)
        if not response_numbers: return True # 事実には数値があるが、回答にはない

        # 回答内の最も近い数値が、事実の数値と10%以上乖離していれば矛盾
        is_far = all(abs(float(res_val) - fact_value) / fact_value > 0.1 for res_val in response_numbers)
        return is_far

    def _detect_contradiction(self, fact: str, response: str, fact_type: str) -> bool:
        """事実のタイプに応じて矛盾検出ロジックを振り分け"""
        if fact_type == "numerical":
            return self._detect_numerical_contradiction(fact, response)
        # 他のfact_type（categorical, causal）の実装はWeek 10
        else:
            # デフォルト：否定語の存在で簡易的に判定
            negations = ["ない", "ではなく", "ではない", "誤り", "間違い"]
            if any(neg in response for neg in negations) and self._is_mentioned(fact, response):
                 return True
        return False
    
    def _extract_relevant_excerpt(self, fact: str, response: str) -> str:
        """事実に関連する回答の抜粋を抽出"""
        keywords = [word for word in fact.split() if len(word) > 1][:3]
        sentences = response.split("。")
        for sentence in sentences:
            if any(kw in sentence for kw in keywords):
                return sentence.strip() + "。"
        return response[:100] + "..."

    async def check_anchor_facts(self, response_text: str, db_context: dict) -> dict:
        """Anchor事実との矛盾を検出する"""
        contradictions = []
        
        for coord, tile in db_context.items():
            anchor_facts = tile.get("anchor_facts", [])
            for fact in anchor_facts:
                fact_text = fact.get("text", "")
                fact_type = fact.get("type", "causal")
                
                if not self._is_mentioned(fact_text, response_text):
                    continue

                if self._detect_contradiction(fact_text, response_text, fact_type):
                    contradictions.append({
                        "type": "anchor_fact_contradiction",
                        "coordinate": coord,
                        "fact": fact_text,
                        "fact_type": fact_type,
                        "response_excerpt": self._extract_relevant_excerpt(fact_text, response_text),
                        "severity": "critical",
                    })
        
        return {
            "contradictions": contradictions,
            "contradiction_count": len(contradictions),
            "passed": len(contradictions) == 0
        }
    
    async def validate_response_basic(self, alpha_response: dict, db_context: dict) -> dict:
        """
        α-Lobeの回答を検証する（Week 9の基本機能版）。
        Anchor事実チェックのみを行う。
        """
        response_text = alpha_response.get("main_response", "")
        
        # ステップ1: Anchor事実との矛盾検出
        anchor_check_result = await self.check_anchor_facts(response_text, db_context)
        
        # ステップ2: 検証結果を構造化
        validation_result = {
            "timestamp": datetime.now().isoformat(),
            "response_text": response_text,
            "checks": {"anchor_facts": anchor_check_result},
            "has_contradictions": anchor_check_result["contradiction_count"] > 0,
            "severity": "critical" if anchor_check_result["contradiction_count"] > 0 else "none",
        }
        
        self.validation_history.append(validation_result)
        return validation_result

# --- 使用例 ---
async def main():
    class MockDB:
        pass # この例ではdb_contextを直接渡すため、DBインターフェースは不要
    
    beta_lobe = BetaLobeBasic(MockDB(), None)
    
    # --- ケース1: 矛盾あり ---
    print("--- Case 1: Contradiction Test ---")
    alpha_res_1 = {"main_response": "心筋梗塞は脳の血流が悪くなることで発生します。"}
    db_ctx_1 = {
        (28, 55, 15): {
            "anchor_facts": [{"text": "心筋梗塞は心臓の冠動脈が詰まることで起こる", "type": "causal"}]
        }
    }
    validation_1 = await beta_lobe.validate_response_basic(alpha_res_1, db_ctx_1)
    import json
    print(json.dumps(validation_1, indent=2, ensure_ascii=False))

    # --- ケース2: 矛盾なし ---
    print("\n--- Case 2: No Contradiction Test ---")
    alpha_res_2 = {"main_response": "心筋梗塞の死亡率は約5%です。"}
    db_ctx_2 = {
        (28, 85, 15): {
            "anchor_facts": [{"text": "心筋梗塞の急性期死亡率は約5-10%", "type": "numerical"}]
        }
    }
    validation_2 = await beta_lobe.validate_response_basic(alpha_res_2, db_ctx_2)
    print(json.dumps(validation_2, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
