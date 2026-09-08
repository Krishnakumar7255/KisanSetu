import React, { useEffect, useMemo, useState } from "react";
import { ShieldCheck, Building2, CheckCircle2, XCircle, RefreshCw, TrendingUp, MapPinned, Activity, Clock3, UserRound, Copy, IndianRupee, Save } from "lucide-react";
import { api, getApiError } from "../api/api";
import { Card, Pill } from "../components/UI";
import { useLanguage } from "../i18n/LanguageContext";

const dayLabel = d => new Date(`${d}T00:00:00`).toLocaleDateString("en-IN", { day:"2-digit", month:"short" });

function RateManager({t}) {
  const crops=["Wheat","Rice","Maize","Mustard"]; const [rates,setRates]=useState([]),[values,setValues]=useState({}),[busy,setBusy]=useState(""),[message,setMessage]=useState("");
  const load=async()=>{try{const r=await api.get("/admin/rates");const list=r.data?.items||[];setRates(list);setValues(Object.fromEntries(crops.map(c=>[c,String(list.find(x=>x.crop===c)?.rate_per_kg??"")])))}catch(e){setMessage(getApiError(e,t("rateUpdateFailed")))}};
  useEffect(()=>{load()},[]);
  const saveRate=async crop=>{const value=Number(values[crop]);if(!Number.isFinite(value)||value<=0){setMessage(t("rateMustPositive"));return}setBusy(crop);try{await api.post("/admin/rates",{crop,rate_per_kg:value,quality_grade:"FAQ"});setMessage(`${t("rateUpdated")} • ${crop}: ₹${value.toFixed(2)}/kg`);await load()}catch(e){setMessage(getApiError(e,t("rateUpdateFailed")))}finally{setBusy("")}};
  return <div className="p-5"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{crops.map(c=>{const current=rates.find(x=>x.crop===c)?.rate_per_kg;return <div key={c} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-center justify-between"><b>{c}</b><span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-black text-emerald-700">FAQ</span></div><div className="mt-3 flex gap-2"><div className="flex min-w-0 flex-1 items-center rounded-xl border border-slate-200 bg-slate-50 px-3"><span className="font-black text-slate-500">₹</span><input type="number" min="0.01" step="0.01" value={values[c]||""} onChange={e=>setValues(v=>({...v,[c]:e.target.value}))} className="w-full bg-transparent px-2 py-2 text-sm font-black outline-none" placeholder="0.00"/></div><button onClick={()=>saveRate(c)} disabled={busy===c} className="rounded-xl bg-emerald-700 px-3 py-2 text-white disabled:opacity-60">{busy===c?<RefreshCw className="animate-spin" size={16}/>:<Save size={16}/>}</button></div><p className="mt-2 text-[10px] text-slate-500">{current!=null?`${t("currentRate")}: ₹${Number(current).toFixed(2)}/kg`:t("notConfigured")}</p></div>})}</div>{message&&<div className="mt-4 rounded-xl bg-emerald-50 p-3 text-xs font-bold text-emerald-800">{message}</div>}<div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50 p-3 text-xs text-indigo-900"><b>{t("centralRateRule")}</b> {t("centralRateRuleDesc")}</div></div>;
}

