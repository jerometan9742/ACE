const PHASE_MAP = {
  ACCUMULATION: { label: "ACCUMULATION", cls: "amd-acc" },
  MANIPULATION: { label: "MANIPULATION", cls: "amd-man" },
  DISTRIBUTION:  { label: "DISTRIBUTION",  cls: "amd-dist" },
  UNKNOWN:       { label: "UNKNOWN",        cls: "amd-unk" },
};

export default function AMDPhase({ phase, confluenceScore }) {
  const p = PHASE_MAP[phase] || PHASE_MAP.UNKNOWN;
  const pct = Math.min(100, (confluenceScore / 10) * 100);

  const barColor =
    confluenceScore >= 7 ? "var(--green)" :
    confluenceScore >= 4 ? "var(--amber)" : "var(--red)";

  return (
    <div className="amd-panel">
      <div className="card-label">◈ AMD Phase</div>
      <div className={`amd-phase-badge ${p.cls}`}>{p.label}</div>
      <div className="conf-bar-wrap">
        <div className="card-label">Confluence {confluenceScore}/10</div>
        <div className="conf-bar-bg">
          <div
            className="conf-bar-fill"
            style={{ width: `${pct}%`, background: barColor }}
          />
        </div>
      </div>
    </div>
  );
}
