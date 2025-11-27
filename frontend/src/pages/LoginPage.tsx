import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const LoginPage: React.FC = () => {
  const { t } = useTranslation();
  const [error, setError] = useState('');
  const [loadingProvider, setLoadingProvider] = useState<string | null>(null);
  const { continueAsGuest } = useAuth();

  const handleOAuthLogin = (provider: 'google' | 'github' | 'orcid') => {
    setError('');
    setLoadingProvider(provider);
    
    // 現在のフロントエンドのURLをリダイレクト先としてバックエンドに渡す
    const redirectUrl = window.location.origin + '/';
    window.location.href = `${API_BASE_URL}/api/oauth/${provider}/login?redirect_url=${encodeURIComponent(redirectUrl)}`;
  };

  const handleGuestAccess = () => {
    continueAsGuest();
  };

  const AuthButton = ({ provider, providerName, icon, color, textColor, onClick }: any) => (
    <button
      onClick={onClick}
      disabled={loadingProvider === provider}
      style={{
        width: '100%',
        padding: '12px',
        marginBottom: '15px',
        backgroundColor: color,
        color: textColor,
        border: 'none',
        borderRadius: '8px',
        cursor: 'pointer',
        fontSize: '16px',
        fontWeight: 600,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '10px'
      }}
    >
      {icon}
      {loadingProvider === provider ? `Redirecting to ${providerName}...` : `Continue with ${providerName}`}
    </button>
  );

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">NullAI Knowledge</h1>
          <p className="auth-subtitle">Public Knowledge Base Editor</p>
        </div>

        {error && <div className="error-message" style={{marginBottom: '15px'}}>{error}</div>}
        
        {/* OAuth Login Buttons */}
        <AuthButton
          provider="google"
          providerName="Google"
          onClick={() => handleOAuthLogin('google')}
          color="#4285F4"
          textColor="white"
          icon={<img src="https://www.svgrepo.com/show/475656/google-color.svg" alt="Google" style={{width: '20px'}} />}
        />
        <AuthButton
          provider="github"
          providerName="GitHub"
          onClick={() => handleOAuthLogin('github')}
          color="#333"
          textColor="white"
          icon={<img src="https://www.svgrepo.com/show/512317/github-142.svg" alt="GitHub" style={{width: '20px', filter: 'invert(1)'}} />}
        />
        <AuthButton
          provider="orcid"
          providerName="ORCID"
          onClick={() => handleOAuthLogin('orcid')}
          color="#a6ce39"
          textColor="white"
          icon={<img src="https://orcid.org/sites/default/files/images/orcid_16x16.png" alt="ORCID" style={{ width: '20px' }} />}
        />
        <p style={{fontSize: '12px', color: '#666', marginTop: '-5px', marginBottom: '20px', textAlign: 'center'}}>
          ORCID login grants an "Expert" verification badge.
        </p>

        <div className="divider" style={{
          display: 'flex',
          alignItems: 'center',
          marginBottom: '20px',
          color: '#666'
        }}>
          <span style={{ flex: 1, borderBottom: '1px solid #ddd' }}></span>
          <span style={{ padding: '0 10px' }}>or</span>
          <span style={{ flex: 1, borderBottom: '1px solid #ddd' }}></span>
        </div>

        {/* Guest Access Button */}
        <button
          onClick={handleGuestAccess}
          className="guest-button"
          style={{
            width: '100%',
            padding: '12px',
            backgroundColor: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '16px',
            fontWeight: 600
          }}
        >
          {t('auth.continueAsGuest')}
        </button>
      </div>
    </div>
  );
};
