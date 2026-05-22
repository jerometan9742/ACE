export default function Footer({ connected }) {
  return (
    <footer className="footer">
      <div className="footer-dot" style={{ background: connected ? "var(--green)" : "var(--red)" }} />
      <span>ACE MISSION CONTROL</span>
      <span>|</span>
      <span>PAPER TRADING MODE</span>
      <span>|</span>
      <span>{connected ? "WS LIVE" : "WS RECONNECTING…"}</span>
    </footer>
  );
}
