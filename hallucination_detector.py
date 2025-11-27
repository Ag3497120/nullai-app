import numpy as np

def _classify_risk_level(score: float) -> str:
    """リスクスコアをカテゴリに分類する。"""
    if score < 0.1: return "very_low"
    if score < 0.3: return "low"
    if score < 0.6: return "moderate"
    if score < 0.8: return "high"
    return "very_high"

def calculate_hallucination_risk_score(alpha_response: dict, validation_result: dict) -> dict:
    """
    α-Lobeの回答とβ-Lobeの検証結果から、ハルシネーションのリスクを計算します。

    Args:
        alpha_response (dict): α-Lobeからの構造化レスポンス。
        validation_result (dict): β-Lobeによる検証結果。

    Returns:
        dict: ハルシネーションリスクスコアと関連情報。
    """
    risk_score = 0.0
    
    # --- 検証結果に基づくリスク加算 ---
    anchor_passed = validation_result["checks"]["anchor_facts"]["passed"]
    logic_passed = validation_result["checks"].get("logic", {"passed": True})["passed"]
    context_passed = validation_result["checks"].get("context", {"passed": True})["passed"]
    
    # Anchor事実との矛盾は最大のリスク
    risk_score += (1 - (1 if anchor_passed else 0)) * 0.5
    # 論理矛盾も高いリスク
    risk_score += (1 - (1 if logic_passed else 0)) * 0.3
    # 医学的文脈の矛盾
    risk_score += (1 - (1 if context_passed else 0)) * 0.2
    
    # --- 回答内容に基づくリスク加算 ---
    
    # α-Lobe自体の自信度が低い場合
    alpha_confidence = alpha_response.get("confidence", 0.7)
    if alpha_confidence < 0.5:
        risk_score += 0.1
        
    # 不確実性に関する言及がない場合、過信しているリスク
    uncertainties = alpha_response.get("uncertainties", [])
    if not uncertainties:
        risk_score += 0.05
        
    # 引用元が全くない場合
    sources_cited = alpha_response.get("sources_cited", [])
    if not sources_cited:
        risk_score += 0.1

    final_risk_score = min(1.0, risk_score)
    
    return {
        "hallucination_risk_score": final_risk_score,
        "risk_level": _classify_risk_level(final_risk_score),
        "action_required": final_risk_score >= 0.3
    }

if __name__ == '__main__':
    # --- ダミーデータによる使用例 ---
    
    # ケース1: 安全な回答
    safe_alpha_res = {
        "confidence": 0.9, "uncertainties": [], "sources_cited": ["JCS 2023 Guideline"]
    }
    safe_validation_res = {
        "checks": {"anchor_facts": {"passed": True}, "logic": {"passed": True}, "context": {"passed": True}}
    }
    risk_1 = calculate_hallucination_risk_score(safe_alpha_res, safe_validation_res)
    print(f"--- Case 1: Safe Response ---")
    print(f"  Risk Score: {risk_1['hallucination_risk_score']:.2f} ({risk_1['risk_level']})")
    print(f"  Action Required: {risk_1['action_required']}")

    # ケース2: リスクのある回答 (事実誤認、引用なし)
    risky_alpha_res = {
        "confidence": 0.95, "uncertainties": [], "sources_cited": []
    }
    risky_validation_res = {
        "checks": {"anchor_facts": {"passed": False}, "logic": {"passed": True}, "context": {"passed": True}}
    }
    risk_2 = calculate_hallucination_risk_score(risky_alpha_res, risky_validation_res)
    print(f"\n--- Case 2: Risky Response ---")
    print(f"  Risk Score: {risk_2['hallucination_risk_score']:.2f} ({risk_2['risk_level']})")
    print(f"  Action Required: {risk_2['action_required']}")
    
    # ケース3: リスク中程度の回答 (論理エラー、自信度低い)
    medium_alpha_res = {
        "confidence": 0.4, "uncertainties": ["かもしれない"], "sources_cited": ["Some Journal"]
    }
    medium_validation_res = {
        "checks": {"anchor_facts": {"passed": True}, "logic": {"passed": False}, "context": {"passed": True}}
    }
    risk_3 = calculate_hallucination_risk_score(medium_alpha_res, medium_validation_res)
    print(f"\n--- Case 3: Medium Risk Response ---")
    print(f"  Risk Score: {risk_3['hallucination_risk_score']:.2f} ({risk_3['risk_level']})")
    print(f"  Action Required: {risk_3['action_required']}")
