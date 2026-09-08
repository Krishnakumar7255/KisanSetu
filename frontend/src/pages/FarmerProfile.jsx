import React, { useEffect, useMemo, useState } from "react";
import { UserRound, Phone, Mail, MapPin, Sprout, Building2, Pencil, Save, X, ShieldCheck, Ticket, CalendarDays, ArrowLeft, Copy, Check } from "lucide-react";
import { api, getApiError } from "../api/api";
import { Card, Pill } from "../components/UI";
import { useLanguage } from "../i18n/LanguageContext";

const CROPS = ["Wheat", "Rice", "Maize", "Mustard"];

function FarmerField({ icon: Icon, label, value, name, type = "text", options, editing, form, setForm }) {
  return editing ? (
    <label className="block">
      <span className="mb-1.5 block text-xs font-bold text-slate-500">{label}</span>
      {options ? (
        <div className="relative">
          <Icon size={17} className="pointer-events-none absolute left-3 top-3.5 text-emerald-700"/>
          <select className="ks-input w-full pl-10" value={form[name] ?? ""} onChange={e => setForm(prev => ({ ...prev, [name]: e.target.value }))}>
            {options.map(x => <option key={x}>{x}</option>)}
          </select>
        </div>
      ) : (
        <div className="relative">
          <Icon size={17} className="pointer-events-none absolute left-3 top-3.5 text-emerald-700"/>
          <input className="ks-input w-full pl-10" type={type} value={form[name] ?? ""} onChange={e => setForm(prev => ({ ...prev, [name]: e.target.value }))} required={name !== "email"}/>
        </div>
      )}
    </label>
  ) : (
    <div className="rounded-2xl bg-slate-50 p-4">
      <div className="flex items-center gap-2 text-xs font-bold text-slate-500"><Icon size={16} className="text-emerald-700"/>{label}</div>
      <div className="mt-2 break-words text-sm font-extrabold text-slate-900">{value || "—"}</div>
    </div>
  )
}

