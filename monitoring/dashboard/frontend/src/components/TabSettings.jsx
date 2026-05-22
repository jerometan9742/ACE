function SettingsRow({ label, value }) {
  return (
    <div className="settings-row">
      <span className="settings-row-label">{label}</span>
      <span className="settings-row-value">{value ?? "—"}</span>
    </div>
  );
}

export default function TabSettings({ settings }) {
  const s = settings || {};
  const watchlist = Array.isArray(s.watchlist) ? s.watchlist.join(", ") : (s.watchlist || "—");

  return (
    <div className="tab-panel">
      <div className="section-label" style={{ marginBottom: 16 }}>Current Configuration</div>

      <div className="settings-grid">
        <div className="settings-card">
          <div className="section-label" style={{ marginBottom: 10 }}>Exchange</div>
          <SettingsRow label="Trading mode"   value={s.trading_mode?.toUpperCase()} />
          <SettingsRow label="Exchange"       value={s.exchange?.toUpperCase()} />
          <SettingsRow label="Watchlist"      value={watchlist} />
          <SettingsRow label="Paper balance"  value={s.paper_balance != null ? `$${Number(s.paper_balance).toLocaleString()}` : "—"} />
        </div>

        <div className="settings-card">
          <div className="section-label" style={{ marginBottom: 10 }}>Models</div>
          <SettingsRow label="Fast model (Layer 1)"  value={s.model_fast} />
          <SettingsRow label="Smart model (Layer 2)" value={s.model_smart} />
        </div>

        <div className="settings-card">
          <div className="section-label" style={{ marginBottom: 10 }}>Exit Parameters</div>
          <SettingsRow label="ATR SL multiplier" value={s.atr_sl_multiplier != null ? `${s.atr_sl_multiplier}×` : "—"} />
          <SettingsRow label="ATR TP multiplier" value={s.atr_tp_multiplier != null ? `${s.atr_tp_multiplier}×` : "—"} />
          <SettingsRow label="R:R ratio"          value="2:1" />
        </div>
      </div>

      <div className="settings-note">
        Read-only view. To change settings, edit <strong>.env</strong> in the project root and restart the bot.
        Never edit .env directly on VPS — push from local and let auto-deploy handle it.
      </div>
    </div>
  );
}
