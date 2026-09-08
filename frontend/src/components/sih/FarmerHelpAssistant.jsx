import React, { useEffect, useRef, useState } from "react";
import { useLanguage } from "../../i18n/LanguageContext";
import { LANGUAGE_META } from "../../i18n/languages";
import { Bot, ChevronRight, MessageCircle, Send, X, Volume2 } from "lucide-react";

const answers = [
  { keys:["book","slot","बुक","स्लॉट"], text:"Book Slot se date, crop aur quantity select karke available mandi slot reserve kar sakte hain." },
  { keys:["queue","token","कतार","टोकन"], text:"Queue page par aapka token, farmers ahead aur estimated waiting time dikhta hai. Future booking par Slot Confirmed status dikhega." },
  { keys:["payment","dbt","भुगतान","पैसा"], text:"Procurement complete hone ke baad payment section mein DBT status, amount aur e-receipt track kar sakte hain." },
  { keys:["centre","center","nearest","पास","केंद्र"], text:"Booking screen par district-assigned procurement centre select hota hai. Location permission dene par nearest centre bhi identify kiya ja sakta hai." },
];

export default function FarmerHelpAssistant() {
  const { t, language } = useLanguage();
  const speechLang = LANGUAGE_META[language]?.speech || "hi-IN";
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const inputRef = useRef(null);
  const panelRef = useRef(null);

  useEffect(() => {
    setMessages(m => m.length ? m : [{ role:"bot", text:`${t("smartSlotBooking")} • ${t("help")}` }]);
  }, [t]);

  useEffect(() => {
    if (!open) return undefined;
    inputRef.current?.focus();
    const onKey = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const ask = (value) => {
    const q = value.trim();
    if (!q) return;
    const lower = q.toLowerCase();
    const hit = answers.find(a => a.keys.some(k => lower.includes(k)));
    const text = hit?.text || "Main KisanSetu ke slot booking, token/queue, procurement, payment aur centre related help de sakta hoon.";
    setMessages(m => [...m, {role:"user",text:q}, {role:"bot",text}]);
    setInput("");
  };

  const speak = (text) => {
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = speechLang;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  };

  return <>
    <button
      type="button"
      onClick={() => setOpen(true)}
      aria-label="Open KisanSetu farmer help"
      title="Farmer Help"
      className="fixed bottom-[5.75rem] left-4 z-[55] flex h-12 items-center gap-2 rounded-full bg-emerald-700 px-4 text-sm font-bold text-white shadow-lg ring-4 ring-white md:bottom-6"
    >
      <MessageCircle size={19} aria-hidden="true" /> <span className="hidden sm:inline">Help</span>
    </button>

    {open && <div className="fixed bottom-[4.75rem] left-3 right-3 z-[190] sm:bottom-4 sm:left-4 sm:right-auto" role="presentation">
      <div ref={panelRef} role="dialog" aria-modal="true" aria-labelledby="ks-help-title" className="w-full max-w-sm overflow-hidden rounded-3xl border bg-white shadow-2xl">
        <div className="flex items-center justify-between bg-emerald-800 p-4 text-white">
          <div><b id="ks-help-title" className="flex items-center gap-2"><Bot size={18} aria-hidden="true" /> {t('instantHelp')}</b><span className="text-[11px] text-emerald-100">{t('voiceTextAssistant')}</span></div>
          <button type="button" onClick={() => setOpen(false)} aria-label="Close farmer help" className="rounded-lg p-1 hover:bg-emerald-700"><X size={19} aria-hidden="true" /></button>
        </div>
        <div className="max-h-72 space-y-2 overflow-y-auto p-3" aria-live="polite">
          {messages.map((m,i)=><div key={`${m.role}-${i}`} className={`flex ${m.role==='user'?'justify-end':''}`}>
            <div className={`max-w-[88%] rounded-2xl px-3 py-2 text-sm ${m.role==='user'?'bg-emerald-100 text-emerald-950':'bg-slate-100 text-slate-800'}`}>
              {m.text}{m.role==='bot'&&<button type="button" aria-label="Listen to answer" className="ml-2 inline-flex align-middle text-emerald-700" onClick={()=>speak(m.text)} title="Listen"><Volume2 size={14} aria-hidden="true" /></button>}
            </div>
          </div>)}
        </div>
        <form onSubmit={(e)=>{e.preventDefault();ask(input);}} className="flex gap-2 border-t p-3">
          <input ref={inputRef} value={input} onChange={e=>setInput(e.target.value)} placeholder={t('botPlaceholder')} aria-label={t('help')} className="min-w-0 flex-1 rounded-xl border px-3 py-2 text-sm outline-none focus:border-emerald-600" />
          <button type="submit" aria-label="Send question" className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-emerald-700 text-white"><Send size={17} aria-hidden="true" /></button>
        </form>
        <div className="flex flex-wrap gap-2 px-3 pb-3">{[t("bookSlot"),t("token"),t("payments")].map(x=><button type="button" key={x} onClick={()=>ask(x)} className="rounded-full border px-2.5 py-1 text-[11px] font-semibold text-slate-600 hover:bg-slate-50">{x}<ChevronRight className="ml-0.5 inline" size={11} aria-hidden="true" /></button>)}</div>
      </div>
    </div>}
  </>;
}
