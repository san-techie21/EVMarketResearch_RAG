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
  { id: "3", title: "NACS rollout - who's fastest?", when: "Yesterday" },
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

> **Net:** reliability perception is dragged down by the gap between *in-app availability* and *real-world uptime* - the highest-leverage fix area.`;

export const DEMO_SOURCES: Source[] = [
  { app: "chargepoint", source: "google_play", score: 0.912, snippet: "App keeps failing to start a session and the map shows stations that are clearly offline when I arrive..." },
  { app: "chargepoint", source: "app_store", score: 0.884, snippet: "Reliability has been hit or miss - half the chargers it shows as available are broken or ICE'd." },
  { app: "chargepoint", source: "news", score: 0.831, snippet: "ChargePoint rolled out a reliability initiative aimed at closing the gap between reported and actual uptime..." },
  { app: "chargepoint", source: "web_pages", score: 0.802, snippet: "ChargePoint's driver app provides real-time station availability and remote session start across the network." },
];

// -- Question-aware demo answer engine --------------------------------------
// The live backend answers from the real knowledge base. In demo mode we route
// the question to the most relevant canned answer, and decline gracefully when
// it's outside coverage (e.g. rideshare) instead of answering something else.

const EVGO_EA_ANSWER = `**EVgo vs Electrify America - pricing transparency** (from 8,473 Google Play + 6,572 App Store reviews and recent news):

### Plan clarity
**Electrify America** is praised for flat per-kWh Pass+ pricing, but reviewers are confused where billing switches to **per-minute** depending on the state.

### EVgo
Reviewers find EVgo's tiered/membership pricing **harder to predict**, with recurring complaints about **idle fees** and peak-time surprises.

### Net
On transparency, **Electrify America edges ahead** on published per-kWh rates, while **EVgo scores better on reliability** in recent reviews - a price-clarity vs uptime trade-off.`;

const EVGO_EA_SOURCES: Source[] = [
  { app: "evgo", source: "google_play", score: 0.892, snippet: "Pricing is confusing - membership vs pay-as-you-go plus idle fees make the final cost hard to predict." },
  { app: "electrify_america", source: "app_store", score: 0.864, snippet: "Pass+ flat per-kWh is clear, but per-minute billing in a few states throws people off." },
  { app: "evgo", source: "news", score: 0.811, snippet: "EVgo revised its pricing tiers; analysts note clearer per-kWh rates across more markets." },
  { app: "electrify_america", source: "web_pages", score: 0.793, snippet: "Electrify America publishes per-kWh and Pass+ membership pricing on its site." },
];

const PROSUMER_ANSWER = `**Best solar + battery monitoring UX** (prosumer apps - from reviews and video walkthroughs):

### Enphase Enlighten
Consistently top-rated for a clean, **real-time per-panel** view; reviewers love the microinverter-level granularity.

### SolarEdge mySolarEdge
Strong data depth, but reviewers report a **slower, occasionally unresponsive battery screen**.

### Tesla · Sense · Span
**Tesla app** wins on Powerwall storm-watch and backup flows; **Sense** for whole-home disaggregation; **Span** for panel-level breaker control.

### Net
For pure solar + battery monitoring UX, **Enphase leads**, with Tesla strongest on backup/battery.`;

const PROSUMER_SOURCES: Source[] = [
  { app: "enphase", source: "google_play", score: 0.903, snippet: "Enlighten's per-panel real-time view is the best monitoring UX I've used." },
  { app: "solaredge", source: "app_store", score: 0.832, snippet: "mySolarEdge data is detailed but the battery storage screen is slow to load." },
  { app: "tesla_powerwall", source: "news", score: 0.804, snippet: "Tesla app Storm Watch and backup history praised for battery UX." },
];

const NACS_ANSWER = `**Latest on NACS adoption** (from recent news and announcements):

