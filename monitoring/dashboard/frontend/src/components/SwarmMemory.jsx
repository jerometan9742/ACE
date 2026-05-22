function pairClass(pair) {
  const p = (pair || "").toUpperCase();
  if (p.includes("BTC")) return "pair-btc";
  if (p.includes("ETH")) return "pair-eth";
  if (p.includes("SOL")) return "pair-sol";
  return "";
}

function pairShort(pair) {
  return (pair || "—").replace("/USDT", "").slice(0, 3);
}

export default function SwarmMemory({ lessons }) {
  const items = lessons || [];

  return (
    <div className="swarm-memory">
      <div className="section-label">Swarm Memory — Recent Lessons</div>

      {items.length === 0 && (
        <div className="no-data">No lessons recorded yet.</div>
      )}

      {items.map((entry, i) => (
        <div className="memory-entry" key={i}>
          <span className={`memory-pair ${pairClass(entry.pair)}`}>
            {pairShort(entry.pair)}
          </span>
          <span className="memory-text">{entry.lesson || entry.text || ""}</span>
        </div>
      ))}
    </div>
  );
}
