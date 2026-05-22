import { useEffect, useRef } from "react";

function pillClass(level, message) {
  const l = (level || "").toUpperCase();
  const m = (message || "").toUpperCase();
  if (m.includes("BUY"))  return ["pill-buy",  "BUY"];
  if (m.includes("SELL")) return ["pill-sell", "SELL"];
  if (m.includes("HOLD")) return ["pill-hold", "HOLD"];
  if (l === "ERROR")      return ["pill-err",  "ERR"];
  if (l === "WARN")       return ["pill-warn", "WARN"];
  return ["pill-sys", "SYS"];
}

export default function MissionLog({ entries }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  return (
    <div className="mission-log">
      <div className="log-header">
        <span className="section-label" style={{ marginBottom: 0 }}>Mission Log</span>
        <span className="log-cursor" />
      </div>

      {(entries || []).map((e, i) => {
        const ts = e.ts ? e.ts.slice(11, 19) : "--:--:--";
        const [cls, tag] = pillClass(e.level, e.message);
        return (
          <div className="log-entry" key={i}>
            <span className="log-ts">{ts}</span>
            <span className={`log-pill ${cls}`}>{tag}</span>
            <span className="log-msg">{e.message}</span>
          </div>
        );
      })}

      {(!entries || entries.length === 0) && (
        <div className="no-data">Awaiting events…</div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
