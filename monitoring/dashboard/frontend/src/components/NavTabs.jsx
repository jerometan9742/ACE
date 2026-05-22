const TABS = ["Command", "Positions", "AMD Radar", "Memory", "Risk", "Settings"];

export default function NavTabs({ active, onSelect }) {
  return (
    <nav className="nav-tabs">
      {TABS.map((tab) => (
        <button
          key={tab}
          className={`nav-tab${active === tab ? " active" : ""}`}
          onClick={() => onSelect(tab)}
        >
          {tab}
        </button>
      ))}
    </nav>
  );
}
