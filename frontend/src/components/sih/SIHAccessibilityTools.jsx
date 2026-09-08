import React, { useEffect, useRef, useState } from "react";
import { Accessibility, Contrast, Volume2, VolumeX, ZoomIn, ZoomOut, RotateCcw, X } from "lucide-react";

const clamp = (value) => Math.min(125, Math.max(90, Number(value) || 100));

export default function SIHAccessibilityTools() {
  const [open, setOpen] = useState(false);
  const [fontScale, setFontScale] = useState(() => clamp(localStorage.getItem("ks_font_scale") || 100));
  const [contrast, setContrast] = useState(() => localStorage.getItem("ks_high_contrast") === "true");
  const [reduced, setReduced] = useState(() => localStorage.getItem("ks_reduced_motion") === "true");
  const [speaking, setSpeaking] = useState(false);
  const closeRef = useRef(null);

  useEffect(() => {
    document.documentElement.style.fontSize = `${fontScale}%`;
    document.documentElement.classList.toggle("ks-high-contrast", contrast);
    document.documentElement.classList.toggle("ks-reduced-motion", reduced);
    localStorage.setItem("ks_font_scale", String(fontScale));
    localStorage.setItem("ks_high_contrast", String(contrast));
    localStorage.setItem("ks_reduced_motion", String(reduced));
  }, [fontScale, contrast, reduced]);

  useEffect(() => {
    if (!open) return undefined;
    closeRef.current?.focus();
    const onKey = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  const readPage = () => {
    if (!("speechSynthesis" in window)) return;
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const main = document.querySelector("main");
    const text = (main?.innerText || document.body.innerText || "").replace(/\s+/g, " ").trim();
    if (!text) return;
    const utterance = new SpeechSynthesisUtterance(text.slice(0, 5000));
    utterance.lang = window.__KS_SPEECH_LANG__ || "hi-IN";
    utterance.rate = 0.92;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  };

  const reset = () => {
    setFontScale(100);
    setContrast(false);
    setReduced(false);
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  };

  return <>
    <button
      type="button"
      onClick={() => setOpen(true)}
      aria-label="Accessibility options"
      title="Accessibility"
      className="fixed bottom-[5.75rem] right-4 z-[55] grid h-12 w-12 place-items-center rounded-full bg-indigo-700 text-white shadow-lg ring-4 ring-white hover:bg-indigo-800 md:bottom-6"
    >
      <Accessibility size={22} aria-hidden="true" />
    </button>

    {open && <div
      className="fixed inset-0 z-[200] flex items-end justify-center bg-slate-950/50 p-3 backdrop-blur-sm sm:items-center"
      role="presentation"
      onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="ks-accessibility-title"
        className="max-h-[calc(100dvh-1.5rem)] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-5 shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 id="ks-accessibility-title" className="text-lg font-black text-slate-900">Accessibility & Voice</h2>
            <p className="text-xs text-slate-500">Farmer-friendly controls</p>
          </div>
          <button ref={closeRef} type="button" onClick={() => setOpen(false)} aria-label="Close accessibility options" className="rounded-xl p-2 hover:bg-slate-100">
            <X size={20} aria-hidden="true" />
          </button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3">
          <button type="button" onClick={() => setFontScale(v => clamp(v - 10))} disabled={fontScale <= 90} className="rounded-2xl border p-4 text-left hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
            <ZoomOut size={19} aria-hidden="true" /><b className="mt-2 block">Smaller text</b><span className="text-xs text-slate-500">{fontScale}%</span>
          </button>
          <button type="button" onClick={() => setFontScale(v => clamp(v + 10))} disabled={fontScale >= 125} className="rounded-2xl border p-4 text-left hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
            <ZoomIn size={19} aria-hidden="true" /><b className="mt-2 block">Larger text</b><span className="text-xs text-slate-500">{fontScale}%</span>
          </button>
          <button type="button" aria-pressed={contrast} onClick={() => setContrast(v => !v)} className={`rounded-2xl border p-4 text-left ${contrast ? "bg-slate-900 text-white" : "hover:bg-slate-50"}`}>
            <Contrast size={19} aria-hidden="true" /><b className="mt-2 block">High contrast</b><span className="text-xs opacity-70">{contrast ? "On" : "Off"}</span>
          </button>
          <button type="button" aria-pressed={reduced} onClick={() => setReduced(v => !v)} className={`rounded-2xl border p-4 text-left ${reduced ? "bg-amber-50 border-amber-300" : "hover:bg-slate-50"}`}>
            <span aria-hidden="true" className="text-lg">⚡</span><b className="mt-2 block">Reduce motion</b><span className="text-xs text-slate-500">{reduced ? "On" : "Off"}</span>
          </button>
        </div>

        <div className="mt-3 flex gap-3">
          <button type="button" onClick={readPage} className="flex min-w-0 flex-1 items-center justify-center gap-2 rounded-2xl bg-emerald-700 px-4 py-3 text-sm font-bold text-white">
            {speaking ? <VolumeX size={18} aria-hidden="true" /> : <Volume2 size={18} aria-hidden="true" />} {speaking ? "Stop reading" : "Read this page"}
          </button>
          <button type="button" onClick={reset} aria-label="Reset accessibility settings" title="Reset" className="rounded-2xl border px-4 py-3 text-sm font-bold">
            <RotateCcw size={17} aria-hidden="true" />
          </button>
        </div>
      </section>
    </div>}
  </>;
}
