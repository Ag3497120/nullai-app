"""
DeepSeek R1推論エンジンの統合
Ilm-Athensのためのカスタムラッパー

警告: このモジュールはOllamaベースの推論用であり、非推奨です。
新規実装では以下を使用してください：
- null_ai/model_router.py (HuggingFace Transformers)
- ilm_athens_engine/deepseek_integration/hf_deepseek_engine.py

OpenAI/Anthropic等の外部APIは利用規約上の理由からサポートされていません。
"""

import asyncio
import json
import warnings
from typing import Dict, Optional, AsyncGenerator, Tuple
from dataclasses import dataclass
import httpx
import logging
import requests

logger = logging.getLogger(__name__)

# 非推奨警告
warnings.warn(
    "deepseek_runner.pyは非推奨です。HuggingFace Transformersベースの"
    "hf_deepseek_engine.pyまたはnull_ai/model_router.pyの使用を推奨します。",
    DeprecationWarning,
    stacklevel=2
)


@dataclass
class DeepSeekConfig:
    """DeepSeek R1設定"""
    api_url: str = "http://localhost:11434"  # ollama デフォルト
    model_name: str = "deepseek-r1:32b"
    thinking_length: int = 8000
    max_tokens: int = 2000
    temperature: float = 0.2  # デフォルト温度
    top_p: float = 0.95
    timeout: int = 300
    retry_attempts: int = 3


# ドメイン別最適化パラメータ
DOMAIN_PARAMETERS = {
    "medical": {
        "temperature": 0.1,    # 医療: 最も確実性重視
        "top_p": 0.9,
        "max_tokens": 2500,    # 詳細な説明用に拡張
    },
    "legal": {
        "temperature": 0.15,   # 法律: 高い確実性
        "top_p": 0.92,
        "max_tokens": 2500,
    },
    "economics": {
        "temperature": 0.3,    # 経済: 多様な視点のため少し高め
        "top_p": 0.95,
        "max_tokens": 2000,
    },
    "general": {
        "temperature": 0.4,    # 一般: バランス型
        "top_p": 0.95,
        "max_tokens": 1500,
    }
}


