# メタ座標系の数学的定義

## 1.1 3次元メタ座標空間の定義

すべての知識は、以下の3次元空間に埋め込まれます：

```
Universal Meta-Space = ℝ³

座標 (c, g, v) ∈ [0, 100] × [1, 1000] × ℝ

where:
  c = Certainty（確実性軸）: [0, 100]
  g = Granularity（粒度軸）: [1, 1000]
  v = Verification（検証軸）: [0, ∞) （ドメイン依存）
```

## 1.2 各軸の詳細定義

### 確実性軸（Certainty, c ∈ [0, 100]）

```
信頼度スコア = (検証段階 × 50) + (外部ソース数 × 10) + (多重検証ボーナス × 15)
上限: 100

段階別スコア:
  0-20   : 投機的・仮説段階（DeepSeek生成、未検証）
  20-40  : 初期検証（1人の専門家が見た）
  40-60  : 部分検証（1-2人の専門家確認、部分的な外部ソース）
  60-80  : 検証済み（複数専門家確認、主要ソース引用あり）
  80-100 : 完全検証（複数専門家多重合意、複数外部ソース）

計算式:
  certainty = min(100, 
                  initial_review_score * 30 +
                  expert_count * 20 +
                  external_sources * 10 +
                  time_stability_bonus * 15 +
                  consensus_multiplier * 25)
```

### 粒度軸（Granularity, g ∈ [1, 1000]）

```
知識の「サイズ」を表す。何を単位としているか定義する。

粒度レベル:
  1-50    : 原子的事実（"Na原子番号=11", "血糖値正常範囲80-120mg/dL"）
  50-200  : 複合概念（"循環器系の構造", "心電図波形の読み方"）
  200-500 : 複雑な手順（"急性心筋梗塞の診断プロトコル", "手術手技全体"）
  500-1000: 統合体系（"内科学の全領域", "医療法制度の全体像"）

計算式（単語数ベース推定）:
  granularity = min(1000, max(1, ⌈log₂(word_count) × 100⌉))
  
例：
  10語の事実     → g ≈ 33
  100語の説明    → g ≈ 66
  1000語の手順   → g ≈ 100
  10000語の体系  → g ≈ 133
```

### 検証軸（Verification, v ∈ ℝ）

```
検証軸は、ドメインごとに定義される。医学の例：

v_medical = (
  anatomical_accuracy × 20 +
  pathophysiological_soundness × 20 +
  clinical_relevance × 15 +
  evidence_level × 20 +
  recency_score × 15 +
  consensus_agreement × 10
)

evidence_level スコア:
  0   : AI生成のみ（DeepSeek）
  5   : 学部教科書参考
  10  : 査読済み学術論文
  15  : ガイドライン（学会推奨）
  20  : 複数ガイドライン合意
```

## 1.3 座標正規化と距離度量

```
知識A (c_a, g_a, v_a) と知識B (c_b, g_b, v_b) の距離:

Euclidean距離（基本）:
  d_euclidean = √[(c_a - c_b)² + (g_a - g_b)² + (v_a - v_b)²]

意味的近接度（推奨）:
  - 確実性が高いペア（c > 70）: ユークリッド距離
  - 確実性が低いペア（c < 50）: 接続性重視（グラフベース）
  
関連性スコア（0-1）:
  relevance = max(0, 1 - (d_euclidean / max_distance))
```

## 1.4 座標の更新ルール

```
初期座標の決定（DeepSeek生成時）:
  c₀ = 25    # 初期確実性（未検証）
  g₀ = estimate_granularity(deepseek_output)
  v₀ = initial_verification_score(domain, deepseek_prompt)

専門家検証後:
  Δc = +15 per reviewer (max +45 for 3 reviewers)
  c_new = min(100, c_old + Δc)
  
修正提案採択後:
  c_new = c_old + 10  # 修正による信頼度向上
  修正内容が新しい座標領域を作成する場合あり
  
外部ソース追加時:
  c_new = min(100, c_old + (source_reliability × 5))
```
