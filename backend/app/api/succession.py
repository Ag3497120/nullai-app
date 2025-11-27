"""
NullAI モデル世代交代API (NurseLog System)

推論履歴の管理、トレーニングデータのエクスポート、
DB世代管理のためのエンドポイント。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from backend.app.services.inference_service import InferenceService, get_inference_service
from backend.app.config import settings

router = APIRouter()


class SuccessionStatusResponse(BaseModel):
    """世代交代ステータスのレスポンス"""
    status: str
    should_trigger: bool
    high_quality_count: int
    threshold: int
    message: str


class TriggerSuccessionRequest(BaseModel):
    """世代交代トリガーのリクエスト"""
    domain_id: Optional[str] = Field(None, description="特定ドメインのみ対象にする場合")
    min_confidence: float = Field(0.8, ge=0.0, le=1.0, description="最小信頼度")
    db_path: Optional[str] = Field(None, description="DBスナップショットのパス")


class SuccessionTriggerResponse(BaseModel):
    """世代交代実行結果のレスポンス"""
    status: str
    count: int
    exports: Dict[str, str]
    db_snapshot: Optional[str] = None
    log: Optional[Dict[str, Any]] = None


class InferenceHistoryQuery(BaseModel):
    """推論履歴クエリのパラメータ"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    domain_id: Optional[str] = None
    min_confidence: float = 0.0


class InferenceHistoryResponse(BaseModel):
    """推論履歴のレスポンス"""
    total: int
    records: List[Dict[str, Any]]


class SuccessionHistoryResponse(BaseModel):
    """世代交代履歴のレスポンス"""
    total: int
    history: List[Dict[str, Any]]


@router.get("/status", response_model=SuccessionStatusResponse)
async def get_succession_status(
    inference_service: InferenceService = Depends(get_inference_service)
):
    """
    モデル世代交代のステータスを取得。

    高品質な推論データが閾値を超えているかチェックし、
    世代交代が可能かどうかを判定する。
    """
    try:
        result = await inference_service.check_succession_status()
        return SuccessionStatusResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger", response_model=SuccessionTriggerResponse)
