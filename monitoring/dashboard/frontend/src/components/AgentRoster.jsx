const AGENTS = [
  { id: "RD", name: "Regime\nDetector" },
  { id: "TA", name: "Technical\nAnalyst" },
  { id: "OF", name: "Order Flow\nAnalyst" },
  { id: "SP", name: "Sentiment\nAnalyst" },
  { id: "BR", name: "Bull\nResearcher" },
  { id: "BE", name: "Bear\nResearcher" },
  { id: "CB", name: "Consensus\nBuilder" },
  { id: "RM", name: "Risk\nManager" },
  { id: "FM", name: "Fund\nManager" },
  { id: "SM", name: "Swarm\nMemory" },
];

function statusClass(status) {
  switch ((status || "idle").toLowerCase()) {
    case "active":     return "ag-active";
    case "streaming":  return "ag-active";
    case "analysing":  return "ag-analysing";
    case "analyzing":  return "ag-analysing";
    case "debating":   return "ag-debating";
    case "monitoring": return "ag-monitoring";
    case "alert":      return "ag-monitoring";
    default:           return "ag-idle";
  }
}

function statusLabel(status) {
  return (status || "Standby").charAt(0).toUpperCase() + (status || "Standby").slice(1);
}

function AgentAvatar({ id, name, agentData }) {
  const cls = statusClass(agentData?.status);
  const lines = name.split("\n");

  return (
    <div className={`agent-avatar ${cls}`}>
      <div className="agent-ring-wrap">
        <div className="agent-ring-outer" />
        <div className="agent-ring-inner" />
        <div className="agent-core">{id}</div>
      </div>
      <div className="agent-name">
        {lines.map((l, i) => <span key={i} style={{ display: "block" }}>{l}</span>)}
      </div>
      <div className="agent-status-text">{statusLabel(agentData?.status)}</div>
    </div>
  );
}

export default function AgentRoster({ agents }) {
  return (
    <div className="agent-roster">
      <div className="section-label">Agent Roster — 10 active</div>
      <div className="agent-row">
        {AGENTS.map(({ id, name }) => (
          <AgentAvatar key={id} id={id} name={name} agentData={agents?.[id]} />
        ))}
      </div>
    </div>
  );
}
