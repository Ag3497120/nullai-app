// APIサーバーのURL
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface QuestionPayload {
    question: string;
    session_id?: string | null;
    domain_id?: string;
}

interface ApiResponse {
    session_id: string;
    question: string;
    response: string;
    status: string;
    confidence?: number;
    memory_augmented?: boolean;
    detail?: string;
}

/**
 * ローカルストレージからトークンを取得
 */
const getAuthToken = (): string | null => {
    return localStorage.getItem('auth_token');
};

/**
 * 認証ヘッダーを生成
 */
const getAuthHeaders = (): HeadersInit => {
    const token = getAuthToken();
    const headers: HeadersInit = {
        'Content-Type': 'application/json',
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
};

/**
 * APIエラーをハンドリング
 */
const handleApiError = async (response: Response): Promise<never> => {
    if (response.status === 401) {
        // トークン期限切れ - ログアウト処理
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        window.location.reload();
    }

    const errorData = await response.json().catch(() => ({ detail: "An unknown error occurred" }));
    throw new Error(errorData.detail || `Request failed with status ${response.status}`);
};

/**
 * バックエンドに質問を送信し、推論結果を受け取る
 * @param payload - 送信する質問データ
 * @returns - APIからのレスポンス
 */
export const submitQuestion = async (payload: QuestionPayload): Promise<ApiResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/questions/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        await handleApiError(response);
    }

    return response.json();
};

/**
 * ドメイン一覧を取得
 */
export const fetchDomains = async (): Promise<any[]> => {
    const response = await fetch(`${API_BASE_URL}/api/domains/`, {
        method: 'GET',
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        await handleApiError(response);
    }

    return response.json();
};

/**
 * 特定のドメインを取得
 */
export const fetchDomain = async (domainId: string): Promise<any> => {
    const response = await fetch(`${API_BASE_URL}/api/domains/${domainId}`, {
        method: 'GET',
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        await handleApiError(response);
    }

    return response.json();
};

/**
 * ドメインを更新
 */
export const updateDomain = async (domainId: string, data: any): Promise<any> => {
    const response = await fetch(`${API_BASE_URL}/api/domains/${domainId}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
    });

    if (!response.ok) {
        await handleApiError(response);
    }

    return response.json();
};

/**
 * システム状態を取得
 */
export const fetchSystemStatus = async (): Promise<any> => {
    const response = await fetch(`${API_BASE_URL}/api/system/status`, {
        method: 'GET',
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        await handleApiError(response);
    }

    return response.json();
};

// --- 編集提案API ---

export interface Proposal {
    proposal_id: string;
    proposal_type: 'create' | 'update' | 'delete' | 'merge';
    domain_id: string;
    tile_id?: string;
    title: string;
    description: string;
    proposed_content?: any;
    proposed_coordinates?: number[];
    justification: string;
    status: 'pending' | 'under_review' | 'approved' | 'rejected';
    created_by: string;
    created_at: string;
    reviewed_by?: string;
    reviewed_at?: string;
    reviewer_comment?: string;
    validation_score?: number;
}

export interface CreateProposalPayload {
    proposal_type: 'create' | 'update' | 'delete' | 'merge';
    domain_id: string;
    tile_id?: string;
    title: string;
    description: string;
    proposed_content?: any;
    proposed_coordinates?: number[];
    justification: string;
}

/**
 * 提案一覧を取得
 */
export const fetchProposals = async (status?: string, domainId?: string): Promise<Proposal[]> => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (domainId) params.append('domain_id', domainId);

    const url = `${API_BASE_URL}/api/proposals/${params.toString() ? '?' + params.toString() : ''}`;
    const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        await handleApiError(response);
    }

    return response.json();
};

/**
 * 自分の提案一覧を取得
 */
export const fetchMyProposals = async (): Promise<Proposal[]> => {
    const response = await fetch(`${API_BASE_URL}/api/proposals/my`, {
        method: 'GET',
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        await handleApiError(response);
    }

    return response.json();
};

/**
 * 提案を作成
 */
export const createProposal = async (payload: CreateProposalPayload): Promise<Proposal> => {
    const response = await fetch(`${API_BASE_URL}/api/proposals/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        await handleApiError(response);
    }

    return response.json();
};

/**
 * 提案をレビュー（承認/却下）
 */
export const reviewProposal = async (
    proposalId: string,
    status: 'approved' | 'rejected',
    reviewerComment: string,
    validationScore?: number
): Promise<any> => {
    const response = await fetch(`${API_BASE_URL}/api/proposals/${proposalId}/review`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({
            status,
            reviewer_comment: reviewerComment,
            validation_score: validationScore,
        }),
    });

    if (!response.ok) {
        await handleApiError(response);
    }

    return response.json();
};

/**
 * 提案を削除
 */
export const deleteProposal = async (proposalId: string): Promise<any> => {
    const response = await fetch(`${API_BASE_URL}/api/proposals/${proposalId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        await handleApiError(response);
    }

    return response.json();
};
