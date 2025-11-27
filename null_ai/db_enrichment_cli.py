#!/usr/bin/env python3
"""
NullAI DB拡充CLIツール

大量の質問を生成してDBに保存するためのコマンドラインツール。
基本的な知識を先に生成してDBを拡充する。

機能:
- 質問テンプレートからの自動生成
- Web検索による最新情報の収集
- LLM推論結果の自動保存
"""
import asyncio
import argparse
import json
import sys
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from null_ai.config import ConfigManager, ModelConfig
from null_ai.model_router import ModelRouter

# Web検索モジュールのインポート（オプショナル）
try:
    from null_ai.web_search_enrichment import WebSearchEnrichment
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False


@dataclass
class EnrichmentTask:
    """DB拡充タスク"""
    domain_id: str
    topic: str
    questions: List[str]
    priority: int = 1  # 1=高, 2=中, 3=低


# ドメイン別の基本質問テンプレート
DOMAIN_QUESTION_TEMPLATES = {
    "medical": {
        "categories": [
            {
                "name": "症状と診断",
                "questions": [
                    "{disease}の主な症状は何ですか？",
                    "{disease}はどのように診断されますか？",
                    "{disease}の初期症状にはどのようなものがありますか？",
                    "{symptom}が見られる場合、どのような疾患が考えられますか？",
                ]
            },
            {
                "name": "治療法",
                "questions": [
                    "{disease}の標準的な治療法は何ですか？",
                    "{disease}に使用される薬剤にはどのようなものがありますか？",
                    "{disease}の治療における最新のアプローチは？",
                    "{treatment}の副作用について教えてください。",
                ]
            },
            {
                "name": "予防と管理",
                "questions": [
                    "{disease}を予防するにはどうすればよいですか？",
                    "{disease}患者の日常生活での注意点は？",
                    "{disease}の再発を防ぐためには？",
                ]
            }
        ],
        "topics": {
            "disease": ["心筋梗塞", "脳卒中", "糖尿病", "高血圧", "肺炎", "COPD", "心不全", "不整脈", "胃潰瘍", "肝硬変"],
            "symptom": ["胸痛", "息切れ", "めまい", "頭痛", "腹痛", "発熱", "倦怠感", "動悸"],
            "treatment": ["ステロイド療法", "抗生物質治療", "血管形成術", "ペースメーカー", "透析"]
        }
    },
    "legal": {
        "categories": [
            {
                "name": "契約法",
                "questions": [
                    "{contract_type}の法的要件は何ですか？",
                    "{contract_type}を解除するための条件は？",
                    "{contract_type}における瑕疵担保責任とは？",
                ]
            },
            {
                "name": "民事訴訟",
                "questions": [
                    "{legal_issue}の場合、どのような法的手続きが必要ですか？",
                    "{legal_issue}における損害賠償の算定方法は？",
                    "{legal_issue}の時効について教えてください。",
                ]
            },
            {
                "name": "会社法",
                "questions": [
                    "{corporate_action}の手続きについて教えてください。",
                    "{corporate_action}に必要な書類は何ですか？",
                    "{corporate_action}における取締役の責任は？",
                ]
            }
        ],
        "topics": {
            "contract_type": ["売買契約", "賃貸借契約", "業務委託契約", "雇用契約", "ライセンス契約"],
            "legal_issue": ["交通事故", "医療過誤", "名誉毀損", "債務不履行", "不法行為"],
            "corporate_action": ["会社設立", "増資", "合併", "株主総会", "取締役会"]
        }
    },
    "economics": {
        "categories": [
            {
                "name": "マクロ経済",
                "questions": [
                    "{economic_concept}とは何ですか？",
                    "{economic_concept}が経済に与える影響は？",
                    "{economic_concept}の最新動向について教えてください。",
                ]
            },
            {
                "name": "金融市場",
                "questions": [
                    "{financial_topic}の仕組みを説明してください。",
                    "{financial_topic}のリスク要因は何ですか？",
                    "{financial_topic}への投資戦略は？",
                ]
            },
            {
                "name": "企業分析",
                "questions": [
                    "{analysis_method}の計算方法と意味を教えてください。",
                    "{analysis_method}を使った企業評価の方法は？",
                ]
            }
        ],
        "topics": {
            "economic_concept": ["インフレーション", "GDP", "金利政策", "為替レート", "景気循環", "失業率"],
            "financial_topic": ["株式市場", "債券市場", "デリバティブ", "投資信託", "ETF", "暗号資産"],
            "analysis_method": ["PER", "PBR", "ROE", "DCF法", "EBITDA"]
        }
    },
    "programming": {
        "categories": [
            {
                "name": "言語基礎",
                "questions": [
                    "{language}における{concept}の使い方を教えてください。",
                    "{language}で{task}を実装する方法は？",
                    "{language}の{feature}について説明してください。",
                ]
            },
            {
                "name": "設計パターン",
                "questions": [
                    "{pattern}パターンとは何ですか？",
                    "{pattern}パターンの実装例を示してください。",
                    "{pattern}パターンを使うべき状況は？",
                ]
            }
        ],
        "topics": {
            "language": ["Python", "JavaScript", "TypeScript", "Go", "Rust"],
            "concept": ["クラス", "非同期処理", "エラーハンドリング", "ジェネリクス"],
            "task": ["ファイル読み書き", "API呼び出し", "データベース接続", "テスト"],
            "feature": ["型システム", "メモリ管理", "並行処理", "パッケージ管理"],
            "pattern": ["Singleton", "Factory", "Observer", "Strategy", "Decorator"]
        }
    },
    "general": {
        "categories": [
            {
                "name": "一般知識",
                "questions": [
                    "{topic}について教えてください。",
                    "{topic}の歴史と発展について説明してください。",
                    "{topic}の現代における重要性は？",
                ]
            }
        ],
        "topics": {
            "topic": ["人工知能", "気候変動", "再生可能エネルギー", "宇宙開発", "量子コンピュータ"]
        }
    }
}


