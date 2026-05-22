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
import TabPositions from "./components/TabPositions";
import TabAMDRadar from "./components/TabAMDRadar";
import TabMemory from "./components/TabMemory";
import TabRisk from "./components/TabRisk";
import TabSettings from "./components/TabSettings";

function CommandTab({ data }) {
  return (
    <>
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
    </>
  );
}

export default function App() {
  const { data, connected } = useACEData();
  const [activeTab, setActiveTab] = useState("Command");

  function renderTab() {
    switch (activeTab) {
      case "Positions":
        return <TabPositions positions={data.open_positions} prices={data.prices} />;
      case "AMD Radar":
        return <TabAMDRadar pairPhases={data.pair_phases} />;
      case "Memory":
        return <TabMemory lessons={data.swarm_lessons} sessionStats={data.session_stats} />;
      case "Risk":
        return (
          <TabRisk
            riskParams={data.risk_params}
            killSwitch={data.kill_switch_active}
            dailyPnl={data.daily_pnl}
            tradesToday={data.trades_today}
          />
        );
      case "Settings":
        return <TabSettings settings={data.settings} />;
      default:
        return <CommandTab data={data} />;
    }
  }

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
      {renderTab()}
      <Footer connected={connected} uptimeStart={data.uptime_start} />
    </div>
  );
}
