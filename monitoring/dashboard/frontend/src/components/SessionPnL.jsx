const SESSIONS = [
  { key: "asia",       label: "ASIA" },
  { key: "london",     label: "LON" },
  { key: "ny_open",    label: "NYC" },
];

function SessionRow({ label, pnl, trades, winRate, isActive }) {
  const pct = Math.min(100, Math.abs(pnl) / 50 * 100); // scale: $50 = full bar
  const cls = pnl >= 0 ? "pos" : "neg";

  return (
    <div className="session-row">
      <span className="session-row-label" style={isActive ? { color: "var(--green)" } : {}}>
        {label}
      </span>
      <div className="session-bar-wrap">
        <div className={`session-bar-fill ${cls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`session-row-pnl ${cls}`}>
        {pnl !== 0 ? `${pnl >= 0 ? "+" : ""}$${Math.abs(pnl).toFixed(2)}` : "—"}
      </span>
      <span className="session-row-meta">
        {trades > 0 ? `${trades}t · ${winRate}%` : "no trades"}
      </span>
    </div>
  );
}

export default function SessionPnL({ session, dailyPnl, tradesSession }) {
  const curr = (session || "outside").toLowerCase();

  const rows = SESSIONS.map(({ key, label }) => ({
    label,
    pnl: curr === key ? dailyPnl : 0,
    trades: curr === key ? tradesSession : 0,
    winRate: 0,
    isActive: curr === key,
  }));

  // ny_open → NYC active
  if (curr === "ny_afternoon") rows[2].isActive = true;

  return (
    <div className="session-panel">
      <div className="section-label">Session P&amp;L</div>
      {rows.map((r) => (
        <SessionRow key={r.label} {...r} />
      ))}
    </div>
  );
}
