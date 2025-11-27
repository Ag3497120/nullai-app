from sqlalchemy import Column, String, DateTime, JSON, Boolean, ForeignKey, Text, Integer
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid

Base = declarative_base()


class User(Base):
    """ユーザーモデル - 複数の認証方法をサポート"""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=True, index=True)  # OAuth時はnullable
    username = Column(String, unique=True, nullable=True, index=True)
    display_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)  # OAuth時はnullable

    # 認証プロバイダー情報
    auth_provider = Column(String, default="local")  # local, google, github, orcid
    google_id = Column(String, unique=True, nullable=True, index=True)
    github_id = Column(String, unique=True, nullable=True, index=True)
    orcid_id = Column(String, unique=True, nullable=True, index=True)

    # 権限とステータス
    role = Column(String, default="viewer", nullable=False)  # viewer, expert, reviewer, curator, admin
    is_expert = Column(Boolean, default=False)
    is_guest = Column(Boolean, default=False)
    expert_verification_status = Column(String, default="none")  # none, pending, approved, rejected
    expert_credentials = Column(JSON)

    # プロフィール情報
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    affiliation = Column(String, nullable=True)

    # OAuth tokens (暗号化して保存すべき)
    google_access_token = Column(String, nullable=True)
    google_refresh_token = Column(String, nullable=True)
    github_access_token = Column(String, nullable=True)
    orcid_access_token = Column(String, nullable=True)
    orcid_refresh_token = Column(String, nullable=True)

    # タイムスタンプ
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    # リレーションシップ
    workspaces = relationship("Workspace", back_populates="owner", cascade="all, delete-orphan")
    workspace_members = relationship("WorkspaceMember", back_populates="user", cascade="all, delete-orphan")
    proposals = relationship("Proposal", back_populates="proposer", foreign_keys="[Proposal.proposer_id]")
    reviews = relationship("Proposal", back_populates="reviewer", foreign_keys="[Proposal.reviewer_id]")
    contributions = relationship("KnowledgeTile", back_populates="contributor")


class KnowledgeTile(Base):
    """知識タイルモデル"""
    __tablename__ = "knowledge_tiles"

    id = Column(String, primary_key=True, default=lambda: f"ktile_{uuid.uuid4().hex}")
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    domain_id = Column(String, index=True)
    topic = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON, nullable=True)

    # バージョン管理
    version = Column(Integer, default=1)
    is_latest_version = Column(Boolean, default=True)
    based_on_version = Column(Integer, nullable=True)
    
    # 貢献者と検証
    contributor_id = Column(String, ForeignKey("users.id"), nullable=True)
    confidence_score = Column(Float, default=0.0)
    verification_type = Column(String, default="none", index=True)  # none, community, expert, multi_expert
    verification_count = Column(Integer, default=0)
    last_verified_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    last_verified_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace = relationship("Workspace")
    contributor = relationship("User", back_populates="contributions")
    last_verified_by = relationship("User", foreign_keys=[last_verified_by_id])
    proposals = relationship("Proposal", back_populates="tile")


class Proposal(Base):
    """編集提案モデル"""
    __tablename__ = "proposals"

    id = Column(String, primary_key=True, default=lambda: f"prop_{uuid.uuid4().hex}")
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    tile_id = Column(String, ForeignKey("knowledge_tiles.id"), nullable=True) # 新規作成時はnull
    proposer_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    status = Column(String, default="pending", index=True) # pending, approved, rejected
    proposal_type = Column(String, nullable=False) # create, update, delete
    
    justification = Column(Text)
    proposed_content = Column(JSON)
    
    reviewer_id = Column(String, ForeignKey("users.id"), nullable=True)
    reviewer_comment = Column(Text)
    reviewed_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace = relationship("Workspace")
    tile = relationship("KnowledgeTile", back_populates="proposals")
    proposer = relationship("User", back_populates="proposals", foreign_keys=[proposer_id])
    reviewer = relationship("User", back_populates="reviews", foreign_keys=[reviewer_id])




class Workspace(Base):
    """ワークスペース - ユーザーごとの独立したDB環境"""
    __tablename__ = "workspaces"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)  # URLフレンドリーな識別子
    description = Column(Text, nullable=True)

    # オーナー情報
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)

    # 設定
    is_public = Column(Boolean, default=False)  # 公開ワークスペース
    allow_guest_edit = Column(Boolean, default=True)  # ゲストによる編集を許可
    allow_guest_view = Column(Boolean, default=True)  # ゲストによる閲覧を許可

    # データベース設定
    db_type = Column(String, default="sqlite")  # sqlite, postgresql
    db_path = Column(String, nullable=True)  # SQLiteの場合のファイルパス
    db_connection_string = Column(String, nullable=True)  # PostgreSQLの場合

    # 統計情報
    tile_count = Column(Integer, default=0)
    domain_count = Column(Integer, default=0)
    member_count = Column(Integer, default=1)

    # タイムスタンプ
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # リレーションシップ
    owner = relationship("User", back_populates="workspaces")
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")


class WorkspaceMember(Base):
    """ワークスペースメンバー - 共同作業者の管理"""
    __tablename__ = "workspace_members"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # 権限
    role = Column(String, default="viewer")  # viewer, editor, admin
    can_read = Column(Boolean, default=True)
    can_write = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    can_invite = Column(Boolean, default=False)

    # タイムスタンプ
    joined_at = Column(DateTime, default=datetime.utcnow)

    # リレーションシップ
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", back_populates="workspace_members")


class OAuthState(Base):
    """OAuth認証の一時的なstate管理"""
    __tablename__ = "oauth_states"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    state = Column(String, unique=True, nullable=False, index=True)
    provider = Column(String, nullable=False)  # google, orcid
    redirect_url = Column(String, nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # 既存ユーザーとの連携時

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)  # 10分で期限切れ

    def is_expired(self):
        return datetime.utcnow() > self.expires_at
