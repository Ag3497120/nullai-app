/**
 * i18n Configuration for NullAI
 *
 * Supports: Japanese (ja), English (en)
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en.json';
import ja from './locales/ja.json';

// Detect browser language or use localStorage
const getBrowserLanguage = (): string => {
  const savedLang = localStorage.getItem('nullai_language');
  if (savedLang) return savedLang;

  const browserLang = navigator.language.split('-')[0];
  return ['ja', 'en'].includes(browserLang) ? browserLang : 'en';
};

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      ja: { translation: ja }
    },
    lng: getBrowserLanguage(),
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false // React already escapes
    }
  });

export default i18n;
