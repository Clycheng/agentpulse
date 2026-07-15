import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from './locales/en';
import zh from './locales/zh';

const STORAGE_KEY = 'agentpulse_language';

export type AppLanguage = 'zh' | 'en';

function detectInitialLanguage(): AppLanguage {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'zh' || stored === 'en') return stored;
  return navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en';
}

void i18next.use(initReactI18next).init({
  resources: {
    zh: { translation: zh },
    en: { translation: en },
  },
  lng: detectInitialLanguage(),
  fallbackLng: 'zh',
  interpolation: { escapeValue: false },
});

export function setAppLanguage(language: AppLanguage) {
  window.localStorage.setItem(STORAGE_KEY, language);
  void i18next.changeLanguage(language);
}

export function getAppLanguage(): AppLanguage {
  return (i18next.language?.startsWith('en') ? 'en' : 'zh') as AppLanguage;
}

export default i18next;
