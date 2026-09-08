import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { translations, LANGUAGE_META } from './languages';

const LanguageContext = createContext(null);
const supported = Object.keys(LANGUAGE_META);

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => {
    const saved = localStorage.getItem('ks_language');
    return saved && supported.includes(saved) ? saved : 'hi';
  });
  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = language === 'ur' || language === 'sd' ? 'rtl' : 'ltr';
  }, [language]);

  const changeLanguage = (next) => {
    if (!supported.includes(next) || next === language) return;
    setLanguageState(next);
    try { localStorage.setItem('ks_language', next); } catch {}
    document.documentElement.lang = next;
    document.documentElement.dir = next === 'ur' || next === 'sd' ? 'rtl' : 'ltr';
    window.dispatchEvent(new CustomEvent('ks:language-change', { detail: next }));
  };
  const t = (key) => translations[language]?.[key] ?? translations.en?.[key] ?? translations.hi?.[key] ?? key;
  const value = useMemo(() => ({ language, setLanguage: changeLanguage, t, languages: LANGUAGE_META, supportedLanguages: supported }), [language]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}
export function useLanguage() { return useContext(LanguageContext); }
