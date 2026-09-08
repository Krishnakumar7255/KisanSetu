import React, { useEffect, useMemo, useState } from 'react';
import { ExternalLink, RefreshCw, Search, ShieldCheck, Sprout, Landmark, CreditCard, Droplets, Tractor, ChevronRight } from 'lucide-react';
import { api } from '../api/api';
import { Card, Pill } from '../components/UI';
import { useLanguage } from '../i18n/LanguageContext';

const CATEGORY_ICONS = { Financial: CreditCard, Insurance: ShieldCheck, Irrigation: Droplets, Machinery: Tractor, Agriculture: Sprout, Credit: Landmark };

function FarmerSchemes({ user }) {
  const { language, t } = useLanguage();
  const [schemes, setSchemes] = useState([]);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('All');
  const [loading, setLoading] = useState(true);
  const [lastSync, setLastSync] = useState(null);
  const [source, setSource] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get('/schemes', { params: { state: user?.state || 'Bihar', language: language === 'hi' ? 'hi' : 'en' } });
      setSchemes(Array.isArray(r.data?.items) ? r.data.items : []);
      setLastSync(r.data?.catalog_checked_at || null);
      setSource(r.data?.source || 'myScheme / Government of India');
    } catch {
      setSchemes([]);
      setSource('myScheme / Government of India');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [user?.state, language]);

  const categories = useMemo(() => ['All', ...Array.from(new Set(schemes.map(s => s.category).filter(Boolean)))], [schemes]);
  const filtered = useMemo(() => schemes.filter(s => {
    const text = `${s.name} ${s.short_description || ''} ${s.category || ''} ${s.level || ''}`.toLowerCase();
    return (!query.trim() || text.includes(query.toLowerCase())) && (category === 'All' || s.category === category);
  }), [schemes, query, category]);

  return <main className="mx-auto max-w-7xl px-4 pb-28 pt-5 md:px-7 md:pb-12 md:pt-8">
    <div className="rounded-[28px] bg-gradient-to-br from-emerald-900 via-emerald-800 to-slate-900 p-5 text-white shadow-xl md:p-7">
      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div>
          <Pill className="bg-white/10 text-emerald-100"><Sprout size={14}/> {t("schemes")}</Pill>
          <h1 className="mt-3 text-3xl font-black md:text-4xl">{t("governmentSchemes") || "Government Schemes for Farmers"}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-emerald-100">{t("schemesIntroText")}</p>
        </div>
        <a href="https://www.myscheme.gov.in/" target="_blank" rel="noopener noreferrer" className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-extrabold text-emerald-900 hover:bg-emerald-50"><ExternalLink size={16}/> {t("liveSchemeFinder") || "Open Government Scheme Finder"}</a>
      </div>
    </div>

    <Card className="mt-5">
      <div className="p-4 md:p-5">
        <div className="flex flex-col gap-3 md:flex-row">
          <div className="relative flex-1"><Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder={t("schemeSearch") || "Search schemes..."} className="ks-input w-full pl-10" /></div>
          <button onClick={load} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-100 px-4 py-2.5 text-sm font-bold text-slate-700"><RefreshCw size={16} className={loading?'animate-spin':''}/> {t("refresh")}</button>
        </div>
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">{categories.map(c=><button key={c} onClick={()=>setCategory(c)} className={`whitespace-nowrap rounded-full px-3 py-2 text-xs font-bold ${category===c?'bg-emerald-700 text-white':'bg-slate-100 text-slate-600'}`}>{c}</button>)}</div>
      </div>
    </Card>

    <div className="mt-5 flex items-center justify-between gap-3">
      <div><h2 className="text-lg font-black text-slate-900">{t("featuredSchemes") || "Recommended & featured schemes"}</h2><p className="text-xs text-slate-500">{t("schemeSourceNote") || "Official government source links; always verify eligibility before applying."}</p></div>
      {lastSync && <span className="text-[10px] font-semibold text-slate-400">{t("catalogChecked")}: {lastSync}</span>}
    </div>

    {loading ? <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{[1,2,3].map(i=><div key={i} className="h-48 animate-pulse rounded-2xl bg-slate-100"/>)}</div> :
      <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{filtered.map(s=>{
        const Icon = CATEGORY_ICONS[s.category] || Sprout;
        return <Card key={s.id} className="overflow-hidden">
          <div className="p-5">
            <div className="flex items-start justify-between gap-3"><div className="grid h-11 w-11 place-items-center rounded-xl bg-emerald-50 text-emerald-700"><Icon size={21}/></div><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700">{s.level}</span></div>
            <h3 className="mt-4 text-base font-black text-slate-900">{s.name}</h3>
            <p className="mt-2 min-h-12 text-xs leading-5 text-slate-500">{s.short_description}</p>
            {s.benefit && <div className="mt-3 rounded-xl bg-amber-50 p-3"><span className="text-[10px] font-bold text-amber-700">{t("benefitText")}</span><p className="mt-1 text-xs font-bold text-slate-700">{s.benefit}</p></div>}
            <div className="mt-4 flex items-center justify-between gap-2"><span className="text-[10px] font-semibold text-slate-400">{s.category}</span><a href={s.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-xl bg-emerald-700 px-3 py-2 text-xs font-extrabold text-white">{t("officialDetailsText")} <ChevronRight size={14}/></a></div>
          </div>
        </Card>;
      })}</div>}

    {!loading && !filtered.length && <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center"><p className="font-bold text-slate-700">{t("noSchemesText")}</p><button onClick={()=>{setQuery('');setCategory('All')}} className="mt-2 text-xs font-bold text-emerald-700">{t("clearFiltersText")}</button></div>}

    <div className="mt-5 rounded-2xl border border-indigo-100 bg-indigo-50 p-4 text-xs leading-5 text-slate-600"><b className="text-slate-800">{t("liveSource")}:</b> {source}. {t("officialSchemeNote")}</div>
  </main>;
}
export default FarmerSchemes;
