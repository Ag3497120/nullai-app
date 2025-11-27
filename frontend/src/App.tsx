import { useState } from 'react';
import './App.css';
import { useTranslation } from 'react-i18next';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LoginPage } from './pages/LoginPage';
import { DomainEditorPage } from './pages/DomainEditorPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import { ExpertBadge } from './components/VerificationBadge';
import LanguageSwitcher from './components/LanguageSwitcher';

type AppView = 'knowledge' | 'domains' | 'proposals';

const AppContent = () => {
  const { t } = useTranslation();
  const { isAuthenticated, isGuest, isExpert, isLoading, user, logout } = useAuth();
  const [appView, setAppView] = useState<AppView>('knowledge');

  if (isLoading) {
    return (
      <div className="loading-container">
        <p>{t('common.loading')}</p>
      </div>
    );
  }

  if (!isAuthenticated && !isGuest) {
    return (
      <div className="app-container">
        <header className="app-header">
          <div className="header-content">
            <div className="header-title">
              <h1>NullAI Knowledge</h1>
              <p className="tagline">Public Knowledge Base Editor</p>
            </div>
            <LanguageSwitcher />
          </div>
        </header>
        <LoginPage />
      </div>
    );
  }

  // Main application (authenticated or guest)
  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <div className="header-title">
            <h1>NullAI Knowledge</h1>
            <p className="tagline">Public Knowledge Base Editor</p>
          </div>
          <nav className="nav-tabs">
            <button
              className={`nav-tab ${appView === 'knowledge' ? 'active' : ''}`}
              onClick={() => setAppView('knowledge')}
            >
              {t('nav.knowledge')}
            </button>
            <button
              className={`nav-tab ${appView === 'domains' ? 'active' : ''}`}
              onClick={() => setAppView('domains')}
            >
              {t('nav.domains')}
            </button>
            {!isGuest && (
              <button
                className={`nav-tab ${appView === 'proposals' ? 'active' : ''}`}
                onClick={() => setAppView('proposals')}
              >
                {t('nav.proposals')}
              </button>
            )}
          </nav>
          <div className="user-info">
            <LanguageSwitcher />
            {isGuest ? (
              <>
                <span className="guest-label">{t('auth.guest')}</span>
                <button onClick={() => {
                  localStorage.removeItem('is_guest');
                  localStorage.removeItem('auth_token');
                  window.location.reload();
                  }} className="login-button">
                  {t('auth.signIn')}
                </button>
              </>
            ) : (
              <>
                {isExpert && user?.orcid_id ? (
                  <ExpertBadge orcidId={user.orcid_id} displayName={user.display_name} size="small" />
                ) : (
                  <span className="user-email">{user?.display_name || user?.email}</span>
                )}
                <button onClick={logout} className="logout-button">
                  {t('auth.logout')}
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      {isGuest && (
        <div className="guest-banner" style={{
          backgroundColor: '#fff3cd',
          padding: '10px 20px',
          textAlign: 'center',
          borderBottom: '1px solid #ffc107'
        }}>
          <span>You are browsing as a guest. </span>
          <button
            onClick={() => {
              localStorage.removeItem('is_guest');
              localStorage.removeItem('auth_token');
              window.location.reload();
            }}
            style={{
              background: 'none',
              border: 'none',
              color: '#856404',
              textDecoration: 'underline',
              cursor: 'pointer',
              fontWeight: 600
            }}
          >
            Sign in
          </button>
          <span> to edit and contribute.</span>
        </div>
      )}

      <main className="main-content">
        {appView === 'knowledge' && <KnowledgeBasePage />}
        {appView === 'domains' && <DomainEditorPage />}
        {appView === 'proposals' && !isGuest && <ProposalsPage />}
      </main>
    </div>
  );
};

// Placeholder for ProposalsPage - to be implemented
const ProposalsPage = () => {
  const { t } = useTranslation();
  return (
    <div className="proposals-page" style={{padding: "20px"}}>
      <h2>{t('proposals.title')}</h2>
      <p>{t('proposals.description')}</p>
      {/* Proposal list will be implemented here */}
    </div>
  );
};

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
