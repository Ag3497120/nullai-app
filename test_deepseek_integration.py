import asyncio
import json
from typing import List, Dict

# 実装した統合エンジンと設定クラスをインポート
from ilm_athens_engine.inference_engine_deepseek_integrated import IlmAthensDeepSeekEngine
from ilm_athens_engine.deepseek_integration.deepseek_runner import DeepSeekConfig
from ilm_athens_engine.domain.manager import DomainManager

# 50個の医療質問（サンプル）
# 実際には、より多様で専門的な質問リストが必要です。
MEDICAL_QUESTIONS_SAMPLE: List[str] = [
    "心筋梗塞の主な原因は何ですか？",
    "高血圧の診断基準について教えてください。",
    "2型糖尿病の第一選択薬は何ですか？",
    "脳卒中の急性期治療におけるt-PAの役割とは？",
    "COPD（慢性閉塞性肺疾患）の増悪時の対応について説明してください。",
    # 以下、テストの拡充用
    # "インスリン抵抗性のメカニズムを分子レベルで説明して。",
    # "Brugada症候群の心電図上の特徴は？",
    # "潰瘍性大腸炎とクローン病の違いは何ですか？",
    # "免疫チェックポイント阻害剤の副作用にはどのようなものがありますか？",
    # "再生医療におけるiPS細胞の応用例を挙げてください。"
]

async def run_integration_test(engine: IlmAthensDeepSeekEngine, questions: List[str], domain: str) -> List[Dict]:
    """
    指定された質問リストに対して推論を実行し、結果を収集します。
    """
    results = []
    for i, q in enumerate(questions):
        print(f"\n--- Testing question {i+1}/{len(questions)} ---")
        result = await engine.infer(user_query=q, domain_id=domain)
        results.append(result)
        
        # 簡易的な結果表示
        if result.get("status") == "success":
            print(f"  Query: {q}")
            print(f"  Response: {result.get('response', '')[:80]}...")
            print(f"  Verified: {result.get('verified')}")
        else:
            print(f"  Query: {q}")
            print(f"  ERROR: {result.get('message')}")
            
    return results

def analyze_results(results: List[Dict]):
    """
    テスト結果を分析し、サマリーレポートを出力します。
    """
    print("\n" + "="*60)
    print("ドメイン統合テスト分析レポート")
    print("="*60)

    if not results:
        print("テスト結果がありません。")
        return

    total_tests = len(results)
    success_count = sum(1 for r in results if r.get("status") == "success")
    verified_count = sum(1 for r in results if r.get("status") == "success" and r.get("verified"))
    
    deepseek_confidences = [r["confidence"]["deepseek"] for r in results if r.get("status") == "success"]
    judge_scores = [r["confidence"]["judge_verification"] for r in results if r.get("status") == "success"]
    latencies = [r.get("latency_ms", 0) for r in results if r.get("status") == "success"]

    # --- サマリー ---
    print("\n【総合評価】")
    print(f"  実行テスト数: {total_tests} 件")
    print(f"  成功率: {success_count / total_tests:.1%} ({success_count}/{total_tests})")
    
    # --- 精度評価 (成功したテストのみ対象) ---
    if success_count > 0:
        print("\n【精度・信頼度】")
        print(f"  Judge層による承認率: {verified_count / success_count:.1%} ({verified_count}/{success_count})")
        print(f"  DeepSeek平均信頼度: {sum(deepseek_confidences) / len(deepseek_confidences):.1%}")
        print(f"  Judge層平均検証スコア: {sum(judge_scores) / len(judge_scores):.2f}")

    # --- パフォーマンス評価 ---
    if latencies:
        print("\n【パフォーマンス】")
        print(f"  平均レイテンシ: {sum(latencies) / len(latencies):.0f} ms")
        print(f"  最速レイテンシ: {min(latencies)} ms")
        print(f"  最遅レイテンシ: {max(latencies)} ms")

    print("\n" + "="*60)


async def main():
    # 1. エンジンを初期化
    # ご自身の環境に合わせて設定を修正してください
    config = DeepSeekConfig(
        api_url="http://localhost:11434", 
        model_name="deepseek-r1:32b" # deepseek-r1がない場合は、テスト用に他のモデルを指定
    )
    domain_manager = DomainManager("domain_schemas.json")
    
    try:
        engine = IlmAthensDeepSeekEngine(domain_manager, config)
    except Exception as e:
        print(f"エンジンの初期化に失敗しました: {e}")
        return

    # 2. テストを実行
    test_results = await run_integration_test(
        engine=engine,
        questions=MEDICAL_QUESTIONS_SAMPLE,
        domain="medical"
    )
    
    # 3. 結果を分析・表示
    analyze_results(test_results)
    
    # 4. (オプション) 詳細結果をファイルに保存
    with open("test_integration_results.json", "w", encoding="utf-8") as f:
        json.dump(test_results, f, indent=2, ensure_ascii=False)
    print("\n詳細なテスト結果を test_integration_results.json に保存しました。")


if __name__ == "__main__":
    asyncio.run(main())
