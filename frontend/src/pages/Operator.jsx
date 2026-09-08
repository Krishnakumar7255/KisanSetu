import React, { useEffect, useRef, useState } from "react";
import { Building2, Settings, AlertCircle, RefreshCw, UserRound, Clock3, CheckCircle2, XCircle, History, BrainCircuit, TriangleAlert, TrendingUp, Gauge, QrCode, ShieldCheck } from "lucide-react";
import { api, getApiError } from "../api/api";
import { money } from "../utils/helpers";
import { Html5Qrcode } from "html5-qrcode";
import { Card, Pill } from "../components/UI";
import { useLanguage } from "../i18n/LanguageContext";

const fmt = (v) => v ? new Date(v).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—";

function Operator({ user, page = "Dashboard" }) {
  const [bs, setBs] = useState([]);
  const [history, setHistory] = useState([]);
  const [centre, setCentre] = useState(user?.centre_id || "");
  const [form, setForm] = useState({ crop: "Wheat", quality_grade: "FAQ", rate_per_kg: "", gross_weight_kg: "", tare_weight_kg: 0, moisture_percent: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [ai, setAi] = useState(null);
  const [scanToken, setScanToken] = useState("");
  const [scanResult, setScanResult] = useState(null);
  const [scanBusy, setScanBusy] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [procTarget, setProcTarget] = useState(null);
  const [audit, setAudit] = useState([]);
  const [noShows, setNoShows] = useState([]);
  const [grievances, setGrievances] = useState([]);
  const [payments, setPayments] = useState([]);
  const [riskSignals, setRiskSignals] = useState([]);
  const [weatherCapacity, setWeatherCapacity] = useState(null);
  const [rateInfo, setRateInfo] = useState(null);
  const [rateError, setRateError] = useState("");
  const { t } = useLanguage();

  useEffect(() => {
    let cancelled = false;
    const loadRate = async () => {
      if (!form.crop) { setRateInfo(null); setRateError(""); return; }
      setRateInfo(null); setRateError("");
      try {
        const r = await api.get("/rates", { params: { district: user?.district || "", crop: form.crop } });
        const item = r.data?.items?.[0];
        if (!cancelled) {
          setRateInfo(item || null);
          setRateError(item ? "" : (r.data?.diagnostic?.errors ? Object.values(r.data.diagnostic.errors)[0] : (r.data?.note || "Admin procurement rate unavailable.")));
          if (item?.rate_per_kg != null) setForm(prev => ({ ...prev, rate_per_kg: String(item.rate_per_kg) }));
        }
      } catch (e) { if (!cancelled) { setRateInfo(null); setRateError(getApiError(e, "Admin procurement rate unavailable.")); } }
    };
    loadRate();
    return () => { cancelled = true; };
  }, [form.crop, user?.district]);

  const load = async () => {
    if (!centre) {
      setBs([]); setHistory([]); setError(t("noCentreAssigned"));
      return;
    }
    try {
      setError("");
      const results = await Promise.allSettled([
        api.get(`/operator/${centre}/bookings`),
        api.get(`/operator/${centre}/history`),
        api.get(`/ai/centre-insights`, { params: { centre_id: centre } }),
        api.get(`/operator/${centre}/audit`),
        api.get(`/operator/${centre}/no-show`),
        api.get(`/operator/${centre}/grievances`),
        api.get(`/operator/${centre}/payments`),
      ]);
      const value = (i) => results[i].status === "fulfilled" ? results[i].value : null;
      const q=value(0), h=value(1), a=value(2), al=value(3), ns=value(4), gr=value(5), py=value(6);
      if (q) setBs(Array.isArray(q.data) ? q.data : []);
      if (h) setHistory(Array.isArray(h.data) ? h.data : []);
      if (a) setAi(a.data || null);
      if (al) setAudit(Array.isArray(al.data) ? al.data : []);
      if (ns) setNoShows(Array.isArray(ns.data) ? ns.data : []);
      if (gr) setGrievances(Array.isArray(gr.data) ? gr.data : []);
      if (py) setPayments(Array.isArray(py.data) ? py.data : []);
      const rs = await api.get(`/operator/${centre}/risk-signals`).catch(() => null); if (rs) setRiskSignals(rs.data?.signals || []);
      const wc = await api.get(`/operator/${centre}/weather-capacity`).catch(() => null); if (wc) setWeatherCapacity(wc.data || null);
      if (q && results.some(x => x.status === "rejected")) setError("Kuch optional dashboard data temporarily unavailable hai; main queue continue kar rahi hai.");
      else if (!q) setError(getApiError(results[0].reason, "Queue data load nahi ho paaya."));
    } catch (e) { setError(getApiError(e, "Queue data load nahi ho paaya.")); }
  };

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [centre]);

  const act = async (token, action) => {
    setBusy(`${action}:${token}`); setError("");
    try { await api.post(`/queue/${centre}/action`, { token, action }); await load(); }
    catch (e) { setError(getApiError(e, "Queue action failed.")); }
    finally { setBusy(""); }
  };

  const makeProc = async (b) => {
    if (!Number(form.rate_per_kg) || Number(form.rate_per_kg) <= 0) { setError("Admin procurement rate unavailable. Please refresh the crop rate before saving procurement."); return; }
    setBusy(`proc:${b.booking_id}`); setError("");
    try {
      await api.post("/procurements", {
        farmer_id: b.farmer_id, centre_id: centre, token: b.token, crop: b.crop,
        quantity_kg: b.quantity_kg, gross_weight_kg: Number(form.gross_weight_kg || b.quantity_kg), tare_weight_kg: Number(form.tare_weight_kg || 0),
        moisture_percent: form.moisture_percent === "" ? null : Number(form.moisture_percent), quality_grade: form.quality_grade,
        employee_id: user?.employee_id || null,
      });
      setProcTarget(null);
      setForm(f => ({ ...f, gross_weight_kg: "", tare_weight_kg: 0, moisture_percent: "" }));
      await load();
    } catch (e) { setError(getApiError(e, "Procurement save nahi hua.")); }
    finally { setBusy(""); }
  };


  useEffect(() => {
    if (!cameraOpen) return undefined;
    let cancelled = false;
    const scanner = new Html5Qrcode("ks-qr-reader");
    const stopScanner = async () => {
      try { await scanner.stop(); } catch {}
      try { scanner.clear(); } catch {}
    };
    (async () => {
      try {
        await scanner.start(
          { facingMode: "environment" },
          { fps: 10, qrbox: { width: 250, height: 250 } },
          decodedText => {
            if (cancelled) return;
            const match = String(decodedText || "").match(/\|TOKEN\|([^|]+)/i);
            const raw = String(decodedText || "").trim();
            const token = /^KSQR1\./i.test(raw) ? raw : (match?.[1] || (/^T-\d+$/i.test(raw) ? raw : ""));
            if (token) {
              setScanToken(token.toUpperCase());
              setCameraOpen(false);
            }
          },
          () => {}
        );
      } catch (e) {
        if (!cancelled) {
          setError("QR camera start nahi ho paaya. HTTPS/localhost par camera permission allow karein ya manual token verification use karein.");
          setCameraOpen(false);
        }
      }
    })();
    return () => { cancelled = true; void stopScanner(); };
  }, [cameraOpen]);
  const active = bs.filter(x => ["waiting", "serving", "procurement_pending"].includes(x.status));
  const recommended = active.find(x => x.status === "waiting" && x.eligible_now && !x.deferred_at);
  const waiting = active.filter(x => x.status === "waiting");
  const serving = active.filter(x => x.status === "serving");
  const pending = active.filter(x => x.status === "procurement_pending");
  const completed = history.filter(x => x.status === "completed");
  const skipped = history.filter(x => ["skipped", "cancelled"].includes(x.status));

  const FarmerDetails = ({ b }) => (
    <div className="mt-3 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-100">
      <div className="flex items-center gap-2 text-xs font-black text-slate-500"><UserRound size={15} className="text-emerald-700"/> Farmer Details</div>
      <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-4">
        <div><span className="text-slate-400">{t("farmerId")}</span><b className="block text-slate-900">{b.farmer_id}</b></div>
        <div><span className="text-slate-400">{t("name")}</span><b className="block text-slate-900">{b.farmer?.name || "—"}</b></div>
        <div><span className="text-slate-400">{t("mobile")}</span>{b.farmer?.mobile ? <a href={`tel:${b.farmer.mobile}`} className="block font-black text-emerald-700 underline decoration-emerald-200 underline-offset-2 hover:text-emerald-900">{b.farmer.mobile}</a> : <b className="block text-slate-900">—</b>}</div>
        <div><span className="text-slate-400">{t("villageDistrict")}</span>{(b.farmer?.village || b.farmer?.district) ? <a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${b.farmer?.village || ""}, ${b.farmer?.district || ""}, Bihar, India`)}`} target="_blank" rel="noreferrer" className="block font-black text-emerald-700 underline decoration-emerald-200 underline-offset-2 hover:text-emerald-900" title="Open location in Google Maps">{b.farmer?.village || "—"} / {b.farmer?.district || "—"}</a> : <b className="block text-slate-900">—</b>}</div>
      </div>
    </div>
  );

  const statusClass = s => s === "serving" ? "bg-orange-100 text-orange-800" : s === "procurement_pending" ? "bg-blue-100 text-blue-800" : "bg-emerald-100 text-emerald-800";

  return <main className="mx-auto max-w-7xl px-4 pb-28 pt-6 md:px-7 md:pb-12">
    <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div><Pill className="bg-emerald-100 text-emerald-800"><Building2 size={14}/> {t("operatorConsole")}</Pill><h1 className="mt-3 text-3xl font-black">{t("procurementCentreDashboard")}</h1><p className="mt-1 text-sm text-slate-500">{t("operatorDesc")}</p></div>
      <select value={centre} onChange={e=>setCentre(e.target.value)} className="ks-input max-w-xs" disabled={!!user?.centre_id}><option value={user?.centre_id || ""}>{user?.centre_id || "No centre assigned"}</option></select>
    </div>
    {error && <div className="mb-4 flex items-center gap-2 rounded-xl bg-red-50 p-3 text-sm font-bold text-red-700"><AlertCircle size={18}/>{error}</div>}
    <Card className="mb-5 border-emerald-100 bg-emerald-50/40 p-5">
      <div className="flex items-center gap-2"><QrCode size={19} className="text-emerald-700"/><b>{t("gateTokenVerification")}</b><Pill className="ml-auto bg-white text-emerald-700"><ShieldCheck size={13}/> {t("secure")}</Pill></div>
      <p className="mt-1 text-xs text-slate-500">{t("gateTokenDesc")}</p>
      <div className="mb-5 grid gap-4 lg:grid-cols-2"><Card className="border-indigo-100 bg-indigo-50 p-5"><div className="flex items-center justify-between"><div><b className="text-sm text-indigo-900">🧠 {t("digitalTwin")}</b><p className="mt-1 text-xs text-slate-600">{t("digitalTwinDesc")}</p></div><Pill className="bg-white text-indigo-700">{t("live")}</Pill></div><div className="mt-4 grid grid-cols-3 gap-2"><div className="rounded-xl bg-white p-3"><b className="block text-xl">{active.length}</b><span className="text-[10px] text-slate-500">{t("active")}</span></div><div className="rounded-xl bg-white p-3"><b className="block text-xl">{serving.length}</b><span className="text-[10px] text-slate-500">{t("serving")}</span></div><div className="rounded-xl bg-white p-3"><b className="block text-xl">{weatherCapacity?.weather_adjusted_capacity ?? '—'}</b><span className="text-[10px] text-slate-500">{t("safeCapacity")}</span></div></div><p className="mt-3 text-[11px] font-bold text-indigo-900">{t("weather")}: {weatherCapacity?.weather?.condition || '—'} • {t("buffer")} +{weatherCapacity?.weather?.buffer_min ?? 0} min</p></Card><Card className="border-amber-100 bg-amber-50 p-5"><div className="flex items-center justify-between"><div><b className="text-sm text-amber-900">⚠️ Fair-Access Risk Signals</b><p className="mt-1 text-xs text-slate-600">Suspicious patterns go to human review.</p></div><Pill className="bg-white text-amber-700">{riskSignals.length} {t("flags")}</Pill></div><div className="mt-4 space-y-2">{riskSignals.slice(0,3).map(x=><div key={x.farmer_id} className="rounded-xl bg-white p-3"><div className="flex justify-between text-xs"><b>{x.farmer_id}</b><b className="text-red-700">{x.risk_score}/100</b></div><p className="mt-1 text-[10px] text-slate-500">{x.reasons.join(' • ')}</p></div>)}{!riskSignals.length&&<p className="text-xs text-emerald-700 font-bold">{t("noSuspiciousSignal")}</p>}</div></Card></div>
<div className="mt-4 flex flex-col gap-2 sm:flex-row"><input value={scanToken} onChange={e=>setScanToken(e.target.value.toUpperCase())} className="ks-input flex-1" placeholder={t("scannedTokenPlaceholder")}/><button type="button" onClick={()=>setCameraOpen(true)} className="rounded-xl bg-indigo-700 px-5 py-3 text-sm font-extrabold text-white">{t("scanQr")}</button><button disabled={!scanToken.trim()||scanBusy} onClick={async()=>{setScanBusy(true);setScanResult(null);try{const r=await api.get('/qr/verify',{params:{token:scanToken.trim(),centre_id:centre}});setScanResult(r.data)}catch(e){setScanResult({valid:false,message:getApiError(e,'Token verification failed.')})}finally{setScanBusy(false)}}} className="rounded-xl bg-emerald-700 px-5 py-3 text-sm font-extrabold text-white">{scanBusy?t("verifying"):t("verifyToken")}</button></div>
      {scanResult&&<div className={`mt-3 rounded-xl p-3 text-sm font-bold ${scanResult.valid?'bg-emerald-100 text-emerald-800':'bg-red-100 text-red-800'}`}>{scanResult.valid?'✅ ':'❌ '}{scanResult.message}{scanResult.farmer&&<span className="ml-2 font-semibold">• {scanResult.farmer.name} • {scanResult.booking?.slot}</span>}</div>}
    </Card>

    {cameraOpen && <Card className="mb-5 overflow-hidden border-indigo-200 bg-slate-950 p-4">
      <div className="flex items-center justify-between text-white"><b>📷 Live QR Scanner</b><button onClick={()=>setCameraOpen(false)} className="rounded-lg bg-white/10 px-3 py-1 text-xs">Close</button></div>
      <div className="mt-3 overflow-hidden rounded-2xl bg-black"><div id="ks-qr-reader" className="min-h-[280px] w-full" /></div>
      <p className="mt-2 text-center text-xs text-slate-300">Token QR ko camera ke centre me rakhein. Camera supported browser/HTTPS ya localhost par hona chahiye; issue ho to manual token verification use karein.</p>
    </Card>}

    {page === "Dashboard" && ai && <Card className="mt-5 overflow-hidden border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-emerald-50">
      <div className="border-b border-indigo-100 p-5"><div className="flex items-center gap-2"><BrainCircuit size={20} className="text-indigo-700"/><b>AI Mandi Intelligence</b><Pill className="ml-auto bg-white text-indigo-700">{ai.risk_level} Risk</Pill></div><p className="mt-1 text-xs text-slate-500">Explainable predictions using live queue load, recent demand and service history — no external AI API required.</p></div>
      <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-100"><Gauge size={18} className="text-emerald-700"/><b className="mt-2 block text-2xl">{ai.congestion_score}%</b><span className="text-xs text-slate-500">Congestion score</span></div>
        <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-100"><TrendingUp size={18} className="text-indigo-700"/><b className="mt-2 block text-2xl">{ai.forecast_next_day}</b><span className="text-xs text-slate-500">Forecast next-day bookings</span></div>
        <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-100"><Clock3 size={18} className="text-orange-700"/><b className="mt-2 block text-2xl">{ai.avg_wait_min} min</b><span className="text-xs text-slate-500">Historical avg wait</span></div>
        <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-100"><Building2 size={18} className="text-emerald-700"/><b className="mt-2 block text-2xl">{ai.recommended_counters}</b><span className="text-xs text-slate-500">AI recommended counters</span></div>
      </div>
      <div className="grid gap-2 px-5 pb-5 md:grid-cols-2">{(ai.alerts||[]).map((x,i)=><div key={i} className="flex items-start gap-2 rounded-xl bg-white/80 p-3 text-xs text-slate-700 ring-1 ring-slate-100"><TriangleAlert size={15} className="mt-0.5 shrink-0 text-amber-600"/>{x}</div>)}{ai.anomalies?.length>0&&<div className="rounded-xl bg-amber-50 p-3 text-xs font-bold text-amber-900">⚠️ {ai.anomalies.length} unusual wait record(s) flagged for operator review.</div>}</div>
    </Card>}

    {page === "Dashboard" && <div className="grid gap-3 sm:grid-cols-5">
      {[["Live",active.length,"bg-emerald-800 text-white"],["Waiting",waiting.length,"bg-white"],["Serving",serving.length,"bg-white"],["Completed",completed.length,"bg-white"],["Skipped",skipped.length,"bg-white"]].map(([a,n,c])=><div key={a} className={`rounded-2xl p-4 shadow-sm ring-1 ring-slate-200 ${c}`}><span className="text-xs opacity-70">{a}</span><b className="mt-2 block text-3xl">{n}</b></div>)}
    </div>}

    <Card className="mt-5 overflow-hidden" id="operator-queue">
      <div className="flex items-center justify-between border-b border-slate-100 p-5"><div><b>Live Token Queue</b><p className="mt-1 text-xs text-slate-400">Dynamic slot-aware ranking — one no-show never blocks the queue.</p></div><button onClick={load} className="rounded-xl bg-slate-50 px-3 py-2 text-xs font-bold"><RefreshCw size={15} className="mr-1 inline"/> Refresh</button></div>
      {recommended && <div className="m-4 rounded-2xl bg-emerald-50 p-4 ring-1 ring-emerald-200">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div><div className="text-xs font-black uppercase tracking-wide text-emerald-700">Recommended Next Farmer</div><div className="mt-1 text-xl font-black text-slate-900">{recommended.token} • {recommended.farmer?.name || recommended.farmer_id}</div><div className="mt-1 text-xs text-slate-600">{t("slot")} {recommended.slot} • {recommended.crop} • {recommended.quantity_kg} kg • {recommended.checked_in ? t("checkedIn") : t("slotActive")}</div></div>
          <button disabled={!!busy} onClick={()=>act(recommended.token,"accept")} className="rounded-xl bg-emerald-700 px-4 py-3 text-xs font-extrabold text-white">{busy===`accept:${recommended.token}`?t("accepting"):t("acceptRecommended")}</button>
        </div>
      </div>}
      {active.length===0?<p className="p-10 text-center text-sm text-slate-400">No active farmers in queue.</p>:active.map(b=><div key={b.booking_id} className="border-b border-slate-100 p-5 last:border-0">
        <div className="flex flex-col gap-3 md:flex-row md:items-start"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><strong className="text-xl font-black">#{b.queue_rank || "—"} · {b.token}</strong><Pill className={statusClass(b.status)}>{b.status}</Pill></div><span className="mt-1 block text-xs text-slate-400">{b.crop} • {b.quantity_kg} kg • Slot {b.slot} • {b.queue_priority || "waiting"}</span><span className="mt-1 flex items-center gap-1 text-xs text-slate-400"><Clock3 size={13}/> Booked {fmt(b.created_at)} {b.called_at && `• Called ${fmt(b.called_at)}`}</span></div>
        <div className="flex flex-wrap gap-2">{b.status==='waiting'&&<>{<button disabled={!!busy} onClick={()=>act(b.token,'accept')} className="rounded-xl bg-indigo-100 px-3 py-2.5 text-xs font-extrabold text-indigo-900 ring-1 ring-indigo-200">{busy===`accept:${b.token}` ? t("accepting") : t("accept")}</button>}{b.eligible_now&&<button disabled={!!busy} onClick={()=>act(b.token,'defer')} className="rounded-xl bg-amber-100 px-3 py-2.5 text-xs font-extrabold text-amber-800">{t("skipForNow")}</button>}{!b.eligible_now&&<span className="rounded-xl bg-slate-100 px-3 py-2.5 text-xs font-extrabold text-slate-600">{t("upcomingSlot")} • {b.slot}</span>}</>}{b.status==='serving'&&<><button disabled={!!busy} onClick={()=>act(b.token,'skip')} className="rounded-xl bg-slate-100 px-3 py-2.5 text-xs font-bold">{t("skip")}</button><button disabled={!!busy} onClick={()=>act(b.token,'complete')} className="rounded-xl bg-emerald-700 px-3 py-2.5 text-xs font-extrabold text-white">{busy===`complete:${b.token}`?t("moving"):t("moveToProcurement")}</button></>}{b.status==='procurement_pending'&&<button disabled={!!busy} onClick={()=>{setProcTarget(b);setForm(f=>({...f,crop:b.crop,gross_weight_kg:b.quantity_kg,tare_weight_kg:0,moisture_percent:""}))}} className="rounded-xl bg-emerald-700 px-3 py-2.5 text-xs font-extrabold text-white">{busy===`proc:${b.booking_id}`?"Saving...":`${t("completeAndSave")} ${money(Math.max(0,Number(b.quantity_kg)-Number(form.tare_weight_kg||0))*Number(form.rate_per_kg||0))}`}</button>}</div></div>
        <FarmerDetails b={b}/>
      </div>)}
    </Card>

    {(page === "Procurement" || page === "Dashboard") && <Card id="operator-proc" className="mt-5 p-5"><div className="flex items-center gap-2"><Settings size={18} className="text-emerald-700"/><b>{t("digitalWeighment")}</b><Pill className="ml-auto bg-emerald-50 text-emerald-700">{t("auditReady")}</Pill></div><p className="mt-1 text-xs text-slate-500">{t("weighmentDesc")}</p><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5"><label className="ks-label">{t("crop")}<select className="ks-input mt-1" value={form.crop} onChange={e=>setForm({...form,crop:e.target.value})}><option>Wheat</option><option>Rice</option><option>Maize</option><option>Mustard</option></select></label><label className="ks-label">{t("grossKg")}<input className="ks-input mt-1" type="number" min="0" step="0.01" value={form.gross_weight_kg} onChange={e=>setForm({...form,gross_weight_kg:e.target.value})}/></label><label className="ks-label">{t("tareKg")}<input className="ks-input mt-1" type="number" min="0" step="0.01" value={form.tare_weight_kg} onChange={e=>setForm({...form,tare_weight_kg:e.target.value})}/></label><label className="ks-label">{t("moisture")}<input className="ks-input mt-1" type="number" min="0" max="100" step="0.1" value={form.moisture_percent} onChange={e=>setForm({...form,moisture_percent:e.target.value})}/></label><label className="ks-label">{t("ratePerKg")}<input className="ks-input mt-1" type="number" min="0" step="0.01" value={form.rate_per_kg} readOnly aria-readonly="true"/>{rateInfo&&<span className="mt-1 block text-[10px] font-semibold text-emerald-700">{t("adminRateLabel")} ₹{Number(rateInfo.rate_per_kg).toFixed(2)}/kg • {rateInfo.market||t("centralRate")}</span>}{!rateInfo&&<span className="mt-1 block text-[10px] text-amber-700">{rateError || t("adminRateUnavailable")}</span>}</label></div><div className="mt-3 grid gap-3 sm:grid-cols-2"><label className="ks-label">{t("qualityGrade")}<select className="ks-input mt-1" value={form.quality_grade} onChange={e=>setForm({...form,quality_grade:e.target.value})}><option>FAQ</option><option>Grade A</option><option>Grade B</option></select></label>{procTarget&&<div className="rounded-xl bg-emerald-50 p-3 text-xs"><b>Ready: {procTarget.token}</b><p className="mt-1">Net: {Math.max(0,Number(form.gross_weight_kg||procTarget.quantity_kg)-Number(form.tare_weight_kg||0)).toFixed(2)} kg • Payable: {money(Math.max(0,Number(form.gross_weight_kg||procTarget.quantity_kg)-Number(form.tare_weight_kg||0))*Number(form.rate_per_kg||0))}</p><button disabled={!!busy} onClick={()=>makeProc(procTarget)} className="mt-2 rounded-xl bg-emerald-700 px-3 py-2 text-xs font-extrabold text-white">{busy===`proc:${procTarget.booking_id}`?"Saving...":t("saveProcurement")}</button></div>}</div></Card>}

    {page === "Dashboard" && <div className="mt-5 grid gap-5 lg:grid-cols-2">
      <Card className="p-5"><div className="flex items-center gap-2"><TriangleAlert size={18} className="text-amber-600"/><b>{t("noShowRisk")}</b><Pill className="ml-auto bg-amber-50 text-amber-700">AI</Pill></div><p className="mt-1 text-xs text-slate-500">{t("noShowDesc")}</p><div className="mt-4 space-y-2">{noShows.slice(0,6).map(b=><div key={b.booking_id} className="flex items-center justify-between rounded-xl bg-slate-50 p-3"><div><b className="text-sm">{b.token}</b><span className="ml-2 text-xs text-slate-500">{b.farmer?.name||b.farmer_id} • {b.slot}</span></div><Pill className={b.no_show_prediction?.risk==='HIGH'?'bg-red-100 text-red-700':b.no_show_prediction?.risk==='MEDIUM'?'bg-amber-100 text-amber-700':'bg-emerald-100 text-emerald-700'}>{b.no_show_prediction?.risk||'LOW'} {b.no_show_prediction?.score||0}%</Pill></div>)}{!noShows.length&&<p className="text-sm text-slate-400">{t("noWaitingSignals")}</p>}</div></Card>
      <Card className="p-5"><div className="flex items-center gap-2"><History size={18} className="text-indigo-700"/><b>{t("liveAudit")}</b></div><div className="mt-4 max-h-56 space-y-2 overflow-auto">{audit.slice(0,10).map(a=><div key={a.id} className="rounded-xl bg-slate-50 p-3 text-xs"><div className="flex justify-between"><b>{a.event}</b><span className="text-slate-400">{fmt(a.created_at)}</span></div><div className="mt-1 text-slate-500">{a.token||'—'} {a.farmer_id?`• ${a.farmer_id}`:''}</div></div>)}{!audit.length&&<p className="text-sm text-slate-400">{t("noAuditEvents")}</p>}</div></Card>
    </div>}

    {page === "Dashboard" && <Card className="mt-5 overflow-hidden border-amber-100"><div className="border-b border-slate-100 p-5"><div className="flex items-center gap-2"><TriangleAlert size={18} className="text-amber-600"/><b>{t("farmerGrievances")}</b><Pill className="ml-auto bg-amber-50 text-amber-700">{grievances.filter(g=>g.status!=="RESOLVED").length} {t("active")}</Pill></div><p className="mt-1 text-xs text-slate-400">{t("grievanceOperatorDesc")}</p></div>{grievances.length===0?<p className="p-8 text-center text-sm text-slate-400">{t("noGrievances")}</p>:grievances.slice(0,10).map(g=><div key={g.grievance_id} className="border-b border-slate-100 p-4 last:border-0"><div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"><div><div className="flex flex-wrap items-center gap-2"><b>{g.subject}</b><Pill className={g.status==='RESOLVED'?'bg-emerald-100 text-emerald-700':'bg-amber-100 text-amber-700'}>{g.status}</Pill><Pill className="bg-slate-100 text-slate-700">{g.priority}</Pill></div><p className="mt-1 text-xs text-slate-500">{g.category} • {g.farmer_id} {g.token?`• ${g.token}`:''}</p><p className="mt-2 text-sm text-slate-600">{g.description}</p></div>{g.status!=="RESOLVED"&&<button disabled={!!busy} onClick={async()=>{setBusy(`gr:${g.grievance_id}`);try{await api.patch(`/operator/${centre}/grievances/${g.grievance_id}`,{status:"RESOLVED",resolution:"Issue reviewed and resolved by procurement centre."});await load()}catch(e){setError(getApiError(e,"Grievance update failed."))}finally{setBusy("")}}} className="rounded-xl bg-emerald-700 px-4 py-2.5 text-xs font-extrabold text-white">{busy===`gr:${g.grievance_id}`?"Resolving...":t("markResolved")}</button>}</div></div>)}</Card>}

    {page === "Dashboard" && <Card className="mt-5 overflow-hidden border-emerald-100">
      <div className="border-b border-slate-100 p-5"><div className="flex items-center gap-2"><CheckCircle2 size={18} className="text-emerald-700"/><b>{t("dbtSettlement")}</b><Pill className="ml-auto bg-emerald-50 text-emerald-700">{t("operatorVerified")}</Pill></div><p className="mt-1 text-xs text-slate-400">{t("dbtDesc")}</p></div>
      {payments.length===0?<p className="p-8 text-center text-sm text-slate-400">{t("noPayments")}</p>:payments.slice(0,10).map(p=><div key={p.payment_id} className="flex flex-col gap-3 border-b border-slate-100 p-4 last:border-0 md:flex-row md:items-center md:justify-between"><div><b>{p.token}</b><p className="mt-1 text-xs text-slate-500">{p.farmer_id} • {money(Number(p.amount||0))} • {p.status}</p>{p.utr&&<p className="text-xs text-emerald-700">UTR: {p.utr}</p>}</div>{p.status==='processing'&&<button disabled={!!busy} onClick={async()=>{setBusy(`pay:${p.payment_id}`);setError('');try{await api.post(`/operator/${centre}/payments/${p.payment_id}/complete`);await load()}catch(e){setError(getApiError(e,'DBT settlement failed.'))}finally{setBusy('')}}} className="rounded-xl bg-emerald-700 px-4 py-2.5 text-xs font-extrabold text-white">{busy===`pay:${p.payment_id}`?'Settling...':'Settle DBT'}</button>}</div>)}
    </Card>}

    <Card className="mt-5 overflow-hidden" id="operator-history">
      <div className="border-b border-slate-100 p-5"><div className="flex items-center gap-2"><History size={18} className="text-emerald-700"/><b>{t("serviceHistory")}</b></div><p className="mt-1 text-xs text-slate-400">{t("serviceHistoryDesc")}</p></div>
      {history.length===0?<p className="p-10 text-center text-sm text-slate-400">{t("noHistory")}</p>:history.map(b=><div key={b.booking_id} className="border-b border-slate-100 p-5 last:border-0"><div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between"><div><div className="flex items-center gap-2"><b className="text-lg">{b.token}</b><Pill className={b.status === "completed" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}>{b.status}</Pill></div><div className="mt-1 text-xs text-slate-500">{b.crop} • {b.quantity_kg} kg • Slot {b.slot}</div><div className="mt-2 grid gap-1 text-xs text-slate-500"><span>{t("booked")}: {fmt(b.created_at)}</span>{b.called_at&&<span>{t("called")}: {fmt(b.called_at)}</span>}{b.completed_at&&<span className="font-bold text-emerald-700">{t("completed")}: {fmt(b.completed_at)}</span>}{b.skipped_at&&<span className="font-bold text-amber-700">{t("skipped")}: {fmt(b.skipped_at)}</span>}{b.skip_reason&&<span>{t("reason")}: {b.skip_reason}</span>}</div></div><div className="min-w-[280px]"><FarmerDetails b={b}/></div></div></div>)}
    </Card>
  </main>;
}
export default Operator;