export default function FarmerProfile({ user, onBack, onUserUpdate }) {
  const { language, t } = useLanguage();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: user?.name || "", email: user?.email || "", village: user?.village || "", district: user?.district || "", crop: user?.crop || "Wheat" });
  const [bookings, setBookings] = useState([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setForm({ name: user?.name || "", email: user?.email || "", village: user?.village || "", district: user?.district || "", crop: user?.crop || "Wheat" });
    api.get(`/bookings/${user.farmer_id}`).then(r => setBookings(Array.isArray(r.data) ? r.data : [])).catch(() => setBookings([]));
  }, [user]);

  const active = useMemo(() => bookings.filter(b => ["waiting", "serving", "procurement_pending"].includes(b.status)), [bookings]);
  const latest = bookings.at(-1);
  const copyId = async () => {
    try { await navigator.clipboard.writeText(user.farmer_id); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch {}
  };
  const save = async () => {
    setMsg(""); setSaving(true);
    try {
      const res = await api.patch(`/farmers/${user.farmer_id}`, form);
      onUserUpdate?.(res.data);
      setEditing(false);
      setMsg(t("profile") + " ✓");
    } catch (e) { setMsg(getApiError(e, t("error"))); }
    finally { setSaving(false); }
  };
  const cancel = () => { setForm({ name: user?.name || "", email: user?.email || "", village: user?.village || "", district: user?.district || "", crop: user?.crop || "Wheat" }); setEditing(false); setMsg(""); };

  const labels = {
    title: t("profile"), subtitle: t("details"), edit: t("profile"), save: t("save"), cancel: t("cancel"),
    farmerId: t("farmerIdText"), mobile: t("mobileText"), email: t("emailText"), name: t("nameText"), village: t("villageLabel"), district: t("districtText"), crop: t("crop"),
    centre: t("selectCentre"), account: t("accountInformation"), created: t("registered"), bookings: t("totalBookings"), active: t("activeBookings"), latest: t("latestBookingText"),
    secure: t("profileProtected"), noBooking: t("noData"), copied: t("copiedText")
  };



  return <main className="mx-auto max-w-5xl px-4 pb-28 pt-5 md:px-7 md:pb-12 md:pt-8">
    <div className="mb-5 flex items-center gap-3"><button onClick={onBack} className="grid h-10 w-10 place-items-center rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-50" aria-label={t("backText")}><ArrowLeft size={19}/></button><div><h1 className="text-2xl font-black text-slate-900 md:text-3xl">{labels.title}</h1><p className="mt-1 text-sm text-slate-500">{labels.subtitle}</p></div></div>

    <Card className="overflow-hidden"><div className="bg-gradient-to-br from-emerald-900 to-emerald-700 p-6 text-white md:p-8"><div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-4"><div className="grid h-16 w-16 place-items-center rounded-2xl bg-white/15 text-2xl ring-1 ring-white/20"><UserRound size={30}/></div><div><div className="text-xl font-black">{user.name}</div><div className="mt-1 text-sm text-emerald-100">{user.village}, {user.district}</div><div className="mt-2 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold"><ShieldCheck size={14}/> {labels.secure}</div></div></div>{!editing ? <button onClick={() => { setMsg(""); setEditing(true); }} className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-extrabold text-emerald-800"><Pencil size={16}/> {labels.edit}</button> : <div className="flex gap-2"><button onClick={cancel} className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-3 text-sm font-extrabold text-white ring-1 ring-white/20"><X size={16}/> {labels.cancel}</button><button onClick={save} disabled={saving} className="inline-flex items-center gap-2 rounded-xl bg-emerald-300 px-4 py-3 text-sm font-extrabold text-emerald-950"><Save size={16}/> {saving ? t("savingText") : labels.save}</button></div>}</div></div>
      <div className="p-5 md:p-7">
        <div className="mb-5 flex flex-col gap-3 rounded-2xl border border-emerald-100 bg-emerald-50 p-4 sm:flex-row sm:items-center sm:justify-between"><div><div className="text-xs font-bold text-emerald-700">{labels.farmerId}</div><div className="mt-1 text-2xl font-black tracking-wider text-emerald-900">{user.farmer_id}</div></div><button onClick={copyId} className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-3 py-2 text-xs font-extrabold text-slate-700 ring-1 ring-emerald-100">{copied ? <Check size={15}/> : <Copy size={15}/>} {copied ? labels.copied : t("copyIdText")}</button></div>
        <div className="grid gap-4 md:grid-cols-2"><FarmerField editing={editing} form={form} setForm={setForm} icon={UserRound} label={labels.name} value={user.name} name="name"/><FarmerField editing={false} form={form} setForm={setForm} icon={Phone} label={labels.mobile} value={user.mobile} name="mobile"/><FarmerField editing={editing} form={form} setForm={setForm} icon={Mail} label={labels.email} value={user.email} name="email" type="email"/><FarmerField editing={editing} form={form} setForm={setForm} icon={MapPin} label={labels.village} value={user.village} name="village"/><FarmerField editing={editing} form={form} setForm={setForm} icon={MapPin} label={labels.district} value={user.district} name="district"/><FarmerField editing={editing} form={form} setForm={setForm} icon={Sprout} label={labels.crop} value={user.crop} name="crop" options={CROPS}/></div>
        <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4"><div className="flex items-center gap-2 text-xs font-bold text-slate-500"><Building2 size={16} className="text-emerald-700"/>{labels.centre}</div><div className="mt-2 text-sm font-extrabold text-slate-900">{user.centre_id || "C014"} <span className="font-semibold text-slate-500">• {user.district || "Bihar"} {t("procurementCentreText")}</span></div><p className="mt-1 text-xs text-slate-500">{t("centreIdHelp")}</p></div>
        {msg && <div className={`mt-4 rounded-xl p-3 text-sm font-semibold ${msg.includes("failed") || msg.includes("nahi") || msg.includes("Could") ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>{msg}</div>}
      </div></Card>

    <div className="mt-5 grid gap-4 sm:grid-cols-3"><div className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-center gap-2 text-xs font-bold text-slate-500"><CalendarDays size={17} className="text-emerald-700"/>{labels.bookings}</div><div className="mt-3 text-3xl font-black">{bookings.length}</div></div><div className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-center gap-2 text-xs font-bold text-slate-500"><Ticket size={17} className="text-emerald-700"/>{labels.active}</div><div className="mt-3 text-3xl font-black text-emerald-700">{active.length}</div></div><div className="rounded-2xl border border-slate-200 bg-white p-5"><div className="text-xs font-bold text-slate-500">{labels.latest}</div><div className="mt-3 text-2xl font-black">{latest?.token || "—"}</div><div className="mt-1 text-xs font-semibold text-slate-500">{latest ? `${latest.date} • ${latest.slot}` : labels.noBooking}</div></div></div>
  </main>;
}
