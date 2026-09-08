export const today = () => {
  const d = new Date();
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
};

export const money = (n) => `₹${Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

export const haversine = (lat1, lon1, lat2, lon2) => {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
};

let preferredVoice = null;
if (typeof window !== "undefined" && "speechSynthesis" in window) {
  const pick = () => {
    const voices = window.speechSynthesis.getVoices();
    preferredVoice = voices.find(v => /^hi-IN$/i.test(v.lang)) || voices.find(v => /^hi/i.test(v.lang)) || voices.find(v => /^en-IN$/i.test(v.lang)) || voices[0] || null;
  };
  pick();
  window.speechSynthesis.onvoiceschanged = pick;
}

export function speak(text, language = "hi-IN") {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  const Utterance = window.SpeechSynthesisUtterance;
  if (!Utterance) return false;
  window.speechSynthesis.cancel();
  const u = new Utterance(text);
  u.lang = language || "hi-IN";
  u.rate = 0.98;
  u.volume = 1;
  const voices = window.speechSynthesis.getVoices();
  const requested = String(language || "hi-IN").toLowerCase();
  const langPrefix = requested.split("-")[0];
  const voice = voices.find(v => String(v.lang || "").toLowerCase() === requested) || voices.find(v => String(v.lang || "").toLowerCase().startsWith(langPrefix)) || preferredVoice;
  if (voice) u.voice = voice;
  window.speechSynthesis.speak(u);
  return true;
}

export function localBot(q, language = "hi") {
  const text = String(q || "").toLowerCase();
  if (language === "hi") {
    if (/token|टोकन|queue|कतार|number|नंबर/.test(text)) return "आपका टोकन और कतार होम पेज पर लाइव अपडेट होते हैं। जब आपके आगे 2 से कम किसान हों, तो केंद्र की ओर निकल सकते हैं।";
    if (/slot|स्लॉट|booking|बुकिंग|book|बुक/.test(text)) return "बुक स्लॉट में केंद्र, तारीख, मात्रा और उपलब्ध समय स्लॉट चुनें।";
    if (/payment|भुगतान|paise|पैसे|paisa|पैसा|dbt/.test(text)) return "खरीद पूरी होने के बाद भुगतान पेज पर DBT स्थिति और राशि दिखाई देगी।";
    if (/receipt|रसीद|parchi|पर्ची/.test(text)) return "भुगतान पेज से ई-रसीद PDF डाउनलोड की जा सकती है।";
    if (/centre|center|केंद्र|mandi|मंडी|location|लोकेशन/.test(text)) return "लोकेशन खोजने पर किसानसेतु नज़दीकी खरीद केंद्र और दूरी दिखाता है।";
    return "मैं किसानसेतु सहायता बॉट हूँ। टोकन, स्लॉट, कतार, केंद्र, भुगतान या रसीद के बारे में पूछिए।";
  }
  if (/token|queue|number/.test(text)) return "Your token and queue update live on the Home page. When fewer than 2 farmers are ahead, you can leave for the centre.";
  if (/slot|booking|book/.test(text)) return "In Book Slot, select your centre, date, quantity and available time slot.";
  if (/payment|paise|paisa|dbt/.test(text)) return "After procurement is complete, the Payment page shows DBT status and amount.";
  if (/receipt|parchi/.test(text)) return "You can download the e-receipt PDF from the Payment page.";
  if (/centre|center|mandi|location/.test(text)) return "KisanSetu detects your location and shows the nearest procurement centre and distance.";
  return "I am the KisanSetu help bot. Ask me about your token, slot, queue, centre, payment or receipt.";
}
