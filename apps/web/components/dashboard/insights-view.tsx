"use client";

import { motion } from "framer-motion";
import { TrendingUp, Newspaper, Swords, MapPin, Sparkles } from "lucide-react";
import { CountUp } from "@/components/count-up";
import { KB_STATS, SENTIMENT_SERIES, TOP_THEMES, SOURCE_LABELS } from "@/lib/mock";

const card = {
  hidden: { opacity: 0, y: 18 },
  show: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.07, type: "spring" as const, stiffness: 110, damping: 18 },
  }),
};

export function InsightsView() {
  return (
    <div className="h-full overflow-y-auto px-4 py-6 md:px-8">
      <div className="mx-auto max-w-5xl">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-2xl font-semibold tracking-tight">
            Market <span className="text-gradient">Pulse</span>
          </h1>
          <p className="mt-1 text-sm text-[var(--text-2)]">
            Live competitive signal across the EV &amp; energy app landscape.
          </p>
        </motion.div>

        {/* KPI row */}
        <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi i={0} label="Knowledge chunks" value={<CountUp to={KB_STATS.total} />} accent="#22d3ee" />
          <Kpi i={1} label="Apps tracked" value={<CountUp to={KB_STATS.apps} />} accent="#8b5cf6" />
          <Kpi i={2} label="Live stations" value={<CountUp to={61240} />} accent="#34d399" />
          <Kpi i={3} label="Sources" value={"5"} accent="#f472b6" />
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {/* Sentiment over time */}
          <motion.div variants={card} custom={4} initial="hidden" animate="show" className="glass rounded-2xl p-5">
            <CardHead icon={TrendingUp} title="Sentiment over time" sub="% positive · last 8 weeks" />
            <SentimentChart />
            <div className="mt-3 flex gap-4 text-[11px]">
              <Legend color="#22d3ee" label="ChargePoint" />
              <Legend color="#8b5cf6" label="EVgo" />
              <Legend color="#34d399" label="Electrify America" />
            </div>
          </motion.div>

          {/* Source distribution */}
          <motion.div variants={card} custom={5} initial="hidden" animate="show" className="glass rounded-2xl p-5">
            <CardHead icon={Newspaper} title="Knowledge mix" sub="chunks by source" />
            <div className="mt-4 space-y-3">
              {KB_STATS.bySource.map((s, i) => {
                const pct = Math.round((s.count / KB_STATS.total) * 100);
                return (
                  <div key={s.source}>
                    <div className="mb-1 flex justify-between text-[12px]">
                      <span className="text-[var(--text-2)]">{SOURCE_LABELS[s.source]}</span>
                      <span className="text-[var(--text-3)]">{s.count.toLocaleString()}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-white/5">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ delay: 0.3 + i * 0.08, duration: 0.9, ease: "easeOut" }}
                        className="h-full rounded-full"
                        style={{ background: s.color }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>

          {/* Top themes */}
          <motion.div variants={card} custom={6} initial="hidden" animate="show" className="glass rounded-2xl p-5">
            <CardHead icon={Sparkles} title="Theme mining" sub="ChargePoint · what drives sentiment" />
            <div className="mt-4 space-y-3">
              {TOP_THEMES.map((t, i) => (
                <div key={t.label}>
                  <div className="mb-1 flex justify-between text-[12px]">
                    <span className="text-[var(--text-2)]">{t.label}</span>
                    <span className={t.tone === "neg" ? "text-rose-400" : "text-emerald-400"}>
                      {t.tone === "neg" ? "−" : "+"}{t.value}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/5">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${t.value}%` }}
                      transition={{ delay: 0.3 + i * 0.08, duration: 0.9, ease: "easeOut" }}
                      className="h-full rounded-full"
                      style={{ background: t.tone === "neg" ? "#fb7185" : "#34d399" }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Battlecard teaser */}
          <motion.div variants={card} custom={7} initial="hidden" animate="show" className="glass relative overflow-hidden rounded-2xl p-5">
            <CardHead icon={Swords} title="Auto-battlecard" sub="one-click competitive brief" />
            <p className="mt-3 text-[13px] leading-relaxed text-[var(--text-2)]">
              Generate a board-ready brief comparing any two apps across reliability,
              pricing, UX and momentum — synthesised from every source, with citations.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {["ChargePoint vs EVgo", "Enphase vs SolarEdge", "Tesla vs Electrify America"].map((b) => (
                <span key={b} className="glass glass-hover cursor-pointer rounded-full px-3 py-1.5 text-[12px] text-[var(--text-2)]">
                  {b}
                </span>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-2 text-[12px] text-[var(--text-3)]">
              <MapPin className="h-3.5 w-3.5 text-[var(--accent-emerald)]" />
              Live station data via OpenChargeMap &amp; NREL — free, no key needed.
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

function Kpi({ i, label, value, accent }: { i: number; label: string; value: React.ReactNode; accent: string }) {
  return (
    <motion.div variants={card} custom={i} initial="hidden" animate="show" className="glass rounded-2xl p-4">
      <div className="mb-2 h-1 w-8 rounded-full" style={{ background: accent }} />
      <p className="text-2xl font-semibold tracking-tight">{value}</p>
      <p className="mt-0.5 text-[11.5px] text-[var(--text-3)]">{label}</p>
    </motion.div>
  );
}

function CardHead({ icon: Icon, title, sub }: { icon: typeof TrendingUp; title: string; sub: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-8 w-8 place-items-center rounded-lg glass">
        <Icon className="h-4 w-4 text-[var(--accent-cyan)]" />
      </span>
      <div>
        <p className="text-[14px] font-semibold leading-none">{title}</p>
        <p className="mt-1 text-[11px] text-[var(--text-3)]">{sub}</p>
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[var(--text-3)]">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} /> {label}
    </span>
  );
}

function SentimentChart() {
  const W = 320, H = 130, PAD = 8;
  const min = 45, max = 75;
  const n = SENTIMENT_SERIES.length;
  const x = (i: number) => PAD + (i / (n - 1)) * (W - PAD * 2);
  const y = (v: number) => H - PAD - ((v - min) / (max - min)) * (H - PAD * 2);
  const line = (key: "chargepoint" | "evgo" | "electrify_america") =>
    SENTIMENT_SERIES.map((d, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(d[key])}`).join(" ");

  const series: { key: "chargepoint" | "evgo" | "electrify_america"; color: string }[] = [
    { key: "chargepoint", color: "#22d3ee" },
    { key: "evgo", color: "#8b5cf6" },
    { key: "electrify_america", color: "#34d399" },
  ];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 w-full">
      {[0, 0.5, 1].map((g) => (
        <line key={g} x1={PAD} x2={W - PAD} y1={PAD + g * (H - PAD * 2)} y2={PAD + g * (H - PAD * 2)} stroke="rgba(255,255,255,.06)" strokeWidth={1} />
      ))}
      {series.map((s, si) => (
        <g key={s.key}>
          <motion.path
            d={line(s.key)}
            fill="none"
            stroke={s.color}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ delay: 0.2 + si * 0.15, duration: 1.2, ease: "easeInOut" }}
          />
          {SENTIMENT_SERIES.map((d, i) => (
            <motion.circle
              key={i}
              cx={x(i)} cy={y(d[s.key])} r={2.4} fill={s.color}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              transition={{ delay: 0.6 + si * 0.15 + i * 0.04 }}
            />
          ))}
        </g>
      ))}
    </svg>
  );
}
