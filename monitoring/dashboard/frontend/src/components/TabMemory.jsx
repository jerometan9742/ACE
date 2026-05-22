function pairClass(pair) {
  const p = (pair || "").toUpperCase();
  if (p.includes("BTC")) return "pair-btc";
  if (p.includes("ETH")) return "pair-eth";
  if (p.includes("SOL")) return "pair-sol";
  return "";
}

function winRate(stats) {
  if (!stats || stats.trades === 0) return null;
  return ((stats.wins / stats.trades) * 100).toFixed(0);
}

function SessionStatCard({ name, stats }) {
  const wr = winRate(stats);
  return (
    <div className="session-stat-card">
      <div className="session-stat-name">{name}</div>
      <div className="session-stat-wr" style={{ color: wr == null ? "var(--text-muted)" : Number(wr) >= 50 ? "var(--green)" : "var(--red)" }}>
        {wr != null ? `${wr}%` : "—"}
      </div>
      <div className="session-stat-meta">
        {stats?.trades > 0 ? `${stats.wins}W / ${stats.trades - stats.wins}L (${stats.trades} trades)` : "No trades"}
      </div>
    </div>
  );
}

export default function TabMemory({ lessons, sessionStats }) {
  const items = (lessons || []).slice(-20).reverse();

  return (
    <div className="tab-panel">
      <div className="section-label" style={{ marginBottom: 16 }}>
        Swarm Memory — Last {items.length} Lessons
      </div>

      <div className="memory-full-list">
        {items.length === 0 && (
          <div className="no-data">No lessons recorded yet.</div>
        )}
        {items.map((entry, i) => {
          const ts = entry.ts ? entry.ts.slice(0, 16).replace("T", " ") : "—";
          return (
            <div className="memory-full-entry" key={i}>
              <span className={`memory-pair ${pairClass(entry.pair)}`}>
                {(entry.pair || "—").replace("/USDT", "")}
              </span>
              <span className="memory-full-ts">{ts}</span>
              <span className="memory-text">{entry.lesson || entry.text || ""}</span>
            </div>
          );
        })}
      </div>

      <div className="section-label" style={{ marginBottom: 12 }}>Session Win Rates</div>
      <div className="session-stats-grid">
        <SessionStatCard name="Asia"   stats={sessionStats?.asia} />
        <SessionStatCard name="London" stats={sessionStats?.london} />
        <SessionStatCard name="NYC"    stats={sessionStats?.ny} />
      </div>
    </div>
  );
}
