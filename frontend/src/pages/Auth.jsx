import React, { useState } from "react";
import {
  ArrowRight,
  BadgeCheck,
  Building2,
  CalendarDays,
  CheckCircle2,
  Clock3,
  CloudSun,
  IndianRupee,
  LockKeyhole,
  MapPin,
  MessageSquareText,
  ShieldCheck,
  Smartphone,
  Sprout,
  Ticket,
  Truck,
  UserRound,
  WalletCards,
} from "lucide-react";

import { api, getApiError } from "../api/api";
import { BIHAR_CENTRES } from "../data/centres";
import { useLanguage } from "../i18n/LanguageContext";

const FEATURES = [
  {
    icon: CalendarDays,
    title: "Smart Slot Booking",
    text: "Visit date aur preferred time pehle se reserve karein.",
  },
  {
    icon: Ticket,
    title: "Live Token & Queue",
    text: "Token position aur estimated waiting time real-time dekhein.",
  },
  {
    icon: Clock3,
    title: "Smart Arrival",
    text: "Queue movement ke basis par better arrival timing milegi.",
  },
  {
    icon: WalletCards,
    title: "Procurement to DBT",
    text: "Weighment, quality, procurement aur payment status ek jagah.",
  },
];

function Auth({ onLogin }) {
  const { language, setLanguage, t, languages, supportedLanguages } = useLanguage();
  const [mode, setMode] = useState("login");
  const [role, setRole] = useState("farmer");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [registeredId, setRegisteredId] = useState("");

  const [form, setForm] = useState({
    farmer_id: "",
    employee_id: "",
    mobile: "",
    email: "",
    name: "",
    village: "",
    district: "Jehanabad",
    crop: "Wheat",
    centre_id: "C014",
    address: "",
    counters: 2,
    username: "",
    password: "",
  });

  const handleChange = (field, value) => setForm((prev) => ({ ...prev, [field]: value }));

  const handleRoleChange = (newRole) => {
    setRole(newRole);
    if (newRole === "admin") setMode("login");
    setMsg("");
    setRegisteredId("");
    handleChange("farmer_id", "");
    handleChange("employee_id", "");
  };

  const handleModeChange = (newMode) => {
    setMode(newMode);
    setMsg("");
    setRegisteredId("");
  };

  const validateForm = () => {
    if (mode === "login" && role === "admin") {
      if (!form.username?.trim() || !form.password) {
        setMsg("Admin username and password are required.");
        return false;
      }
      return true;
    }

    if (!/^[0-9]{10}$/.test(form.mobile.trim())) {
      setMsg("Please enter a valid 10-digit mobile number.");
      return false;
    }

    if (mode === "login" && role === "farmer" && !form.farmer_id.trim()) {
      setMsg("Farmer ID is required.");
      return false;
    }

    if (mode === "login" && role === "centre" && !form.employee_id.trim()) {
      setMsg("Employee ID is required.");
      return false;
    }

    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMsg("");
    if (!validateForm()) return;
    setLoading(true);

    try {
      if (mode === "register") {
        let response;
        if (role === "farmer") {
          response = await api.post("/farmers", {
            mobile: form.mobile.trim(),
            email: form.email.trim() || null,
            name: form.name.trim(),
            village: form.village.trim(),
            district: form.district.trim(),
            crop: form.crop,
            centre_id: form.centre_id,
          });
        } else {
          response = await api.post("/centres/register", {
            mobile: form.mobile.trim(),
            name: form.name.trim(),
            district: form.district.trim(),
            address: form.address.trim(),
            counters: Number(form.counters),
          });
        }

        const generatedId = response.data?.farmer_id;
        const centreId = response.data?.centre_id;

        if (role === "farmer") {
          setRegisteredId(generatedId || "");
          setMode("login");
          setForm((prev) => ({ ...prev, farmer_id: generatedId || "" }));
          setMsg(`Registration successful. Farmer ID: ${generatedId || "generated"}. Now login with Farmer ID + mobile.`);
        } else {
          setRegisteredId(centreId || "");
          setMode("login");
          setMsg(`Application submitted successfully. Centre ID: ${centreId || "generated"}. It is pending admin validation. Employee ID will be generated after approval.`);
        }
        return;
      }

      const loginData = {
        mobile: role === "admin" ? "" : form.mobile.trim(),
        role,
      };

      if (role === "admin") {
        loginData.username = form.username.trim();
        loginData.password = form.password;
      }
      if (role === "farmer") loginData.farmer_id = form.farmer_id.trim();
      if (role === "centre") loginData.employee_id = form.employee_id.trim();

      const response = await api.post("/auth/login", loginData);
      onLogin(role, response.data.user, response.data.access_token);
    } catch (error) {
      console.error("Authentication error:", error);
      setMsg(getApiError(error, "Request failed. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  const selectedCentre = BIHAR_CENTRES.find((c) => c.district === form.district);
  const isAdmin = role === "admin";

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#f4f8f5] text-slate-900">
      {/* Desktop / mobile hero */}
      <div className="relative overflow-hidden bg-[#073b2a] text-white">
        <div className="absolute -left-28 -top-32 h-72 w-72 rounded-full bg-emerald-400/15 blur-3xl" />
        <div className="absolute -right-20 bottom-0 h-80 w-80 rounded-full bg-lime-300/10 blur-3xl" />

        <div className="relative mx-auto max-w-7xl px-5 pb-7 pt-5 sm:px-8 md:pb-9 md:pt-7 lg:px-10">
          <div className="flex items-center justify-between gap-4">
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-white/10 text-2xl ring-1 ring-white/15 backdrop-blur">🌾</div>
              <div className="min-w-0">
                <div className="truncate text-xl font-black tracking-tight sm:text-2xl">KisanSetu</div>
                <div className="text-[10px] font-bold uppercase tracking-[.16em] text-emerald-200 sm:text-[11px]">{t("smartMandiFlow")}</div>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-full bg-white/10 px-3 py-2 text-[11px] font-bold text-emerald-50 ring-1 ring-white/10">
              <ShieldCheck size={15} /> {t("secureDigitalProcurement")}
              <select aria-label={t("switchLanguage")} value={language} onChange={e=>setLanguage(e.target.value)} className="ml-1 max-w-[115px] cursor-pointer bg-transparent text-emerald-50 outline-none">{supportedLanguages.map(code=><option className="text-slate-900" key={code} value={code}>{languages[code].native}</option>)}</select>
            </div>
          </div>

          <div className="mt-7 max-w-4xl md:mt-10">
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-400/10 px-3 py-1.5 text-[10px] font-black uppercase tracking-[.12em] text-emerald-200 ring-1 ring-emerald-300/15 sm:text-[11px]">
              <Sprout size={14} /> Bihar farmers • procurement centres • transparent journey
            </div>
            <h1 className="mt-4 max-w-3xl text-3xl font-black leading-[1.04] tracking-tight sm:text-4xl md:text-5xl lg:text-[54px]">
              Mandi visit ko <span className="text-emerald-300">predictable</span> banayein.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-emerald-50/75 sm:text-base sm:leading-7">
              Slot booking se lekar live token, Smart Arrival, digital weighment, procurement aur DBT payment tak — KisanSetu poori journey ko ek simple digital flow mein connect karta hai.
            </p>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-2.5 sm:grid-cols-4 sm:gap-3">
            {[
              ["38", "Bihar districts"],
              ["1", "Centre / district"],
              ["Live", "Queue tracking"],
              ["24×7", "Status access"],
            ].map(([value, label]) => (
              <div key={label} className="rounded-2xl bg-white/[.07] px-3 py-3 ring-1 ring-white/10 backdrop-blur-sm sm:px-4">
                <div className="text-lg font-black sm:text-xl">{value}</div>
                <div className="mt-0.5 text-[10px] font-semibold text-emerald-100/65 sm:text-[11px]">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <main className="mx-auto grid w-full max-w-7xl gap-6 px-4 py-5 sm:px-6 md:py-7 lg:grid-cols-[minmax(0,1.12fr)_minmax(390px,.88fr)] lg:px-10 lg:py-9">
        {/* Product story */}
        <section className="min-w-0 rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_18px_55px_rgba(16,55,34,.07)] sm:p-7 lg:p-8">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.12em] text-emerald-700">
            <BadgeCheck size={16} /> Why KisanSetu?
          </div>
          <h2 className="mt-2 max-w-2xl text-2xl font-black tracking-tight sm:text-3xl">Farmer ko sirf token nahi, poori journey ka control.</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Traditional mandi process mein uncertainty sabse bada problem hai. KisanSetu booking, queue aur payment information ko ek single farmer-friendly dashboard mein laata hai.
          </p>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {FEATURES.map(({ icon: Icon, title, text }, featureIndex) => (
              <div key={title} className="group rounded-2xl border border-slate-200 bg-slate-50/80 p-4 transition hover:-translate-y-0.5 hover:border-emerald-200 hover:bg-emerald-50/40">
                <div className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-100 text-emerald-700">
                  <Icon size={19} />
                </div>
                <h3 className="mt-3 text-sm font-black">{[t("smartSlotBooking"), t("liveQueue"), t("smartArrival"), t("dbtPayment")][featureIndex]}</h3>
                <p className="mt-1 text-xs leading-5 text-slate-500">{[t("authSmartSlotDesc"), t("authQueueDesc"), t("authArrivalDesc"), t("authDbtDesc")][featureIndex]}</p>
              </div>
            ))}
          </div>

          <div className="mt-5 grid gap-3 rounded-2xl bg-gradient-to-r from-emerald-50 to-lime-50 p-4 sm:grid-cols-3">
            <div className="flex items-center gap-3"><div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white text-emerald-700"><MapPin size={17}/></div><div><b className="block text-xs">{t("assignedCentreLabel")}</b><span className="text-[11px] text-slate-500">{t("districtRouting")}</span></div></div>
            <div className="flex items-center gap-3"><div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white text-emerald-700"><MessageSquareText size={17}/></div><div><b className="block text-xs">{t("smartAlerts")}</b><span className="text-[11px] text-slate-500">{t("queuePaymentUpdates")}</span></div></div>
            <div className="flex items-center gap-3"><div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white text-emerald-700"><LockKeyhole size={17}/></div><div><b className="block text-xs">{t("secureAccess")}</b><span className="text-[11px] text-slate-500">{t("roleBasedPlatform")}</span></div></div>
          </div>

          <div className="mt-5 hidden items-center gap-4 border-t border-slate-100 pt-5 text-xs text-slate-500 sm:flex">
            <div className="flex items-center gap-2"><CloudSun size={16} className="text-emerald-700"/> Weather-aware planning ready</div>
            <div className="h-4 w-px bg-slate-200" />
            <div className="flex items-center gap-2"><Smartphone size={16} className="text-emerald-700"/> Mobile-friendly PWA experience</div>
          </div>
        </section>

        {/* Auth */}
        <section className="min-w-0 self-start rounded-[28px] border border-slate-200 bg-white p-4 shadow-[0_20px_70px_rgba(28,61,37,.13)] sm:p-6 lg:sticky lg:top-6 lg:p-7">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-lg font-black sm:text-xl">{t("welcome")}</div>
              <p className="mt-1 text-xs leading-5 text-slate-500">Apni role select karein aur secure access se continue karein.</p>
            </div>
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-emerald-50 text-emerald-700"><Truck size={19}/></div>
          </div>

          <div className="mt-5 grid grid-cols-3 gap-1 rounded-2xl bg-slate-100 p-1">
            {[
              ["farmer", UserRound, t("farmer")],
              ["centre", Building2, t("centre")],
              ["admin", ShieldCheck, t("admin")],
            ].map(([value, Icon, label]) => (
              <button type="button" key={value} onClick={() => handleRoleChange(value)} className={`flex min-w-0 items-center justify-center gap-1.5 rounded-xl px-2 py-3 text-xs font-black transition sm:text-sm ${role === value ? "bg-white text-emerald-700 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}>
                <Icon size={16}/><span>{label}</span>
              </button>
            ))}
          </div>

          {!isAdmin && (
            <div className="mt-3 flex rounded-xl border border-slate-200 p-1">
              <button type="button" onClick={() => handleModeChange("login")} className={`flex-1 rounded-lg py-2.5 text-xs font-black sm:text-sm ${mode === "login" ? "bg-emerald-700 text-white" : "text-slate-500"}`}>{t("login")}</button>
              <button type="button" onClick={() => handleModeChange("register")} className={`flex-1 rounded-lg py-2.5 text-xs font-black sm:text-sm ${mode === "register" ? "bg-emerald-700 text-white" : "text-slate-500"}`}>{t("registration")}</button>
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-4 grid gap-3">
            {mode === "login" && role === "admin" && <>
              <label className="ks-label">{t("adminUsername")}<input className="ks-input" placeholder="Enter admin username" value={form.username} onChange={e=>handleChange("username",e.target.value)} required /></label>
              <label className="ks-label">{t("adminPassword")}<input className="ks-input" type="password" placeholder="Enter admin password" value={form.password} onChange={e=>handleChange("password",e.target.value)} required /></label>
            </>}

            {mode === "login" && role === "farmer" && <label className="ks-label">{t("farmerIdLabel")}<input className="ks-input" placeholder="e.g. F123456" value={form.farmer_id} onChange={e=>handleChange("farmer_id",e.target.value.toUpperCase())} required /></label>}
            {mode === "login" && role === "centre" && <label className="ks-label">{t("employeeIdLabel")}<input className="ks-input" placeholder="e.g. EMP-1001" value={form.employee_id} onChange={e=>handleChange("employee_id",e.target.value.toUpperCase())} required /></label>}

            {mode === "register" && <label className="ks-label">{role === "farmer" ? "Farmer Name" : "Centre Manager / Employee Name"}<input className="ks-input" placeholder={role === "farmer" ? "Enter your full name" : "Enter responsible person name"} value={form.name} onChange={e=>handleChange("name",e.target.value)} required /></label>}

            {!isAdmin && <label className="ks-label">Registered Mobile Number<input className="ks-input" type="tel" inputMode="numeric" maxLength={10} placeholder="10-digit mobile number" value={form.mobile} onChange={e=>handleChange("mobile",e.target.value.replace(/\D/g,""))} required /></label>}

            {mode === "register" && role === "farmer" && <>
              <label className="ks-label">Email <span className="font-semibold text-slate-400">(optional)</span><input className="ks-input" type="email" placeholder="For notifications" value={form.email} onChange={e=>handleChange("email",e.target.value)} /></label>
              <label className="ks-label">Village<input className="ks-input" placeholder="Village / Panchayat" value={form.village} onChange={e=>handleChange("village",e.target.value)} required /></label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="ks-label">District<select className="ks-input" value={form.district} onChange={e=>{const district=e.target.value;const centre=BIHAR_CENTRES.find(c=>c.district===district);handleChange("district",district);handleChange("centre_id",centre?.centre_id||"")}} required>{BIHAR_CENTRES.map(c=><option key={c.centre_id} value={c.district}>{c.district}</option>)}</select></label>
                <label className="ks-label">Crop<select className="ks-input" value={form.crop} onChange={e=>handleChange("crop",e.target.value)}><option>Wheat</option><option>Rice</option><option>Maize</option><option>Mustard</option></select></label>
              </div>
              <div className="flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-2.5 text-xs font-bold text-emerald-800"><MapPin size={15}/><span>Assigned Centre: <b>{selectedCentre?.centre_id || "—"}</b> • {selectedCentre?.city || form.district}</span></div>
            </>}

            {mode === "register" && role === "centre" && <>
              <label className="ks-label">District<select className="ks-input" value={form.district} onChange={e=>{const district=e.target.value;const centre=BIHAR_CENTRES.find(c=>c.district===district);handleChange("district",district);handleChange("centre_id",centre?.centre_id||"")}} required>{BIHAR_CENTRES.map(c=><option key={c.centre_id} value={c.district}>{c.district}</option>)}</select></label>
              <div className="flex items-center gap-2 rounded-xl bg-indigo-50 px-3 py-2.5 text-xs font-bold text-indigo-800"><Building2 size={15}/><span>Centre Code: <b>{selectedCentre?.centre_id || "Will be generated"}</b></span></div>
              <label className="ks-label">Centre Address<input className="ks-input" placeholder="Full procurement centre address" value={form.address} onChange={e=>handleChange("address",e.target.value)} required /></label>
              <label className="ks-label">Number of Counters<input className="ks-input" type="number" min="1" max="20" value={form.counters} onChange={e=>handleChange("counters",Number(e.target.value))} /></label>
            </>}

            <button type="submit" disabled={loading} className={`mt-1 flex min-h-12 items-center justify-center gap-2 rounded-2xl px-4 py-3.5 text-sm font-black text-white shadow-lg transition disabled:cursor-not-allowed disabled:opacity-60 ${isAdmin ? "bg-indigo-700 shadow-indigo-700/20 hover:bg-indigo-800" : "bg-emerald-700 shadow-emerald-700/20 hover:bg-emerald-800"}`}>
              {loading ? "Please wait..." : mode === "login" ? "Continue to KisanSetu" : "Create KisanSetu Account"}
              {!loading && <ArrowRight size={17}/>} 
            </button>

            {msg && <div className={`rounded-2xl p-3 text-xs font-semibold leading-5 ${registeredId ? "bg-emerald-50 text-emerald-800 ring-1 ring-emerald-100" : "bg-red-50 text-red-700 ring-1 ring-red-100"}`}>
              <div className="flex items-start gap-2"><CheckCircle2 size={16} className="mt-0.5 shrink-0"/><span>{msg}</span></div>
              {registeredId && <div className="mt-2 rounded-xl bg-white px-3 py-2 font-black tracking-wide ring-1 ring-emerald-100">{role === "farmer" ? "Farmer ID" : "Centre ID"}: {registeredId}</div>}
            </div>}
          </form>

          <div className="mt-5 border-t border-slate-100 pt-4">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-slate-50 px-2 py-2.5"><IndianRupee size={15} className="mx-auto text-emerald-700"/><span className="mt-1 block text-[9px] font-bold text-slate-500 sm:text-[10px]">{t("paymentTracking")}</span></div>
              <div className="rounded-xl bg-slate-50 px-2 py-2.5"><CheckCircle2 size={15} className="mx-auto text-emerald-700"/><span className="mt-1 block text-[9px] font-bold text-slate-500 sm:text-[10px]">{t("digitalStatus")}</span></div>
              <div className="rounded-xl bg-slate-50 px-2 py-2.5"><Smartphone size={15} className="mx-auto text-emerald-700"/><span className="mt-1 block text-[9px] font-bold text-slate-500 sm:text-[10px]">{t("mobileReady")}</span></div>
            </div>
            <p className="mt-3 text-center text-[10px] leading-4 text-slate-400">
              {role === "admin" ? "Admin access is restricted to authorized KisanSetu administrators." : mode === "login" && role === "farmer" ? "Farmer login requires Farmer ID + registered mobile number." : mode === "login" && role === "centre" ? "Centre login requires Employee ID + registered mobile number." : "Register first, then login using your generated ID and registered mobile number."}
            </p>
          </div>
        </section>
      </main>

      <footer className="px-5 pb-7 text-center text-[10px] font-semibold text-slate-400 sm:text-xs">
        KisanSetu • Smart Procurement & Queue Management • Built for Bihar's digital mandi journey
      </footer>
    </div>
  );
}

export default Auth;
