"""
知識ベースサービス (ナレッジタイルと提案)
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import uuid4
from datetime import datetime

from backend.app.database import models
from backend.app import schemas

class KnowledgeService:
    
    def get_tile(self, db: Session, tile_id: str) -> Optional[models.KnowledgeTile]:
        """IDで単一の知識タイルを取得"""
        return db.query(models.KnowledgeTile).filter(models.KnowledgeTile.id == tile_id, models.KnowledgeTile.is_latest_version == True).first()

    def list_tiles(
        self, 
        db: Session, 
        page: int = 1, 
        page_size: int = 20, 
        domain_id: Optional[str] = None,
        verification_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> (List[models.KnowledgeTile], int):
        """
        知識タイルをページネーション付きで一覧取得
        """
        query = db.query(models.KnowledgeTile).filter(models.KnowledgeTile.is_latest_version == True)
        
        if domain_id:
            query = query.filter(models.KnowledgeTile.domain_id == domain_id)
        if verification_type:
            query = query.filter(models.KnowledgeTile.verification_type == verification_type)
        if search:
            search_lower = f"%{search.lower()}%"
            query = query.filter(
                (func.lower(models.KnowledgeTile.topic).like(search_lower)) |
                (func.lower(models.KnowledgeTile.content).like(search_lower))
            )
            
        total_count = query.count()
        
        tiles = query.order_by(models.KnowledgeTile.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return tiles, total_count

    def update_tile(
        self,
        db: Session,
        tile_id: str,
        content: str,
        user: models.User,
    ) -> models.KnowledgeTile:
        """知識タイルを更新し、検証マークを適用"""
        
        db_tile = self.get_tile(db, tile_id)
        if not db_tile:
            return None

        # 貢献者と検証タイプの決定
        auth_provider = getattr(user, 'auth_provider', None)
        contributor_id = user.id
        
        if auth_provider == 'orcid':
            verification_type = "expert"
            confidence = 0.9
            # 既存の検証がexpertであればmulti-expertに格上げすることも可能
            if db_tile.verification_type == 'expert' and db_tile.last_verified_by_id != user.id:
                verification_type = 'multi_expert'
        else: # google, github
            verification_type = "community"
            confidence = 0.7

        # 新しいバージョンを作成 (論理削除)
        db_tile.is_latest_version = False
        db.add(db_tile)
        
        new_tile = models.KnowledgeTile(
            id=db_tile.id,
            workspace_id=db_tile.workspace_id,
            domain_id=db_tile.domain_id,
            topic=db_tile.topic,
            content=content,
            tags=db_tile.tags,
            version=db_tile.version + 1,
            based_on_version=db_tile.version,
            contributor_id=contributor_id,
            confidence_score=confidence,
            verification_type=verification_type,
            verification_count=db_tile.verification_count + 1,
            last_verified_by_id=user.id,
            last_verified_at=datetime.utcnow()
        )

        db.add(new_tile)
        db.commit()
        db.refresh(new_tile)
        
        return new_tile

# 依存性注入用
def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService()
