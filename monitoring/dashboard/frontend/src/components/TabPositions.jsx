import { useState, useEffect } from "react";

function fmtDuration(isoTs) {
  if (!isoTs) return "—";
  const diffMs = Date.now() - new Date(isoTs).getTime();
  if (diffMs < 0) return "—";
  const m = Math.floor(diffMs / 60000);
  const h = Math.floor(m / 60);
  return h > 0 ? `${h}h ${m % 60}m` : `${m}m`;
}

function fmtPrice(v) {
  if (v == null) return "—";
  return Number(v) >= 100
    ? Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 })
    : Number(v).toFixed(4);
}

function PositionRow({ pos, currentPrices }) {
  const currentPrice = currentPrices?.[pos.pair] ?? null;
  const upnl =
    currentPrice != null && pos.quantity != null && pos.entry_price != null
      ? pos.action === "BUY"
        ? (currentPrice - pos.entry_price) * pos.quantity
        : (pos.entry_price - currentPrice) * pos.quantity
      : null;

  const upnlClass = upnl == null ? "pnl-zero" : upnl > 0 ? "pnl-pos" : upnl < 0 ? "pnl-neg" : "pnl-zero";

  return (
    <tr>
      <td>{pos.pair}</td>
      <td className={pos.action === "BUY" ? "side-buy" : "side-sell"}>{pos.action}</td>
      <td>{pos.quantity ?? "—"}</td>
      <td>${fmtPrice(pos.entry_price)}</td>
      <td>{currentPrice != null ? `$${fmtPrice(currentPrice)}` : "—"}</td>
      <td className={upnlClass}>
        {upnl != null ? `${upnl >= 0 ? "+" : ""}$${Math.abs(upnl).toFixed(2)}` : "—"}
      </td>
      <td>${fmtPrice(pos.sl_price)}</td>
      <td>${fmtPrice(pos.tp_price)}</td>
      <td>{fmtDuration(pos.timestamp)}</td>
    </tr>
  );
}

export default function TabPositions({ positions, prices }) {
  const rows = positions || [];

  return (
    <div className="tab-panel">
      <div className="section-label" style={{ marginBottom: 16 }}>
        Open Positions — {rows.length} active
      </div>

      {rows.length === 0 ? (
        <div className="empty-state">No open positions</div>
      ) : (
        <div className="positions-table-wrap">
          <table className="positions-table">
            <thead>
              <tr>
                <th>Pair</th>
                <th>Side</th>
                <th>Quantity</th>
                <th>Entry Price</th>
                <th>Current Price</th>
                <th>Unrealised P&amp;L</th>
                <th>SL</th>
                <th>TP</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p, i) => (
                <PositionRow key={p.order_id || i} pos={p} currentPrices={prices} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
