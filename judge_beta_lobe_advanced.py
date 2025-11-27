from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


# ドメイン別の危険な主張を検出するためのパターン
DOMAIN_DANGEROUS_PATTERNS = {
    "medical": [
        (r"(必ず|絶対に|確実に).*(治る|完治|治癒)", "absolute_cure_claim", "critical"),
        (r"(副作用|リスク).*(ない|ありません|存在しない)", "no_side_effects_claim", "critical"),
        (r"(すべての|全ての|あらゆる)患者に(有効|効果的)", "universal_effectiveness", "high"),
        (r"(西洋|現代)医学.*(不要|いらない|無意味)", "anti_medicine_claim", "critical"),
        (r"(自己判断|自分で).*治療", "self_treatment_encouragement", "moderate"),
        (r"医師.*(相談|受診).*(不要|いらない|必要ない)", "avoid_doctor_claim", "critical"),
    ],
    "legal": [
        (r"(必ず|絶対に|確実に).*(勝訴|勝てる|認められる)", "absolute_outcome_claim", "critical"),
        (r"弁護士.*(不要|いらない|必要ない)", "avoid_lawyer_claim", "critical"),
        (r"(すべての|全ての)ケースで", "universal_applicability", "high"),
        (r"(違法|犯罪).*(ではない|にならない).*絶対", "absolute_legality_claim", "critical"),
        (r"(時効|期限).*(気にしなくて|無視して)", "ignore_deadlines", "critical"),
        (r"(判例|法律).*無視", "ignore_precedent", "high"),
    ],
    "economics": [
        (r"(必ず|絶対に|確実に).*(儲かる|利益|リターン)", "guaranteed_profit_claim", "critical"),
        (r"リスク.*(ない|ゼロ|存在しない)", "no_risk_claim", "critical"),
        (r"(すべての|全ての)投資家に", "universal_advice", "high"),
        (r"(買う|売る)べき.*絶対", "absolute_trading_advice", "critical"),
        (r"市場.*予測.*確実", "certain_market_prediction", "high"),
        (r"(暴落|暴騰).*(ない|しない).*絶対", "absolute_market_stability", "high"),
    ]
}

# 後方互換性のため
DANGEROUS_CLAIM_PATTERNS = DOMAIN_DANGEROUS_PATTERNS["medical"]

# 医学的数値の妥当性範囲
MEDICAL_VALUE_RANGES = {
    "血圧": {"systolic": (60, 250), "diastolic": (40, 150)},
    "体温": {"min": 35.0, "max": 42.0},
    "心拍数": {"min": 30, "max": 220},
    "SpO2": {"min": 70, "max": 100},
    "血糖値": {"min": 20, "max": 600},
}

# 法学ドメインの検証パターン
LEGAL_VALIDATION_PATTERNS = {
    "disclaimer_required": r"(免責|情報提供|法的助言ではありません)",
    "statute_citation": r"(第\d+条|条文|法律)",
    "precedent_citation": r"(判例|最判|最決|高判)",
}

# 経済学ドメインの検証パターン
ECONOMICS_VALIDATION_PATTERNS = {
    "data_source_required": r"(統計|データ|出典|IMF|日銀|内閣府)",
    "uncertainty_disclosure": r"(予測|推計|不確実|シナリオ)",
    "disclaimer_required": r"(投資助言ではありません|自己責任)",
}


