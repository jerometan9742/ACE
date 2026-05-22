export default function MetricsBar({ data }) {
  const { equity, daily_pnl, daily_pnl_pct, open_positions, win_rate, agents } = data;

  const pnlClass = daily_pnl > 0 ? "pos" : daily_pnl < 0 ? "neg" : "neutral";
  const posCount = (open_positions || []).length;

  // avg confidence from agents that have a confidence field (fallback: 0)
  const avgConf = (() => {
    if (!agents) return 0;
    const vals = Object.values(agents)
      .map((a) => parseFloat(a?.confidence || 0))
      .filter((v) => v > 0);
    return vals.length ? (vals.reduce((s, v) => s + v, 0) / vals.length).toFixed(1) : "—";
  })();

  return (
    <div className="metrics-bar">
      <div className="metric-card green">
        <div className="metric-label">Today P&amp;L</div>
        <div className={`metric-value ${pnlClass}`}>
          {daily_pnl >= 0 ? "+" : ""}${Math.abs(daily_pnl).toFixed(2)}
        </div>
        <div className="metric-sub">
          {daily_pnl_pct >= 0 ? "+" : ""}{(daily_pnl_pct || 0).toFixed(2)}% from open
        </div>
      </div>

      <div className="metric-card blue">
        <div className="metric-label">Win Rate</div>
        <div className="metric-value blue">
          {typeof win_rate === "number" ? `${win_rate.toFixed(0)}%` : "—"}
        </div>
        <div className="metric-sub">all closed trades today</div>
      </div>

      <div className="metric-card amber">
        <div className="metric-label">Open Positions</div>
        <div className="metric-value amber">{posCount}</div>
        <div className="metric-sub">of 3 max concurrent</div>
      </div>

      <div className="metric-card purple">
        <div className="metric-label">Avg Confidence</div>
        <div className="metric-value purple">{avgConf}</div>
        <div className="metric-sub">last pipeline run</div>
      </div>
    </div>
  );
}
