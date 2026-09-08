import React, { useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronRight, LocateFixed, Search, AlertCircle, CheckCircle2, ShieldCheck } from "lucide-react";
import { api, getApiError } from "../api/api";
import { today, money, haversine } from "../utils/helpers";
import { BIHAR_CENTRES } from "../data/centres";
import { Card, Pill } from "../components/UI";
import { useLanguage } from "../i18n/LanguageContext";

function Booking({ user, onBooked }) {
  const { t } = useLanguage();
  const [centres, setCentres] = useState(BIHAR_CENTRES);
  const [slots, setSlots] = useState([]);
  const [location, setLocation] = useState(null);
  const [search, setSearch] = useState("");
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [loading, setLoading] = useState(false);
  const [confirmedBooking, setConfirmedBooking] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [aiRec, setAiRec] = useState(null);
  const [landRecords, setLandRecords] = useState([]);
  const [debouncedQuantity, setDebouncedQuantity] = useState(420);
  const [adminRate, setAdminRate] = useState(null);
  const [adminRateError, setAdminRateError] = useState("");
  const [f, setF] = useState({ centre_id: user?.centre_id || "", crop: user?.crop || "Wheat", quantity_kg: 420, date: today(), slot: "" });

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      api.get("/centres"),
      api.get(`/v1/land/${encodeURIComponent(user.farmer_id)}`),
    ]).then(([c, l]) => {
      if (cancelled) return;
      if (c.status === "fulfilled" && Array.isArray(c.value.data) && c.value.data.length) setCentres(c.value.data);
      // Keep the assigned centre usable even if the public centre list is temporarily unavailable. 
      if (l.status === "fulfilled" && Array.isArray(l.value.data)) setLandRecords(l.value.data);
    });
    return () => { cancelled = true; };
  }, [user.farmer_id]);

  useEffect(() => {
    let cancelled = false;
    setAdminRate(null); setAdminRateError("");
    api.get("/rates", { params: { district: user?.district || "", crop: f.crop } })
      .then(r => {
        if (cancelled) return;
        const item = r.data?.items?.[0] || null;
        setAdminRate(item);
        setAdminRateError(item ? "" : (r.data?.diagnostic?.errors ? Object.values(r.data.diagnostic.errors)[0] : (r.data?.note || t("adminRateUnavailable"))));
      })
      .catch(e => { if (!cancelled) { setAdminRate(null); setAdminRateError(getApiError(e, t("adminRateUnavailable"))); } });
    return () => { cancelled = true; };
  }, [f.crop, user?.district]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuantity(f.quantity_kg), 400);
    return () => clearTimeout(timer);
  }, [f.quantity_kg]);

  useEffect(() => {
    if (!f.centre_id || !f.date) return;
    let cancelled = false;
    setLoadingSlots(true);
    setError("");

    const loadSlots = async () => {
      try {
        const response = await api.get("/slots", {
          params: {
            centre_id: f.centre_id,
            booking_date: f.date,
            crop: f.crop,
            quantity_kg: Number(debouncedQuantity) || 100,
          },
        });
        if (!cancelled) setSlots(Array.isArray(response.data) ? response.data : []);

        // AI is optional and must never delay the normal slot list.
        api.get("/ai/slot-recommendation", {
          params: { centre_id: f.centre_id, booking_date: f.date, crop: f.crop, quantity_kg: Number(debouncedQuantity) || 0 },
          timeout: 6000,
        }).then(aiResponse => {
          if (!cancelled) setAiRec(aiResponse.data);
        }).catch(aiError => {
          console.warn("AI recommendation unavailable:", aiError);
          if (!cancelled) setAiRec(null);
        });
      } catch (e) {
        if (!cancelled) {
          setSlots([]);
          setAiRec(null);
          setError(getApiError(e, "Slots load nahi ho paaye."));
        }
      } finally {
        if (!cancelled) setLoadingSlots(false);
      }
    };

    loadSlots();
    return () => { cancelled = true; };
  }, [f.centre_id, f.date, f.crop, debouncedQuantity]);
  const locate = () => {
    setError("");
    if (!navigator.geolocation) { setError("Is browser me GPS available nahi hai."); return; }
    navigator.geolocation.getCurrentPosition(
      p => setLocation({ lat: p.coords.latitude, lon: p.coords.longitude }),
      e => setError(e.code === 1 ? "Location permission denied. Browser me Allow karein." : "GPS location nahi mil paayi."),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
  };

  const sorted = useMemo(() => {
    const term = search.trim().toLowerCase();
    const withDistance = centres.map(c => ({ ...c, distance: location ? haversine(location.lat, location.lon, Number(c.lat) || 0, Number(c.lon) || 0) : null }));
    const filtered = term ? withDistance.filter(c => `${c.district || ""} ${c.city || ""} ${c.name || ""}`.toLowerCase().includes(term)) : withDistance;
    return location ? filtered.sort((a, b) => (a.distance ?? 99999) - (b.distance ?? 99999)) : filtered;
  }, [centres, location, search]);

  const update = (key, value) => setF(prev => ({ ...prev, [key]: value }));

  const submit = async e => {
    e.preventDefault();
    setError(""); setSuccess("");
    const qty = Number(f.quantity_kg);
    const selectedSlot = slots.find(s => s.slot === f.slot);
    if (!f.centre_id) { setError(t("centreNotAssigned")); return; }
    if (!f.slot) { setError(t("selectSlotError")); return; }
    if (!Number.isFinite(qty) || qty <= 0) { setError(t("quantityError")); return; }
    if (!selectedSlot?.available_for_booking || selectedSlot?.is_full || selectedSlot?.is_past || Number(selectedSlot?.available ?? 0) <= 0) { setError(t("slotUnavailableError")); return; }
    setLoading(true);
    try {
      const r = await api.post("/bookings", { ...f, quantity_kg: qty, farmer_id: user.farmer_id });
      setSuccess(`${t("bookingConfirmed")}: ${r.data.token}`);
      setConfirmedBooking(r.data);
      try { localStorage.setItem(`ks_token_${r.data.token}`, JSON.stringify({ ...r.data, saved_at: Date.now() })); } catch {}
      onBooked?.(r.data);
    } catch (e) {
      const msg = getApiError(e, t("bookingFailed"));
      setError(msg.includes("schema cache") || msg.includes("Booking RPC is unavailable") ? t("bookingSetupIncomplete") : msg);
      // Refresh availability after every booking failure so a stale slot cannot be retried blindly.
      if (f.centre_id && f.date) {
        try {
          const fresh = await api.get("/slots", { params: { centre_id: f.centre_id, booking_date: f.date, crop: f.crop, quantity_kg: qty } });
          setSlots(Array.isArray(fresh.data) ? fresh.data : []);
        } catch {}
      }
    }
    finally { setLoading(false); }
  };

  const joinWaitlist = async (slot) => {
    setError("");
    try {
      await api.post("/waitlist", { farmer_id:user.farmer_id, centre_id:f.centre_id, crop:f.crop, quantity_kg:Number(f.quantity_kg)||1, date:f.date, slot });
      setSuccess(`${t("waitlistJoined")}: ${slot}. ${t("waitlistNotify")}`);
    } catch (e) { setError(getApiError(e, t("waitlistFailed"))); }
  };

  const downloadGatePass = async () => {
    if (!confirmedBooking?.token) return;
    try {
      const response = await api.get(`/bookings/${encodeURIComponent(confirmedBooking.token)}/token-pdf`, { responseType: "blob" });
      const url = window.URL.createObjectURL(response.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `KisanSetu_GatePass_${confirmedBooking.token}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setError(t("gatePassPdfFailed"));
    }
  };

  return <main className="mx-auto max-w-5xl px-4 pb-28 pt-6 md:px-7 md:pb-12">
    <div className="mb-5"><Pill className="bg-emerald-100 text-emerald-800"><CalendarDays size={14}/> {t("smartSlotBooking")}</Pill><h1 className="mt-3 text-3xl font-black tracking-tight">{t("bookingTitle")}</h1><p className="mt-1 text-sm text-slate-500">{t("bookingIntro")}</p></div>
    <div className="mb-5 flex flex-col gap-3 rounded-[20px] border border-indigo-100 bg-indigo-50 p-4 sm:flex-row sm:items-center"><div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-white text-emerald-700"><LocateFixed size={20}/></div><div className="flex-1"><b className="text-sm">{t("assignedCentre")}</b><p className="text-xs text-slate-500">{t("gpsDistanceOnly")}</p></div><button type="button" onClick={locate} className="rounded-xl bg-white px-4 py-2.5 text-xs font-extrabold text-emerald-700 shadow-sm">{t("detectLocation")}</button></div>
    {landRecords.length > 0 && <div className="mb-5 rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
      <div className="flex items-center gap-2"><ShieldCheck size={18} className="text-emerald-700"/><b className="text-sm text-emerald-900">{t("verifiedFarmQuota")}</b><Pill className="ml-auto bg-white text-emerald-700">{t("mockLandSource")}</Pill></div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">{landRecords.map(r => <div key={r.land_record_id} className="rounded-xl bg-white p-3 text-xs"><b>{r.crop}</b><div className="mt-1 text-slate-500">Khasra: {r.survey_khasra_no} • {r.land_area_acre} acre • Max eligible: {Number(r.max_crop_quantity_kg).toLocaleString()} kg</div></div>)}</div>
    </div>}
    <Card className="p-5 md:p-7"><form onSubmit={submit} className="grid gap-5">
      <div><label className="ks-label">{t("selectCentre")}</label><div className="relative"><Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder={t("searchDistrictCentre")} className="ks-input pl-10"/></div><select required value={f.centre_id} onChange={e=>{update("centre_id",e.target.value);update("slot","");}} className="ks-input mt-2">{sorted.filter(c=>c.centre_id===user?.centre_id && (!search.trim() || `${c.district||""} ${c.city||""} ${c.name||""}`.toLowerCase().includes(search.trim().toLowerCase()))).map(c=><option key={c.centre_id} value={c.centre_id}>{c.district} — {c.city}{c.distance!=null?` • ${c.distance.toFixed(1)} km`:""}</option>)}{!sorted.some(c=>c.centre_id===user?.centre_id)&&user?.centre_id&&<option value={user.centre_id}>{user.district || user.centre_id} — {user.centre_id}</option>}</select><p className="mt-1 text-[10px] font-semibold text-slate-500">{t("assignedCentre")}: {user?.district || "—"}</p></div>
      <div className="grid gap-4 sm:grid-cols-2"><div><label className="ks-label">{t("crop")}</label><select value={f.crop} onChange={e=>update("crop",e.target.value)} className="ks-input"><option>Wheat</option><option>Rice</option><option>Maize</option><option>Mustard</option></select></div><div><label className="ks-label">{t("quantity")}</label><input required type="number" min="1" step="1" value={f.quantity_kg} onChange={e=>update("quantity_kg",e.target.value)} className="ks-input"/></div><div><label className="ks-label">{t("selectDate")}</label><input required type="date" min={today()} value={f.date} onChange={e=>{update("date",e.target.value);update("slot","");}} className="ks-input"/></div><div><label className="ks-label">{t("selectSlot")}</label><select required value={f.slot} onChange={e=>update("slot",e.target.value)} className="ks-input"><option value="">{loadingSlots ? t("loading") : t("chooseSlot")}</option>{slots.map(s=><option key={s.slot} disabled={!s.available} value={s.slot}>{s.slot} — {s.available} {t("left")} • {t("capacityShort")} {s.capacity}</option>)}</select></div></div>
      {aiRec?.results?.length>0 && (() => { const ranked=[...aiRec.results].filter(x=>x.available>0).sort((a,b)=>a.predicted_wait_min-b.predicted_wait_min); const best=ranked[0]; return best ? <div className="rounded-2xl border border-indigo-100 bg-indigo-50 p-4"><div className="flex items-start justify-between gap-3"><div><b className="text-sm text-indigo-900">🧠 {t("aiSmartSlotPlanner")}</b><p className="mt-1 text-xs text-slate-600">{t("bestSlot")}: <b>{best.slot}</b> • {t("predictedWait")}: <b>{best.predicted_wait_min} {t("minUnit")}</b> • {best.available} {t("capacityLeft")}</p><p className="mt-1 text-[11px] text-slate-500">{t("aiPlannerDesc")} {aiRec.training_samples} {t("historicalObservations")}</p></div><button type="button" onClick={()=>update("slot",best.slot)} className="rounded-xl bg-indigo-700 px-3 py-2 text-xs font-extrabold text-white">{t("useAiSlot")}</button></div><div className="mt-3 grid gap-2 sm:grid-cols-3">{ranked.slice(0,3).map((x,i)=><button type="button" key={x.slot} onClick={()=>update("slot",x.slot)} className={`rounded-xl bg-white p-3 text-left ring-1 ${i===0?'ring-indigo-300':'ring-slate-100'}`}><span className="text-[10px] font-black text-indigo-600">#{i+1} {t("aiPick")}</span><b className="mt-1 block text-xs">{x.slot}</b><span className="text-[11px] text-slate-500">~{x.predicted_wait_min} {t("minUnit")} • {x.available} {t("left")}</span></button>)}</div></div> : null; })()}
      <div className="grid gap-3 sm:grid-cols-3">{slots.map(s=><div key={s.slot} className={`rounded-2xl border p-3 ${f.slot===s.slot?"border-emerald-500 bg-emerald-50":"border-slate-200 bg-white"}`}><button type="button" disabled={!s.available || loadingSlots} onClick={()=>update("slot",s.slot)} className="w-full text-left disabled:opacity-40"><span className="block text-xs font-bold text-slate-500">{s.slot}</span><b className="mt-1 block text-sm">{s.available} {t("slotsWord")}</b><span className="text-[10px] text-slate-400">{t("capacityWord")} {s.capacity} • ~{s.service_minutes}m {t("serviceWord")}</span></button>{s.is_full&&!s.is_past&&<button type="button" onClick={()=>joinWaitlist(s.slot)} className="mt-2 w-full rounded-lg bg-amber-50 px-2 py-2 text-[10px] font-extrabold text-amber-700">{t("joinWaitlist")}</button>}</div>)}</div>
      <div className="flex flex-col gap-3 rounded-2xl bg-slate-50 p-4 sm:flex-row sm:items-center"><div className="flex-1"><b className="text-sm">{t("estimatedValue")}</b><p className="text-xs text-slate-500">{adminRate ? <>{t("adminRateLabel")}: ₹{Number(adminRate.rate_per_kg).toFixed(2)}/kg • {adminRate.market || t("biharMandi")}</> : <>{t("adminRateUnavailable")}. {adminRateError || t("retryAdminRates")}</>} • {t("finalAmountDepends")}</p></div><b className="text-2xl font-black text-emerald-700">{adminRate ? money(Number(f.quantity_kg)*Number(adminRate.rate_per_kg)) : "—"}</b></div>
      {(error || success) && <div className={`flex items-start gap-2 rounded-xl p-3 text-sm font-bold ${error?"bg-red-50 text-red-700":"bg-emerald-50 text-emerald-700"}`}>{error?<AlertCircle size={18}/>:<CheckCircle2 size={18}/>}<span>{error || success}</span></div>}{confirmedBooking?.token && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><b className="text-sm text-emerald-900">🎫 {t("gatePassReady")}</b><p className="mt-1 text-xs text-emerald-800">{t("tokenPdfInfo")} <b>{confirmedBooking.token}</b></p></div><button type="button" onClick={downloadGatePass} className="rounded-xl bg-emerald-700 px-4 py-3 text-xs font-black text-white">{t("downloadGatePass")}</button></div></div>}
      <button disabled={loading || loadingSlots || !f.centre_id} className="rounded-2xl bg-emerald-700 px-5 py-4 font-black text-white shadow-lg shadow-emerald-700/20 disabled:opacity-60">{loading ? t("bookingInProgress") : t("confirmBooking")} <ChevronRight className="ml-1 inline" size={18}/></button>
    </form></Card>
  </main>;
}
export default Booking;