class BetaLobeAdvanced:
    """
    検証院（β-Lobe）の高度な機能。
    論理的妥当性、医学的文脈の検証、ハルシネーション検出を実装。
    """

    def __init__(self, db_interface, medical_ontology):
        self.db = db_interface
        self.ontology = medical_ontology

    # --- 基本的なAnchor事実チェック ---
    def _is_mentioned(self, fact: str, response: str) -> bool:
        """事実がレスポンスに言及されているか確認"""
        fact_keywords = [word for word in fact.split() if len(word) > 1]
        if not fact_keywords:
            return False
        mentioned_count = sum(1 for kw in fact_keywords if kw in response)
        return (mentioned_count / len(fact_keywords)) > 0.5

    def _detect_numerical_contradiction(self, fact: str, response: str) -> bool:
        """数値の矛盾を検出"""
        fact_numbers = re.findall(r'[-+]?\d*\.\d+|\d+', fact)
        if not fact_numbers:
            return False
        fact_value = float(fact_numbers[0])
        response_numbers = re.findall(r'[-+]?\d*\.\d+|\d+', response)
        if not response_numbers:
            return True
        # 10%以上の乖離で矛盾とみなす
        is_far = all(abs(float(res_val) - fact_value) / max(fact_value, 0.001) > 0.1 for res_val in response_numbers)
        return is_far

    async def check_anchor_facts(self, response_text: str, db_context: dict) -> dict:
        """DBの知識タイルと回答の整合性を検証"""
        contradictions = []

        for coord, tile in db_context.items():
            if not tile:
                continue

            # タイルから主要な事実を抽出
            anchor_facts = self._extract_anchor_facts(tile)

            for fact in anchor_facts:
                # 事実が言及されているか確認
                if self._is_mentioned(fact["statement"], response_text):
                    # 数値の矛盾をチェック
                    if fact.get("has_numbers") and self._detect_numerical_contradiction(fact["statement"], response_text):
                        contradictions.append({
                            "type": "numerical_contradiction",
                            "fact": fact["statement"],
                            "source": coord,
                            "severity": "high"
                        })

        return {
            "contradictions": contradictions,
            "contradiction_count": len(contradictions),
            "passed": len(contradictions) == 0
        }

    def _extract_anchor_facts(self, tile: dict) -> list:
        """タイルから検証用の事実を抽出"""
        facts = []
        content = tile.get("content", "") or tile.get("data", "")

        if isinstance(content, str):
            # 箇条書きや重要な記述を抽出
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if len(line) > 10 and any(marker in line for marker in ["は", "である", "です", "："]):
                    has_numbers = bool(re.search(r'\d+', line))
                    facts.append({
                        "statement": line[:200],  # 最大200文字
                        "has_numbers": has_numbers
                    })
                    if len(facts) >= 5:  # 最大5つの事実
                        break

        return facts

    # --- 危険な主張の検出（ドメイン対応） ---
    def _detect_dangerous_claims(self, response: str, domain: str = "medical") -> list:
        """ドメイン別の危険な主張を検出"""
        issues = []
        patterns = DOMAIN_DANGEROUS_PATTERNS.get(domain, DOMAIN_DANGEROUS_PATTERNS["medical"])

        for pattern, claim_type, severity in patterns:
            match = re.search(pattern, response)
            if match:
                issues.append({
                    "type": "dangerous_claim",
                    "domain": domain,
                    "claim_type": claim_type,
                    "matched_text": match.group(0),
                    "severity": severity,
                    "message": f"危険な主張を検出 [{domain}]: {claim_type}"
                })
        return issues

    # --- ドメイン固有の検証 ---
    def _validate_legal_response(self, response: str) -> list:
        """法学ドメイン固有の検証"""
        issues = []

        # 免責事項の確認
        if not re.search(LEGAL_VALIDATION_PATTERNS["disclaimer_required"], response):
            issues.append({
                "type": "missing_disclaimer",
                "domain": "legal",
                "severity": "high",
                "message": "法的免責事項が欠落しています"
            })

        # 条文引用の確認（法律質問の場合）
        # ここでは警告レベルにとどめる
        if not re.search(LEGAL_VALIDATION_PATTERNS["statute_citation"], response):
            issues.append({
                "type": "missing_citation",
                "domain": "legal",
                "severity": "moderate",
                "message": "条文への参照がありません"
            })

        return issues

    def _validate_economics_response(self, response: str) -> list:
        """経済学ドメイン固有の検証"""
        issues = []

        # データ出典の確認
        if not re.search(ECONOMICS_VALIDATION_PATTERNS["data_source_required"], response):
            issues.append({
                "type": "missing_data_source",
                "domain": "economics",
                "severity": "moderate",
                "message": "データ出典への参照がありません"
            })

        # 予測の場合の不確実性開示
        if "予測" in response or "見通し" in response:
            if not re.search(ECONOMICS_VALIDATION_PATTERNS["uncertainty_disclosure"], response):
                issues.append({
                    "type": "missing_uncertainty_disclosure",
                    "domain": "economics",
                    "severity": "high",
                    "message": "予測の不確実性が明示されていません"
                })

        return issues

    # --- 医学的数値の妥当性検証 ---
    def _validate_medical_values(self, response: str) -> list:
        """医学的数値が妥当な範囲内か検証"""
        issues = []

        # 血圧の検出と検証
        bp_pattern = r'(\d{2,3})/(\d{2,3})\s*(?:mmHg)?'
        bp_matches = re.findall(bp_pattern, response)
        for systolic, diastolic in bp_matches:
            s, d = int(systolic), int(diastolic)
            ranges = MEDICAL_VALUE_RANGES["血圧"]
            if not (ranges["systolic"][0] <= s <= ranges["systolic"][1]):
                issues.append({
                    "type": "invalid_medical_value",
                    "value_type": "血圧（収縮期）",
                    "value": s,
                    "expected_range": ranges["systolic"],
                    "severity": "high"
                })
            if not (ranges["diastolic"][0] <= d <= ranges["diastolic"][1]):
                issues.append({
                    "type": "invalid_medical_value",
                    "value_type": "血圧（拡張期）",
                    "value": d,
                    "expected_range": ranges["diastolic"],
                    "severity": "high"
                })

        # 体温の検出と検証
        temp_pattern = r'(\d{2}(?:\.\d)?)\s*(?:°C|度|℃)'
        temp_matches = re.findall(temp_pattern, response)
        for temp in temp_matches:
            t = float(temp)
            ranges = MEDICAL_VALUE_RANGES["体温"]
            if not (ranges["min"] <= t <= ranges["max"]):
                issues.append({
                    "type": "invalid_medical_value",
                    "value_type": "体温",
                    "value": t,
                    "expected_range": (ranges["min"], ranges["max"]),
                    "severity": "high"
                })

        return issues

    # --- 高度な検証機能 ---

    def _detect_false_dichotomy(self, response: str) -> list:
        """偽の二者択一を検出"""
        errors = []
        dichotomy_pattern = r"(AかBのいずれかしかない|AかBしかない)" # 簡易パターン
        if re.search(dichotomy_pattern, response.replace(" ","")): # 空白除去
             errors.append({"type": "false_dichotomy", "statement": response, "severity": "moderate"})
        return errors
    
    async def _check_logical_consistency(self, question, alpha_response) -> dict:
        """推論の論理的妥当性を検証"""
        errors = []
        response_text = alpha_response["main_response"]
        
        # 偽の二者択一を検出
        dichotomy_errors = self._detect_false_dichotomy(response_text)
        errors.extend(dichotomy_errors)
        
        # NOTE: 環状論理、論理的飛躍、根拠なき仮定の検出は高度なNLPが必要なため、
        # ここではプレースホルダーとして成功を返す。
        
        return {"logical_errors": errors, "error_count": len(errors), "passed": len(errors) == 0}

    async def _verify_treatment_validity(self, response_text, db_context) -> dict:
        """治療法の妥当性を検証"""
        issues = []
        # 簡易的な治療法抽出
        mentioned_treatments_regex = re.findall(r"(\S+)が良い|(\w+)が有効な治療法|(\w+)を投与", response_text)
        # 抽出結果はタプルのリストになるため、フラット化する
        extracted_phrases = [item for tpl in mentioned_treatments_regex for item in tpl if item]
        
        # 後処理で助詞などを除去し、治療法名を正確に切り出す
        processed_treatments = []
        for phrase in extracted_phrases:
            if "には" in phrase:
                processed_treatments.append(phrase.split("には")[-1])
            elif "は" in phrase:
                processed_treatments.append(phrase.split("は")[-1])
            else:
                processed_treatments.append(phrase)

        for treatment in processed_treatments:
            if not treatment: continue
            treatment_info = await self.db.search_treatment(treatment)
            if not treatment_info:
                issues.append({"type": "unknown_treatment", "treatment": treatment, "severity": "moderate", "message": f"「{treatment}」は未知の治療法"})
            elif not treatment_info.get("is_validated"):
                issues.append({"type": "unvalidated_treatment", "treatment": treatment, "severity": "critical", "message": f"「{treatment}」は未検証の治療法"})
        
        return {"valid": len(issues) == 0, "issues": issues}

    async def _check_medical_context(self, response_text: str, db_context: dict) -> dict:
        """医学的コンテキストが適切か確認"""
        issues = []
        treatment_check = await self._verify_treatment_validity(response_text, db_context)
        if not treatment_check["valid"]:
            issues.extend(treatment_check["issues"])
        
        # NOTE: 診断基準、数値、禁忌の検証はプレースホルダー
        return {"issues": issues, "issue_count": len(issues), "passed": len(issues) == 0}

    async def validate_response(self, question: str, alpha_response: dict, db_context: dict, web_results=None, session_context=None, domain: str = "medical") -> dict:
        """回答を多角的に検証する（基本＋高度、ドメイン対応）"""

        response_text = alpha_response.get("main_response", "")
        # alpha_responseにドメイン情報があればそちらを優先
        domain = alpha_response.get("domain", domain)

        logger.info(f"BetaLobe検証開始: domain={domain}")

        # 1. 基本的なAnchor事実チェック
        anchor_check = await self.check_anchor_facts(response_text, db_context)

        # 2. 高度な論理チェック
        logic_check = await self._check_logical_consistency(question, alpha_response)

        # 3. ドメイン別の文脈チェック
        if domain == "medical":
            context_check = await self._check_medical_context(response_text, db_context)
        elif domain == "legal":
            context_issues = self._validate_legal_response(response_text)
            context_check = {"issues": context_issues, "issue_count": len(context_issues), "passed": len(context_issues) == 0}
        elif domain == "economics":
            context_issues = self._validate_economics_response(response_text)
            context_check = {"issues": context_issues, "issue_count": len(context_issues), "passed": len(context_issues) == 0}
        else:
            context_check = {"issues": [], "issue_count": 0, "passed": True}

        # 4. ドメイン別の危険な主張の検出
        dangerous_claims = self._detect_dangerous_claims(response_text, domain)
        safety_check = {
            "issues": dangerous_claims,
            "issue_count": len(dangerous_claims),
            "passed": len(dangerous_claims) == 0
        }

        # 5. ドメイン別の数値妥当性検証
        if domain == "medical":
            value_issues = self._validate_medical_values(response_text)
        else:
            value_issues = []  # 法学・経済学は数値検証なし（将来拡張可能）
        value_check = {
            "issues": value_issues,
            "issue_count": len(value_issues),
            "passed": len(value_issues) == 0
        }

        # 全ての問題を集約
        all_issues = (
            anchor_check["contradictions"] +
            logic_check["logical_errors"] +
            context_check["issues"] +
            safety_check["issues"] +
            value_check["issues"]
        )

        # 重大度を判定
        severity = "none"
        if any(i.get("severity") == "critical" for i in all_issues):
            severity = "critical"
        elif any(i.get("severity") == "high" for i in all_issues):
            severity = "high"
        elif any(i.get("severity") == "moderate" for i in all_issues):
            severity = "moderate"

        # ハルシネーションリスクスコアを計算
        hallucination_risk = self._calculate_hallucination_risk(
            alpha_response, anchor_check, logic_check, context_check, safety_check
        )

        validation_result = {
            "timestamp": datetime.now().isoformat(),
            "response_text": response_text[:500],  # 長い回答は切り詰め
            "checks": {
                "anchor_facts": anchor_check,
                "logic": logic_check,
                "context": context_check,
                "safety": safety_check,
                "medical_values": value_check
            },
            "all_issues": all_issues,
            "issue_count": len(all_issues),
            "has_contradictions": len(all_issues) > 0,
            "severity": severity,
            "hallucination_risk": hallucination_risk,
            "recommendations": self._generate_recommendations(all_issues)
        }

        logger.info(f"検証完了: {len(all_issues)}件の問題, 重大度={severity}, ハルシネーションリスク={hallucination_risk['score']:.2f}")
        return validation_result

    def _calculate_hallucination_risk(self, alpha_response, anchor_check, logic_check, context_check, safety_check) -> dict:
        """ハルシネーションリスクスコアを計算"""
        score = 0.0

        # Anchor事実との矛盾（最大0.4）
        if not anchor_check["passed"]:
            score += 0.4

        # 論理エラー（最大0.2）
        if not logic_check["passed"]:
            score += 0.2

        # 医学的文脈の問題（最大0.15）
        if not context_check["passed"]:
            score += 0.15

        # 危険な主張（最大0.25）
        if not safety_check["passed"]:
            score += 0.25

        # 信頼度が低い場合のペナルティ
        confidence = alpha_response.get("confidence", 0.5)
        if confidence < 0.4:
            score += 0.1

        final_score = min(1.0, score)

        # リスクレベルの分類
        if final_score < 0.1:
            level = "very_low"
        elif final_score < 0.25:
            level = "low"
        elif final_score < 0.5:
            level = "moderate"
        elif final_score < 0.75:
            level = "high"
        else:
            level = "critical"

        return {
            "score": final_score,
            "level": level,
            "action_required": final_score >= 0.25
        }

    def _generate_recommendations(self, all_issues: list) -> list:
        """問題に基づいて修正推奨を生成"""
        recommendations = []

        for issue in all_issues[:3]:  # 最大3件
            issue_type = issue.get("type", "unknown")

            if issue_type == "dangerous_claim":
                recommendations.append({
                    "type": "remove_dangerous_claim",
                    "message": f"危険な主張を削除または修正: {issue.get('claim_type')}",
                    "priority": "high"
                })
            elif issue_type == "numerical_contradiction":
                recommendations.append({
                    "type": "verify_numbers",
                    "message": f"数値を確認: {issue.get('fact', '')[:50]}",
                    "priority": "medium"
                })
            elif issue_type == "invalid_medical_value":
                recommendations.append({
                    "type": "correct_value",
                    "message": f"{issue.get('value_type')}の値が範囲外: {issue.get('value')}",
                    "priority": "high"
                })

        return recommendations
