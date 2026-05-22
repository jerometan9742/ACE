const PHASES = [
  {
    key: "ACCUMULATION",
    cls: "acc",
    label: "Accumulation",
    descs: {
      active: "Smart money building long positions. FVGs forming below price.",
      inactive: "Waiting for accumulation signals.",
    },
  },
  {
    key: "MANIPULATION",
    cls: "man",
    label: "Manipulation",
    descs: {
      active: "Judas swing detected. Liquidity hunt in progress.",
      inactive: "No manipulation phase active.",
    },
  },
  {
    key: "DISTRIBUTION",
    cls: "dist",
    label: "Distribution",
    descs: {
      active: "BOS confirmed. Distribution targeting HTF liquidity.",
      inactive: "No distribution phase active.",
    },
  },
];

export default function AMDPhase({ phase, confluenceScore }) {
  const active = (phase || "UNKNOWN").toUpperCase();

  return (
    <div className="amd-panel">
      <div className="section-label">
        AMD Phase — Confluence {confluenceScore}/10
      </div>
      <div className="amd-boxes">
        {PHASES.map(({ key, cls, label, descs }) => {
          const isActive = active === key;
          return (
            <div key={key} className={`amd-box ${cls}${isActive ? " active" : ""}`}>
              <div className="amd-dot" />
              <span className="amd-box-label">{label.toUpperCase()}</span>
              <span className="amd-box-desc">
                {isActive ? descs.active : descs.inactive}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