async def trigger_succession(
    request: TriggerSuccessionRequest,
    inference_service: InferenceService = Depends(get_inference_service)
):
    """
    モデル世代交代を手動でトリガー。

    推論履歴から高品質なデータを抽出し、
    複数フォーマット（JSONL, CSV, Parquet, HuggingFace Datasets）でエクスポート。
    指定されている場合はDBスナップショットも作成。
    """
    try:
        # デフォルトのDB pathを取得
        db_path = request.db_path or getattr(settings, "DB_PATH", "ilm_athens_medical_db.iath")

        result = await inference_service.trigger_succession(
            domain_id=request.domain_id,
            min_confidence=request.min_confidence,
            db_path=db_path if os.path.exists(db_path) else None
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message", "Succession failed"))

        return SuccessionTriggerResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/inference", response_model=InferenceHistoryResponse)
async def get_inference_history(
    start_date: Optional[str] = Query(None, description="開始日 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="終了日 (YYYY-MM-DD)"),
    domain_id: Optional[str] = Query(None, description="ドメインID"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="最小信頼度"),
    limit: int = Query(100, ge=1, le=1000, description="最大取得件数"),
    inference_service: InferenceService = Depends(get_inference_service)
):
    """
    推論履歴を取得。

    日付、ドメイン、信頼度でフィルタリング可能。
    トレーニングデータの品質確認に使用。
    """
    try:
        if not inference_service.inference_history:
            raise HTTPException(
                status_code=503,
                detail="NurseLog System not available"
            )

        history = inference_service.inference_history.load_history(
            start_date=start_date,
            end_date=end_date,
            domain_id=domain_id,
            min_confidence=min_confidence
        )

        # limitで制限
        history = history[:limit]

        return InferenceHistoryResponse(
            total=len(history),
            records=history
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/succession", response_model=SuccessionHistoryResponse)
async def get_succession_history(
    inference_service: InferenceService = Depends(get_inference_service)
):
    """
    世代交代の履歴を取得。

    過去にいつ、どのようなトレーニングデータが生成されたかの記録。
    """
    try:
        manager = inference_service.get_succession_manager()
        if not manager:
            raise HTTPException(
                status_code=503,
                detail="NurseLog System not available"
            )

        history = manager.get_succession_history()

        return SuccessionHistoryResponse(
            total=len(history),
            history=history
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exports")
async def list_exported_files():
    """
    エクスポートされたトレーニングデータファイルの一覧を取得。
    """
    try:
        training_data_dir = "training_data"
        if not os.path.exists(training_data_dir):
            return {"files": []}

        files = []
        for filename in os.listdir(training_data_dir):
            filepath = os.path.join(training_data_dir, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                files.append({
                    "filename": filename,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / 1024 / 1024, 2),
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        # 作成日時の降順でソート
        files.sort(key=lambda x: x["created_at"], reverse=True)

        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots")
async def list_db_snapshots():
    """
    DBスナップショットの一覧を取得。
    """
    try:
        from null_ai.nurse_log_system import DBArchiveManager

        archive_manager = DBArchiveManager(archive_dir="db_archives")
        snapshots = archive_manager.list_snapshots()

        return {"snapshots": snapshots}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshots/restore")
async def restore_db_snapshot(
    snapshot_path: str,
    target_path: Optional[str] = None
):
    """
    DBスナップショットを復元。

    注意: 現在のDBは自動的にバックアップされます。
    """
    try:
        from null_ai.nurse_log_system import DBArchiveManager

        if not target_path:
            target_path = getattr(settings, "DB_PATH", "ilm_athens_medical_db.iath")

        archive_manager = DBArchiveManager(archive_dir="db_archives")
        success = archive_manager.restore_snapshot(
            snapshot_path=snapshot_path,
            target_path=target_path
        )

        if success:
            return {
                "status": "success",
                "message": f"Restored snapshot {snapshot_path} to {target_path}"
            }
        else:
            raise HTTPException(status_code=500, detail="Restore failed")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_succession_stats(
    inference_service: InferenceService = Depends(get_inference_service)
):
    """
    世代交代システムの統計情報を取得。

    - 総推論数
    - 高品質推論数
    - ドメイン別の統計
    - 世代交代の回数
    """
    try:
        if not inference_service.inference_history:
            raise HTTPException(
                status_code=503,
                detail="NurseLog System not available"
            )

        # 全推論履歴
        all_history = inference_service.inference_history.load_history()

        # 高品質推論
        high_quality = [r for r in all_history if r.get("confidence", 0) >= 0.8]

        # ドメイン別統計
        domain_stats = {}
        for record in all_history:
            domain = record.get("domain_id", "unknown")
            if domain not in domain_stats:
                domain_stats[domain] = {
                    "total": 0,
                    "high_quality": 0,
                    "avg_confidence": 0.0
                }
            domain_stats[domain]["total"] += 1
            if record.get("confidence", 0) >= 0.8:
                domain_stats[domain]["high_quality"] += 1

        # 平均信頼度を計算
        for domain in domain_stats:
            domain_records = [r for r in all_history if r.get("domain_id") == domain]
            if domain_records:
                avg_conf = sum(r.get("confidence", 0) for r in domain_records) / len(domain_records)
                domain_stats[domain]["avg_confidence"] = round(avg_conf, 3)

        # 世代交代履歴
        manager = inference_service.get_succession_manager()
        succession_count = 0
        if manager:
            succession_history = manager.get_succession_history()
            succession_count = len(succession_history)

        return {
            "total_inferences": len(all_history),
            "high_quality_inferences": len(high_quality),
            "succession_count": succession_count,
            "domain_stats": domain_stats,
            "next_succession_at": inference_service.get_succession_manager().succession_threshold if manager else None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-standalone-package")
async def create_standalone_package(
    request: TriggerSuccessionRequest,
    inference_service: InferenceService = Depends(get_inference_service)
):
    """
    完全なスタンドアロンパッケージを生成。

    含まれるもの:
    - トレーニングデータ (全フォーマット)
    - Knowledge Base (DB)
    - README.md (使い方ガイド)
    - run_inference.py (推論実行スクリプト)
    - config.json (設定)

    このパッケージは、単体で動作する完全な推論エンジンになります。
    推論中は使わないDBが付属するため、そのまま使えます。
    """
    try:
        manager = inference_service.get_succession_manager()
        if not manager:
            raise HTTPException(
                status_code=503,
                detail="NurseLog System not available"
            )

        logger.info(f"Creating standalone package for domain: {request.domain_id or 'all'}")

        # デフォルトのDB pathを取得
        db_path = request.db_path or getattr(settings, "DB_PATH", "ilm_athens_medical_db.iath")

        # スタンドアロンパッケージを生成
        result = await manager.create_standalone_package(
            domain_id=request.domain_id,
            min_confidence=request.min_confidence,
            db_path=db_path if os.path.exists(db_path) else None
        )

        if result.get("status") != "success":
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Package creation failed")
            )

        return {
            "status": "success",
            "package_path": result["package_path"],
            "package_name": result["package_name"],
            "training_data_count": result["training_data_count"],
            "generation": result["generation"],
            "size_mb": round(result["size_bytes"] / 1024 / 1024, 2),
            "message": "Standalone package created successfully. This package contains training data and knowledge base, ready to use independently."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Standalone package creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
