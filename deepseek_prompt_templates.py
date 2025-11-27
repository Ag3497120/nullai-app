import os
import requests
import json

# 設計書で定義されたDeepSeek R1用のプロンプトテンプレート
MEDICAL_KNOWLEDGE_GENERATION_PROMPT = """
You are a medical knowledge expert. Your task is to generate verified medical knowledge 
for the Ilm-Athens system.

【生成タスク】
トピック: {topic}
対象読者: {audience_level}  # beginner/intermediate/expert
言語: Japanese

【出力形式】
1. <思考プロセス> セクション
   - なぜこの情報が重要か
   - 関連する医学的概念
   - 証拠となる事実やメカニズム
   
2. <最終回答> セクション
   - 明確で簡潔な説明
   - 医学的根拠の明示
   - 不確実性があれば明記

3. <参考資料> セクション
   - 学術論文
   - 臨床ガイドライン
   - 教科書参照

【重要な指示】
- Chain of Thoughtを詳細に展開してください
- 仮説と事実を明確に区別してください
- 確実性レベルを明示してください（確実/可能性あり/投機的）
- 現在の医学知識の限界も記載してください

トピック: {topic}
"""

class DeepSeekLocalAPI:
    """
    ローカルで実行されているDeepSeekモデル（例: deepseek-r1 32b）への
    APIリクエストを管理するクラス。
    """
    def __init__(self, api_base_url="http://localhost:8080/v1"):
        """
        Args:
            api_base_url (str): ローカルLLM APIのエンドポイント。
                                 環境に合わせて変更してください。
        """
        self.api_base_url = api_base_url
        self.headers = {"Content-Type": "application/json"}

    def generate(self, prompt: str, thinking_length_tokens: int = 8000, max_tokens: int = 3000):
        """
        ローカルのDeepSeekモデルにリクエストを送信し、思考プロセスと最終回答を取得します。
        
        Note: このメソッドは、一般的なローカルLLMサーバー（LM Studio, vLLMなど）の
              OpenAI互換エンドポイントを想定しています。
              ご使用の環境のAPI仕様に合わせてペイロードの調整が必要になる場合があります。
              また、DeepSeek R1特有の<thinking>タグを正しく出力させるための
              特別なパラメータが必要な場合があります。
        """
        
        # OpenAI互換API用のペイロード例
        data = {
            "model": "local-model", # モデル名はサーバー設定に依存
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens + thinking_length_tokens,
            "temperature": 0.7,
            # 'thinking_length_tokens'のようなカスタムパラメータはサーバーに依存します。
            # ここでは単純にmax_tokensに含めています。
        }

        try:
            response = requests.post(
                f"{self.api_base_url}/chat/completions",
                headers=self.headers,
                data=json.dumps(data)
            )
            response.raise_for_status()
            
            response_data = response.json()
            full_text = response_data['choices'][0]['message']['content']

            # <思考プロセス>と<最終回答>を分離する（仮の実装）
            thinking_part = ""
            response_part = ""
            
            if "<思考プロセス>" in full_text and "<最終回答>" in full_text:
                thinking_start = full_text.find("<思考プロセス>") + len("<思考プロセス>")
                thinking_end = full_text.find("</思考プロセス>") if "</思考プロセス>" in full_text else full_text.find("<最終回答>")
                thinking_part = full_text[thinking_start:thinking_end].strip()

                response_start = full_text.find("<最終回答>") + len("<最終回答>")
                response_end = full_text.find("</最終回答>") if "</最終回答>" in full_text else len(full_text)
                response_part = full_text[response_start:response_end].strip()
            else:
                # タグが見つからない場合は、暫定的に全体をレスポンスとする
                response_part = full_text

            return {
                "thinking": thinking_part,
                "response": response_part,
                "raw_response": full_text
            }

        except requests.exceptions.RequestException as e:
            print(f"APIリクエスト中にエラーが発生しました: {e}")
            return {
                "thinking": "",
                "response": f"Error: {e}",
                "raw_response": ""
            }

# --- 使用例 ---
if __name__ == "__main__":
    # ユーザーはこのURLを自身のローカル環境に合わせて変更する必要があります。
    LOCAL_API_URL = "http://localhost:8080/v1"
    
    deepseek_api = DeepSeekLocalAPI(api_base_url=LOCAL_API_URL)

    topic = "心筋梗塞の急性期診断アルゴリズム"
    audience_level = "intermediate"  # 医学生～若手医師向け

    prompt = MEDICAL_KNOWLEDGE_GENERATION_PROMPT.format(
        topic=topic,
        audience_level=audience_level
    )

    print("--- 生成AIに送信するプロンプト ---")
    print(prompt)
    print("\n--- ローカルAPIからのレスポンス待機中... ---")

    # 実際にAPIを叩く
    # response_data = deepseek_api.generate(prompt=prompt)
    
    # このスクリプト単体でテストするためのダミーレスポンス
    response_data = {
        'thinking': 'まず、心筋梗塞の定義から始めます。これは心筋への血流が途絶えることで心筋が壊死する状態です。次に、診断のゴールドスタンダードであるトロポニン測定について考慮します。これは～という理由で重要です。さらに心電図の変化も重要な所見です。ST上昇が見られる場合、緊急性が高いと判断されます。',
        'response': '急性心筋梗塞は、迅速な診断と治療が求められる救急疾患です。診断は主に、臨床症状（胸痛など）、心電図変化（ST上昇など）、心筋逸脱酵素（特にトロポニン）の上昇を三本柱として行われます。アルゴリズムとしては、まず疑いがあれば直ちに12誘導心電図を記録し、バイタルサインを確認します。ST上昇があれば、緊急カテーテル治療の適応を考慮します。<参考資料> 日本循環器学会ガイドライン2023',
        'raw_response': '<思考プロセス>まず、心筋梗塞の定義から始めます。これは心筋への血流が途絶えることで心筋が壊死する状態です。次に、診断のゴールドスタンダードであるトロポニン測定について考慮します。これは～という理由で重要です。さらに心電図の変化も重要な所見です。ST上昇が見られる場合、緊急性が高いと判断されます。</思考プロセス>\n<最終回答>急性心筋梗塞は、迅速な診断と治療が求められる救急疾患です。診断は主に、臨床症状（胸痛など）、心電図変化（ST上昇など）、心筋逸脱酵素（特にトロポニン）の上昇を三本柱として行われます。アルゴリズムとしては、まず疑いがあれば直ちに12誘導心電図を記録し、バイタルサインを確認します。ST上昇があれば、緊急カテーテル治療の適応を考慮します。<参考資料> 日本循環器学会ガイドライン2023</最終回答>'
    }


    print("\n--- APIからのレスポンス ---")
    print(f"思考プロセス: {response_data['thinking']}")
    print(f"最終回答: {response_data['response']}")