class QuestionGenerator:
    """質問生成器"""

    def __init__(self, domain_id: str):
        self.domain_id = domain_id
        self.templates = DOMAIN_QUESTION_TEMPLATES.get(domain_id, DOMAIN_QUESTION_TEMPLATES["general"])

    def generate_questions(self, max_questions: int = 100) -> List[str]:
        """質問を生成"""
        questions = []
        categories = self.templates.get("categories", [])
        topics = self.templates.get("topics", {})

        for category in categories:
            for q_template in category["questions"]:
                # テンプレート内のプレースホルダーを特定
                placeholders = [p.strip("{}") for p in q_template.split("{") if "}" in p]
                placeholders = [p.split("}")[0] for p in placeholders]

                if not placeholders:
                    questions.append(q_template)
                else:
                    # プレースホルダーごとに質問を生成
                    for placeholder in placeholders:
                        if placeholder in topics:
                            for value in topics[placeholder]:
                                q = q_template.replace("{" + placeholder + "}", value)
                                # 他のプレースホルダーも置換
                                for other_ph in placeholders:
                                    if other_ph != placeholder and other_ph in topics:
                                        q = q.replace("{" + other_ph + "}", topics[other_ph][0])
                                questions.append(q)
                                if len(questions) >= max_questions:
                                    return questions

        return questions[:max_questions]


