const AGENT_ORDER = ["RD", "TA", "OF", "SP", "BR", "BE", "CB", "RM", "FM", "SM"];

function AgentAvatar({ id, agent }) {
  const status = agent?.status || "idle";
  const cls = `agent-${status}`;
  return (
    <div className="agent-avatar">
      <div className="agent-ring-wrap">
        <div className={`agent-ring ${cls}`} />
        <div className={`agent-core ${cls}`}>{id}</div>
      </div>
      <span className="agent-label">{agent?.name || id}</span>
    </div>
  );
}

export default function AgentRoster({ agents }) {
  return (
    <div className="agents-panel card">
      <div className="card-label">◈ Agent Swarm</div>
      <div className="agents-grid">
        {AGENT_ORDER.map((id) => (
          <AgentAvatar key={id} id={id} agent={agents[id]} />
        ))}
      </div>
    </div>
  );
}
