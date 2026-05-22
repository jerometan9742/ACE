import { useState, useEffect } from "react";

const PHASE_DESCS = {
  ACCUMULATION: "Smart money building positions. FVGs forming. Expect manipulation sweep soon.",
  MANIPULATION: "Judas swing in progress. Liquidity hunt above/below recent highs/lows.",
  DISTRIBUTION:  "BOS confirmed. Distribution targeting HTF liquidity pool.",
  UNKNOWN:       "Insufficient data. Awaiting confluence signal ≥ 7.",
};

const KILL_ZONES = [
  { key: "london",      label: "London Open",   utcStart: [7,  0], utcEnd: [9,  0] },
  { key: "ny_open",     label: "NY Open",        utcStart: [13,30], utcEnd: [15, 0] },
  { key: "ny_afternoon",label: "NY Afternoon",   utcStart: [17, 0], utcEnd: [19, 0] },
];

function minsUntil(hStart, mStart) {
  const now = new Date();
  const nowMins = now.getUTCHours() * 60 + now.getUTCMinutes();
  const target = hStart * 60 + mStart;
  const diff = target > nowMins ? target - nowMins : 1440 - nowMins + target;
  return diff;
}

function isActive(hStart, mStart, hEnd, mEnd) {
  const now = new Date();
  const nowMins = now.getUTCHours() * 60 + now.getUTCMinutes();
  return nowMins >= hStart * 60 + mStart && nowMins < hEnd * 60 + mEnd;
}

function fmtCountdown(mins) {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h > 0 ? `in ${h}h ${m}m` : `in ${m}m`;
}

function phaseClass(phase) {
  switch ((phase || "").toUpperCase()) {
    case "ACCUMULATION": return "phase-acc";
    case "MANIPULATION": return "phase-man";
    case "DISTRIBUTION":  return "phase-dist";
    default:              return "phase-unk";
  }
}

function barColor(phase) {
  switch ((phase || "").toUpperCase()) {
    case "ACCUMULATION": return "var(--green)";
    case "MANIPULATION": return "var(--amber)";
    case "DISTRIBUTION":  return "var(--red)";
    default:              return "var(--text-muted)";
  }
}

function RadarCard({ pair, phaseData }) {
  const phase = (phaseData?.phase || "UNKNOWN").toUpperCase();
  const score = phaseData?.confluence_score ?? 0;
  const pct = Math.min(100, (score / 10) * 100);
  const cls = phaseClass(phase);

  return (
    <div className="radar-card">
      <div className="radar-pair">
        <span>{pair}</span>
        <span className={`radar-phase-badge ${cls}`}>{phase}</span>
      </div>
      <div className="radar-score-bar">
        <div className="radar-score-label">Confluence {score}/10</div>
        <div className="radar-bar-bg">
          <div className="radar-bar-fill" style={{ width: `${pct}%`, background: barColor(phase) }} />
        </div>
      </div>
      <div className="radar-desc">{PHASE_DESCS[phase] || PHASE_DESCS.UNKNOWN}</div>
    </div>
  );
}

function KillZoneTimer() {
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 60000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="killzone-panel">
      <div className="section-label">Kill Zone Schedule (UTC)</div>
      <div className="killzone-grid">
        {KILL_ZONES.map(({ key, label, utcStart, utcEnd }) => {
          const active = isActive(utcStart[0], utcStart[1], utcEnd[0], utcEnd[1]);
          const minsLeft = active
            ? (utcEnd[0] * 60 + utcEnd[1]) - (new Date().getUTCHours() * 60 + new Date().getUTCMinutes())
            : minsUntil(utcStart[0], utcStart[1]);

          return (
            <div key={key} className={`killzone-item${active ? " active-zone" : ""}`}>
              <div className="killzone-name">{label}</div>
              <div className="killzone-time">
                {String(utcStart[0]).padStart(2,"0")}:{String(utcStart[1]).padStart(2,"0")}–
                {String(utcEnd[0]).padStart(2,"0")}:{String(utcEnd[1]).padStart(2,"0")} UTC
              </div>
              <div className="killzone-time" style={{ marginTop: 4, fontSize: 10 }}>
                {active ? `Active · closes in ${minsLeft}m` : fmtCountdown(minsLeft)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function TabAMDRadar({ pairPhases }) {
  const PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"];

  return (
    <div className="tab-panel">
      <div className="section-label" style={{ marginBottom: 16 }}>AMD Radar — All Pairs</div>
      <div className="radar-grid">
        {PAIRS.map((pair) => (
          <RadarCard key={pair} pair={pair} phaseData={pairPhases?.[pair]} />
        ))}
      </div>
      <KillZoneTimer />
    </div>
  );
}
