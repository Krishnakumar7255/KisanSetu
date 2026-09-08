import React, { useEffect, useState } from "react";
import "./styles.css";
import { api } from "./api/api";
import Auth from "./pages/Auth";
import FarmerHome from "./pages/FarmerHome";
import FarmerProfile from "./pages/FarmerProfile";
import FarmerSchemes from "./pages/FarmerSchemes";
import EmployeeProfile from "./pages/EmployeeProfile";
import Booking from "./pages/Booking";
import Queue from "./pages/Queue";
import Payments from "./pages/Payments";
import Operator from "./pages/Operator";
import { Header } from "./components/Header";
import BottomNav from "./components/BottomNav";
import DesktopNav from "./components/DesktopNav";
import NotificationDrawer from "./components/NotificationDrawer";
import Admin from "./pages/Admin";
import SIHAccessibilityTools from "./components/sih/SIHAccessibilityTools";
import FarmerHelpAssistant from "./components/sih/FarmerHelpAssistant";
import Support from "./pages/Support";
import { useLanguage } from "./i18n/LanguageContext";

const FARMER_PAGES = ["Home", "Book Slot", "Queue", "Payments", "Schemes", "Support", "Profile"];
const CENTRE_PAGES = ["Dashboard", "Queue", "Procurement", "Profile"];
const ADMIN_PAGES = ["Dashboard", "Approvals", "Command Center", "Impact", "Profile"];

function readSession() {
  try {
    const raw = localStorage.getItem("ks_session");
    if (!raw) return null;
    const s = JSON.parse(raw);
    if (!s?.role || !s?.user) return null;
    return s;
  } catch {
    localStorage.removeItem("ks_session");
    return null;
  }
}

class ErrorBoundary extends React.Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error("KisanSetu frontend error", error, info); }
  render() {
    if (!this.state.error) return this.props.children;
    return <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-2xl rounded-2xl border border-red-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-black text-red-700">KisanSetu frontend error</h1>
        <p className="mt-2 text-sm text-slate-600">App render karte waqt error aaya.</p>
        <pre className="mt-4 overflow-auto rounded-xl bg-slate-50 p-4 text-xs">{String(this.state.error?.stack || this.state.error)}</pre>
        <button className="mt-4 rounded-xl bg-emerald-700 px-4 py-2 text-sm font-bold text-white" onClick={() => { localStorage.removeItem("ks_session"); location.reload(); }}>Reset session</button>
      </div>
    </div>;
  }
}

function App() {
  const { language } = useLanguage();
  const [session, setSession] = useState(readSession);
  const [page, setPage] = useState(() => {
    const s = readSession();
    return s?.role === "centre" || s?.role === "admin" ? "Dashboard" : s?.role === "farmer" ? "Home" : null;
  });
  const [showNotes, setShowNotes] = useState(false);
  const [notes, setNotes] = useState([]);

  const navigate = (next) => {
    if (!session) return;
    const allowed = session.role === "farmer" ? FARMER_PAGES : session.role === "centre" ? CENTRE_PAGES : ADMIN_PAGES;
    setPage(allowed.includes(next) ? next : (session.role === "farmer" ? "Home" : "Dashboard"));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const login = (role, user, access_token) => {
    const next = { role, user, access_token };
    localStorage.setItem("ks_session", JSON.stringify(next));
    setSession(next);
    setPage(role === "farmer" ? "Home" : "Dashboard");
  };

  const updateUser = (updatedUser) => {
    const next = { ...session, user: updatedUser };
    localStorage.setItem("ks_session", JSON.stringify(next));
    setSession(next);
  };

  const logout = () => {
    localStorage.removeItem("ks_session");
    setSession(null);
    setPage(null);
    setNotes([]);
  };

  useEffect(() => {
    const forceLogout = () => { setSession(null); setPage(null); setNotes([]); };
    window.addEventListener("ks:logout", forceLogout);
    return () => window.removeEventListener("ks:logout", forceLogout);
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (session?.role !== "farmer" || !session.user?.farmer_id) return undefined;
    api.get(`/notifications/${session.user.farmer_id}`)
      .then(r => { if (!cancelled) setNotes(Array.isArray(r.data) ? r.data : []); })
      .catch(() => { if (!cancelled) setNotes([]); });
    return () => { cancelled = true; };
  }, [session]);

  if (!session) return <Auth onLogin={login} />;
  const activePage = page || (session.role === "farmer" ? "Home" : "Dashboard");
  const { role, user } = session;

  return <div key={language} lang={language} className="min-h-screen">
    <Header user={user} onLogout={logout} onBell={() => setShowNotes(true)} onProfile={() => navigate("Profile")} unread={notes.length} />
    <DesktopNav page={activePage} setPage={navigate} role={role} />
    {role === "farmer" && activePage === "Home" && <FarmerHome user={user} setPage={navigate} />}
    {role === "farmer" && activePage === "Book Slot" && <Booking user={user} onBooked={() => {}} />}
    {role === "farmer" && activePage === "Queue" && <Queue user={user} />}
    {role === "farmer" && activePage === "Payments" && <Payments user={user} />}
    {role === "farmer" && activePage === "Schemes" && <FarmerSchemes user={user} />}
    {role === "farmer" && activePage === "Support" && <Support user={user} />}
    {role === "farmer" && activePage === "Profile" && <FarmerProfile user={user} onBack={() => navigate("Home")} onUserUpdate={updateUser} />}
    {role === "centre" && activePage !== "Profile" && <Operator user={user} page={activePage} />}
    {role === "admin" && <Admin user={user} page={activePage} />}
    {role === "centre" && activePage === "Profile" && <EmployeeProfile user={user} onBack={() => navigate("Dashboard")} onUserUpdate={updateUser} />}
    <BottomNav page={activePage} setPage={navigate} role={role} />
    {showNotes && <NotificationDrawer notes={notes} onClose={() => setShowNotes(false)} />}
    <SIHAccessibilityTools />
    {role === "farmer" && <FarmerHelpAssistant />}
  </div>;
}

export default function RootApp() {
  return <ErrorBoundary><App /></ErrorBoundary>;
}
