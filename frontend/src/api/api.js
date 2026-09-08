import axios from "axios";

const configuredApi = (import.meta.env.VITE_API_URL || "").trim();
const defaultApi = (() => {
  if (configuredApi) return configuredApi.replace(/\/$/, "");
  if (typeof window === "undefined") return "http://127.0.0.1:8000/api";
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") return `${window.location.protocol}//${host}:8000/api`;
  return "/api";
})();

export const api = axios.create({
  baseURL: defaultApi,
  timeout: 60000,
  headers: { "Content-Type": "application/json" },
});

export function getApiError(error, fallback = "Something went wrong") {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map(item => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const field = Array.isArray(item.loc) ? item.loc.filter(Boolean).slice(-1)[0] : "";
        const message = item.msg || item.message;
        return field && message ? `${field}: ${message}` : (message || JSON.stringify(item));
      }
      return "";
    }).filter(Boolean);
    return messages.join(", ") || fallback;
  }
  if (detail && typeof detail === "object") {
    return detail.msg || detail.message || detail.error || fallback;
  }
  if (error?.response?.data?.message) return String(error.response.data.message);
  if (error?.code === "ECONNABORTED" || error?.message?.toLowerCase?.().includes("timeout")) return "Backend response mein timeout ho gaya. FastAPI aur Supabase connection check karein.";
  if (error?.message === "Network Error") { const target = defaultApi.replace(/\/$/, "") + "/health"; return `Backend se connection nahi ho raha. FastAPI aur API connection check karein: ${target}`; }
  return error?.message ? String(error.message) : fallback;
}


api.interceptors.request.use((config) => {
  try {
    const session = JSON.parse(localStorage.getItem("ks_session") || "null");
    if (session?.access_token) config.headers.Authorization = `Bearer ${session.access_token}`;
  } catch {}
  return config;
});


// If the backend rejects an expired/invalid session, clear the stale browser session
// so the app can return to the login screen instead of looping on 401s.
api.interceptors.response.use(
  response => response,
  error => {
    if (error?.response?.status === 401) {
      try { localStorage.removeItem("ks_session"); window.dispatchEvent(new Event("ks:logout")); } catch {}
    }
    return Promise.reject(error);
  }
);