class DBEnrichmentEngine:
    """DB拡充エンジン"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.model_router = ModelRouter(config_manager)
        self.results: List[Dict[str, Any]] = []
        self.output_dir = "enrichment_output"
        os.makedirs(self.output_dir, exist_ok=True)

    async def process_question(
        self,
        question: str,
        domain_id: str,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """単一の質問を処理してDBに保存"""
        print(f"  Processing: {question[:50]}...")

        try:
            result = await self.model_router.infer(
                prompt=question,
                domain_id=domain_id,
                model_id=model_id,
                save_to_memory=True  # 自動保存有効
            )

            return {
                "question": question,
                "domain_id": domain_id,
                "response": result.get("response", ""),
                "confidence": result.get("confidence", 0.0),
                "saved_to_memory": result.get("saved_to_memory", False),
                "tile_id": result.get("tile_id"),
                "status": "success"
            }

        except Exception as e:
            return {
                "question": question,
                "domain_id": domain_id,
                "error": str(e),
                "status": "error"
            }

    async def enrich_domain(
        self,
        domain_id: str,
        max_questions: int = 50,
        model_id: Optional[str] = None,
        batch_size: int = 5,
        delay_between_batches: float = 1.0
    ) -> Dict[str, Any]:
        """ドメインのDBを拡充"""
        print(f"\n{'='*60}")
        print(f"Domain: {domain_id}")
        print(f"Max Questions: {max_questions}")
        print(f"{'='*60}\n")

        generator = QuestionGenerator(domain_id)
        questions = generator.generate_questions(max_questions)

        print(f"Generated {len(questions)} questions")

        results = []
        success_count = 0
        error_count = 0

        # バッチ処理
        for i in range(0, len(questions), batch_size):
            batch = questions[i:i + batch_size]
            print(f"\nBatch {i // batch_size + 1}/{(len(questions) + batch_size - 1) // batch_size}")

            batch_results = await asyncio.gather(*[
                self.process_question(q, domain_id, model_id)
                for q in batch
            ])

            for r in batch_results:
                results.append(r)
                if r["status"] == "success":
                    success_count += 1
                else:
                    error_count += 1

            # レート制限対策
            if i + batch_size < len(questions):
                await asyncio.sleep(delay_between_batches)

        # 結果を保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(
            self.output_dir,
            f"enrichment_{domain_id}_{timestamp}.json"
        )

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "domain_id": domain_id,
                "timestamp": timestamp,
                "total_questions": len(questions),
                "success_count": success_count,
                "error_count": error_count,
                "results": results
            }, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"Enrichment Complete!")
        print(f"Success: {success_count}, Errors: {error_count}")
        print(f"Results saved to: {output_file}")
        print(f"{'='*60}\n")

        return {
            "domain_id": domain_id,
            "total": len(questions),
            "success": success_count,
            "errors": error_count,
            "output_file": output_file
        }

    async def enrich_all_domains(
        self,
        max_questions_per_domain: int = 30,
        model_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """全ドメインのDBを拡充"""
        domains = self.config_manager.list_domains(active_only=True)
        results = []

        for domain in domains:
            result = await self.enrich_domain(
                domain_id=domain.domain_id,
                max_questions=max_questions_per_domain,
                model_id=model_id
            )
            results.append(result)

        return results

    async def enrich_with_web_search(
        self,
        domain_id: str,
        queries: List[str] = None,
        count: int = 10,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Web検索による最新情報でドメインを拡充

        Args:
            domain_id: ドメインID
            queries: 検索クエリリスト（Noneの場合は自動生成）
            count: 検索クエリ数
            model_id: 使用するモデルID（要約用）
        """
        if not WEB_SEARCH_AVAILABLE:
            print("[ERROR] Web search module not available.")
            print("Make sure web_search_enrichment.py exists in null_ai/")
            return {"status": "error", "message": "Web search not available"}

        print(f"\n{'='*60}")
        print(f"Web Search Enrichment: {domain_id}")
        print(f"{'='*60}\n")

        # WebSearchEnrichmentにLLMクライアントを渡す（オプション）
        llm_client = None
        if model_id:
            # 簡易的なLLMクライアントラッパー
            class LLMClient:
                def __init__(self, router, model_id, domain_id):
                    self.router = router
                    self.model_id = model_id
                    self.domain_id = domain_id

                async def summarize(self, text: str, prompt: str) -> str:
                    result = await self.router.infer(
                        prompt=f"{prompt}\n\n{text}",
                        domain_id=self.domain_id,
                        model_id=self.model_id,
                        save_to_memory=False,
                        max_tokens=500
                    )
                    return result.get("response", text[:1000])

            llm_client = LLMClient(self.model_router, model_id, domain_id)

        enricher = WebSearchEnrichment(llm_client=llm_client)

        # 検索を実行
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(
            self.output_dir,
            f"web_enrichment_{domain_id}_{timestamp}.json"
        )

        tiles = await enricher.enrich_domain(
            domain_id=domain_id,
            queries=queries,
            count=count,
            save_path=save_path
        )

        # 各タイルをメモリに保存
        saved_count = 0
        for tile in tiles:
            try:
                # ModelRouterを通じてメモリに保存
                if hasattr(self.model_router, '_save_to_memory'):
                    await self.model_router._save_to_memory(
                        prompt=tile.query,
                        response=tile.content.get("final_response", ""),
                        domain_id=domain_id,
                        confidence=0.7,  # Web検索結果はやや低めの信頼度
                        coordinate=tile.coordinates
                    )
                    saved_count += 1
            except Exception as e:
                print(f"[WARN] Failed to save tile {tile.tile_id}: {e}")

        return {
            "domain_id": domain_id,
            "total_tiles": len(tiles),
            "saved_to_memory": saved_count,
            "output_file": save_path,
            "status": "success"
        }