function Admin({ user, page = "Dashboard" }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [state, setState] = useState(null);
  const [impact, setImpact] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const { t, language } = useLanguage();

  const sectionMap = {
    Dashboard: "admin-dashboard",
    Approvals: "admin-approvals",
    "Command Center": "admin-command",
    Impact: "admin-impact"
  };

  useEffect(() => {
    if (page === "Profile") return;
    const id = sectionMap[page] || "admin-dashboard";
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, [page]);

  const AdminProfile = () => {
    const [copied, setCopied] = useState(false);
    const copyId = async () => {
      try { await navigator.clipboard.writeText(user?.employee_id || user?.admin_id || ""); setCopied(true); setTimeout(() => setCopied(false), 1200); } catch {}
    };
    const labels = {
      title: t("profile"), subtitle: t("adminProfileSubtitle"),
      role: t("admin"), id: t("adminId"), name: t("nameLabel"), mobile: t("mobileNumber"), district: t("districtLabel"), access: t("accessLevel"), secure: t("adminProfileSecure"), copy: copied ? t("copied") : t("copyId")
    };
    return <main className="mx-auto max-w-5xl px-4 pb-28 pt-6 md:px-7 md:pb-12">
      <Card className="overflow-hidden">
        <div className="bg-gradient-to-br from-indigo-900 to-indigo-700 p-6 text-white md:p-8">
          <div className="flex items-center gap-4"><div className="grid h-16 w-16 place-items-center rounded-2xl bg-white/15 ring-1 ring-white/20"><ShieldCheck size={30}/></div><div><h1 className="text-2xl font-black">{labels.title}</h1><p className="mt-1 text-sm text-indigo-100">{labels.subtitle}</p><span className="mt-2 inline-flex rounded-full bg-white/10 px-3 py-1 text-xs font-bold">{labels.secure}</span></div></div>
        </div>
        <div className="grid gap-4 p-5 md:grid-cols-2 md:p-7">
          <div className="rounded-2xl border border-indigo-100 bg-indigo-50 p-4"><div className="text-xs font-bold text-indigo-700">{labels.id}</div><div className="mt-1 text-xl font-black text-indigo-950">{user?.employee_id || user?.admin_id || "—"}</div><button onClick={copyId} className="mt-3 inline-flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-xs font-extrabold ring-1 ring-indigo-100"><Copy size={14}/>{labels.copy}</button></div>
          <div className="rounded-2xl bg-slate-50 p-4"><div className="text-xs font-bold text-slate-500">{labels.role}</div><div className="mt-1 text-lg font-black">{labels.role}</div><div className="mt-1 text-xs text-slate-500">{labels.access}: {user?.role || "admin"}</div></div>
          <div className="rounded-2xl bg-slate-50 p-4"><div className="text-xs font-bold text-slate-500">{labels.name}</div><div className="mt-1 font-black">{user?.name || "—"}</div></div>
          <div className="rounded-2xl bg-slate-50 p-4"><div className="text-xs font-bold text-slate-500">{labels.mobile}</div><div className="mt-1 font-black">{user?.mobile || "—"}</div></div>
          <div className="rounded-2xl bg-slate-50 p-4 md:col-span-2"><div className="text-xs font-bold text-slate-500">{labels.district}</div><div className="mt-1 font-black">{user?.district || "Bihar"}</div></div>
        </div>
      </Card>
    </main>;
  };

  const load = async () => {
    try {
      setError("");
      const results = await Promise.allSettled([api.get("/admin/dashboard"), api.get("/admin/state-command"), api.get("/admin/impact")]);
      const value = (i) => results[i].status === "fulfilled" ? results[i].value : null;
      const r=value(0), sc=value(1), im=value(2);
      if (r) setData(r.data);
      if (!r) setError("Admin dashboard API unavailable. Please check backend/API connection.");
      setLoaded(true);
      if (sc) setState(sc.data);
      if (im) setImpact(im.data);
      if (r && results.some(x => x.status === "rejected")) setError("Kuch optional admin analytics temporarily unavailable hai; core dashboard available hai.");
    } catch (e) { setError(getApiError(e, "Admin dashboard load nahi ho paaya.")); }
  };
  useEffect(() => { load(); const t=setInterval(load,10000); return()=>clearInterval(t); }, []);

  const approve = async id => {
    setBusy(id);
    try { const r=await api.post(`/admin/centre-requests/${id}/approve`); alert(`Centre approved. Employee ID: ${r.data.employee_id}`); await load(); }
    catch(e){ setError(getApiError(e,"Approval failed.")); }
    finally{setBusy("");}
  };
  const reject = async id => {
    setBusy(id);
    try { await api.post(`/admin/centre-requests/${id}/reject`); await load(); }
    catch(e){ setError(getApiError(e,"Rejection failed.")); }
    finally{setBusy("");}
  };

  const maxDaily = useMemo(() => Math.max(1, ...(data?.daily || []).map(x=>x.completed)), [data]);
  const maxDistrict = useMemo(() => Math.max(1, ...(data?.districts || []).map(x=>x.completed)), [data]);

  // Profile is a standalone admin page and must never be blocked by analytics/API availability.
  if (page === "Profile") return <AdminProfile />;
  if (!loaded) return <main className="mx-auto max-w-7xl p-6"><Card className="p-8 text-center"><RefreshCw className="mx-auto animate-spin"/><p className="mt-3 text-sm text-slate-500">{t("loading")}</p></Card></main>;
  if (!data) return <main className="mx-auto max-w-7xl p-6"><Card className="p-8 text-center"><XCircle className="mx-auto text-red-600"/><p className="mt-3 text-sm font-bold text-red-700">{t("adminDashboardUnavailable")}</p><button onClick={load} className="mt-4 rounded-xl bg-emerald-700 px-4 py-2 text-xs font-extrabold text-white">{t("retry")}</button></Card></main>;

  const s={ district_count:0, approved_centres:0, pending_registrations:0, total_completed:0, active_queue:0, ...(data?.summary||{}) };
  const pendingRequests = Array.isArray(data?.pending_registrations) ? data.pending_registrations : [];
  const stateTotals = state?.totals || { active:0, completed:0, high_congestion:0, high_no_show:0 };
  const impactGrievances = impact?.grievances || { open:0, in_progress:0, escalated:0, categories:{} };
  const impactFeedback = impact?.feedback || { average_rating:0, centre_ratings:[] };

  return <main id="admin-dashboard" className="mx-auto max-w-7xl px-4 pb-28 pt-6 md:px-7 md:pb-12">
    <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div>
        <Pill className="bg-indigo-100 text-indigo-800"><ShieldCheck size={14}/> {t("adminControlCenter")}</Pill>
        <h1 className="mt-3 text-3xl font-black">{t("stateOperations")}</h1>
        <p className="mt-1 text-sm text-slate-500">{t("stateOperationsDesc")}</p>
      </div>
      <button onClick={load} className="rounded-xl bg-white px-4 py-2.5 text-xs font-extrabold shadow-sm ring-1 ring-slate-200"><RefreshCw size={15} className="mr-1 inline"/> {t("refresh")}</button>
    </div>
    {error && <div className="mb-4 rounded-xl bg-red-50 p-3 text-sm font-bold text-red-700">{error}</div>}

    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
      {[
        [t("districts"),s.districts,MapPinned],[t("approvedCentres"),s.approved_centres,Building2],
        [t("pendingRequests"),s.pending_registrations,Clock3],[t("totalCompleted"),s.total_completed,CheckCircle2],
        [t("liveQueue"),s.active_queue,Activity],[t("completionTrend"),data.daily?.at(-1)?.completed || 0,TrendingUp]
      ].map(([label,val,Icon])=><div key={label} className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200"><Icon size={18} className="text-emerald-700"/><b className="mt-2 block text-2xl">{val}</b><span className="text-xs text-slate-500">{label}</span></div>)}
    </div>

    <div className="mt-5 grid gap-5 lg:grid-cols-[1.15fr_.85fr]">
      <Card className="p-5">
        <div className="flex items-center justify-between"><div><b>{t("dailyProcurementCompletion")}</b><p className="mt-1 text-xs text-slate-400">{t("last7Days")}</p></div><Pill className="bg-emerald-50 text-emerald-700">{t("live")}</Pill></div>
        <div className="mt-6 flex h-64 items-end gap-2 border-b border-slate-100 px-2">
          {(data.daily||[]).map(x=><div key={x.date} className="flex h-full flex-1 flex-col items-center justify-end gap-2">
            <span className="text-xs font-black text-slate-600">{x.completed}</span>
            <div title={`${x.completed} completed`} className="w-full max-w-10 rounded-t-xl bg-emerald-600 transition-all" style={{height:`${Math.max(6,(x.completed/maxDaily)*82)}%`}} />
            <span className="text-[10px] font-bold text-slate-400">{dayLabel(x.date)}</span>
          </div>)}
        </div>
      </Card>

      <Card className="p-5">
        <div><b>{t("districtPerformance")}</b><p className="mt-1 text-xs text-slate-400">{t("districtPerformanceDesc")}</p></div>
        <div className="mt-5 space-y-4 max-h-64 overflow-auto pr-1">
          {(data.districts||[]).map(x=><div key={x.district}>
            <div className="mb-1 flex justify-between text-xs"><span className="font-bold text-slate-700">{x.district}</span><b>{x.completed}</b></div>
            <div className="h-2.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-indigo-600" style={{width:`${(x.completed/maxDistrict)*100}%`}}/></div>
            <div className="mt-1 text-[10px] text-slate-400">{x.centres} centre(s) • {x.active} active queue</div>
          </div>)}
        </div>
      </Card>
    </div>

    {state && <Card id="admin-command" className="mt-5 overflow-hidden border-indigo-100"><div className="border-b border-slate-100 p-5"><div className="flex items-center gap-2"><Activity size={19} className="text-indigo-700"/><b>{t("biharCommandCenter")}</b><Pill className="ml-auto bg-indigo-50 text-indigo-700">{t("live")} • {state.date}</Pill></div><p className="mt-1 text-xs text-slate-400">{t("stateCommandDesc")}</p></div><div className="grid gap-3 p-5 sm:grid-cols-4">{[[t("activeQueue"),stateTotals.active,"text-emerald-700"],[t("completedToday"),stateTotals.completed,"text-indigo-700"],[t("highCongestion"),stateTotals.high_congestion,"text-red-700"],[t("highNoShow"),stateTotals.high_no_show,"text-amber-700"]].map(([l,v,c])=><div key={l} className="rounded-2xl bg-slate-50 p-4"><b className={`text-2xl ${c}`}>{v}</b><span className="mt-1 block text-xs text-slate-500">{l}</span></div>)}</div><div className="grid gap-3 px-5 pb-5 sm:grid-cols-2 lg:grid-cols-3">{(state.districts||[]).map(x=><div key={x.centre_id} className="rounded-2xl border border-slate-100 p-4"><div className="flex items-center justify-between"><b className="text-sm">{x.district}</b><Pill className={x.congestion==='HIGH'?'bg-red-100 text-red-700':x.congestion==='MEDIUM'?'bg-amber-100 text-amber-700':'bg-emerald-100 text-emerald-700'}>{x.congestion}</Pill></div><div className="mt-3 flex justify-between text-xs text-slate-500"><span>{t("queue")} {x.active}</span><span>{x.utilization_percent}% {t("loadWord")}</span><span>{t("doneWord")} {x.completed}</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-indigo-600" style={{width:`${x.utilization_percent}%`}}/></div>{x.no_show_high>0&&<p className="mt-2 text-[10px] font-bold text-amber-700">⚠ {x.no_show_high} high no-show signal(s)</p>}</div>)}</div></Card>}

    {impact && <Card id="admin-impact" className="mt-5 overflow-hidden border-amber-100"><div className="border-b border-slate-100 p-5"><div className="flex items-center gap-2"><Activity size={19} className="text-amber-700"/><b>{t("grievanceCommand")}</b><Pill className="ml-auto bg-amber-50 text-amber-700">{t("sihImpact")}</Pill></div><p className="mt-1 text-xs text-slate-400">{t("grievanceDesc")}</p></div><div className="grid gap-3 p-5 sm:grid-cols-4">{[[t("open"),impactGrievances.open,"text-amber-700"],[t("inProgress"),impactGrievances.in_progress,"text-indigo-700"],[t("escalated"),impactGrievances.escalated,"text-red-700"],[t("avgRating"),impactFeedback.average_rating+" / 5","text-emerald-700"]].map(([l,v,c])=><div key={l} className="rounded-2xl bg-slate-50 p-4"><b className={`text-2xl ${c}`}>{v}</b><span className="mt-1 block text-xs text-slate-500">{l}</span></div>)}</div><div className="grid gap-5 px-5 pb-5 lg:grid-cols-2"><div><b className="text-sm">{t("complaintCategories")}</b><div className="mt-3 grid grid-cols-2 gap-2">{Object.entries(impactGrievances.categories||{}).map(([k,v])=><div key={k} className="rounded-xl border p-3 text-xs"><b>{k}</b><span className="float-right font-black">{v}</span></div>)}</div></div><div><b className="text-sm">{t("centreSatisfaction")}</b><div className="mt-3 max-h-36 space-y-2 overflow-auto">{(impactFeedback.centre_ratings||[]).map(x=><div key={x.centre_id} className="flex justify-between rounded-xl bg-slate-50 p-3 text-xs"><b>{x.centre_id}</b><span>⭐ {x.rating} ({x.responses})</span></div>)}{!impactFeedback.centre_ratings?.length&&<p className="text-xs text-slate-400">{t("feedbackEmpty")}</p>}</div></div></div></Card>}

    <Card id="admin-rates" className="mt-5 overflow-hidden border-emerald-100"><div className="border-b border-slate-100 bg-gradient-to-r from-emerald-50 to-white p-5"><div className="flex items-center gap-2"><IndianRupee size={19} className="text-emerald-700"/><b>{t("adminRateManagement")}</b><Pill className="ml-auto bg-emerald-100 text-emerald-800">{t("allBihar")}</Pill></div><p className="mt-1 text-xs text-slate-500">{t("adminRateManagementDesc")}</p></div><RateManager t={t}/></Card>

    <Card id="admin-approvals" className="mt-5 overflow-hidden">
      <div className="border-b border-slate-100 p-5"><div className="flex items-center gap-2"><ShieldCheck size={19} className="text-indigo-700"/><b>{t("registrationApprovals")}</b><Pill className="ml-auto bg-amber-100 text-amber-800">{s.pending_registrations} {t("pending")}</Pill></div><p className="mt-1 text-xs text-slate-400">{t("approvalDesc")}</p></div>
      {pendingRequests.length===0 ? <div className="p-10 text-center text-sm text-slate-400">{t("noPendingRegistrations")}</div> :
      pendingRequests.map(r=><div key={r.request_id} className="border-b border-slate-100 p-5 last:border-0">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div><div className="flex flex-wrap items-center gap-2"><b className="text-lg">{r.name}</b><Pill className="bg-amber-100 text-amber-800">{r.status}</Pill></div>
            <div className="mt-2 grid gap-1 text-xs text-slate-500 sm:grid-cols-2"><span><b>{t("centreLabel")}</b> {r.centre_id}</span><span><b>{t("districtLabel")}</b> {r.district}</span><span><b>{t("mobileLabel")}</b> {r.mobile}</span><span><b>{t("countersLabel")}</b> {r.counters}</span></div>
            <p className="mt-2 text-xs text-slate-500">{r.address}</p>
          </div>
          <div className="flex gap-2">
            <button disabled={!!busy} onClick={()=>approve(r.request_id)} className="rounded-xl bg-emerald-700 px-4 py-2.5 text-xs font-extrabold text-white"><CheckCircle2 size={15} className="mr-1 inline"/>{busy===r.request_id?t("processingStatus"):"Validate & Generate ID"}</button>
            <button disabled={!!busy} onClick={()=>reject(r.request_id)} className="rounded-xl bg-red-50 px-4 py-2.5 text-xs font-extrabold text-red-700"><XCircle size={15} className="mr-1 inline"/>{t("reject")}</button>
          </div>
        </div>
      </div>)}
    </Card>
  </main>;
}
export default Admin;
