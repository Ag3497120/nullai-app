import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import VerificationBadge, { ExpertBadge } from '../components/VerificationBadge';

interface VerificationMark {
  verification_type: 'none' | 'community' | 'expert' | 'multi_expert';
  is_expert_verified: boolean;
  expert_orcid_id?: string;
  expert_name?: string;
  verification_date?: string;
  verification_count: number;
}

interface KnowledgeTile {
  tile_id: string;
  domain_id: string;
  topic: string;
  content_preview: string;
  created_at: string;
  updated_at: string;
  verification_mark: VerificationMark;
  contributor_id?: string;
  contributor_name?: string;
  is_contributor_expert: boolean;
  confidence_score: number;
  tags: string[];
}

interface KnowledgeListResponse {
  tiles: KnowledgeTile[];
  total_count: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

interface KnowledgeStats {
  total_tiles: number;
  by_domain: Record<string, number>;
  by_verification: Record<string, number>;
  expert_contributors: number;
  avg_confidence: number;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const domainLabels: Record<string, string> = {
  medical: 'Medical',
  legal: 'Legal',
  economics: 'Economics',
  programming: 'Programming',
  general: 'General',
};

const domainIcons: Record<string, string> = {
  medical: 'medical',
  legal: 'legal',
  economics: 'economics',
  programming: 'code',
  general: 'general',
};

const KnowledgeBasePage: React.FC = () => {
  const { token, isExpert, user } = useAuth();
  const [tiles, setTiles] = useState<KnowledgeTile[]>([]);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDomain, setSelectedDomain] = useState<string>('');
  const [selectedVerification, setSelectedVerification] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedTile, setSelectedTile] = useState<KnowledgeTile | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editContent, setEditContent] = useState('');

  useEffect(() => {
    fetchTiles();
    fetchStats();
  }, [selectedDomain, selectedVerification, searchQuery, page]);

  const fetchTiles = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (selectedDomain) params.append('domain_id', selectedDomain);
      if (selectedVerification) params.append('verification_type', selectedVerification);
      if (searchQuery) params.append('search', searchQuery);
      params.append('page', page.toString());
      params.append('page_size', '20');

      const response = await fetch(`${API_BASE_URL}/api/knowledge/?${params}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!response.ok) {
        throw new Error('Failed to fetch knowledge tiles');
      }

      const data: KnowledgeListResponse = await response.json();
      setTiles(data.tiles);
      setHasMore(data.has_more);
      setTotalCount(data.total_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/knowledge/stats/summary`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const handleEdit = async () => {
    if (!selectedTile || !editContent.trim()) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/knowledge/${selectedTile.tile_id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ content: editContent }),
      });

      if (!response.ok) {
        throw new Error('Failed to update tile');
      }

      const updatedTile = await response.json();
      setTiles(tiles.map(t => t.tile_id === updatedTile.tile_id ? updatedTile : t));
      setShowEditModal(false);
      setSelectedTile(null);
      setEditContent('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('ja-JP', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.9) return '#4caf50';
    if (score >= 0.7) return '#ff9800';
    return '#f44336';
  };

  return (
    <div className="knowledge-base-page" style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 700, marginBottom: '8px' }}>Knowledge Base</h1>
        <p style={{ color: '#666', fontSize: '14px' }}>
          Expert-verified knowledge tiles with transparent verification status
        </p>
      </div>

      {/* Stats Summary */}
      {stats && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: '16px',
          marginBottom: '24px'
        }}>
          <div style={{ backgroundColor: '#f5f5f5', padding: '16px', borderRadius: '8px', textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#1976d2' }}>{stats.total_tiles}</div>
            <div style={{ fontSize: '12px', color: '#666' }}>Total Tiles</div>
          </div>
          <div style={{ backgroundColor: '#f5f5f5', padding: '16px', borderRadius: '8px', textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#4caf50' }}>{stats.by_verification.expert + stats.by_verification.multi_expert}</div>
            <div style={{ fontSize: '12px', color: '#666' }}>Expert Verified</div>
          </div>
          <div style={{ backgroundColor: '#f5f5f5', padding: '16px', borderRadius: '8px', textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#ff9800' }}>{stats.expert_contributors}</div>
            <div style={{ fontSize: '12px', color: '#666' }}>Expert Contributors</div>
          </div>
          <div style={{ backgroundColor: '#f5f5f5', padding: '16px', borderRadius: '8px', textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#9c27b0' }}>{(stats.avg_confidence * 100).toFixed(0)}%</div>
            <div style={{ fontSize: '12px', color: '#666' }}>Avg Confidence</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{
        display: 'flex',
        gap: '12px',
        marginBottom: '24px',
        flexWrap: 'wrap',
        alignItems: 'center'
      }}>
        <input
          type="text"
          placeholder="Search knowledge..."
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setPage(1);
          }}
          style={{
            padding: '10px 16px',
            border: '1px solid #ddd',
            borderRadius: '8px',
            fontSize: '14px',
            minWidth: '200px',
            flex: '1'
          }}
        />

        <select
          value={selectedDomain}
          onChange={(e) => {
            setSelectedDomain(e.target.value);
            setPage(1);
          }}
          style={{
            padding: '10px 16px',
            border: '1px solid #ddd',
            borderRadius: '8px',
            fontSize: '14px',
            backgroundColor: 'white'
          }}
        >
          <option value="">All Domains</option>
          <option value="medical">Medical</option>
          <option value="legal">Legal</option>
          <option value="economics">Economics</option>
          <option value="programming">Programming</option>
          <option value="general">General</option>
        </select>

        <select
          value={selectedVerification}
          onChange={(e) => {
            setSelectedVerification(e.target.value);
            setPage(1);
          }}
          style={{
            padding: '10px 16px',
            border: '1px solid #ddd',
            borderRadius: '8px',
            fontSize: '14px',
            backgroundColor: 'white'
          }}
        >
          <option value="">All Verification</option>
          <option value="multi_expert">Multi-Expert</option>
          <option value="expert">Expert</option>
          <option value="community">Community</option>
          <option value="none">Unverified</option>
        </select>
      </div>

      {/* Results count */}
      <div style={{ marginBottom: '16px', color: '#666', fontSize: '14px' }}>
        {totalCount} knowledge tiles found
      </div>

      {/* Loading / Error */}
      {loading && <div style={{ textAlign: 'center', padding: '40px' }}>Loading...</div>}
      {error && <div style={{ textAlign: 'center', padding: '40px', color: '#f44336' }}>{error}</div>}

      {/* Tiles Grid */}
      {!loading && !error && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {tiles.map((tile) => (
            <div
              key={tile.tile_id}
              style={{
                backgroundColor: 'white',
                border: '1px solid #e0e0e0',
                borderRadius: '12px',
                padding: '20px',
                boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
                transition: 'box-shadow 0.2s',
                cursor: 'pointer'
              }}
              onClick={() => setSelectedTile(tile)}
            >
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{
                    padding: '4px 8px',
                    backgroundColor: '#e3f2fd',
                    color: '#1976d2',
                    borderRadius: '4px',
                    fontSize: '12px',
                    fontWeight: 600
                  }}>
                    {domainLabels[tile.domain_id] || tile.domain_id}
                  </span>
                  <VerificationBadge verificationMark={tile.verification_mark} size="small" />
                </div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '12px'
                }}>
                  <span style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: getConfidenceColor(tile.confidence_score)
                  }} />
                  <span style={{ color: '#666' }}>{(tile.confidence_score * 100).toFixed(0)}%</span>
                </div>
              </div>

              {/* Topic */}
              <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px', color: '#333' }}>
                {tile.topic}
              </h3>

              {/* Preview */}
              <p style={{ fontSize: '14px', color: '#666', marginBottom: '16px', lineHeight: '1.6' }}>
                {tile.content_preview}
              </p>

              {/* Tags */}
              <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
                {tile.tags.map((tag, i) => (
                  <span
                    key={i}
                    style={{
                      padding: '2px 8px',
                      backgroundColor: '#f5f5f5',
                      borderRadius: '12px',
                      fontSize: '11px',
                      color: '#666'
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>

              {/* Footer */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                borderTop: '1px solid #eee',
                paddingTop: '12px',
                fontSize: '12px',
                color: '#999'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {tile.is_contributor_expert && tile.verification_mark.expert_orcid_id ? (
                    <ExpertBadge
                      orcidId={tile.verification_mark.expert_orcid_id}
                      displayName={tile.contributor_name}
                      size="small"
                    />
                  ) : (
                    <span>by {tile.contributor_name || 'Anonymous'}</span>
                  )}
                </div>
                <span>Updated: {formatDate(tile.updated_at)}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {!loading && tiles.length > 0 && (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: '8px',
          marginTop: '24px'
        }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              padding: '8px 16px',
              border: '1px solid #ddd',
              borderRadius: '8px',
              backgroundColor: page === 1 ? '#f5f5f5' : 'white',
              cursor: page === 1 ? 'not-allowed' : 'pointer'
            }}
          >
            Previous
          </button>
          <span style={{ padding: '8px 16px' }}>Page {page}</span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={!hasMore}
            style={{
              padding: '8px 16px',
              border: '1px solid #ddd',
              borderRadius: '8px',
              backgroundColor: !hasMore ? '#f5f5f5' : 'white',
              cursor: !hasMore ? 'not-allowed' : 'pointer'
            }}
          >
            Next
          </button>
        </div>
      )}

      {/* Detail Modal */}
      {selectedTile && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000
          }}
          onClick={() => setSelectedTile(null)}
        >
          <div
            style={{
              backgroundColor: 'white',
              borderRadius: '16px',
              padding: '24px',
              maxWidth: '600px',
              width: '90%',
              maxHeight: '80vh',
              overflow: 'auto'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
              <div>
                <span style={{
                  padding: '4px 8px',
                  backgroundColor: '#e3f2fd',
                  color: '#1976d2',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 600,
                  marginRight: '8px'
                }}>
                  {domainLabels[selectedTile.domain_id]}
                </span>
                <VerificationBadge verificationMark={selectedTile.verification_mark} size="medium" />
              </div>
              <button
                onClick={() => setSelectedTile(null)}
                style={{
                  border: 'none',
                  background: 'none',
                  fontSize: '24px',
                  cursor: 'pointer',
                  color: '#999'
                }}
              >
                x
              </button>
            </div>

            <h2 style={{ fontSize: '22px', fontWeight: 700, marginBottom: '16px' }}>
              {selectedTile.topic}
            </h2>

            <p style={{ fontSize: '14px', lineHeight: '1.8', color: '#444', marginBottom: '20px' }}>
              {selectedTile.content_preview}
            </p>

            {/* Verification Info */}
            <div style={{
              backgroundColor: '#f9f9f9',
              padding: '16px',
              borderRadius: '8px',
              marginBottom: '20px'
            }}>
              <h4 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px' }}>Verification Status</h4>
              <div style={{ fontSize: '13px', color: '#666' }}>
                <p>Type: {selectedTile.verification_mark.verification_type}</p>
                {selectedTile.verification_mark.is_expert_verified && (
                  <>
                    <p>Verified by: {selectedTile.verification_mark.expert_name}</p>
                    <p>ORCID: {selectedTile.verification_mark.expert_orcid_id}</p>
                    <p>Date: {selectedTile.verification_mark.verification_date}</p>
                  </>
                )}
                <p>Confidence Score: {(selectedTile.confidence_score * 100).toFixed(0)}%</p>
              </div>
            </div>

            {/* Warning for guest edits */}
            {!token && (
              <div style={{
                backgroundColor: '#fff3e0',
                border: '1px solid #ffcc80',
                padding: '12px',
                borderRadius: '8px',
                marginBottom: '16px',
                fontSize: '13px',
                color: '#e65100'
              }}>
                Guest edits will not receive a verification mark. Log in with ORCID for expert verification.
              </div>
            )}

            {/* Edit Button */}
            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={() => {
                  setEditContent(selectedTile.content_preview);
                  setShowEditModal(true);
                }}
                style={{
                  padding: '10px 20px',
                  backgroundColor: '#1976d2',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 600
                }}
              >
                Edit Content
              </button>
              <button
                onClick={() => setSelectedTile(null)}
                style={{
                  padding: '10px 20px',
                  backgroundColor: '#f5f5f5',
                  color: '#333',
                  border: '1px solid #ddd',
                  borderRadius: '8px',
                  cursor: 'pointer'
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {showEditModal && selectedTile && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1001
          }}
        >
          <div
            style={{
              backgroundColor: 'white',
              borderRadius: '16px',
              padding: '24px',
              maxWidth: '600px',
              width: '90%'
            }}
          >
            <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>
              Edit: {selectedTile.topic}
            </h3>

            {/* Edit permission info */}
            <div style={{
              backgroundColor: isExpert ? '#e8f5e9' : token ? '#e3f2fd' : '#fff3e0',
              padding: '12px',
              borderRadius: '8px',
              marginBottom: '16px',
              fontSize: '13px'
            }}>
              {isExpert ? (
                <span style={{ color: '#2e7d32' }}>
                  Your edit will be marked as Expert Verified (ORCID: {user?.orcidId})
                </span>
              ) : token ? (
                <span style={{ color: '#1565c0' }}>
                  Your edit will be marked as Community Reviewed
                </span>
              ) : (
                <span style={{ color: '#e65100' }}>
                  Guest edit - No verification mark will be applied
                </span>
              )}
            </div>

            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              style={{
                width: '100%',
                height: '200px',
                padding: '12px',
                border: '1px solid #ddd',
                borderRadius: '8px',
                fontSize: '14px',
                resize: 'vertical',
                marginBottom: '16px'
              }}
            />

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => {
                  setShowEditModal(false);
                  setEditContent('');
                }}
                style={{
                  padding: '10px 20px',
                  backgroundColor: '#f5f5f5',
                  color: '#333',
                  border: '1px solid #ddd',
                  borderRadius: '8px',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleEdit}
                style={{
                  padding: '10px 20px',
                  backgroundColor: '#4caf50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 600
                }}
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default KnowledgeBasePage;
