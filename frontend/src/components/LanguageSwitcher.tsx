/**
 * Language Switcher Component
 *
 * Allows users to switch between Japanese and English
 */
import { useTranslation } from 'react-i18next';

type Language = 'ja' | 'en';

interface LanguageOption {
  code: Language;
  label: string;
  flag: string;
}

const languages: LanguageOption[] = [
  { code: 'ja', label: '日本語', flag: '🇯🇵' },
  { code: 'en', label: 'English', flag: '🇬🇧' }
];

export const LanguageSwitcher = () => {
  const { i18n } = useTranslation();

  const changeLanguage = (lang: Language) => {
    i18n.changeLanguage(lang);
    localStorage.setItem('nullai_language', lang);
  };

  const currentLanguage = i18n.language as Language;

  return (
    <div className="language-switcher" style={{
      display: 'flex',
      gap: '8px',
      alignItems: 'center'
    }}>
      {languages.map((lang) => (
        <button
          key={lang.code}
          onClick={() => changeLanguage(lang.code)}
          className={`lang-button ${currentLanguage === lang.code ? 'active' : ''}`}
          style={{
            padding: '6px 12px',
            border: currentLanguage === lang.code ? '2px solid #007bff' : '1px solid #ccc',
            borderRadius: '4px',
            backgroundColor: currentLanguage === lang.code ? '#e7f3ff' : '#fff',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: currentLanguage === lang.code ? 'bold' : 'normal',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            transition: 'all 0.2s'
          }}
        >
          <span>{lang.flag}</span>
          <span>{lang.label}</span>
        </button>
      ))}
    </div>
  );
};

export default LanguageSwitcher;
