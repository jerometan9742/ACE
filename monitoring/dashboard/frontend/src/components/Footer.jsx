import { useState, useEffect } from "react";

function fmtUptime(isoStart) {
  if (!isoStart) return "—";
  const diffMs = Date.now() - new Date(isoStart).getTime();
  if (diffMs < 0) return "—";
  const s = Math.floor(diffMs / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export default function Footer({ connected, uptimeStart }) {
  const [uptime, setUptime] = useState("—");

  useEffect(() => {
    const tick = () => setUptime(fmtUptime(uptimeStart));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [uptimeStart]);

  return (
    <footer className="footer">
      <span>
        ACE v1.0.0 &nbsp;·&nbsp; VPS TBD &nbsp;·&nbsp; Uptime {uptime}
      </span>
      <div className="footer-right">
        <span>Daily limit: 3%</span>
        <span className="footer-ok">
          Watchdog: {connected ? "OK" : "—"}
        </span>
      </div>
    </footer>
  );
}
