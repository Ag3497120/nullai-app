from datetime import datetime
import numpy as np
import re

class WebSearchAutonomySystem:
    """
    Web検索の必要性を4層のハイブリッドモデルで自律的に判定します。
    """
    
    def __init__(self):
        self.decision_history = []

    def _check_level1_keywords(self, question: str) -> dict:
        """レベル1：事前判定（キーワードベース）"""
        triggers = {
            "temporal": ["2025年", "最新", "今年", "最近", "昨日", "今週", "現在", "今", "最新版", "新規", "新しい", "更新"],
            "current_events": ["ニュース", "報告", "速報", "発表", "公開", "リリース"],
            "regulatory": ["認可", "承認", "FDA", "EMA", "PMDA", "許可", "ガイドライン", "基準", "法的", "規制", "ルール"]
        }
        detected = [kw for category, kws in triggers.items() for kw in kws if kw in question]
        if detected:
            return {"should_search": True, "confidence": 0.95, "reason": f"L1: Trigger keyword(s) found: {', '.join(detected)}"}
        return {"should_search": False, "confidence": 0.0}

    def _check_level2_semantics(self, question: str) -> dict:
        """レベル2：セマンティック分析"""
        question_types = {
            "epidemiology": {"keywords": ["患者数", "発症率", "流行", "疫学"], "web_necessity": 0.9},
            "treatment": {"keywords": ["治療", "薬", "手術", "療法"], "web_necessity": 0.8},
            "prognosis": {"keywords": ["予後", "生存率", "予測"], "web_necessity": 0.7},
            "diagnosis": {"keywords": ["診断", "検査", "診断基準"], "web_necessity": 0.6},
            "mechanism": {"keywords": ["メカニズム", "機序", "なぜ", "仕組み"], "web_necessity": 0.4}
        }
        max_necessity = 0.0
        match = None
        for category, config in question_types.items():
            if any(kw in question for kw in config["keywords"]) and config["web_necessity"] > max_necessity:
                max_necessity = config["web_necessity"]
                match = category
        if max_necessity > 0.5:
            return {"should_search": True, "confidence": 0.70, "reason": f"L2: Question type is '{match}'"}
        return {"should_search": False, "confidence": 0.0}

    def _check_level3_inference_state(self, inference_state) -> dict:
        """レベル3：推論中の動的判定"""
        if not inference_state or not hasattr(inference_state, 'partial_response'):
            return {"should_search": False, "confidence": 0.0}
        
        partial_response = inference_state.partial_response
        uncertainty_indicators = ["不明である", "確定的ではない", "議論の余地がある", "～かもしれない", "可能性がある", "詳しくは", "正確には", "詳細については", "最新情報では"]
        
        for indicator in uncertainty_indicators:
            if indicator in partial_response:
                return {"should_search": True, "confidence": 0.9, "reason": f"L3: Uncertainty phrase found: '{indicator}'"}
        return {"should_search": False, "confidence": 0.0}

    def _check_level4_special_cases(self, question: str) -> dict:
        """レベル4：特殊ケース判定"""
        special_triggers = {
            "drug": r"(医薬品|薬|ドラッグ).*(名前|効果|副作用)",
            "legal": r"(法的|合法|違法|規制)",
            "geographic": r"(日本|アメリカ|EU).*(ガイドライン|基準)",
            "conference": r"(学会|カンファレンス).*(発表|報告)"
        }
        for trigger_type, pattern in special_triggers.items():
            if re.search(pattern, question):
                return {"should_search": True, "confidence": 0.75, "reason": f"L4: Special case matched: '{trigger_type}'"}
        return {"should_search": False, "confidence": 0.0}

    def _aggregate_decisions(self, decisions: dict) -> dict:
        """4レベルの判定を統合"""
        weights = {"level1": 0.4, "level2": 0.2, "level3": 0.3, "level4": 0.1}
        score = sum(decisions[level].get("confidence", 0) * weight for level, weight in weights.items() if decisions[level].get("should_search"))
        
        return {
            "should_search": score >= 0.3,
            "aggregate_score": score,
            "decision_details": decisions,
            "confidence": np.mean([d.get("confidence", 0) for d in decisions.values() if d.get("should_search")]) if any(d.get("should_search") for d in decisions.values()) else 0.0
        }

    def should_search(self, question: str, inference_state=None) -> dict:
        """Web検索が必要か総合的に判定します。"""
        decisions = {
            "level1": self._check_level1_keywords(question),
            "level2": self._check_level2_semantics(question),
            "level3": self._check_level3_inference_state(inference_state),
            "level4": self._check_level4_special_cases(question)
        }
        
        final_decision = self._aggregate_decisions(decisions)
        self.decision_history.append({"timestamp": datetime.now().isoformat(), "question": question, "decisions": decisions, "final": final_decision})
        return final_decision

if __name__ == '__main__':
    # 'numpy' が必要です: pip install numpy
    search_system = WebSearchAutonomySystem()

    # --- テストケース ---
    test_questions = [
        "心筋梗塞のメカニズムについて教えて",  # L2(0.4) -> score 0.08 -> No
        "2025年最新の心筋梗塞治療ガイドラインは？", # L1(0.95), L4(0.75) -> score 0.4*0.95 + 0.1*0.75 = 0.455 -> Yes
        "糖尿病の疫学について知りたい", # L2(0.9) -> score 0.2*0.9 = 0.18 -> No (but close)
        "その薬の法的な扱いはどうなっていますか？", # L4(0.75) -> score 0.1*0.75 = 0.075 -> No
    ]
    
    print("--- 事前判定テスト ---")
    for q in test_questions:
        decision = search_system.should_search(q)
        print(f"\n質問: '{q}'")
        print(f"  -> 検索判定: {'Yes' if decision['should_search'] else 'No'} (スコア: {decision['aggregate_score']:.3f})")
        for level, details in decision['decision_details'].items():
            if details['should_search']:
                print(f"     - {details['reason']}")

    print("\n--- 推論中動的判定テスト ---")
    class MockInferenceState:
        def __init__(self, text):
            self.partial_response = text
    
    inference_state = MockInferenceState("この症状の原因は明確ではなく、いくつかの可能性があると言われています。")
    dynamic_decision = search_system.should_search("原因は？", inference_state=inference_state)
    print(f"質問: '原因は？' (推論中: '{inference_state.partial_response}')")
    print(f"  -> 検索判定: {'Yes' if dynamic_decision['should_search'] else 'No'} (スコア: {dynamic_decision['aggregate_score']:.3f})")
    for level, details in dynamic_decision['decision_details'].items():
        if details['should_search']:
            print(f"     - {details['reason']}")