async def main():
    parser = argparse.ArgumentParser(
        description="NullAI DB拡充ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 医療ドメインを50件の質問で拡充
  python db_enrichment_cli.py --domain medical --count 50

  # 全ドメインを拡充（各30件）
  python db_enrichment_cli.py --all --count 30

  # 特定のモデルを使用
  python db_enrichment_cli.py --domain legal --model deepseek-r1-32b --count 20

  # 生成される質問の一覧を表示（実行なし）
  python db_enrichment_cli.py --domain medical --preview

  # Web検索で最新情報を収集
  python db_enrichment_cli.py --domain medical --web-search --count 10

  # 特定のクエリでWeb検索
  python db_enrichment_cli.py --domain medical --web-search --query "最新の糖尿病治療法 2024"

  # クエリファイルからWeb検索
  python db_enrichment_cli.py --domain legal --web-search --queries-file legal_queries.txt
        """
    )

    parser.add_argument(
        "--domain", "-d",
        type=str,
        help="対象ドメイン (medical, legal, economics, programming, general)"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="全ドメインを拡充"
    )
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=30,
        help="生成する質問数 (デフォルト: 30)"
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        help="使用するモデルID"
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=5,
        help="バッチサイズ (デフォルト: 5)"
    )
    parser.add_argument(
        "--preview", "-p",
        action="store_true",
        help="生成される質問をプレビュー（実行しない）"
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="利用可能なモデル一覧を表示"
    )
    parser.add_argument(
        "--list-domains",
        action="store_true",
        help="利用可能なドメイン一覧を表示"
    )

    # Web検索オプション
    parser.add_argument(
        "--web-search", "-w",
        action="store_true",
        help="Web検索で最新情報を収集"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="単一の検索クエリ"
    )
    parser.add_argument(
        "--queries-file",
        type=str,
        help="検索クエリファイル（1行に1クエリ）"
    )
    parser.add_argument(
        "--list-search-providers",
        action="store_true",
        help="利用可能な検索プロバイダーを表示"
    )

    args = parser.parse_args()

    # 設定マネージャー初期化
    config_manager = ConfigManager()

    # モデル一覧表示
    if args.list_models:
        print("\n利用可能なモデル:")
        print("-" * 60)
        for model in config_manager.list_models():
            default_mark = " [DEFAULT]" if model.is_default else ""
            print(f"  {model.model_id}: {model.display_name}{default_mark}")
            print(f"    Provider: {model.provider.value}")
            print(f"    Domains: {', '.join(model.supported_domains)}")
            print()
        return

    # ドメイン一覧表示
    if args.list_domains:
        print("\n利用可能なドメイン:")
        print("-" * 60)
        for domain in config_manager.list_domains():
            print(f"  {domain.domain_id}: {domain.name}")
            print(f"    Description: {domain.description}")
            print(f"    Default Model: {domain.default_model_id}")
            print()
        return

    # 検索プロバイダー一覧
    if args.list_search_providers:
        if WEB_SEARCH_AVAILABLE:
            enricher = WebSearchEnrichment()
            print("\n利用可能な検索プロバイダー:")
            print("-" * 60)
            for provider in enricher.search_providers:
                print(f"  - {provider.__class__.__name__}")
            print("\n追加プロバイダーを有効にするには環境変数を設定:")
            print("  BRAVE_API_KEY - Brave Search API (無料2,000クエリ/月)")
            print("  TAVILY_API_KEY - Tavily AI Search API")
        else:
            print("[ERROR] Web search module not available")
        return

    # プレビューモード
    if args.preview:
        domain_id = args.domain or "medical"
        generator = QuestionGenerator(domain_id)
        questions = generator.generate_questions(args.count)

        print(f"\n生成される質問 ({domain_id}, {len(questions)}件):")
        print("-" * 60)
        for i, q in enumerate(questions, 1):
            print(f"{i:3}. {q}")
        return

    # 拡充実行
    if not args.domain and not args.all:
        parser.print_help()
        print("\nエラー: --domain または --all を指定してください")
        return

    engine = DBEnrichmentEngine(config_manager)

    # Web検索モード
    if args.web_search:
        if not WEB_SEARCH_AVAILABLE:
            print("[ERROR] Web search module not available")
            print("Make sure null_ai/web_search_enrichment.py exists")
            return

        # クエリを準備
        queries = None
        if args.query:
            queries = [args.query]
        elif args.queries_file:
            if os.path.exists(args.queries_file):
                with open(args.queries_file, "r", encoding="utf-8") as f:
                    queries = [line.strip() for line in f if line.strip()]
            else:
                print(f"[ERROR] Queries file not found: {args.queries_file}")
                return

        await engine.enrich_with_web_search(
            domain_id=args.domain,
            queries=queries,
            count=args.count,
            model_id=args.model
        )
    elif args.all:
        await engine.enrich_all_domains(
            max_questions_per_domain=args.count,
            model_id=args.model
        )
    else:
        await engine.enrich_domain(
            domain_id=args.domain,
            max_questions=args.count,
            model_id=args.model,
            batch_size=args.batch_size
        )


if __name__ == "__main__":
    asyncio.run(main())
