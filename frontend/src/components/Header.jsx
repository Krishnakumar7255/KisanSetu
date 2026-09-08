import React from "react";
import { Bell, LogOut, Languages } from "lucide-react";
import { IconButton } from "./UI";
import { useLanguage } from '../i18n/LanguageContext';

function Header({ user, onLogout, onBell, onProfile, unread = 0 }) {
  const { language, setLanguage, t, languages, supportedLanguages } = useLanguage();
  return <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/95 backdrop-blur-xl">
    <div className="mx-auto flex h-[70px] max-w-7xl items-center justify-between px-4 md:px-7">
      <div className="flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-50 text-xl ring-1 ring-emerald-100">🌾</div>
        <div><div className="text-[19px] font-black leading-none text-emerald-800">KisanSetu</div><div className="mt-1 text-[11px] font-semibold text-slate-500">{t('smartSlotBooking')}</div></div>
      </div>
      <div className="flex items-center gap-2 rounded-full bg-indigo-50 px-2 py-1.5 text-xs font-bold text-slate-700">
        <Languages size={17} className="text-emerald-700" />
        <select aria-label={t('switchLanguage')} value={language} onChange={(e) => setLanguage(e.target.value)} className="max-w-[155px] cursor-pointer bg-transparent font-bold outline-none">
          {supportedLanguages.map(code => <option key={code} value={code}>{languages[code].native}</option>)}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <button type="button" onClick={onBell} aria-label={t("notifications")} className="relative grid h-10 w-10 place-items-center rounded-xl text-slate-700 hover:bg-slate-50"><Bell size={21}/>{unread > 0 && <span className="absolute right-2 top-1 h-2.5 w-2.5 rounded-full bg-red-600 ring-2 ring-white" />}</button>
        <button type="button" onClick={onProfile} className="hidden max-w-[180px] truncate rounded-full bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-100 sm:block">{user?.name || user?.centre_id || t('farmer')}</button>
        <IconButton label={t("logout")} onClick={onLogout}><LogOut size={18}/></IconButton>
      </div>
    </div>
  </header>;
}
export { Header };
