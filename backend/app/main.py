from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from backend.app.api import (auth, domains, knowledge, models, orcid_auth,
                             proposals, questions, succession, system)
from backend.app.config import settings

# 新しいOAuth & ワークスペースAPIをインポート
try:
    from backend.app.api import oauth, workspaces
    oauth_available = True
except ImportError:
    oauth_available = False
    logging.warning("OAuth and Workspaces modules not available")

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPIアプリケーションの作成
app = FastAPI(
    title="NullAI API",
    description="Zero-Hallucination Knowledge Reasoning Engine API with Multi-Tenant Workspaces",
    version="0.2.0"
)

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Check app mode from environment variable
APP_MODE = os.getenv("APP_MODE", "FULL").upper()

# ルーター登録
# Core routers for both modes
# app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"]) # DEPRECATED
# app.include_router(orcid_auth.router, prefix="/api/auth", tags=["ORCID Authentication"]) # DEPRECATED
app.include_router(domains.router, prefix="/api/domains", tags=["Domains"])
app.include_router(proposals.router, prefix="/api/proposals", tags=["Proposals"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["Knowledge Base"])
app.include_router(system.router, prefix="/api/system", tags=["System"])

# Routers for FULL mode only
if APP_MODE == "FULL":
    app.include_router(questions.router, prefix="/api/questions", tags=["Questions"])
    app.include_router(models.router, prefix="/api/models", tags=["Models"])
    app.include_router(succession.router, prefix="/api/succession", tags=["Model Succession"])
    logger.info("Running in FULL mode. All inference APIs enabled.")
else:
    logger.info(f"Running in {APP_MODE} mode. Inference APIs are disabled.")


# 新しい認証&ワークスペースルーター
if oauth_available:
    app.include_router(oauth.router, prefix="/api/oauth", tags=["OAuth Authentication"])
    app.include_router(workspaces.router, prefix="/api/workspaces", tags=["Workspaces"])
    logger.info("OAuth and Workspaces APIs enabled")


# ヘルスチェック
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ilm-athens-api"}

# ルートエンドポイント
@app.get("/")
async def root():
    return {
        "message": "Ilm-Athens API v0.1 (Backend)",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    # `reload=True`は開発時のみ使用
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )
