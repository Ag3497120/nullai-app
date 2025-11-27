def calculate_certainty(
    initial_review: bool,
    expert_count: int,
    external_sources: int,
    time_stability_bonus: float,
    consensus_multiplier: float,
) -> int:
    """
    Ilm-Athens DB層設計書に基づき、知識タイルの確実性スコアを計算します。

    Args:
        initial_review (bool): 初期レビューが完了したかどうか (完了で1, 未了で0)。
        expert_count (int): 確認した専門家の人数。
        external_sources (int): 参照された外部ソースの数。
        time_stability_bonus (float): 時間的安定性によるボーナス係数 (例: 0.0-1.0)。
        consensus_multiplier (float): 合意形成の度合いによる乗数 (例: 0.0-1.0)。

    Returns:
        int: 計算された確実性スコア (0-100)。
    """
    
    initial_review_score = 1 if initial_review else 0
    
    score = (
        initial_review_score * 30 +
        expert_count * 20 +
        external_sources * 10 +
        time_stability_bonus * 15 +
        consensus_multiplier * 25
    )
    
    return min(100, int(score))

def calculate_granularity(word_count: int) -> int:
    """
    Ilm-Athens DB層設計書に基づき、知識の粒度を計算します。
    単語数ベースの推定式を使用します。

    Args:
        word_count (int): 知識コンテンツの単語数。

    Returns:
        int: 計算された粒度スコア (1-1000)。
    """
    import math

    if word_count <= 0:
        return 1
        
    # log2(0) は未定義のため、word_countが0の場合は1として扱います。
    # 設計書では⌈log₂(word_count) × 100⌉となっていますが、
    # 実際にはlog2(1)=0となるため、word_count=1でも結果が0になります。
    # 最小値を1とするため、log2(word_count + 1)とするか、結果に+1するなどの調整が考えられます。
    # ここでは簡易的に math.log2(word_count) を使用します。
    granularity_score = math.ceil(math.log2(word_count) * 100) if word_count > 0 else 0


    return min(1000, max(1, int(granularity_score)))
