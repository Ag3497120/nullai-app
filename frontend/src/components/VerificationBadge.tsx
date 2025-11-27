import React from 'react';

interface VerificationMark {
  is_expert_verified: boolean;
  expert_orcid_id?: string;
  expert_name?: string;
  verification_date?: string;
  verification_type: 'none' | 'community' | 'expert' | 'multi_expert';
}

interface VerificationBadgeProps {
  verificationMark?: VerificationMark;
  size?: 'small' | 'medium' | 'large';
  showTooltip?: boolean;
}

const VerificationBadge: React.FC<VerificationBadgeProps> = ({
  verificationMark,
  size = 'medium',
  showTooltip = true
}) => {
  if (!verificationMark || verificationMark.verification_type === 'none') {
    return null;
  }

  const sizeClasses = {
    small: 'badge-sm',
    medium: 'badge-md',
    large: 'badge-lg'
  };

  const getBadgeStyle = () => {
    switch (verificationMark.verification_type) {
      case 'multi_expert':
        return {
          backgroundColor: '#ffd700',
          color: '#000',
          icon: 'gold-star',
          label: 'Multi-Expert Verified'
        };
      case 'expert':
        return {
          backgroundColor: '#4caf50',
          color: '#fff',
          icon: 'check-verified',
          label: 'Expert Verified'
        };
      case 'community':
        return {
          backgroundColor: '#2196f3',
          color: '#fff',
          icon: 'community',
          label: 'Community Reviewed'
        };
      default:
        return null;
    }
  };

  const style = getBadgeStyle();
  if (!style) return null;

  const tooltipContent = verificationMark.is_expert_verified
    ? `Verified by ${verificationMark.expert_name || 'Expert'} (ORCID: ${verificationMark.expert_orcid_id})`
    : 'Community reviewed content';

  return (
    <span
      className={`verification-badge ${sizeClasses[size]}`}
      style={{
        backgroundColor: style.backgroundColor,
        color: style.color,
        display: 'inline-flex',
        alignItems: 'center',
        padding: size === 'small' ? '2px 6px' : size === 'large' ? '6px 12px' : '4px 8px',
        borderRadius: '12px',
        fontSize: size === 'small' ? '10px' : size === 'large' ? '14px' : '12px',
        fontWeight: 600,
        gap: '4px',
        cursor: showTooltip ? 'help' : 'default'
      }}
      title={showTooltip ? tooltipContent : undefined}
    >
      {verificationMark.verification_type === 'multi_expert' && (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
        </svg>
      )}
      {verificationMark.verification_type === 'expert' && (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
        </svg>
      )}
      {verificationMark.verification_type === 'community' && (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
        </svg>
      )}
      <span>{style.label}</span>
    </span>
  );
};

export const ExpertBadge: React.FC<{ orcidId: string; displayName?: string; size?: 'small' | 'medium' | 'large' }> = ({
  orcidId,
  displayName,
  size = 'medium'
}) => {
  return (
    <a
      href={`https://orcid.org/${orcidId}`}
      target="_blank"
      rel="noopener noreferrer"
      className="expert-badge-link"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        textDecoration: 'none',
        color: 'inherit'
      }}
    >
      <img
        src="https://orcid.org/sites/default/files/images/orcid_16x16.png"
        alt="ORCID"
        style={{ width: size === 'small' ? '12px' : size === 'large' ? '20px' : '16px' }}
      />
      <span
        style={{
          backgroundColor: '#a6ce39',
          color: '#fff',
          padding: size === 'small' ? '2px 6px' : '4px 8px',
          borderRadius: '4px',
          fontSize: size === 'small' ? '10px' : size === 'large' ? '14px' : '12px',
          fontWeight: 600
        }}
      >
        {displayName || orcidId}
      </span>
    </a>
  );
};

export default VerificationBadge;
