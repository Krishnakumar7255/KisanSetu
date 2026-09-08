import React from "react";
import { Home as HomeIcon, Ticket, Wallet, CalendarDays, ClipboardCheck, UserRound, MessageSquare, ShieldCheck, Activity, CheckCircle2, Sprout } from "lucide-react";
import { useLanguage } from '../i18n/LanguageContext';

function DesktopNav({ page, setPage, role }) {
  const { t } = useLanguage();
  const items = role === "farmer"
    ? [["Home", HomeIcon, t("home")], ["Book Slot", CalendarDays, t("bookSlot")], ["Queue", Ticket, t("queue")], ["Payments", Wallet, t("payments")], ["Schemes", Sprout, t("schemes")], ["Support", MessageSquare, t("support")], ["Profile", UserRound, t("profile")]]
    : role === "admin"
      ? [["Dashboard", HomeIcon, t("dashboard")], ["Approvals", CheckCircle2, t("pendingRequests")], ["Command Center", Activity, t("biharCommandCenter")], ["Impact", ShieldCheck, t("sihImpact")], ["Profile", UserRound, t("profile")]]
      : [["Dashboard", HomeIcon, t("dashboard")], ["Queue", Ticket, t("queue")], ["Procurement", ClipboardCheck, t("procurement")], ["Profile", UserRound, t("profile")]];
  return <nav className="mx-auto hidden max-w-7xl px-4 pt-3 md:block md:px-7" aria-label="Main navigation">
    <div className="inline-flex rounded-2xl border border-slate-200 bg-white p-1 shadow-sm">
      {items.map(([name, Icon, label]) => <button type="button" key={name} onClick={() => setPage(name)} aria-current={page === name ? "page" : undefined} className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold transition ${page === name ? "bg-emerald-700 text-white shadow-md shadow-emerald-700/20" : "text-slate-500 hover:bg-slate-50 hover:text-emerald-700"}`}>
        <Icon size={17} /> {label}
      </button>)}
    </div>
  </nav>;
}
export default DesktopNav;
