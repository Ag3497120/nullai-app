-- SQL Schema for NullAI Public Knowledge Base
-- Compatible with PostgreSQL

-- Enables UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users Table
CREATE TABLE users (
    id VARCHAR PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR UNIQUE,
    username VARCHAR UNIQUE,
    display_name VARCHAR,
    hashed_password VARCHAR,
    auth_provider VARCHAR NOT NULL DEFAULT 'local',
    google_id VARCHAR UNIQUE,
    github_id VARCHAR UNIQUE,
    orcid_id VARCHAR UNIQUE,
    "role" VARCHAR NOT NULL DEFAULT 'viewer',
    is_expert BOOLEAN NOT NULL DEFAULT false,
    is_guest BOOLEAN NOT NULL DEFAULT false,
    expert_verification_status VARCHAR DEFAULT 'none',
    expert_credentials JSONB,
    avatar_url VARCHAR,
    bio TEXT,
    affiliation VARCHAR,
    google_access_token VARCHAR,
    google_refresh_token VARCHAR,
    github_access_token VARCHAR,
    orcid_access_token VARCHAR,
    orcid_refresh_token VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_github_id ON users(github_id);
CREATE INDEX idx_users_orcid_id ON users(orcid_id);


-- Workspaces Table
-- For the public DB, we will likely only have one main public workspace.
CREATE TABLE workspaces (
    id VARCHAR PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR NOT NULL,
    slug VARCHAR UNIQUE NOT NULL,
    description TEXT,
    owner_id VARCHAR NOT NULL REFERENCES users(id),
    is_public BOOLEAN NOT NULL DEFAULT false,
    allow_guest_edit BOOLEAN NOT NULL DEFAULT false,
    allow_guest_view BOOLEAN NOT NULL DEFAULT true,
    db_type VARCHAR DEFAULT 'postgresql',
    db_path VARCHAR,
    db_connection_string VARCHAR,
    tile_count INTEGER DEFAULT 0,
    domain_count INTEGER DEFAULT 0,
    member_count INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_workspaces_slug ON workspaces(slug);
CREATE INDEX idx_workspaces_owner_id ON workspaces(owner_id);

-- Knowledge Tiles Table
CREATE TABLE knowledge_tiles (
    id VARCHAR PRIMARY KEY DEFAULT 'ktile_' || uuid_generate_v4(),
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id),
    domain_id VARCHAR,
    topic VARCHAR NOT NULL,
    content TEXT NOT NULL,
    tags JSONB,
    version INTEGER NOT NULL DEFAULT 1,
    is_latest_version BOOLEAN NOT NULL DEFAULT true,
    based_on_version INTEGER,
    contributor_id VARCHAR REFERENCES users(id),
    confidence_score REAL DEFAULT 0.0,
    verification_type VARCHAR NOT NULL DEFAULT 'none',
    verification_count INTEGER NOT NULL DEFAULT 0,
    last_verified_by_id VARCHAR REFERENCES users(id),
    last_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_tiles_workspace_id ON knowledge_tiles(workspace_id);
CREATE INDEX idx_knowledge_tiles_domain_id ON knowledge_tiles(domain_id);
CREATE INDEX idx_knowledge_tiles_verification_type ON knowledge_tiles(verification_type);
CREATE INDEX idx_knowledge_tiles_contributor_id ON knowledge_tiles(contributor_id);


-- Proposals Table
CREATE TABLE proposals (
    id VARCHAR PRIMARY KEY DEFAULT 'prop_' || uuid_generate_v4(),
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id),
    tile_id VARCHAR REFERENCES knowledge_tiles(id),
    proposer_id VARCHAR NOT NULL REFERENCES users(id),
    status VARCHAR NOT NULL DEFAULT 'pending',
    proposal_type VARCHAR NOT NULL,
    justification TEXT,
    proposed_content JSONB,
    reviewer_id VARCHAR REFERENCES users(id),
    reviewer_comment TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_proposals_workspace_id ON proposals(workspace_id);
CREATE INDEX idx_proposals_tile_id ON proposals(tile_id);
CREATE INDEX idx_proposals_proposer_id ON proposals(proposer_id);
CREATE INDEX idx_proposals_status ON proposals(status);


-- OAuth State Table
CREATE TABLE oauth_states (
    id VARCHAR PRIMARY KEY DEFAULT uuid_generate_v4(),
    state VARCHAR UNIQUE NOT NULL,
    provider VARCHAR NOT NULL,
    redirect_url VARCHAR,
    user_id VARCHAR REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_oauth_states_state ON oauth_states(state);

-- Workspace Members Table (Optional for this setup, but good to have)
CREATE TABLE workspace_members (
    id VARCHAR PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    "role" VARCHAR NOT NULL DEFAULT 'viewer',
    can_read BOOLEAN DEFAULT true,
    can_write BOOLEAN DEFAULT false,
    can_delete BOOLEAN DEFAULT false,
    can_invite BOOLEAN DEFAULT false,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, user_id)
);

CREATE INDEX idx_workspace_members_workspace_id ON workspace_members(workspace_id);
CREATE INDEX idx_workspace_members_user_id ON workspace_members(user_id);
