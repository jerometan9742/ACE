const SESSION_LABELS = {
  london:       "London Open",
  ny_open:      "NY Open",
  ny_afternoon: "NY Afternoon",
  outside:      "Outside Hours",
};

export default function SessionPnL({ session, isActive, dailyPnl, tradesSession }) {
  const label = SESSION_LABELS[session] || session.toUpperCase();
  const pnlClass = dailyPnl > 0 ? "positive" : dailyPnl < 0 ? "negative" : "neutral";

  return (
    <div className="session-panel">
      <div className="card-label">◈ Session</div>
      {isActive ? (
        <>
          <div className="session-name">{label}</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
            Trades: {tradesSession} &nbsp;|&nbsp;
            P&L: <span className={`metric-value ${pnlClass}`} style={{ fontSize: 13 }}>
              {dailyPnl >= 0 ? "+" : ""}{dailyPnl.toFixed(2)}
            </span>
          </div>
        </>
      ) : (
        <>
          <div className="session-inactive">{label}</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-dim)", marginTop: 4 }}>
            Waiting for kill zone…
          </div>
        </>
      )}
    </div>
  );
}
