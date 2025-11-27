# NullAI 機能解説

## システム概要

NullAIは、専門家検証機能付きのマルチドメイン知識推論システムです。
HuggingFace Transformersベースで、外部API依存なしに動作します。

---

## 1. 推論システム (Inference System)

### 1.1 ModelRouter (`null_ai/model_router.py`)
**機能**: ドメインに応じた最適なモデルの自動選択と推論実行

```python
# 使用例
router = ModelRouter(config_manager)
result = await router.infer(
    prompt="心筋梗塞の初期症状は？",
    domain_id="medical",
    save_to_memory=True
)
```

**効果**:
- 55以上のドメインに対応した専門的な回答
- 自動モデル選択による最適化
- 推論結果の自動メモリ保存

### 1.2 HuggingFace Integration
**対応プロバイダー**:
| プロバイダー | 説明 | 推奨用途 |
|-------------|------|---------|
| `huggingface` | ローカルTransformers | 高品質推論 |
| `huggingface_api` | Inference API | 低リソース環境 |
| `gguf` | llama.cpp互換 | 高速CPU推論 |

### 1.3 ストリーミング生成
**機能**: トークン単位でのリアルタイム配信

```python
async for chunk in service.stream_tokens(session_id, question, domain_id):
    if chunk["type"] == "token":
        print(chunk["content"], end="", flush=True)
```

---

## 2. 知識ベースシステム (Knowledge Base)

### 2.1 IATH形式データベース
**機能**: 高圧縮・高速アクセスの独自バイナリ形式

```
┌─────────────────────────────────────┐
│ IATH Header (Magic + Version)       │
├─────────────────────────────────────┤
│ Metadata (JSON, zstd compressed)    │
├─────────────────────────────────────┤
│ Tiles Index                         │
├─────────────────────────────────────┤
│ Knowledge Tiles (zstd compressed)   │
└─────────────────────────────────────┘
```

**効果**:
- 70-90%の圧縮率
- O(1)のタイルアクセス
- 増分更新サポート

### 2.2 Knowledge Tile
**構造**:
```json
{
  "tile_id": "med_001",
  "domain_id": "medical",
  "topic": "心筋梗塞の初期症状",
  "content": "...",
  "spatial_coords": [0.7, 0.3, 0.85],
  "confidence_score": 0.95,
  "verification_mark": {
    "type": "expert",
    "expert_orcid": "0000-0002-1234-5678"
  }
}
```

---

## 3. 検証マークシステム (Verification System)

### 3.1 検証レベル
| レベル | 条件 | 信頼度 |
|--------|------|--------|
| `multi_expert` | 2人以上の専門家が検証 | 最高 |
| `expert` | ORCID認証済み専門家が検証 | 高 |
| `community` | 認証ユーザーがレビュー | 中 |
| `none` | 未検証（ゲスト編集含む） | 低 |

### 3.2 ORCID認証
**フロー**:
```
ユーザー → ORCID OAuth → 認証コード → JWTトークン → 専門家ステータス
```

**効果**:
- 学術的な信頼性の担保
- 専門家の所属機関・業績の確認可能
- 改ざん防止

---

## 4. 判断システム (Judgment System)

### 4.1 α-Lobe（生成ローブ）
**機能**: 質問に対する初期回答の生成

```python
class JudgeAlphaLobe:
    def generate_initial_response(self, question, context):
        # 空間座標の計算
        coords = self.calculate_spatial_coordinates(question)
        # 関連知識の検索
        relevant_tiles = self.search_knowledge_base(coords)
        # 回答生成
        return self.generate_response(question, relevant_tiles)
```

### 4.2 β-Lobe（検証ローブ）
**機能**: 生成された回答の品質検証

