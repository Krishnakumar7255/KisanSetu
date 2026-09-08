import React, { useEffect, useState } from "react";
import { Building2, Phone, MapPin, Pencil, Save, X, ShieldCheck, Copy, Check, Hash, UsersRound } from "lucide-react";
import { api, getApiError } from "../api/api";
import { Card } from "../components/UI";
import { useLanguage } from "../i18n/LanguageContext";

function EmployeeField ({ icon: Icon, label, value, name, type = "text", editing, form, setForm }) {
  return editing ? (
    <label className="block">
      <span className="mb-1.5 block text-xs font-bold text-slate-500">{label}</span>
      <div className="relative">
        <Icon size={17} className="pointer-events-none absolute left-3 top-3.5 text-emerald-700" />
        <input className="ks-input w-full pl-10" type={type} value={form[name] ?? ""} onChange={(e) => setForm(prev => ({ ...prev, [name]: e.target.value }))} required />
      </div>
    </label>
  ) : (
    <div className="rounded-2xl bg-slate-50 p-4">
      <div className="flex items-center gap-2 text-xs font-bold text-slate-500"><Icon size={16} className="text-emerald-700" />{label}</div>
      <div className="mt-2 break-words text-sm font-extrabold text-slate-900">{value || "—"}</div>
    </div>
  )
}

export default function EmployeeProfile({ user, onBack, onUserUpdate }) {
  const { language } = useLanguage();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [copied, setCopied] = useState(false);
  const [form, setForm] = useState({
    name: user?.name || "",
    district: user?.district || "",
    city: user?.city || "",
    address: user?.address || "",
    counters: user?.counters || 2,
  });

  useEffect(() => {
    setForm({
      name: user?.name || "",
      district: user?.district || "",
      city: user?.city || "",
      address: user?.address || "",
      counters: user?.counters || 2,
    });
  }, [user]);

  const labels = language === "hi" ? {
    title: "कर्मचारी प्रोफाइल", subtitle: "आपकी खरीद केंद्र और कर्मचारी जानकारी",
    edit: "प्रोफाइल एडिट करें", save: "सेव करें", cancel: "रद्द करें",
    employeeId: "Employee ID", mobile: "मोबाइल नंबर", name: "केंद्र / कर्मचारी नाम",
    district: "जिला", city: "शहर", address: "केंद्र का पता", counters: "काउंटर",
    secure: "प्रोफाइल सुरक्षित है", copied: "Copied!", copy: "Copy ID",
    readOnly: "Employee ID और Mobile Number बदले नहीं जा सकते।"
  } : {
    title: "Employee Profile", subtitle: "Your procurement centre and employee information",
    edit: "Edit Profile", save: "Save Changes", cancel: "Cancel",
    employeeId: "Employee ID", mobile: "Mobile Number", name: "Centre / Employee Name",
    district: "District", city: "City", address: "Centre Address", counters: "Counters",
    secure: "Profile is protected", copied: "Copied!", copy: "Copy ID",
    readOnly: "Employee ID and Mobile Number cannot be changed."
  };

  const copyId = async () => {
    try {
      await navigator.clipboard.writeText(user?.employee_id || "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  const cancel = () => {
    setForm({ name: user?.name || "", district: user?.district || "", city: user?.city || "", address: user?.address || "", counters: user?.counters || 2 });
    setEditing(false);
    setMsg("");
  };

  const save = async () => {
    setSaving(true);
    setMsg("");
    try {
      const response = await api.patch(`/centres/${user.centre_id}`, {
        name: form.name,
        address: form.address,
        counters: Number(form.counters),
      });
      onUserUpdate?.(response.data);
      setEditing(false);
      setMsg(language === "hi" ? "Profile successfully update ho gaya." : "Profile updated successfully.");
    } catch (error) {
      setMsg(getApiError(error, language === "hi" ? "Profile update nahi ho paya." : "Could not update profile."));
    } finally {
      setSaving(false);
    }
  };



  return (
    <main className="mx-auto max-w-5xl px-4 pb-28 pt-5 md:px-7 md:pb-12 md:pt-8">
      <div className="mb-5 flex items-center gap-3">
        <button onClick={onBack} className="grid h-10 w-10 place-items-center rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-50">←</button>
        <div>
          <h1 className="text-2xl font-black text-slate-900 md:text-3xl">{labels.title}</h1>
          <p className="mt-1 text-sm text-slate-500">{labels.subtitle}</p>
        </div>
      </div>

      <Card className="overflow-hidden">
        <div className="bg-gradient-to-br from-emerald-900 to-emerald-700 p-6 text-white md:p-8">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-4">
              <div className="grid h-16 w-16 place-items-center rounded-2xl bg-white/15 ring-1 ring-white/20"><Building2 size={30} /></div>
              <div>
                <div className="text-xl font-black">{user?.name}</div>
                <div className="mt-1 text-sm text-emerald-100">{user?.centre_id} • {user?.district}</div>
                <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold"><ShieldCheck size={14} /> {labels.secure}</div>
              </div>
            </div>
            {!editing ? (
              <button onClick={() => { setMsg(""); setEditing(true); }} className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-extrabold text-emerald-800"><Pencil size={16} /> {labels.edit}</button>
            ) : (
              <div className="flex gap-2">
                <button onClick={cancel} className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-3 text-sm font-extrabold text-white ring-1 ring-white/20"><X size={16} /> {labels.cancel}</button>
                <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 rounded-xl bg-emerald-300 px-4 py-3 text-sm font-extrabold text-emerald-950"><Save size={16} /> {saving ? "Saving..." : labels.save}</button>
              </div>
            )}
          </div>
        </div>

        <div className="p-5 md:p-7">
          <div className="mb-5 grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
              <div className="text-xs font-bold text-emerald-700">{labels.employeeId}</div>
              <div className="mt-1 text-2xl font-black tracking-wider text-emerald-900">{user?.employee_id || "—"}</div>
              <button onClick={copyId} className="mt-3 inline-flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-xs font-extrabold text-slate-700 ring-1 ring-emerald-100"><Copy size={15} />{copied ? labels.copied : labels.copy}</button>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-500"><Phone size={16} className="text-emerald-700" />{labels.mobile}</div>
              <div className="mt-2 text-lg font-black text-slate-900">{user?.mobile || "—"}</div>
              <p className="mt-1 text-xs text-slate-500">{labels.readOnly}</p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <EmployeeField editing={editing} form={form} setForm={setForm} icon={Building2} label={labels.name} value={user?.name} name="name" />
            <EmployeeField editing={false} form={form} setForm={setForm} icon={MapPin} label={labels.district} value={user?.district} name="district" />
            <EmployeeField editing={false} form={form} setForm={setForm} icon={MapPin} label={labels.city} value={user?.city} name="city" />
            <EmployeeField editing={editing} form={form} setForm={setForm} icon={UsersRound} label={labels.counters} value={user?.counters} name="counters" type="number" />
            <div className="md:col-span-2"><EmployeeField editing={editing} form={form} setForm={setForm} icon={MapPin} label={labels.address} value={user?.address} name="address" /></div>
          </div>

          {msg && <div className={`mt-4 rounded-xl p-3 text-sm font-semibold ${msg.includes("failed") || msg.includes("nahi") || msg.includes("Could") || msg.includes("Invalid") ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>{msg}</div>}
        </div>
      </Card>
    </main>
  );
}