- Most major automakers have committed to **NACS** (the Tesla connector), with adapters shipping and native NACS ports landing on new models.
- **Electrify America** and other CCS networks are adding NACS connectors at stations.
- Reviewers flag early **adapter reliability** hiccups, but Supercharger access for non-Tesla EVs is improving fast.

### Net
The market is consolidating around NACS faster than expected - the open question is **station-side rollout pace**, not automaker commitment.`;

const NACS_SOURCES: Source[] = [
  { app: "tesla", source: "news", score: 0.881, snippet: "Automakers adopt the Tesla NACS connector; native ports and adapters rolling out across 2025-26 models." },
  { app: "electrify_america", source: "news", score: 0.833, snippet: "Electrify America adding NACS connectors across its DC fast-charging network." },
  { app: "chargepoint", source: "news", score: 0.781, snippet: "ChargePoint to ship NACS-equipped hardware as the connector standard consolidates." },
];

const clip = (s: string) => (s.length > 90 ? s.slice(0, 90) + "…" : s);

function genericApp(name: string, question: string): string {
  return `Here's what the knowledge base surfaces on **${name}** for *"${clip(question)}"*:

Across reviews, news and official sources, the strongest signals cluster around **reliability**, **app experience**, and **pricing**, with sentiment trending up in recent weeks.

> **Demo answer.** The live backend returns a full, cited synthesis from the real 24,863-chunk knowledge base - this preview shows the experience and citations.`;
}

function outOfScope(question: string): string {
  return `**That's outside Voltaic's coverage.**

I focus on **EV charging and home-energy apps**, so I don't have data on *"${clip(question)}"*.

Try asking about **ChargePoint, EVgo, Electrify America, Tesla, Enphase, SolarEdge, Sense or Span** - for example:

- What are the most common complaints about ChargePoint?
- How does EVgo compare to Electrify America on pricing?
- Which prosumer apps have the best battery monitoring?`;
}

function srcFor(slug: string): Source[] {
  return [
    { app: slug, source: "google_play", score: 0.88, snippet: "User reviews highlight reliability and app experience as the dominant themes." },
    { app: slug, source: "news", score: 0.79, snippet: "Recent coverage notes network expansion and product updates." },
  ];
}

const IN_SCOPE_RE =
  /\b(ev|evs|electric|charg\w*|supercharg\w*|solar|batter\w*|powerwall|enphase|solaredge|sunpower|prosumer|nacs|energy|chargepoint|evgo|tesla|blink|plugshare|electrify|sense|span|emporia|generac|reliab\w*|review\w*|station\w*|monitor\w*)\b/i;

export function answerFor(question: string): { answer: string; sources: Source[] } {
  const q = question.toLowerCase();
  const matched = APPS.filter((a) => q.includes(a.name.toLowerCase()));

  if (q.includes("nacs") || (q.includes("news") && IN_SCOPE_RE.test(q)))
    return { answer: NACS_ANSWER, sources: NACS_SOURCES };

  if ((q.includes("evgo") || q.includes("electrify")) &&
      (q.includes("compar") || q.includes(" vs") || q.includes("pricing") || q.includes("price")))
    return { answer: EVGO_EA_ANSWER, sources: EVGO_EA_SOURCES };

  if (q.includes("solar") || q.includes("batter") || q.includes("powerwall") ||
      q.includes("prosumer") || q.includes("enphase") || q.includes("solaredge") || q.includes("monitor"))
    return { answer: PROSUMER_ANSWER, sources: PROSUMER_SOURCES };

  if (q.includes("chargepoint"))
    return { answer: DEMO_ANSWER, sources: DEMO_SOURCES };

  if (matched.length > 0 || IN_SCOPE_RE.test(q)) {
    const app = matched[0];
    if (app) return { answer: genericApp(app.name, question), sources: srcFor(app.slug) };
    return { answer: genericApp("the tracked apps", question), sources: DEMO_SOURCES.slice(0, 2) };
  }

  return { answer: outOfScope(question), sources: [] };
}

// Sentiment-over-time (innovative feature preview) - % positive by week.
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
