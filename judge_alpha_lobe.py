from typing import Dict, Any, Optional
import logging

from ilm_athens_engine.deepseek_integration.deepseek_runner import DeepSeekR1Engine

logger = logging.getLogger(__name__)


# ドメイン別のプロンプトテンプレート
DOMAIN_PROMPT_TEMPLATES = {
    "medical": """【医療知識ベース参考情報】
{db_context}

【セッション履歴】
{session_summary}

【ユーザーの医療質問】
{question}

上記の参考情報を踏まえ、医学的に正確な回答を構造化フォーマットで提供してください。""",

    "legal": """【法律知識ベース参考情報】
{db_context}

【セッション履歴】
{session_summary}

【ユーザーの法律質問】
{question}

上記の参考情報を踏まえ、法的に正確な回答を構造化フォーマットで提供してください。
※これは法的助言ではなく、情報提供です。""",

    "economics": """【経済知識ベース参考情報】
{db_context}

【セッション履歴】
{session_summary}

【ユーザーの経済質問】
{question}

上記の参考情報を踏まえ、客観的な経済分析を構造化フォーマットで提供してください。""",

    "general": """【参考情報】
{db_context}

【ユーザーの質問】
{question}"""
}


class AlpheLobe:
    """
    生成院（α-Lobe）：DeepSeek R1エンジンをラップし、
    ドメイン対応の構造化されたプロンプトを渡して回答を生成する責務を持つ。
    """
    def __init__(self, engine: DeepSeekR1Engine):
        self.engine = engine

    def _format_db_context(self, db_context: Dict) -> str:
        """DB知識コンテキストを読みやすい形式にフォーマット"""
        if not db_context:
            return "（参考情報なし）"

        formatted_parts = []
        for coord, tile in db_context.items():
            if tile:
                content = tile.get("content", tile.get("data", ""))
                if isinstance(content, str) and content:
                    formatted_parts.append(f"[{coord}]\n{content[:500]}")

        return "\n\n".join(formatted_parts) if formatted_parts else "（参考情報なし）"

    def _format_session_context(self, session_context: Optional[Dict]) -> str:
        """セッション履歴を要約"""
        if not session_context:
            return "（新規セッション）"

        history = session_context.get("history", [])
        if not history:
            return "（履歴なし）"

        # 直近3件の会話を要約
        recent = history[-3:]
        summary_parts = []
        for item in recent:
            q = item.get("question", "")[:50]
            summary_parts.append(f"Q: {q}...")

        return "\n".join(summary_parts)

    async def generate_response(
        self,
        question: str,
        db_context: Dict,
        session_context: Optional[Dict] = None,
        domain_id: str = "medical"
    ) -> Dict[str, Any]:
        """
        ドメイン対応のプロンプトを構築し、DeepSeekエンジンで推論を実行する。
        """
        # 1. プロンプトテンプレートを選択
        template = DOMAIN_PROMPT_TEMPLATES.get(domain_id, DOMAIN_PROMPT_TEMPLATES["general"])

        # 2. コンテキストをフォーマット
        formatted_db = self._format_db_context(db_context)
        formatted_session = self._format_session_context(session_context)

        # 3. プロンプトを構築
        prompt = template.format(
            db_context=formatted_db,
            session_summary=formatted_session,
            question=question
        )

        logger.debug(f"AlpheLobe生成プロンプト (domain={domain_id}): {prompt[:200]}...")

        # 4. DeepSeekエンジンに推論を依頼
        result = await self.engine.infer(
            prompt,
            domain_context={"domain_name": domain_id}
        )

        # 5. 不確実性を抽出
        uncertainties = self._extract_uncertainties(result.get("response", ""))

        # 6. Judge層が期待する形式に合わせる
        return {
            "main_response": result.get("response", ""),
            "thinking_process": result.get("thinking", ""),
            "structured": result.get("structured", {}),
            "confidence": result.get("confidence", 0.0),
            "domain": domain_id,
            "sources_cited": self._extract_sources(result.get("response", "")),
            "uncertainties": uncertainties,
            "latency_ms": result.get("latency_ms", 0)
        }

    def _extract_uncertainties(self, response: str) -> list:
        """回答から不確実性の言及を抽出"""
        uncertainty_markers = [
            "可能性があります",
            "かもしれません",
            "不確実",
            "データが限定的",
            "議論があります",
            "見解が分かれ",
            "要検討",
            "専門家に相談"
        ]

        uncertainties = []
        for marker in uncertainty_markers:
            if marker in response:
                # マーカー周辺のコンテキストを抽出
                idx = response.find(marker)
                start = max(0, idx - 30)
                end = min(len(response), idx + len(marker) + 30)
                context = response[start:end]
                uncertainties.append({
                    "marker": marker,
                    "context": context.strip()
                })

        return uncertainties[:5]  # 最大5件

    def _extract_sources(self, response: str) -> list:
        """回答から参考文献の言及を抽出"""
        import re

        sources = []

        # 【参考】セクションを探す
        ref_match = re.search(r'【参考[^】]*】(.+?)(?=【|$)', response, re.DOTALL)
        if ref_match:
            ref_text = ref_match.group(1).strip()
            # 行ごとに分割して抽出
            for line in ref_text.split('\n'):
                line = line.strip()
                if line and len(line) > 5:
                    sources.append(line[:100])

        return sources[:5]  # 最大5件
