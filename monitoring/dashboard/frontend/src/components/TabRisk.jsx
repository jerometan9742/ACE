function pct(v) { return `${(Number(v) * 100).toFixed(1)}%`; }

function RiskRow({ label, value, cls }) {
  return (
    <div className="risk-row">
      <span className="risk-row-label">{label}</span>
      <span className={`risk-row-value${cls ? ` ${cls}` : ""}`}>{value}</span>
    </div>
  );
}

export default function TabRisk({ riskParams, killSwitch, dailyPnl, tradesToday }) {
  const rp = riskParams || {};
  const maxLoss = rp.max_daily_loss_pct ? Number(rp.max_daily_loss_pct) * 100 : 3;
  const dailyPnlPct = dailyPnl < 0 ? Math.abs(dailyPnl) / 10000 * 100 : 0;
  const pnlClass = dailyPnlPct > maxLoss * 0.8 ? "danger" : dailyPnlPct > maxLoss * 0.5 ? "warn" : "ok";

  const maxTrades = rp.max_trades_per_session || 10;
  const tradesClass = tradesToday >= maxTrades ? "danger" : tradesToday >= maxTrades * 0.7 ? "warn" : "ok";

  const toggleKS = async () => {
    const ep = killSwitch ? "/api/kill-switch/deactivate" : "/api/kill-switch/activate";
    await fetch(ep, { method: "POST" });
  };

  return (
    <div className="tab-panel">
      <div className="section-label" style={{ marginBottom: 16 }}>Risk Parameters</div>

      <div className="risk-grid">
        <div className="risk-card">
          <div className="section-label" style={{ marginBottom: 10 }}>Entry Filters</div>
          <RiskRow label="Confluence min score"   value={rp.confluence_min_score ?? 7} />
          <RiskRow label="Min confidence"         value={rp.min_confidence_score ?? "7.0"} />
          <RiskRow label="Correlation limit"      value={rp.correlation_limit ?? "0.85"} />
          <RiskRow label="Max trades per session" value={rp.max_trades_per_session ?? 10} />
        </div>

        <div className="risk-card">
          <div className="section-label" style={{ marginBottom: 10 }}>Position Sizing</div>
          <RiskRow label="Max position size"  value={pct(rp.max_position_size_pct ?? 0.05)} />
          <RiskRow label="Risk per trade"     value={pct(rp.risk_per_trade_pct ?? 0.01)} />
          <RiskRow label="ATR SL multiplier"  value={`${rp.atr_sl_multiplier ?? 1.5}×`} />
          <RiskRow label="ATR TP multiplier"  value={`${rp.atr_tp_multiplier ?? 3.0}×`} />
        </div>

        <div className="risk-card">
          <div className="section-label" style={{ marginBottom: 10 }}>Live Exposure</div>
          <RiskRow label="Daily loss limit"  value={pct(rp.max_daily_loss_pct ?? 0.03)} />
          <RiskRow
            label="Daily P&L"
            value={`${dailyPnl >= 0 ? "+" : ""}$${Number(dailyPnl).toFixed(2)}`}
            cls={dailyPnl < 0 && dailyPnlPct > maxLoss * 0.5 ? "warn" : "ok"}
          />
          <RiskRow
            label="Trades today"
            value={`${tradesToday} / ${maxTrades}`}
            cls={tradesClass}
          />
        </div>
      </div>

      <div className="ks-panel">
        <div className="ks-status">
          <div className={`ks-status-dot ${killSwitch ? "ks-on" : "ks-off"}`} />
          <span>
            Kill Switch: <strong style={{ color: killSwitch ? "var(--red)" : "var(--green)" }}>
              {killSwitch ? "ACTIVE — No new trades" : "INACTIVE — Trading allowed"}
            </strong>
          </span>
        </div>
        <button className={`ks-btn${killSwitch ? " active" : ""}`} onClick={toggleKS}>
          {killSwitch ? "Deactivate Kill Switch" : "Activate Kill Switch"}
        </button>
      </div>
    </div>
  );
}
