// Demo data so the UI runs standalone (deployable to Vercel with no backend).
// Swap these for live API calls when the FastAPI backend is wired in.

export type Category = "ev_charging" | "prosumer";
export type SourceType = "google_play" | "app_store" | "news" | "web_pages" | "youtube";

export interface AppItem {
  slug: string;
  name: string;
  category: Category;
  accent: string;
}

export const APPS: AppItem[] = [
  { slug: "chargepoint", name: "ChargePoint", category: "ev_charging", accent: "#22d3ee" },
  { slug: "evgo", name: "EVgo", category: "ev_charging", accent: "#38bdf8" },
  { slug: "electrify_america", name: "Electrify America", category: "ev_charging", accent: "#34d399" },
  { slug: "tesla", name: "Tesla", category: "ev_charging", accent: "#f472b6" },
  { slug: "blink", name: "Blink", category: "ev_charging", accent: "#60a5fa" },
  { slug: "flo", name: "FLO", category: "ev_charging", accent: "#2dd4bf" },
  { slug: "enphase", name: "Enphase", category: "prosumer", accent: "#a78bfa" },
  { slug: "solaredge", name: "SolarEdge", category: "prosumer", accent: "#fbbf24" },
  { slug: "tesla_powerwall", name: "Tesla Powerwall", category: "prosumer", accent: "#f87171" },
  { slug: "sense", name: "Sense", category: "prosumer", accent: "#818cf8" },
  { slug: "span", name: "Span", category: "prosumer", accent: "#4ade80" },
  { slug: "emporia", name: "Emporia", category: "prosumer", accent: "#c084fc" },
];

export const SOURCE_LABELS: Record<SourceType, string> = {
  google_play: "Google Play",
  app_store: "App Store",
  news: "News",
  web_pages: "Website",
  youtube: "YouTube",
};

export const KB_STATS = {
  total: 24863,
  bySource: [
    { source: "google_play" as SourceType, count: 8473, color: "#22d3ee" },
    { source: "app_store" as SourceType, count: 6572, color: "#818cf8" },
    { source: "news" as SourceType, count: 7218, color: "#c084fc" },
    { source: "web_pages" as SourceType, count: 1284, color: "#34d399" },
    { source: "youtube" as SourceType, count: 1316, color: "#f472b6" },
  ],
  apps: 12,
  freshness: "live",
};

export const EXAMPLE_QUESTIONS = [
  { q: "What are the most common complaints about ChargePoint reliability?", tag: "Reliability" },
  { q: "How does EVgo compare to Electrify America on pricing transparency?", tag: "Comparison" },
  { q: "Which prosumer apps have the best solar + battery monitoring UX?", tag: "Prosumer" },
  { q: "What's the latest news on NACS adoption across charging networks?", tag: "News" },
];

export const RECENT_CHATS = [
  { id: "1", title: "ChargePoint vs EVgo reliability", when: "2m ago" },
  { id: "2", title: "Enphase battery management UX", when: "1h ago" },
  { id: "3", title: "NACS rollout — who's fastest?", when: "Yesterday" },
  { id: "4", title: "Top complaints across EV apps", when: "Yesterday" },
];

export interface Source {
  app: string;
  source: SourceType;
  score: number;
  snippet: string;
}

// A canned, realistic answer + citations for the demo chat.
export const DEMO_ANSWER = `Across **8,473 Google Play** and **6,572 App Store** reviews, three reliability themes dominate ChargePoint feedback:

### 1. Session-start failures
The single most cited complaint. Users report the app spinning on "Starting session" or a charger showing **available in-app but offline on arrival**. This clusters heavily in reviews from the last quarter.

### 2. Map accuracy vs. ground truth
Stations frequently appear active on the map but are **out of service or ICE'd**. Several reviewers contrast this unfavorably with PlugShare's crowd-sourced status.

### 3. Payment & receipts
Sporadic double-charges and missing receipts, though sentiment here has **improved ~12%** since the latest app update per recent reviews.

> **Net:** reliability perception is dragged down by the gap between *in-app availability* and *real-world uptime* — the highest-leverage fix area.`;

export const DEMO_SOURCES: Source[] = [
  { app: "chargepoint", source: "google_play", score: 0.912, snippet: "App keeps failing to start a session and the map shows stations that are clearly offline when I arrive..." },
  { app: "chargepoint", source: "app_store", score: 0.884, snippet: "Reliability has been hit or miss — half the chargers it shows as available are broken or ICE'd." },
  { app: "chargepoint", source: "news", score: 0.831, snippet: "ChargePoint rolled out a reliability initiative aimed at closing the gap between reported and actual uptime..." },
  { app: "chargepoint", source: "web_pages", score: 0.802, snippet: "ChargePoint's driver app provides real-time station availability and remote session start across the network." },
];

// Sentiment-over-time (innovative feature preview) — % positive by week.
export const SENTIMENT_SERIES = [
  { week: "W1", chargepoint: 58, evgo: 62, electrify_america: 55 },
  { week: "W2", chargepoint: 55, evgo: 64, electrify_america: 57 },
  { week: "W3", chargepoint: 61, evgo: 60, electrify_america: 59 },
  { week: "W4", chargepoint: 57, evgo: 66, electrify_america: 62 },
  { week: "W5", chargepoint: 64, evgo: 65, electrify_america: 60 },
  { week: "W6", chargepoint: 67, evgo: 69, electrify_america: 64 },
  { week: "W7", chargepoint: 69, evgo: 68, electrify_america: 67 },
  { week: "W8", chargepoint: 72, evgo: 71, electrify_america: 70 },
];

export const TOP_THEMES = [
  { label: "Session start failures", value: 88, tone: "neg" },
  { label: "Map accuracy", value: 74, tone: "neg" },
  { label: "Charging speed", value: 69, tone: "pos" },
  { label: "Payment & receipts", value: 52, tone: "neg" },
  { label: "Customer support", value: 47, tone: "neg" },
];
