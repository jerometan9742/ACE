import { useACEData } from "./hooks/useACEData";
import TopBar from "./components/TopBar";
import MetricsBar from "./components/MetricsBar";
import AgentRoster from "./components/AgentRoster";
import AMDPhase from "./components/AMDPhase";
import MissionLog from "./components/MissionLog";
import SessionPnL from "./components/SessionPnL";
import SwarmMemory from "./components/SwarmMemory";
import Footer from "./components/Footer";

export default function App() {
  const { data, connected } = useACEData();

  return (
    <div className="ace-grid">
      <TopBar
        status={data.status}
        killSwitch={data.kill_switch_active}
        connected={connected}
      />
      <MetricsBar data={data} />
      <AgentRoster agents={data.agents} />
      <MissionLog entries={data.mission_log} />

      {/* Sidebar */}
      <div className="sidebar">
        <AMDPhase phase={data.amd_phase} confluenceScore={data.confluence_score} />
        <SessionPnL
          session={data.current_session}
          isActive={data.session_is_active}
          dailyPnl={data.daily_pnl}
          tradesSession={data.trades_this_session}
        />
        <SwarmMemory positions={data.open_positions} />
      </div>

      <Footer connected={connected} />
    </div>
  );
}
