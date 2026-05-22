import { useEffect, useState } from "react";

export default function TopBar({ status, killSwitch, connected }) {
  const [utcTime, setUtcTime] = useState("");

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setUtcTime(now.toUTCString().slice(17, 25) + " UTC");
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const dotClass = connected
    ? status === "error" ? "error" : ""
    : "offline";

  const toggleKillSwitch = async () => {
    const endpoint = killSwitch
      ? "/api/kill-switch/deactivate"
      : "/api/kill-switch/activate";
    await fetch(endpoint, { method: "POST" });
  };

  return (
    <header className="topbar">
      <span className="topbar-logo">◈ ACE</span>
      <div className="topbar-sep" />
      <span className="topbar-mode">PAPER</span>
      <div className={`status-dot ${dotClass}`} />
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>
        {connected ? status.toUpperCase() : "DISCONNECTED"}
      </span>
      <div className="topbar-spacer" />
      <span className="topbar-time">{utcTime}</span>
      <button
        className={`ks-btn${killSwitch ? " active" : ""}`}
        onClick={toggleKillSwitch}
      >
        {killSwitch ? "⛔ KILL ACTIVE" : "KILL SWITCH"}
      </button>
    </header>
  );
}