```python
class JudgeBetaLobe:
    def verify_response(self, response, question, context):
        # 事実性チェック
        factual_score = self.check_factuality(response)
        # 一貫性チェック
        consistency_score = self.check_consistency(response, context)
        # 信頼度計算
        confidence = self.calculate_confidence(factual_score, consistency_score)
        return {"verified": confidence > 0.7, "confidence": confidence}
```

### 4.3 Correction Flow
**機能**: β-Lobeが不合格とした場合の再生成

```
α-Lobe生成 → β-Lobe検証 → 不合格 → 修正プロンプト → 再生成 → 再検証
```

---

## 5. 記憶システム (Memory System)

### 5.1 DendriticMemorySpace
**機能**: 円柱座標系での知識表現

```
r (半径): 抽象度 (0=具体的, 1=抽象的)
θ (角度): ドメイン (0-2π)
z (高さ): 時間/重要度
```

**効果**:
- 意味的に近い知識の効率的検索
- ドメイン横断的な関連付け
- 時系列での知識管理

### 5.2 自動メモリ保存
**条件**:
- 信頼度が閾値（デフォルト0.6）以上
- 検証済みコンテンツ
- 新規または更新された知識

---

## 6. 継続学習システム (NurseLog System)

### 6.1 倒木更新（世代交代）
**コンセプト**: 森林の倒木が次世代の栄養となるように、古いモデルの知識を新モデルに継承

```python
class NurseLogSystem:
    def prepare_succession(self):
        # 1. 現行モデルの知識を抽出
        knowledge = self.extract_model_knowledge()
        # 2. 継承データセットの作成
        dataset = self.create_succession_dataset(knowledge)
        # 3. 新モデルのファインチューニング
        new_model = self.finetune_apprentice(dataset)
        # 4. 世代交代
        self.switch_generation(new_model)
```

### 6.2 Dream Mode（夢モード）
**機能**: 低負荷時に知識の整理・統合を実行

```python
# 50会話ごとに自動実行
if conversation_count % 50 == 0:
    await nurse_log_system.enter_dream_mode()
```

---

## 7. API エンドポイント

### 7.1 推論API
```
POST /api/questions/
WebSocket /api/questions/ws/{session_id}
```

### 7.2 知識ベースAPI
```
GET  /api/knowledge/                 # タイル一覧
GET  /api/knowledge/{tile_id}        # タイル詳細
PUT  /api/knowledge/{tile_id}        # 編集（検証マーク付与）
GET  /api/knowledge/stats/summary    # 統計
```

### 7.3 認証API
```
POST /api/auth/token                 # ログイン
POST /api/auth/signup                # 登録
GET  /api/auth/orcid/authorize       # ORCID認証開始
GET  /api/auth/orcid/callback        # ORCID認証コールバック
```

### 7.4 システムAPI
```
GET  /api/system/status              # システム状態
GET  /api/system/health              # ヘルスチェック
GET  /api/system/providers           # 対応プロバイダー
```

---

## 8. ドメイン一覧（55ドメイン）

### 医療・健康 (8)
medical, cardiology, neurology, oncology, pediatrics, psychiatry, pharmacology, nutrition

### 法律 (8)
legal, labor_law, corporate_law, intellectual_property, contract_law, tax_law, family_law, criminal_law

### 経済・金融 (6)
economics, finance, accounting, banking, cryptocurrency, real_estate

### テクノロジー (8)
programming, web_development, machine_learning, cybersecurity, cloud_computing, devops, databases, mobile_development

### 科学 (6)
physics, chemistry, biology, mathematics, environmental_science, astronomy

### ビジネス (6)
business_strategy, marketing, human_resources, project_management, entrepreneurship, supply_chain

### 教育 (4)
education, language_learning, history, philosophy

### 工学 (6)
mechanical_engineering, electrical_engineering, civil_engineering, architecture, manufacturing, robotics

### ライフスタイル (5)
cooking, fitness, travel, gardening, diy

### 芸術 (5)
music, visual_arts, photography, writing, game_development

### 一般 (1)
general
