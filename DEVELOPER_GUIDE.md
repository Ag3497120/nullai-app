# NULL AI プロジェクト - 開発者向け技術ガイド

## 📋 目次

1. [プロジェクト概要](#プロジェクト概要)
2. [システムアーキテクチャ](#システムアーキテクチャ)
3. [ディレクトリ構造](#ディレクトリ構造)
4. [技術スタック](#技術スタック)
5. [データベース設計](#データベース設計)
6. [API仕様](#api仕様)
7. [フロントエンド構成](#フロントエンド構成)
8. [バックエンド構成](#バックエンド構成)
9. [推論エンジン](#推論エンジン)
10. [開発環境セットアップ](#開発環境セットアップ)
11. [デプロイメント](#デプロイメント)
12. [トラブルシューティング](#トラブルシューティング)

---

## プロジェクト概要

### プロジェクト名
**NULL AI** - ドメイン特化型AI推論システム

### 目的
医療・法律など特定ドメインに特化した、高精度なAI質問応答システムを提供する。

### 主な機能
- **ドメイン特化型推論**: 医療(medical)、法律(legal)、一般(general)の3つのドメインに対応
- **多段階判定システム**: Judge Alpha → Judge Beta Basic → Judge Beta Advanced の3段階評価
- **知識ベース拡張**: IATH (Indexed Athens) 形式での知識タイル管理
- **リアルタイムストリーミング**: WebSocketによるトークンレベルのリアルタイム配信
- **キャッシュ機構**: 頻繁なクエリの高速化
- **ユーザー認証**: JWT based認証システム

---

## システムアーキテクチャ

### 全体構成図

```
┌─────────────────────────────────────────────────────────┐
│                    クライアント層                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   React UI   │  │ HF Space UI  │  │  REST Client │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    API Gateway層                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │         FastAPI Server (port 8000)                │  │
│  │  - REST API Endpoints                             │  │
│  │  - WebSocket Endpoints                            │  │
│  │  - JWT Authentication Middleware                  │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  サービス層                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Inference   │  │    Cache     │  │     Auth     │  │
│  │   Service    │  │   Service    │  │   Service    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  推論エンジン層                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │           Inference Engine Unified                │  │
│  │                                                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  │  │
│  │  │Judge Alpha │→│Judge Beta  │→│Judge Beta  │  │  │
│  │  │   Lobe     │ │Basic Lobe  │ │Advanced    │  │  │
│  │  └────────────┘  └────────────┘  └────────────┘  │  │
│  │                                                    │  │
│  │  ┌────────────────────────────────────────────┐  │  │
│  │  │        Knowledge Tile Generator            │  │  │
│  │  └────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   データ層                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  PostgreSQL  │  │  IATH DB     │  │  Hot Cache   │  │
│  │  (Users,     │  │  (Knowledge  │  │  (Redis-like)│  │
│  │   Sessions)  │  │   Tiles)     │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   AI モデル層                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │      Model Router (Hugging Face Integration)     │  │
│  │                                                    │  │
│  │  - DeepSeek-R1-Distill-Qwen-32B (医療・法律)      │  │
│  │  - Qwen2.5-7B-Instruct (一般)                     │  │
│  │  - その他カスタムモデル                            │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### データフロー

#### 1. ユーザークエリの処理フロー

```
User Question
    │
    ▼
[Frontend] Send POST /api/questions or WebSocket
    │
    ▼
[API Gateway] Route to appropriate endpoint
    │
    ├─ JWT Token Validation
    │
    ▼
[InferenceService] process_question()
    │
    ├─ Check Hot Cache
    │   └─ Cache Hit? → Return cached response
    │
    ▼
[Judge Alpha Lobe] 初期判定
    │
    ├─ 質問の複雑度評価 (complexity: 0.0-1.0)
    ├─ ドメイン適合性評価 (domain_fit: 0.0-1.0)
    └─ 処理フロー決定
        │
        ▼
    ┌───────────────────────────┐
    │ complexity < 0.3?         │
    └───────────────────────────┘
        │                    │
        │Yes                 │No
        ▼                    ▼
[Judge Beta Basic]    [Judge Beta Advanced]
    │                        │
    ├─ 軽量推論             ├─ 知識ベース検索
    └─ 高速応答             ├─ コンテキスト拡張
                            └─ 高精度推論
        │
        ▼
[Model Router] モデル選択・推論実行
    │
    ├─ ドメイン特化モデル選択
    ├─ プロンプトテンプレート適用
    └─ ストリーミング生成
        │
        ▼
[Response Post-Processing]
    │
    ├─ 幻覚検出 (Hallucination Detection)
    ├─ 確信度計算 (Confidence Scoring)
    └─ メタデータ付与
        │
        ▼
[Cache Update] Hot Cache更新
    │
    ▼
[Response] クライアントへ返却
```

---

## ディレクトリ構造

```
project_locate/
│
├── frontend/                          # React フロントエンド
│   ├── src/
│   │   ├── components/                # UI コンポーネント
│   │   │   ├── ChatInterface.tsx      # チャットUI
│   │   │   ├── LoginForm.tsx          # ログインフォーム
│   │   │   └── ThinkingIndicator.tsx  # 思考プロセス表示
│   │   ├── services/                  # API クライアント
│   │   │   ├── api.ts                 # REST API
│   │   │   └── websocket.ts           # WebSocket
│   │   ├── hooks/                     # Reactフック
│   │   ├── App.tsx                    # アプリケーションルート
│   │   └── index.tsx                  # エントリーポイント
│   ├── public/
│   └── package.json
│
├── backend/                           # FastAPI バックエンド
│   ├── app/
│   │   ├── api/                       # APIルート
│   │   │   ├── auth.py                # 認証エンドポイント
│   │   │   ├── questions.py           # 質問処理エンドポイント
│   │   │   └── health.py              # ヘルスチェック
│   │   ├── models/                    # データモデル
│   │   │   ├── user.py                # ユーザーモデル
│   │   │   └── session.py             # セッションモデル
│   │   ├── services/                  # ビジネスロジック
│   │   │   ├── inference_service.py   # 推論サービス
│   │   │   └── cache_service.py       # キャッシュサービス
│   │   ├── middleware/                # ミドルウェア
│   │   │   └── auth.py                # JWT認証
│   │   ├── utils/                     # ユーティリティ
│   │   │   ├── password_hash.py       # パスワードハッシュ化
│   │   │   └── jwt_handler.py         # JWT処理
│   │   └── main.py                    # FastAPIアプリケーション
│   └── requirements.txt
│
├── null_ai/                           # 推論エンジンコア
│   ├── inference_engine_unified.py    # 統合推論エンジン
│   ├── judge_alpha_lobe.py            # Judge Alpha (初期判定)
│   ├── judge_beta_lobe_basic.py       # Judge Beta Basic (軽量推論)
│   ├── judge_beta_lobe_advanced.py    # Judge Beta Advanced (高精度推論)
│   ├── knowledge_tile_generator.py    # 知識タイル生成
│   ├── hallucination_detector.py      # 幻覚検出
│   ├── model_router.py                # モデル選択・ルーティング
│   ├── iath_encoder.py                # IATH エンコーダー
│   ├── iath_decoder.py                # IATH デコーダー
│   ├── hot_cache.py                   # ホットキャッシュ
│   └── db_manager.py                  # データベース管理
│
├── ilm_athens_engine/                 # IATH システム
│   ├── layer1_spatial_encoding.py     # 空間エンコーディング
│   ├── layer2_episodic_binding.py     # エピソード結合
│   └── layer5_state_management.py     # 状態管理
│
├── documentation/                     # ドキュメント
│   ├── API_REFERENCE.md               # API仕様書
│   ├── ARCHITECTURE.md                # アーキテクチャ設計
│   └── DEPLOYMENT.md                  # デプロイ手順
│
├── docker-compose.yml                 # Docker構成
├── start_null_ai.sh                   # 起動スクリプト
├── requirements.txt                   # Pythonパッケージ
└── README.md                          # プロジェクト概要
```

---

## 技術スタック

### フロントエンド

| 技術 | バージョン | 用途 |
|------|-----------|------|
| **React** | 18.x | UIフレームワーク |
| **TypeScript** | 5.x | 型安全性 |
| **Vite** | 4.x | ビルドツール |
| **Axios** | 1.x | HTTP クライアント |
| **WebSocket API** | - | リアルタイム通信 |
| **Tailwind CSS** | 3.x | スタイリング |

### バックエンド

| 技術 | バージョン | 用途 |
|------|-----------|------|
| **FastAPI** | 0.104+ | Web フレームワーク |
| **Python** | 3.10+ | プログラミング言語 |
| **Uvicorn** | 0.24+ | ASGI サーバー |
| **PostgreSQL** | 14+ | リレーショナルDB |
| **SQLAlchemy** | 2.x | ORM |
| **Pydantic** | 2.x | データバリデーション |
| **JWT** | - | 認証トークン |
| **Passlib** | 1.7+ | パスワードハッシュ化 |

### AI/ML

| 技術 | バージョン | 用途 |
|------|-----------|------|
| **Transformers** | 4.36+ | HuggingFace モデル |
| **PyTorch** | 2.1+ | 深層学習フレームワーク |
| **DeepSeek-R1** | 32B distill | 医療・法律推論 |
| **Qwen2.5** | 7B | 一般推論 |
| **Accelerate** | 0.25+ | 分散処理 |
| **CUDA** | 11.8+ | GPU アクセラレーション |

### インフラ

| 技術 | 用途 |
|------|------|
| **Docker** | コンテナ化 |
| **HuggingFace Spaces** | デモデプロイ |
| **Nginx** | リバースプロキシ |
| **Git** | バージョン管理 |

---

## データベース設計

### PostgreSQL スキーマ

#### users テーブル
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
```

#### sessions テーブル
```sql
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id),
    domain_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_session_id ON sessions(session_id);
```

#### conversation_history テーブル
```sql
CREATE TABLE conversation_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES sessions(session_id),
    question TEXT NOT NULL,
    response TEXT NOT NULL,
    confidence FLOAT,
    model_used VARCHAR(255),
    thinking_process JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_conv_history_session_id ON conversation_history(session_id);
```

### IATH データベース構造

IATH (Indexed Athens) データベースは独自のバイナリ形式で保存されます。

```
ilm_athens_medical_db.iath
├── Header Section
│   ├── Version: 1.0
│   ├── Domain: medical
│   └── Tile Count: N
│
├── Tile Index
│   └── [tile_id → offset mapping]
│
└── Tile Data Sections
    └── Each Tile:
        ├── tile_id (UUID)
        ├── topic (string)
        ├── coordinates (3D vector)
        ├── content (text)
        ├── metadata (JSON)
        └── timestamp
```

---

## API仕様

### ベースURL
```
http://localhost:8000/api
```

### 認証

#### POST /auth/register
新規ユーザー登録

**リクエスト**
```json
{
  "email": "user@example.com",
  "username": "username",
  "password": "secure_password"
}
```

**レスポンス**
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "username",
  "created_at": "2025-01-01T00:00:00Z"
}
```

#### POST /auth/login
ログイン

**リクエスト**
```json
{
  "username": "username",
  "password": "secure_password"
}
```

**レスポンス**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "username",
    "email": "user@example.com"
  }
}
```

### 質問処理

#### POST /questions/
質問を送信（非ストリーミング）

**リクエスト**
```json
{
  "question": "心筋梗塞の初期症状は？",
  "session_id": "sess_123",
  "domain_id": "medical",
  "model_id": "deepseek-r1-32b",
  "stream": false
}
```

**レスポンス**
```json
{
  "session_id": "sess_123",
  "question": "心筋梗塞の初期症状は？",
  "response": "心筋梗塞の初期症状には...",
  "status": "success",
  "confidence": 0.92,
  "memory_augmented": true,
  "thinking": "Judge Alpha: complexity=0.7, Judge Beta Advanced selected...",
  "model_used": "deepseek-r1-32b"
}
```

#### WebSocket /questions/ws/{session_id}
リアルタイムストリーミング

**接続**
```javascript
const ws = new WebSocket('ws://localhost:8000/api/questions/ws/sess_123');
```

**送信メッセージ**
```json
{
  "type": "question",
  "question": "糖尿病の予防方法は？",
  "domain_id": "medical",
  "model_id": "deepseek-r1-32b",
  "stream": true
}
```

**受信メッセージ (ストリーミング)**
```json
// 接続確認
{"type": "connected", "session_id": "sess_123", "message": "WebSocket connected"}

// 処理開始
{"type": "processing", "message": "Processing your question..."}

// 思考プロセス
{"type": "thinking", "step": "Judge Alpha evaluating..."}

// トークンストリーム
{"type": "token", "content": "糖尿病"}
{"type": "token", "content": "の"}
{"type": "token", "content": "予防"}
...

// 完了
{
  "type": "response",
  "session_id": "sess_123",
  "question": "糖尿病の予防方法は？",
  "response": "糖尿病の予防には...",
  "status": "success"
}
```

#### GET /health
ヘルスチェック

**レスポンス**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-01-01T00:00:00Z"
}
```

---

## フロントエンド構成

### コンポーネント階層

```
App
├── AuthProvider
│   ├── LoginForm
│   └── RegisterForm
│
├── ChatInterface
│   ├── MessageList
│   │   ├── UserMessage
│   │   └── AIMessage
│   │       └── ThinkingIndicator
│   ├── InputArea
│   └── DomainSelector
│
└── SettingsPanel
    ├── ModelSelector
    └── ThemeToggle
```

### 主要コンポーネント

#### ChatInterface.tsx
```typescript
interface ChatInterfaceProps {
  sessionId: string;
  domain: 'medical' | 'legal' | 'general';
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ sessionId, domain }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    // WebSocket接続
    ws.current = new WebSocket(`ws://localhost:8000/api/questions/ws/${sessionId}`);

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleWebSocketMessage(data);
    };

    return () => ws.current?.close();
  }, [sessionId]);

  const sendQuestion = (question: string) => {
    ws.current?.send(JSON.stringify({
      type: 'question',
      question,
      domain_id: domain,
      stream: true
    }));
  };

  // ...
};
```

### 状態管理

Redux/Context API を使用した状態管理:

```typescript
interface AppState {
  auth: {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
  };
  chat: {
    sessions: Record<string, Session>;
    currentSessionId: string | null;
    messages: Message[];
  };
  settings: {
    domain: DomainType;
    model: string;
    theme: 'light' | 'dark';
  };
}
```

---

## バックエンド構成

### FastAPI アプリケーション構造

#### backend/app/main.py
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api import auth, questions, health
from backend.app.middleware.auth import JWTMiddleware

app = FastAPI(
    title="NULL AI API",
    version="1.0.0",
    description="Domain-specific AI inference system"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルート登録
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(questions.router, prefix="/api/questions", tags=["questions"])
app.include_router(health.router, prefix="/api", tags=["health"])

@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の初期化"""
    # データベース接続
    # キャッシュ初期化
    # モデルプリロード
    pass

@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時のクリーンアップ"""
    pass
```

### 依存性注入

```python
from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session
from backend.app.database import SessionLocal

def get_db() -> Generator:
    """データベースセッション取得"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """現在のユーザー取得"""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

---

## 推論エンジン

### Judge Alpha Lobe (初期判定)

**役割**: 質問の複雑度とドメイン適合性を評価し、適切な処理フローを決定

**実装**: `null_ai/judge_alpha_lobe.py`

```python
class JudgeAlphaLobe:
    def evaluate(self, question: str, domain: str) -> dict:
        """
        質問を評価し、処理フローを決定

        Returns:
            {
                "complexity": float (0.0-1.0),
                "domain_fit": float (0.0-1.0),
                "recommended_judge": "beta_basic" | "beta_advanced",
                "reasoning": str
            }
        """
        # 質問の長さ、専門用語密度、構造複雑度を分析
        complexity = self._calculate_complexity(question)
        domain_fit = self._evaluate_domain_fit(question, domain)

        if complexity < 0.3:
            recommended_judge = "beta_basic"
        else:
            recommended_judge = "beta_advanced"

        return {
            "complexity": complexity,
            "domain_fit": domain_fit,
            "recommended_judge": recommended_judge,
            "reasoning": self._generate_reasoning(complexity, domain_fit)
        }
```

### Judge Beta Basic (軽量推論)

**役割**: 低複雑度の質問に対して高速に応答

**特徴**:
- 知識ベース検索なし
- 小型モデル使用 (Qwen2.5-7B)
- 低レイテンシ (<2秒)

### Judge Beta Advanced (高精度推論)

**役割**: 高複雑度の質問に対して知識ベース拡張した高精度応答

**特徴**:
- IATH知識ベース検索
- 大型モデル使用 (DeepSeek-R1-32B)
- コンテキスト拡張 (最大4096トークン)
- 幻覚検出機構

**実装フロー**:
```python
class JudgeBetaAdvanced:
    async def process(self, question: str, domain: str, context: dict) -> dict:
        # 1. 知識ベース検索
        relevant_tiles = await self.search_knowledge_base(question, domain)

        # 2. コンテキスト構築
        augmented_context = self.build_context(question, relevant_tiles, context)

        # 3. プロンプト生成
        prompt = self.generate_prompt(question, augmented_context, domain)

        # 4. モデル推論
        response = await self.model_router.generate(
            prompt=prompt,
            model_id=self.select_model(domain),
            max_tokens=2048,
            temperature=0.7
        )

        # 5. 幻覚検出
        is_hallucinated = self.hallucination_detector.detect(response, relevant_tiles)

        # 6. 確信度計算
        confidence = self.calculate_confidence(response, relevant_tiles)

        return {
            "answer": response,
            "confidence": confidence,
            "hallucination_detected": is_hallucinated,
            "sources": [tile.id for tile in relevant_tiles],
            "reasoning": self.extract_reasoning(response)
        }
```

### Knowledge Tile Generator

**役割**: ドメイン知識を構造化されたタイル形式で生成・管理

**タイル構造**:
```python
@dataclass
class KnowledgeTile:
    tile_id: str                # UUID
    topic: str                  # トピック
    coordinates: tuple[float, float, float]  # 3D空間座標
    content: str                # 知識コンテンツ
    domain: str                 # ドメイン
    confidence: float           # 確信度
    metadata: dict              # メタデータ
    created_at: datetime
    updated_at: datetime
```

---

## 開発環境セットアップ

### 必要環境

- **OS**: macOS / Linux / Windows (WSL2)
- **Python**: 3.10 以上
- **Node.js**: 18 以上
- **PostgreSQL**: 14 以上
- **GPU**: NVIDIA (CUDA 11.8+) 推奨
- **メモリ**: 32GB以上推奨 (DeepSeek-R1-32B使用時)

### セットアップ手順

#### 1. リポジトリクローン
```bash
git clone <repository-url>
cd project_locate
```

#### 2. Python環境構築
```bash
# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係インストール
pip install -r requirements.txt
```

#### 3. データベースセットアップ
```bash
# PostgreSQL起動
brew services start postgresql  # macOS
# または
sudo systemctl start postgresql  # Linux

# データベース作成
createdb nullai_db

# マイグレーション実行
alembic upgrade head
```

#### 4. 環境変数設定
`.env` ファイルを作成:
```bash
# データベース
DATABASE_URL=postgresql://user:password@localhost/nullai_db

# JWT認証
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# HuggingFace
HF_TOKEN=your-huggingface-token

# モデル設定
DEFAULT_MODEL=deepseek-r1-32b
MODEL_CACHE_DIR=./model_cache
```

#### 5. フロントエンドセットアップ
```bash
cd frontend
npm install
```

#### 6. 起動

**バックエンド起動**
```bash
./start_null_ai.sh backend
# または
cd backend && uvicorn app.main:app --reload --port 8000
```

**フロントエンド起動**
```bash
cd frontend && npm run dev
```

**アクセス**
- フロントエンド: http://localhost:3000
- バックエンドAPI: http://localhost:8000
- API ドキュメント: http://localhost:8000/docs

---

## デプロイメント

### Docker デプロイ

#### docker-compose.yml
```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/nullai
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db
    volumes:
      - ./model_cache:/app/model_cache

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=nullai
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

#### デプロイコマンド
```bash
# ビルド
docker-compose build

# 起動
docker-compose up -d

# ログ確認
docker-compose logs -f

# 停止
docker-compose down
```

### HuggingFace Spaces デプロイ

#### requirements.txt (Space用)
```txt
gradio==4.44.0
huggingface_hub==0.19.4
transformers==4.36.0
torch==2.1.0
accelerate==0.25.0
```

#### app.py (Space用)
```python
import gradio as gr
from null_ai.inference_engine_unified import InferenceEngine

engine = InferenceEngine()

def chat(message, history, domain):
    response = engine.process_question(
        question=message,
        domain_id=domain,
        user_id="space_user"
    )
    return response["answer"]

iface = gr.ChatInterface(
    fn=chat,
    additional_inputs=[
        gr.Dropdown(["medical", "legal", "general"], label="Domain")
    ],
    title="NULL AI - Domain-Specific AI Assistant"
)

iface.launch()
```

#### アップロード
```bash
huggingface-cli upload kofdai/null-ai . --repo-type space
```

---

## トラブルシューティング

### 1. Port Already in Use (ポート競合)

**症状**: `Address already in use` エラー

**解決方法**:
```bash
# ポート8000を使用しているプロセスを確認
lsof -i :8000

# プロセスを終了
kill -9 <PID>

# または停止スクリプト使用
./start_null_ai.sh stop
```

### 2. Model Loading Error (モデル読み込みエラー)

**症状**: `OutOfMemoryError` または `Model not found`

**解決方法**:
```bash
# 1. メモリ不足の場合: 軽量モデルに切り替え
export DEFAULT_MODEL=qwen2-7b

# 2. モデルキャッシュクリア
rm -rf ~/.cache/huggingface/

# 3. モデル再ダウンロード
python -c "from transformers import AutoModelForCausalLM; AutoModelForCausalLM.from_pretrained('deepseek-ai/DeepSeek-R1-Distill-Qwen-32B')"
```

### 3. Database Connection Error

**症状**: `Connection refused` または `Database does not exist`

**解決方法**:
```bash
# PostgreSQL起動確認
brew services list  # macOS
systemctl status postgresql  # Linux

# データベース存在確認
psql -l

# データベース作成
createdb nullai_db

# マイグレーション実行
alembic upgrade head
```

### 4. bcrypt Password Hashing Error

**症状**: `Password too long` エラー

**解決方法**:
パスワードは自動的に72バイトに切り詰められます。`backend/app/utils/password_hash.py` 参照。

### 5. WebSocket Connection Failed

**症状**: WebSocket接続が確立できない

**解決方法**:
```bash
# CORS設定確認
# backend/app/main.py の CORSMiddleware 設定を確認

# WebSocketサポート確認
pip install websockets

# ファイアウォール確認
sudo ufw allow 8000  # Linux
```

### 6. HuggingFace Space Error

**症状**: `ImportError: cannot import name 'HfFolder'`

**解決方法**:
```bash
# requirements.txtに正しいバージョンを指定
echo "huggingface_hub==0.19.4" > requirements.txt
huggingface-cli upload kofdai/null-ai requirements.txt --repo-type space
```

---

## 開発ガイドライン

### コーディング規約

#### Python (PEP 8準拠)
```python
# 良い例
def process_question(question: str, domain: str) -> dict:
    """
    質問を処理し、応答を生成する

    Args:
        question: ユーザーの質問
        domain: ドメインID (medical/legal/general)

    Returns:
        応答辞書 {answer, confidence, sources}
    """
    pass

# 悪い例
def pq(q, d):  # 不明瞭な変数名
    pass
```

#### TypeScript
```typescript
// 良い例
interface Question {
  id: string;
  content: string;
  domain: DomainType;
  timestamp: Date;
}

// 悪い例
let q: any;  // any型の乱用
```

### Git コミットメッセージ

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: 新機能
- `fix`: バグ修正
- `docs`: ドキュメント
- `style`: コードスタイル
- `refactor`: リファクタリング
- `test`: テスト
- `chore`: ビルド・ツール

**例:**
```
feat(inference): Add hallucination detection

Implement hallucination detection mechanism in Judge Beta Advanced
using cosine similarity between generated response and source knowledge tiles.

Closes #123
```

### テスト

#### バックエンドテスト
```bash
# ユニットテスト
pytest tests/unit/

# 統合テスト
pytest tests/integration/

# カバレッジ
pytest --cov=backend tests/
```

#### フロントエンドテスト
```bash
# ユニットテスト
npm test

# E2Eテスト
npm run test:e2e
```

---

## パフォーマンス最適化

### 1. モデル最適化

- **量子化**: 4-bit/8-bit量子化でメモリ削減
- **Flash Attention**: 高速アテンション計算
- **Model Pruning**: 不要なレイヤー削減

### 2. キャッシング戦略

```python
# Hot Cache: 頻繁なクエリをメモリキャッシュ
cache.set(query_hash, response, ttl=3600)

# Cold Cache: 長期保存はDB
db.save_to_cache(query, response)
```

### 3. データベースインデックス

```sql
-- 頻繁に検索されるカラムにインデックス
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_conv_history_created_at ON conversation_history(created_at DESC);
```

---

## セキュリティ

### 1. 認証・認可

- **JWT**: トークンベース認証
- **bcrypt**: パスワードハッシュ化 (salt rounds: 12)
- **HTTPS**: 本番環境では必須

### 2. 入力検証

```python
from pydantic import BaseModel, validator

class QuestionRequest(BaseModel):
    question: str
    domain_id: str

    @validator('question')
    def validate_question(cls, v):
        if len(v) > 1000:
            raise ValueError('Question too long')
        return v
```

### 3. レート制限

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/questions/")
@limiter.limit("10/minute")
async def submit_question(request: Request):
    pass
```

---

## 監視・ログ

### ログ設定

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nullai.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Inference started", extra={"session_id": session_id})
```

### メトリクス収集

- **Prometheus**: メトリクス収集
- **Grafana**: ダッシュボード
- **Sentry**: エラートラッキング

---

## 参考リンク

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [HuggingFace Transformers](https://huggingface.co/docs/transformers)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [DeepSeek Model Card](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B)

---

## ライセンス

MIT License

---

## コントリビューション

プルリクエストを歓迎します。大きな変更の場合は、まずIssueで議論してください。

---

**最終更新**: 2025-01-26
**バージョン**: 1.0.0
**メンテナ**: NULL AI Team
