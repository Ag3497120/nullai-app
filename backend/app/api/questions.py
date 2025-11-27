from fastapi import APIRouter, Depends, HTTPException, WebSocket, Query
from typing import Optional
import json
import asyncio

from pydantic import BaseModel
from backend.app.services.inference_service import InferenceService, get_inference_service
from backend.app.services.cache_service import get_cache_service
from backend.app.middleware.auth import get_current_user, get_current_user_optional, User

router = APIRouter()


# --- リクエスト/レスポンススキーマの定義 ---
class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    domain_id: str = "medical"
    model_id: Optional[str] = None
    stream: bool = False


class QuestionResponse(BaseModel):
    session_id: str
    question: str
    response: str
    status: str
    confidence: Optional[float] = None
    memory_augmented: Optional[bool] = None
    thinking: Optional[str] = None
    model_used: Optional[str] = None


# --- APIエンドポイント ---
@router.post("/", response_model=QuestionResponse)
async def submit_question(
    request: QuestionRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: InferenceService = Depends(get_inference_service)
):
    """
    質問を提出し、推論エンジンで処理。
    ゲストユーザーでもアクセス可能。
    """
    # ゲストユーザーの場合は "guest" として扱う
    user_id = current_user.id if current_user else "guest"

    # Session IDがなければ新規生成
    session_id = request.session_id if request.session_id else f"sess_{user_id}_{hash(request.question)}"

    try:
        # 依存性注入されたInferenceServiceを呼び出す
        result = await service.process_question(
            question=request.question,
            user_id=user_id,
            session_id=session_id,
            domain_id=request.domain_id,
            model_id=request.model_id
        )

        return QuestionResponse(
            session_id=session_id,
            question=request.question,
            response=result.get("answer", result.get("response", "回答が得られませんでした。")),
            status=result.get("status", "error"),
            confidence=result.get("confidence"),
            memory_augmented=result.get("memory_augmented"),
            thinking=result.get("thinking"),
            model_used=result.get("model_used")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str
):
    """
    WebSocketで回答のストリーミング配信。
    トークン単位でリアルタイムに配信。
    """
    await websocket.accept()

    # InferenceServiceのインスタンスを作成
    from backend.app.services.cache_service import CacheService
    cache_service = CacheService()
    service = InferenceService(cache_service)

    try:
        # 接続確認メッセージ
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "WebSocket connected"
        })

        while True:
            # クライアントからのメッセージを待機
            data = await websocket.receive_json()

            if data.get("type") == "question":
                question = data.get("question", "")
                domain_id = data.get("domain_id", "medical")
                model_id = data.get("model_id")
                use_streaming = data.get("stream", True)

                # 処理開始通知
                await websocket.send_json({
                    "type": "processing",
                    "message": "Processing your question..."
                })

                try:
                    if use_streaming:
                        # ストリーミングモードで生成
                        await websocket.send_json({
                            "type": "thinking",
                            "step": "Initializing model..."
                        })

                        generated_tokens = []
                        async for chunk in service.stream_tokens(
                            session_id=session_id,
                            question=question,
                            domain_id=domain_id,
                            model_id=model_id
                        ):
                            chunk_type = chunk.get("type", "")

                            if chunk_type == "token":
                                # トークンをリアルタイムで送信
                                token = chunk.get("content", "")
                                generated_tokens.append(token)
                                await websocket.send_json({
                                    "type": "token",
                                    "content": token
                                })

                            elif chunk_type == "thinking":
                                await websocket.send_json({
                                    "type": "thinking",
                                    "step": chunk.get("content", "")
                                })

                            elif chunk_type == "complete":
                                # 完了メッセージ
                                await websocket.send_json({
                                    "type": "response",
                                    "session_id": session_id,
                                    "question": question,
                                    "response": chunk.get("content", ""),
                                    "status": "success"
                                })
                                break

                            elif chunk_type == "error":
                                await websocket.send_json({
                                    "type": "error",
                                    "error": chunk.get("content", chunk.get("message", "Unknown error"))
                                })
                                break

                            elif chunk_type == "heartbeat":
                                # ハートビートは無視（接続維持のため）
                                continue

                            elif chunk_type == "start":
                                await websocket.send_json({
                                    "type": "thinking",
                                    "step": "Starting generation..."
                                })

                    else:
                        # 非ストリーミングモード
                        await websocket.send_json({
                            "type": "thinking",
                            "step": "Processing..."
                        })

                        result = await service.process_question(
                            question=question,
                            user_id="ws_user",
                            session_id=session_id,
                            domain_id=domain_id,
                            model_id=model_id
                        )

                        # 最終回答を送信
                        await websocket.send_json({
                            "type": "response",
                            "session_id": session_id,
                            "question": question,
                            "response": result.get("answer", result.get("response", "")),
                            "status": result.get("status", "error"),
                            "confidence": result.get("confidence"),
                            "thinking": result.get("thinking"),
                            "model_used": result.get("model_used")
                        })

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    await websocket.send_json({
                        "type": "error",
                        "error": str(e)
                    })

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

            elif data.get("type") == "close":
                break

    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "error": str(e)
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
