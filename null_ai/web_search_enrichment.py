"""
NullAI Web検索によるDB拡充モジュール

Web検索APIを使用して最新情報を収集し、知識ベースを拡充する。

サポートする検索プロバイダー:
- DuckDuckGo (無料、APIキー不要)
- Brave Search (無料プランあり)
- SerpAPI (Google検索、有料)
- Tavily (AI向け検索API)

使用方法:
    python null_ai/web_search_enrichment.py --domain medical --query "最新の糖尿病治療法 2024"
    python null_ai/web_search_enrichment.py --domain legal --topics-file legal_topics.txt
    python null_ai/web_search_enrichment.py --all-domains --auto-topics
"""
import os
import sys
import json
import asyncio
import argparse
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import httpx
from urllib.parse import quote_plus

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class SearchResult:
    """検索結果"""
    title: str
    url: str
    snippet: str
    source: str
    published_date: Optional[str] = None
    relevance_score: float = 0.0


@dataclass
class EnrichedKnowledge:
    """拡充された知識タイル"""
    tile_id: str
    domain_id: str
    query: str
    sources: List[Dict]
    content: Dict[str, Any]
    coordinates: List[float]
    created_at: str
    source_type: str = "web_search"
    is_verified: bool = False


class WebSearchProvider:
    """Web検索プロバイダーの基底クラス"""

    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        raise NotImplementedError


class DuckDuckGoSearch(WebSearchProvider):
    """
    DuckDuckGo検索 (無料、APIキー不要)

    注意: DDGはAPIを公式提供していないため、HTMLスクレイピングを使用。
    レート制限あり。
    """

    def __init__(self):
        self.base_url = "https://html.duckduckgo.com/html/"

    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        results = []

        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.post(
                self.base_url,
                data={"q": query, "b": ""},
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                }
            )

            if response.status_code != 200:
                print(f"[WARN] DuckDuckGo search failed: {response.status_code}")
                return results

            # 簡易的なHTMLパース（本番環境ではBeautifulSoupを使用推奨）
            html = response.text
            # 結果リンクを抽出
            import re
            result_pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)">([^<]+)</a>'
            snippet_pattern = r'<a class="result__snippet"[^>]*>([^<]+)</a>'

            links = re.findall(result_pattern, html)
            snippets = re.findall(snippet_pattern, html)

            for i, (url, title) in enumerate(links[:num_results]):
                snippet = snippets[i] if i < len(snippets) else ""
                results.append(SearchResult(
                    title=title.strip(),
                    url=url,
                    snippet=snippet.strip(),
                    source="duckduckgo"
                ))

        return results


class BraveSearch(WebSearchProvider):
    """
    Brave Search API (無料プランあり: 2,000クエリ/月)

    https://brave.com/search/api/
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("BRAVE_API_KEY")
        self.base_url = "https://api.search.brave.com/res/v1/web/search"

    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        if not self.api_key:
            print("[WARN] BRAVE_API_KEY not set, skipping Brave Search")
            return []

        results = []
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self.base_url,
                params={"q": query, "count": num_results},
                headers=headers
            )

            if response.status_code != 200:
                print(f"[WARN] Brave Search failed: {response.status_code}")
                return results

            data = response.json()
            for item in data.get("web", {}).get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    source="brave",
                    published_date=item.get("age")
                ))

        return results


class TavilySearch(WebSearchProvider):
    """
    Tavily AI Search API (AI向け最適化、無料プランあり)

    https://tavily.com/
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com/search"

    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        if not self.api_key:
            print("[WARN] TAVILY_API_KEY not set, skipping Tavily Search")
            return []

        results = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.base_url,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": num_results,
                    "include_answer": True
                }
            )

            if response.status_code != 200:
                print(f"[WARN] Tavily Search failed: {response.status_code}")
                return results

            data = response.json()
            for item in data.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source="tavily",
                    relevance_score=item.get("score", 0.0)
                ))

        return results


class SerpAPISearch(WebSearchProvider):
    """
    SerpAPI (Google検索、有料)

    https://serpapi.com/
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY")
        self.base_url = "https://serpapi.com/search"

    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        if not self.api_key:
            print("[WARN] SERPAPI_API_KEY not set, skipping SerpAPI Search")
            return []

        results = []

        params = {
            "api_key": self.api_key,
            "q": query,
            "num": num_results,
            "engine": "google",
            "hl": "ja",
            "gl": "jp"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.base_url, params=params)

            if response.status_code != 200:
                print(f"[WARN] SerpAPI Search failed: {response.status_code}")
                return results

            data = response.json()
            for item in data.get("organic_results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source="serpapi",
                    published_date=item.get("date")
                ))

        return results


class GoogleCustomSearch(WebSearchProvider):
    """
    Google Custom Search API (無料枠: 100クエリ/日)

    https://developers.google.com/custom-search/v1/overview
    """

    def __init__(self, api_key: str = None, cx: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.cx = cx or os.getenv("GOOGLE_SEARCH_CX")
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        if not self.api_key or not self.cx:
            print("[WARN] GOOGLE_API_KEY or GOOGLE_SEARCH_CX not set, skipping Google Search")
            return []

        results = []

        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": min(num_results, 10)  # Google CSE max is 10
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.base_url, params=params)

            if response.status_code != 200:
                print(f"[WARN] Google Custom Search failed: {response.status_code}")
                return results

            data = response.json()
            for item in data.get("items", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source="google"
                ))

        return results


class WebSearchEnrichment:
    """Web検索によるDB拡充エンジン"""

    # ドメイン別の検索キーワードテンプレート
    DOMAIN_SEARCH_TEMPLATES = {
        "medical": {
            "topics": [
                "最新 {disease} 治療法 {year}",
                "{disease} 新薬 承認 {year}",
                "{symptom} 診断 ガイドライン 最新",
                "{disease} 予防 研究 最新",
                "医療AI {application} 最新動向"
            ],
            "variables": {
                "disease": ["糖尿病", "高血圧", "がん", "心臓病", "認知症", "うつ病", "喘息"],
                "symptom": ["頭痛", "発熱", "咳", "胸痛", "腹痛", "めまい"],
                "application": ["診断支援", "画像診断", "創薬", "予後予測"]
            }
        },
        "legal": {
            "topics": [
                "{law_type} 改正 {year} ポイント",
                "{legal_topic} 最新 判例 {year}",
                "{law_type} 実務 解説 最新",
                "AI法規制 {country} 最新動向"
            ],
            "variables": {
                "law_type": ["民法", "刑法", "会社法", "労働法", "知的財産法", "個人情報保護法"],
                "legal_topic": ["契約解除", "損害賠償", "相続", "離婚", "著作権侵害"],
                "country": ["日本", "EU", "アメリカ", "中国"]
            }
        },
        "economics": {
            "topics": [
                "{topic} 経済影響 {year} 分析",
                "{country} 金融政策 最新 {year}",
                "{industry} 市場動向 {year}",
                "インフレ対策 {country} 最新"
            ],
            "variables": {
                "topic": ["AI", "気候変動", "人口減少", "デジタル化", "グローバル化"],
                "country": ["日本", "アメリカ", "中国", "EU"],
                "industry": ["半導体", "EV", "再生可能エネルギー", "医薬品", "金融"]
            }
        },
        "programming": {
            "topics": [
                "{language} 最新バージョン 新機能 {year}",
                "{framework} ベストプラクティス {year}",
                "{topic} 実装方法 最新",
                "AI/ML {application} {language} チュートリアル"
            ],
            "variables": {
                "language": ["Python", "TypeScript", "Rust", "Go", "Swift"],
                "framework": ["React", "FastAPI", "Next.js", "PyTorch", "LangChain"],
                "topic": ["認証", "キャッシュ", "マイクロサービス", "CI/CD"],
                "application": ["RAG", "ファインチューニング", "プロンプトエンジニアリング"]
            }
        }
    }

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLM推論用クライアント（要約・整理用）
        """
        self.llm_client = llm_client
        self.search_providers = []

        # 利用可能な検索プロバイダーを初期化
        # DuckDuckGoは常に利用可能（無料、キー不要）
        self.search_providers.append(DuckDuckGoSearch())

        # APIキーがあれば追加プロバイダーを有効化
        if os.getenv("BRAVE_API_KEY"):
            self.search_providers.append(BraveSearch())
        if os.getenv("TAVILY_API_KEY"):
            self.search_providers.append(TavilySearch())
        if os.getenv("SERPAPI_API_KEY"):
            self.search_providers.append(SerpAPISearch())
        if os.getenv("GOOGLE_API_KEY") and os.getenv("GOOGLE_SEARCH_CX"):
            self.search_providers.append(GoogleCustomSearch())

    def generate_search_queries(
        self,
        domain_id: str,
        count: int = 10,
        year: str = None
    ) -> List[str]:
        """ドメインに基づいて検索クエリを生成"""
        if year is None:
            year = str(datetime.now().year)

        templates = self.DOMAIN_SEARCH_TEMPLATES.get(domain_id, {})
        if not templates:
            return []

        queries = []
        topic_templates = templates.get("topics", [])
        variables = templates.get("variables", {})

        import itertools
        import random

        for template in topic_templates:
            # テンプレート内の変数を取得
            placeholders = [p.strip("{}") for p in template.split() if p.startswith("{") and p.endswith("}")]

            # 変数の組み合わせを生成
            var_options = []
            for p in placeholders:
                if p == "year":
                    var_options.append([year])
                elif p in variables:
                    var_options.append(variables[p])
                else:
                    var_options.append([""])

            # 組み合わせからクエリを生成
            for combo in itertools.product(*var_options):
                query = template
                for p, v in zip(placeholders, combo):
                    query = query.replace(f"{{{p}}}", v)
                queries.append(query.strip())

        # シャッフルして指定数を返す
        random.shuffle(queries)
        return queries[:count]

    async def search_multiple_providers(
        self,
        query: str,
        num_results: int = 5
    ) -> List[SearchResult]:
        """複数の検索プロバイダーから結果を収集"""
        all_results = []

        for provider in self.search_providers:
            try:
                results = await provider.search(query, num_results)
                all_results.extend(results)
                print(f"  [{provider.__class__.__name__}] {len(results)} results")
            except Exception as e:
                print(f"  [{provider.__class__.__name__}] Error: {e}")

        # 重複URLを除去
        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)

        return unique_results

    async def fetch_and_summarize(
        self,
        results: List[SearchResult],
        query: str
    ) -> Dict[str, Any]:
        """
        検索結果を取得して要約する

        LLMクライアントが設定されている場合はLLMで要約、
        そうでない場合はスニペットを結合
        """
        if not results:
            return {"summary": "", "sources": []}

        sources = [asdict(r) for r in results]

        # スニペットを結合
        combined_text = "\n\n".join([
            f"【{r.title}】\n{r.snippet}"
            for r in results if r.snippet
        ])

        if self.llm_client:
            # LLMで要約（実装は使用するLLMクライアントに依存）
            try:
                summary = await self.llm_client.summarize(
                    text=combined_text,
                    prompt=f"以下の検索結果を「{query}」というクエリに対する回答として簡潔に要約してください。"
                )
            except Exception as e:
                print(f"[WARN] LLM summarization failed: {e}")
                summary = combined_text[:2000]
        else:
            summary = combined_text[:2000]

        return {
            "summary": summary,
            "sources": sources,
            "query": query,
            "fetched_at": datetime.utcnow().isoformat()
        }

    def create_knowledge_tile(
        self,
        domain_id: str,
        query: str,
        search_data: Dict[str, Any],
        coordinates: List[float] = None
    ) -> EnrichedKnowledge:
        """検索結果から知識タイルを作成"""

        # タイルIDを生成（クエリのハッシュベース）
        tile_id = f"web_{domain_id}_{hashlib.md5(query.encode()).hexdigest()[:12]}"

        # デフォルト座標（ランダムまたは中心）
        if coordinates is None:
            import random
            coordinates = [
                random.uniform(0, 100),  # r
                random.uniform(0, 360),  # theta
                random.uniform(-50, 50)  # z
            ]

        return EnrichedKnowledge(
            tile_id=tile_id,
            domain_id=domain_id,
            query=query,
            sources=search_data.get("sources", []),
            content={
                "question": query,
                "final_response": search_data.get("summary", ""),
                "source_urls": [s.get("url") for s in search_data.get("sources", [])],
                "fetched_at": search_data.get("fetched_at")
            },
            coordinates=coordinates,
            created_at=datetime.utcnow().isoformat(),
            source_type="web_search",
            is_verified=False
        )

    async def enrich_domain(
        self,
        domain_id: str,
        queries: List[str] = None,
        count: int = 10,
        save_path: str = None
    ) -> List[EnrichedKnowledge]:
        """
        ドメインの知識を拡充

        Args:
            domain_id: ドメインID
            queries: 検索クエリリスト（Noneの場合は自動生成）
            count: 生成するタイル数
            save_path: 結果を保存するパス

        Returns:
            生成された知識タイルのリスト
        """
        print(f"\n{'='*60}")
        print(f"Domain: {domain_id}")
        print(f"{'='*60}")

        # クエリを生成
        if queries is None:
            queries = self.generate_search_queries(domain_id, count)

        print(f"Generated {len(queries)} search queries")

        enriched_tiles = []

        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] Query: {query}")

            # 検索実行
            results = await self.search_multiple_providers(query, num_results=5)

            if not results:
                print("  No results found, skipping...")
                continue

            # 要約・整理
            search_data = await self.fetch_and_summarize(results, query)

            # タイル作成
            tile = self.create_knowledge_tile(domain_id, query, search_data)
            enriched_tiles.append(tile)

            print(f"  Created tile: {tile.tile_id}")
            print(f"  Sources: {len(tile.sources)}")

            # レート制限対策
            await asyncio.sleep(1.0)

        # 結果を保存
        if save_path:
            output_data = {
                "domain_id": domain_id,
                "generated_at": datetime.utcnow().isoformat(),
                "tile_count": len(enriched_tiles),
                "tiles": [asdict(t) for t in enriched_tiles]
            }

            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            print(f"\nSaved {len(enriched_tiles)} tiles to {save_path}")

        return enriched_tiles


async def main():
    parser = argparse.ArgumentParser(description="NullAI Web Search DB Enrichment")
    parser.add_argument("--domain", type=str, help="Target domain (medical, legal, economics, programming)")
    parser.add_argument("--query", type=str, help="Single search query")
    parser.add_argument("--queries-file", type=str, help="File containing search queries (one per line)")
    parser.add_argument("--count", type=int, default=10, help="Number of queries to generate")
    parser.add_argument("--all-domains", action="store_true", help="Enrich all domains")
    parser.add_argument("--output", type=str, default="enrichment_output", help="Output directory")
    parser.add_argument("--list-providers", action="store_true", help="List available search providers")

    args = parser.parse_args()

    enricher = WebSearchEnrichment()

    if args.list_providers:
        print("\nAvailable Search Providers:")
        print("-" * 40)
        for provider in enricher.search_providers:
            print(f"  - {provider.__class__.__name__}")
        print("\nTo enable more providers, set these environment variables:")
        print("  BRAVE_API_KEY - Brave Search API")
        print("  TAVILY_API_KEY - Tavily AI Search API")
        return

    # 検索クエリを準備
    queries = None
    if args.query:
        queries = [args.query]
    elif args.queries_file:
        with open(args.queries_file, "r", encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]

    # ドメインを処理
    domains_to_process = []
    if args.all_domains:
        domains_to_process = ["medical", "legal", "economics", "programming"]
    elif args.domain:
        domains_to_process = [args.domain]
    else:
        print("Error: Please specify --domain or --all-domains")
        parser.print_help()
        return

    # 各ドメインを拡充
    for domain in domains_to_process:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = f"{args.output}/web_enrichment_{domain}_{timestamp}.json"

        await enricher.enrich_domain(
            domain_id=domain,
            queries=queries,
            count=args.count,
            save_path=save_path
        )

    print("\n" + "=" * 60)
    print("Web Search Enrichment Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
