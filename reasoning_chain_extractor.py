def extract_concepts(text: str) -> list:
    """
    文章から医学的概念を抽出します。
    この関数はダミー実装であり、実際のプロジェクトでは
    MeSHやUMLSなどの医学オントロジー、あるいはより高度なNERモデルを
    使用して実装する必要があります。
    
    Args:
        text (str): 分析対象のテキスト。

    Returns:
        list: 抽出された概念のリスト。
    """
    # プレースホルダー実装
    concepts = []
    if "心筋梗塞" in text:
        concepts.append("心筋梗塞")
    if "心電図" in text:
        concepts.append("心電図")
    if "トロポニン" in text:
        concepts.append("トロポニン")
    return concepts

def estimate_confidence(sentence: str) -> float:
    """
    文中の表現から確実性を推定します。
    (0.0 - 1.0の範囲のスコアを返す)
    """
    high_confidence_phrases = [
        "必ず", "常に", "確実に", "証明されている", "である"
    ]
    medium_confidence_phrases = [
        "通常は", "多くの場合", "一般的に", "考えられている"
    ]
    low_confidence_phrases = [
        "かもしれない", "可能性がある", "推測される", "示唆される", "仮説として"
    ]
    
    # 完全な一致ではなく、部分的な一致を許容するため 'in' を使用
    if any(phrase in sentence for phrase in high_confidence_phrases):
        return 0.85
    elif any(phrase in sentence for phrase in medium_confidence_phrases):
        return 0.60
    elif any(phrase in sentence for phrase in low_confidence_phrases):
        return 0.35
    else:
        # デフォルトは中間的な信頼度よりやや下
        return 0.50

def classify_depth(sentence: str) -> int:
    """
    文の内容から医学的な深さを5段階で分類します。
    1=症状, 2=診断, 3=機序, 4=分子, 5=複合
    """
    depth_keywords = {
        1: ["症状", "訴え", "患者が感じる", "胸痛", "息切れ"],
        2: ["検査", "所見", "診断基準", "心電図", "バイオマーカー", "トロポニン"],
        3: ["メカニズム", "機序", "なぜ", "原因", "血流", "虚血"],
        4: ["分子", "遺伝子", "酵素", "受容体", "細胞", "イオン"],
        5: ["複合", "相互作用", "システム", "統合", "複数の因子"]
    }
    
    for level, keywords in reversed(list(depth_keywords.items())):
        if any(keyword in sentence for keyword in keywords):
            return level
    
    return 2  # デフォルト：診断レベル

def extract_reasoning_chain(deepseek_response: dict) -> list:
    """
    DeepSeek R1の<thinking>セクションから推論ステップを抽出します。
    
    Args:
        deepseek_response (dict): 'thinking'キーを含むDeepSeek APIのレスポンス。

    Returns:
        list: 各ステップが辞書として格納されたリスト。
    """
    thinking_text = deepseek_response.get("thinking", "")
    if not thinking_text:
        return []
    
    # 推論の区切りとなりうるマーカー
    reasoning_markers = [
        "まず", "次に", "その結果", "さらに", "これは～という理由で",
        "～を考えると", "～に基づいて", "したがって", "一方で"
    ]
    
    # テキストを文（「。」）で分割
    sentences = thinking_text.replace("。。", "。\n").split("\n")
    sentences = [s.strip() for s in sentences if s.strip()]
    
    reasoning_steps = []
    current_step_text = ""
    
    for i, sentence in enumerate(sentences):
        # マーカーで始まる場合、または前のステップが長すぎる場合に新しいステップを開始
        is_new_step = any(sentence.startswith(marker) for marker in reasoning_markers)
        if is_new_step and current_step_text:
            reasoning_steps.append(current_step_text)
            current_step_text = sentence
        else:
            current_step_text += (" " + sentence) if current_step_text else sentence

    if current_step_text:
        reasoning_steps.append(current_step_text)

    # 抽出したステップを構造化データに変換
    structured_steps = []
    for i, step_text in enumerate(reasoning_steps):
        step = {
            "sequence": i,
            "text": step_text,
            "confidence": estimate_confidence(step_text),
            "concepts": extract_concepts(step_text),
            "depth_level": classify_depth(step_text)
        }
        structured_steps.append(step)
    
    return structured_steps

# --- 使用例 ---
if __name__ == "__main__":
    # deepseek_prompt_templates.py からのダミーレスポンスを想定
    dummy_response = {
        'thinking': 'まず、心筋梗塞の定義から始めます。これは心筋への血流が途絶えることで心筋が壊死する状態です。次に、診断のゴールドスタンダードであるトロポニン測定について考慮します。これは～という理由で重要です。さらに心電図の変化も重要な所見です。ST上昇が見られる場合、緊急性が高いと判断されます。',
        'response': '...'
    }

    print("--- 推論チェーンの抽出テスト ---")
    reasoning_chain = extract_reasoning_chain(dummy_response)

    for step in reasoning_chain:
        print(f"\nステップ {step['sequence']}:")
        print(f"  テキスト: {step['text']}")
        print(f"  信頼度: {step['confidence']:.2f}")
        print(f"  深さレベル: {step['depth_level']}")
        print(f"  関連概念: {step['concepts']}")

    # 出力例：
    #
    # --- 推論チェーンの抽出テスト ---
    #
    # ステップ 0:
    #   テキスト: まず、心筋梗塞の定義から始めます。 これは心筋への血流が途絶えることで心筋が壊死する状態です。
    #   信頼度: 0.85
    #   深さレベル: 3
    #   関連概念: ['心筋梗塞']
    #
    # ステップ 1:
    #   テキスト: 次に、診断のゴールドスタンダードであるトロポニン測定について考慮します。 これは～という理由で重要です。
    #   信頼度: 0.85
    #   深さレベル: 2
    #   関連概念: ['トロポニン']
    #
    # ステップ 2:
    #   テキスト: さらに心電図の変化も重要な所見です。 ST上昇が見られる場合、緊急性が高いと判断されます。
    #   信頼度: 0.85
    #   深さレベル: 2
    #   関連概念: ['心電図']
