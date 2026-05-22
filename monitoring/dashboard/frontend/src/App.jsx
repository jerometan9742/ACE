import { useState } from "react";
import { useACEData } from "./hooks/useACEData";
import TopBar from "./components/TopBar";
import MetricsBar from "./components/MetricsBar";
import NavTabs from "./components/NavTabs";
import AgentRoster from "./components/AgentRoster";
import AMDPhase from "./components/AMDPhase";
import MissionLog from "./components/MissionLog";
import SessionPnL from "./components/SessionPnL";
import SwarmMemory from "./components/SwarmMemory";
import Footer from "./components/Footer";

export default function App() {
  const { data, connected } = useACEData();
  const [activeTab, setActiveTab] = useState("Command");

  return (
    <div className="ace-shell">
      <TopBar
        status={data.status}
        killSwitch={data.kill_switch_active}
        connected={connected}
        prices={data.prices}
      />
      <MetricsBar data={data} />
      <NavTabs active={activeTab} onSelect={setActiveTab} />
      <AgentRoster agents={data.agents} />

      <div className="main-content">
        <div className="left-col">
          <AMDPhase phase={data.amd_phase} confluenceScore={data.confluence_score} />
          <SessionPnL
            session={data.current_session}
            isActive={data.session_is_active}
            dailyPnl={data.daily_pnl}
            tradesSession={data.trades_this_session}
          />
        </div>
        <div className="right-col">
          <MissionLog entries={data.mission_log} />
          <SwarmMemory lessons={data.swarm_lessons} />
        </div>
      </div>

      <Footer connected={connected} uptimeStart={data.uptime_start} />
    </div>
  );
}