class DeepSeekR1Engine:
    """
    DeepSeek R1推論エンジン
    思考チェーン（thinking）を活用した推論
    """
    
    def __init__(self, config: Optional[DeepSeekConfig] = None):
        self.config = config or DeepSeekConfig()
        self.client = httpx.AsyncClient(timeout=self.config.timeout)
        self._validate_connection()
    
    def _validate_connection(self):
        """DeepSeekサーバーへの接続確認"""
        try:
            response = requests.get(
                f"{self.config.api_url}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                
                if self.config.model_name in model_names:
                    print(f"✓ DeepSeek R1接続確認: {self.config.api_url}")
                    print(f"  モデル: {self.config.model_name}")
                else:
                    print(f"⚠️  モデル未検出: {self.config.model_name}")
                    print(f"  利用可能: {model_names}")
            else:
                print(f"⚠️  接続失敗: {response.status_code}")
        except Exception as e:
            print(f"⚠️  DeepSeek接続エラー: {e}")
            print(f"  確認事項:")
            print(f"  1. ollama/llama.cpp が起動しているか？")
            print(f"  2. APIエンドポイント正しいか？ ({self.config.api_url})")
            print(f"  3. モデルはロード済みか？ (ollama pull {self.config.model_name})")
    
    async def infer(
        self,
        prompt: str,
        domain_context: Optional[Dict] = None,
        return_thinking: bool = True
    ) -> Dict[str, any]:
        """
        DeepSeek R1で推論実行
        """
        import time
        start_time = time.time()

        # ドメイン名を抽出
        domain_name = domain_context.get("domain_name", "general") if domain_context else "general"

        optimized_prompt = self._optimize_prompt(
            prompt,
            domain_context
        )

        try:
            response = await self._call_deepseek(optimized_prompt, domain_name)
            result = self._parse_response(response, return_thinking, domain_name)
            result["latency_ms"] = int((time.time() - start_time) * 1000)
            result["domain"] = domain_name
            return result
        except Exception as e:
            logger.error(f"推論エラー: {e}")
            return {
                "thinking": "",
                "response": "",
                "confidence": 0.0,
                "error": str(e),
                "latency_ms": int((time.time() - start_time) * 1000),
                "domain": domain_name
            }
    
    def _optimize_prompt(
        self,
        prompt: str,
        domain_context: Optional[Dict] = None
    ) -> str:
        """プロンプトをドメインコンテキストで最適化"""
        optimized = prompt
        if domain_context:
            domain_name = domain_context.get("domain_name", "general")
            instructions = self._get_domain_instructions(domain_name)
            optimized = f"{instructions}\n\n{prompt}"
        return optimized
    
    def _get_domain_instructions(self, domain_name: str) -> str:
        """ドメイン固有の指示を取得"""
        instructions = {
            "medical": """【医療専門AIアシスタント - 厳密回答モード】

あなたは臨床経験豊富な医学AIです。以下の構造で回答してください：

## 必須ルール
1. **エビデンスベース**: 査読済み文献・ガイドラインに基づく情報のみ
2. **確実性の明示**: 各主張に確信度を付与（高/中/低）
3. **ハルシネーション厳禁**: 不確実な情報は「現時点で明確なエビデンスなし」と明記
4. **最新性への注意**: ガイドライン更新の可能性に言及

## 回答構造（厳守）
```
【概要】1-2文で要点を記述

【詳細説明】
- 病態生理/メカニズム
- 診断基準/検査
- 治療アプローチ

【エビデンスレベル】
A: RCT/メタ分析に基づく
B: 観察研究に基づく
C: 専門家意見/症例報告
D: 理論的推測

【鑑別診断】（該当する場合）
- 可能性の高い順にリスト

【注意事項】
- 重要な禁忌・警告
- 専門医への相談推奨ケース

【参考】主要ガイドライン・文献名
```

## 禁止事項
- 具体的な用量・投薬指示（「〇〇mgを投与」など）
- 断定的な診断（「これは〇〇です」）
- 根拠のない安心・不安の誘発

思考プロセスを<thinking>タグ内で展開してから回答してください。""",
            
            "legal": """【法学専門AIアシスタント - 厳密回答モード】

あなたは法律実務と学術の両面に精通した法学AIです。以下の構造で回答してください：

## 必須ルール
1. **法的正確性**: 現行法令・確立された判例に基づく情報のみ提供
2. **管轄の明確化**: 日本法を前提とし、国際私法や外国法が関係する場合は明記
3. **複数解釈**: 学説・判例の対立がある場合は主要な見解を併記
4. **最新性への注意**: 法改正情報・施行日に言及

## 回答構造（厳守）
```
【概要】1-2文で法的結論を記述

【法的根拠】
- 関連条文（〇〇法第X条）
- 適用される法原則・法理

【判例・学説】
A: 最高裁判例（最判〇〇年〇月〇日）
B: 下級審判例・有力判例
C: 通説・多数説
D: 有力少数説

【具体的検討】
- 要件充足性の検討
- 法的効果の分析

【実務上の注意】
- 時効・除斥期間
- 立証責任
- 手続き上の留意点

【免責事項】
※本情報は法的助言ではありません。具体的案件は弁護士にご相談ください。

【参考文献】条文・判例集・基本書名
```

## 禁止事項
- 具体的な訴訟戦略の提案
- 断定的な勝訴予測
- 弁護士法違反となる法的助言

思考プロセスを<thinking>タグ内で展開してから回答してください。""",

            "economics": """【経済学専門AIアシスタント - 分析モード】

あなたは計量経済学と理論経済学に精通した経済アナリストAIです。以下の構造で回答してください：

## 必須ルール
1. **データ駆動**: 信頼できる統計・経済指標（内閣府、日銀、IMF、世銀等）に基づく
2. **理論の明示**: 依拠する経済理論・学派を明確化
3. **中立性**: 政治的・イデオロギー的偏向を排除
4. **不確実性の明示**: 予測の限界・前提条件を明記

## 回答構造（厳守）
```
【概要】1-2文で経済的結論・見解を記述

【理論的背景】
- 関連する経済理論（ケインズ、新古典派、MMT等）
- 主要な経済モデル・フレームワーク

【データ・エビデンス】
A: 公式統計（GDP、CPI、失業率等）
B: 学術研究・実証分析
C: 市場データ・民間調査
D: 理論的推測

【分析】
ミクロ視点:
- 個別主体（家計・企業）への影響
- 市場メカニズムの作用

マクロ視点:
- 総需要・総供給への影響
- 財政・金融政策との関連

【シナリオ分析】
楽観シナリオ:
基準シナリオ:
悲観シナリオ:

【政策的含意】（該当する場合）
- 考えられる政策オプション
- 各政策のトレードオフ

【注意事項】
- 予測の不確実性
- データの制約・更新時期

【参考】統計出典・学術論文・レポート名
```

## 禁止事項
- 特定の政党・政策への支持表明
- 投資助言・具体的な売買推奨
- 根拠のない経済予測

思考プロセスを<thinking>タグ内で展開してから回答してください。""",
            
            "general": """【一般ドメイン指示】正確で有益な情報を提供してください。思考プロセスを明確に説明し、信頼度を示してください。"""
        }
        return instructions.get(domain_name, instructions["general"])
    
    def _get_domain_parameters(self, domain_name: str) -> Dict:
        """ドメイン別の最適化パラメータを取得"""
        return DOMAIN_PARAMETERS.get(domain_name, DOMAIN_PARAMETERS["general"])

    async def _call_deepseek(self, prompt: str, domain_name: str = "general") -> Dict:
        """DeepSeek R1 APIを呼び出し (Ollama想定)"""
        # ドメイン別パラメータを取得
        domain_params = self._get_domain_parameters(domain_name)

        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": domain_params["temperature"],
                "top_p": domain_params["top_p"],
                "num_predict": domain_params["max_tokens"],
            }
        }

        logger.info(f"推論パラメータ: domain={domain_name}, temp={domain_params['temperature']}, top_p={domain_params['top_p']}")

        response = await self.client.post(f"{self.config.api_url}/api/generate", json=payload)
        response.raise_for_status()
        return response.json()
    
    def _parse_response(self, response: Dict, return_thinking: bool, domain: str = "medical") -> Dict:
        """DeepSeek応答を解析"""
        full_text = response.get("response", "")
        thinking, final_response = "", full_text

        if "<thinking>" in full_text and "</thinking>" in full_text:
            thinking_start = full_text.find("<thinking>") + len("<thinking>")
            thinking_end = full_text.find("</thinking>")
            thinking = full_text[thinking_start:thinking_end].strip()
            final_response = full_text[thinking_end + len("</thinking>"):].strip()

        confidence = self._estimate_confidence(thinking, final_response, domain)
        tokens_used = response.get("eval_count", 0)

        # 構造化回答のパース（ドメイン対応）
        structured = self._parse_structured_response(final_response, domain)

        return {
            "thinking": thinking if return_thinking else "",
            "response": final_response,
            "structured": structured,
            "confidence": confidence,
            "tokens_used": int(tokens_used),
            "full_response": full_text
        }

    def _parse_structured_response(self, response: str, domain: str = "medical") -> Dict:
        """構造化回答をセクションごとにパース（ドメイン対応）"""

        # ドメイン別セクション定義
        domain_sections = {
            "medical": {
                "summary": "",           # 【概要】
                "details": "",           # 【詳細説明】
                "evidence_level": "",    # 【エビデンスレベル】
                "differential": "",      # 【鑑別診断】
                "cautions": "",          # 【注意事項】
                "references": "",        # 【参考】
            },
            "legal": {
                "summary": "",           # 【概要】
                "legal_basis": "",       # 【法的根拠】
                "precedents": "",        # 【判例・学説】
                "analysis": "",          # 【具体的検討】
                "practical_notes": "",   # 【実務上の注意】
                "disclaimer": "",        # 【免責事項】
                "references": "",        # 【参考文献】
            },
            "economics": {
                "summary": "",           # 【概要】
                "theory": "",            # 【理論的背景】
                "data_evidence": "",     # 【データ・エビデンス】
                "analysis": "",          # 【分析】
                "scenarios": "",         # 【シナリオ分析】
                "policy": "",            # 【政策的含意】
                "cautions": "",          # 【注意事項】
                "references": "",        # 【参考】
            }
        }

        sections = domain_sections.get(domain, domain_sections["medical"])

        # ドメイン別マーカー定義
        domain_markers = {
            "medical": {
                "【概要】": "summary",
                "【詳細説明】": "details",
                "【エビデンスレベル】": "evidence_level",
                "【鑑別診断】": "differential",
                "【注意事項】": "cautions",
                "【参考】": "references",
            },
            "legal": {
                "【概要】": "summary",
                "【法的根拠】": "legal_basis",
                "【判例・学説】": "precedents",
                "【具体的検討】": "analysis",
                "【実務上の注意】": "practical_notes",
                "【免責事項】": "disclaimer",
                "【参考文献】": "references",
            },
            "economics": {
                "【概要】": "summary",
                "【理論的背景】": "theory",
                "【データ・エビデンス】": "data_evidence",
                "【分析】": "analysis",
                "【シナリオ分析】": "scenarios",
                "【政策的含意】": "policy",
                "【注意事項】": "cautions",
                "【参考】": "references",
            }
        }

        section_markers = domain_markers.get(domain, domain_markers["medical"])

        # 各セクションの開始位置を特定
        positions = []
        for marker, key in section_markers.items():
            pos = response.find(marker)
            if pos != -1:
                positions.append((pos, marker, key))

        # 位置でソート
        positions.sort(key=lambda x: x[0])

        # 各セクションの内容を抽出
        for i, (pos, marker, key) in enumerate(positions):
            start = pos + len(marker)
            if i + 1 < len(positions):
                end = positions[i + 1][0]
            else:
                end = len(response)
            sections[key] = response[start:end].strip()

        return sections
    
    def _estimate_confidence(self, thinking: str, response: str, domain: str = "medical") -> float:
        """
        ドメイン対応の多角的信頼度推定
        - 思考の深度
        - エビデンスレベルの言及
        - 回答の構造化度
        - 不確実性の明示
        """
        confidence = 0.5
        factors = {}

        # 1. 思考の深度スコア (0-0.15)
        if thinking:
            word_count = len(thinking.split())
            thinking_score = min(0.15, word_count / 800 * 0.15)
            confidence += thinking_score
            factors["thinking_depth"] = thinking_score

        # 2. ドメイン別エビデンスキーワード (0-0.15)
        domain_evidence_keywords = {
            "medical": {
                "high": ["エビデンスレベルA", "RCT", "メタ分析", "ガイドライン推奨", "確立された", "標準治療"],
                "medium": ["エビデンスレベルB", "観察研究", "コホート研究", "複数の報告"],
                "low": ["エビデンスレベルC", "症例報告", "専門家意見", "限定的なデータ"]
            },
            "legal": {
                "high": ["最高裁判例", "最判", "確立された判例", "通説", "条文明記"],
                "medium": ["下級審判例", "有力説", "多数説", "実務上の運用"],
                "low": ["少数説", "学説上の議論", "傍論", "類推適用"]
            },
            "economics": {
                "high": ["公式統計", "内閣府", "日銀", "IMF", "実証研究", "計量分析"],
                "medium": ["民間調査", "複数の研究", "理論的根拠"],
                "low": ["推計", "予測", "シミュレーション", "理論的推測"]
            }
        }

        evidence_keywords = domain_evidence_keywords.get(domain, domain_evidence_keywords["medical"])
        evidence_score = 0
        for level, keywords in evidence_keywords.items():
            for kw in keywords:
                if kw in response:
                    evidence_score = {"high": 0.15, "medium": 0.10, "low": 0.05}[level]
                    break
            if evidence_score > 0:
                break
        confidence += evidence_score
        factors["evidence_level"] = evidence_score

        # 3. ドメイン別構造化度スコア (0-0.10)
        domain_structure_markers = {
            "medical": ["【概要】", "【詳細説明】", "【注意事項】", "【参考】", "【鑑別診断】", "【エビデンスレベル】"],
            "legal": ["【概要】", "【法的根拠】", "【判例・学説】", "【具体的検討】", "【実務上の注意】", "【免責事項】"],
            "economics": ["【概要】", "【理論的背景】", "【データ・エビデンス】", "【分析】", "【シナリオ分析】", "【政策的含意】"]
        }

        structure_markers = domain_structure_markers.get(domain, domain_structure_markers["medical"])
        structure_count = sum(1 for marker in structure_markers if marker in response)
        structure_score = min(0.10, structure_count * 0.02)
        confidence += structure_score
        factors["structure"] = structure_score

        # 4. ドメイン別確実性キーワード調整 (-0.15 to +0.10)
        domain_confidence_keywords = {
            "medical": {
                "high": ["確実", "明確", "標準治療", "第一選択", "推奨グレードA"],
                "low": ["不明", "推測", "可能性", "議論がある", "データ不十分", "要検討"]
            },
            "legal": {
                "high": ["確定判例", "判例変更なし", "条文上明らか", "争いなし"],
                "low": ["見解の対立", "未確定", "解釈の余地", "事案による", "個別判断"]
            },
            "economics": {
                "high": ["統計的に有意", "複数の実証研究", "経済理論と整合"],
                "low": ["不確実性", "予測困難", "シナリオ依存", "前提条件次第", "議論がある"]
            }
        }

        keywords_config = domain_confidence_keywords.get(domain, domain_confidence_keywords["medical"])
        keyword_adjustment = 0
        for keyword in keywords_config["high"]:
            if keyword in response:
                keyword_adjustment += 0.02
        for keyword in keywords_config["low"]:
            if keyword in response:
                keyword_adjustment -= 0.03  # 不確実性の明示は正直さの表れなので軽めの減点

        keyword_adjustment = max(-0.15, min(0.10, keyword_adjustment))
        confidence += keyword_adjustment
        factors["keywords"] = keyword_adjustment

        final_confidence = min(0.95, max(0.1, confidence))  # 0.1-0.95の範囲に制限

        logger.debug(f"信頼度推定[{domain}]: {final_confidence:.2f} (factors: {factors})")
        return final_confidence

    async def infer_streaming(self, prompt: str, domain_context: Optional[Dict] = None) -> AsyncGenerator[str, None]:
        """ストリーミング推論"""
        optimized_prompt = self._optimize_prompt(prompt, domain_context)
        payload = {
            "model": self.config.model_name,
            "prompt": optimized_prompt,
            "stream": True,
            "options": {
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "num_predict": self.config.max_tokens,
            }
        }
        
        try:
            async with self.client.stream("POST", f"{self.config.api_url}/api/generate", json=payload, timeout=self.config.timeout) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield token
        except Exception as e:
            logger.error(f"ストリーミングエラー: {e}")

if __name__ == "__main__":
    async def test_deepseek():
        config = DeepSeekConfig(model_name="deepseek-r1:32b")
        engine = DeepSeekR1Engine(config)
        medical_prompt = "心筋梗塞の診断基準は何ですか？"
        domain_context = {"domain_name": "medical"}
        
        print("="*60 + "\nDeepSeek R1推論テスト\n" + "="*60)
        result = await engine.infer(medical_prompt, domain_context=domain_context)
        
        print(f"\n✓ 推論完了\n  信頼度: {result.get('confidence', 0):.1%}\n  レイテンシ: {result.get('latency_ms', 0)}ms")
        if result.get('thinking'):
            print(f"\n【思考プロセス】\n{result['thinking'][:500]}...")
        print(f"\n【回答】\n{result.get('response', '')[:500]}...")
    
    asyncio.run(test_deepseek())