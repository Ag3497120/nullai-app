from datetime import datetime

class JudgeCorrectionFlow:
    """
    β-Lobeの検証結果に基づき、回答を「承認」「自動修正」「再生成」の
    いずれのアクションに振り分け、実行を制御します。
    """

    def __init__(self, alpha_lobe, beta_lobe):
        self.alpha_lobe = alpha_lobe
        self.beta_lobe = beta_lobe

    def _summarize_and_decide_action(self, validation_result: dict) -> str:
        """検証結果の深刻度に基づき、次のアクションを決定する。"""
        severity = validation_result.get("severity", "none")
        
        if severity == "critical":
            return "regenerate"
        if severity == "moderate":
            # 中程度の問題が1つでもあれば再生成を試みる（より安全な方針）
            return "regenerate"
        
        # 軽微な問題や問題なしの場合は承認
        return "approve"

    def _construct_regeneration_feedback(self, validation_result: dict) -> str:
        """再生成を指示するためのフィードバック文を構築する。"""
        feedback_parts = []
        for check_name, check_result in validation_result.get("checks", {}).items():
            issues = check_result.get("contradictions", []) + check_result.get("logical_errors", []) + check_result.get("issues", [])
            for issue in issues[:2]: # 各カテゴリから最大2件
                issue_type = issue.get("type", "issue")
                detail = issue.get("fact", issue.get("message", "詳細不明"))
                feedback_parts.append(f"✗ {issue_type}: {detail}")
        return "\n".join(feedback_parts)

    async def _auto_correct_response(self, original_response: str, validation_result: dict) -> str:
        """軽微な問題を自動修正する。"""
        corrected_response = original_response
        recommendations = validation_result.get("recommendations", [])
        
        for rec in recommendations:
            if rec['type'] == 'fact_correction':
                if rec['current_statement'] in corrected_response:
                    corrected_response = corrected_response.replace(rec['current_statement'], rec['correct_statement'])
        return corrected_response

    async def process_and_correct(self, question: str, db_context: dict, session_context=None, web_results=None, max_regenerations: int = 1, domain_id: str = "medical"):
        """
        質問を処理し、生成、検証、修正/再生成の完全なフローを実行する。
        ドメイン対応版。
        """
        regeneration_count = 0
        print(f"  -> JudgeCorrectionFlow開始 (domain={domain_id})")

        # α-Lobeで初回回答生成（ドメイン対応）
        alpha_response = await self.alpha_lobe.generate_response(
            question, db_context, session_context, domain_id=domain_id
        )

        while regeneration_count <= max_regenerations:
            # β-Lobeで検証（ドメイン対応）
            validation = await self.beta_lobe.validate_response(
                question, alpha_response, db_context, web_results, session_context, domain=domain_id
            )

            # アクションを決定
            action = self._summarize_and_decide_action(validation)
            print(f"  -> 検証結果: severity={validation.get('severity')}, action={action}")

            if action == "approve":
                return {
                    "status": "approved",
                    "response": alpha_response["main_response"],
                    "structured": alpha_response.get("structured", {}),
                    "confidence": alpha_response.get("confidence", 0.0),
                    "validation": validation,
                    "domain": domain_id
                }

            if action == "auto_correct":
                corrected_text = await self._auto_correct_response(alpha_response["main_response"], validation)
                alpha_response["main_response"] = corrected_text
                second_validation = await self.beta_lobe.validate_response(
                    question, alpha_response, db_context, web_results, session_context, domain=domain_id
                )
                return {
                    "status": "corrected",
                    "response": corrected_text,
                    "original_validation": validation,
                    "final_validation": second_validation,
                    "domain": domain_id
                }

            if action == "regenerate":
                if regeneration_count < max_regenerations:
                    regeneration_count += 1
                    print(f"  -> 再生成試行 {regeneration_count}/{max_regenerations}")
                    feedback = self._construct_regeneration_feedback(validation)
                    regeneration_prompt = f"前回の回答に以下の問題がありました:\n{feedback}\n\n元の質問: {question}\n\nこれらの点を修正して、再度回答してください。"

                    # α-Lobeにフィードバックを与えて再生成（ドメイン対応）
                    alpha_response = await self.alpha_lobe.generate_response(
                        regeneration_prompt, db_context, session_context, domain_id=domain_id
                    )
                    continue
                else:
                    return {
                        "status": "unable_to_answer",
                        "reason": "再生成の上限に達しましたが、問題が解決しませんでした。",
                        "final_validation": validation,
                        "domain": domain_id
                    }

        return {"status": "error", "message": "予期せぬエラーが発生しました。", "domain": domain_id}
