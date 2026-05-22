export default function MetricsBar({ data }) {
  const { equity, daily_pnl, daily_pnl_pct, trades_today, trades_this_session, prices } = data;

  const pnlClass = daily_pnl > 0 ? "positive" : daily_pnl < 0 ? "negative" : "neutral";

  const fmtPrice = (v) =>
    v >= 1000
      ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
      : v.toFixed(2);

  return (
    <div className="metrics-bar">
      <div className="metric">
        <span className="metric-label">Equity</span>
        <span className="metric-value neutral">${equity.toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>
      </div>
      <div className="metric">
        <span className="metric-label">Daily P&L</span>
        <span className={`metric-value ${pnlClass}`}>
          {daily_pnl >= 0 ? "+" : ""}${Math.abs(daily_pnl).toFixed(2)}
          <span style={{ fontSize: 11, marginLeft: 4 }}>({daily_pnl_pct >= 0 ? "+" : ""}{daily_pnl_pct.toFixed(2)}%)</span>
        </span>
      </div>
      <div className="metric">
        <span className="metric-label">Trades Today</span>
        <span className="metric-value neutral">{trades_today}</span>
      </div>
      <div className="metric">
        <span className="metric-label">Session Trades</span>
        <span className="metric-value neutral">{trades_this_session}</span>
      </div>
      {Object.entries(prices).map(([pair, price]) => (
        <div className="metric" key={pair}>
          <span className="metric-label">{pair.replace("/USDT", "")}</span>
          <span className="metric-value amber">${fmtPrice(price)}</span>
        </div>
      ))}
    </div>
  );
}
