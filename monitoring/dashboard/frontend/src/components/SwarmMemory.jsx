export default function SwarmMemory({ positions }) {
  return (
    <div className="positions-panel">
      <div className="card-label">◈ Open Positions</div>
      {positions.length === 0 ? (
        <div className="no-positions">No open positions</div>
      ) : (
        positions.map((p) => (
          <div className="position-row" key={p.order_id || p.pair}>
            <span style={{ color: "var(--text-muted)" }}>{p.pair}</span>
            <span className={p.action === "BUY" ? "pos-buy" : "pos-sell"}>{p.action}</span>
            <span style={{ color: "var(--text-muted)", textAlign: "right" }}>
              @{Number(p.entry_price).toFixed(2)}
            </span>
          </div>
        ))
      )}
    </div>
  );
}
