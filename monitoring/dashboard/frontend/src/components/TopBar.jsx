import { useEffect, useState } from "react";

export default function TopBar({ status, killSwitch, connected, prices }) {
  const [utcTime, setUtcTime] = useState("");

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      const h = String(now.getUTCHours()).padStart(2, "0");
      const m = String(now.getUTCMinutes()).padStart(2, "0");
      const s = String(now.getUTCSeconds()).padStart(2, "0");
      setUtcTime(`${h}:${m}:${s} UTC`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const dotClass = !connected ? "offline" : status === "error" ? "error" : "";

  const toggleKillSwitch = async () => {
    const ep = killSwitch ? "/api/kill-switch/deactivate" : "/api/kill-switch/activate";
    await fetch(ep, { method: "POST" });
  };

  const fmtPrice = (v) =>
    v >= 1000
      ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
      : Number(v).toFixed(3);

  return (
    <header className="topbar">
      <span className="topbar-logo-badge">ACE</span>
      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        <span className="topbar-title">Mission Control</span>
        <span className="topbar-subtitle">Intraday Trading Bot // v1.0.0</span>
      </div>

      <div className="topbar-sep" />

      <div className="topbar-prices">
        {Object.entries(prices || {}).map(([pair, price]) => (
          <div className="price-item" key={pair}>
            <span className="price-pair">{pair.replace("/USDT", "/USDT")}</span>
            <span className="price-val">${fmtPrice(price)}</span>
          </div>
        ))}
        {(!prices || Object.keys(prices).length === 0) && (
          <>
            {["BTC/USDT", "ETH/USDT", "SOL/USDT"].map((p) => (
              <div className="price-item" key={p}>
                <span className="price-pair">{p}</span>
                <span className="price-val" style={{ color: "var(--text-muted)" }}>—</span>
              </div>
            ))}
          </>
        )}
      </div>

      <div className="topbar-spacer" />

      <div className="topbar-status">
        <div className={`status-dot ${dotClass}`} />
        <span>{connected ? "Systems operational" : "Reconnecting…"}</span>
      </div>

      <span className="topbar-time">{utcTime}</span>

      <button
        className={`ks-btn${killSwitch ? " active" : ""}`}
        onClick={toggleKillSwitch}
      >
        {killSwitch ? "⛔ Kill Active" : "Kill Switch"}
      </button>
    </header>
  );
}
