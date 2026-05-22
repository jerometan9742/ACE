import { useEffect, useRef } from "react";

export default function MissionLog({ entries }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  return (
    <div className="log-panel">
      <div className="card-label" style={{ marginBottom: 8 }}>◈ Mission Log</div>
      {entries.map((e, i) => {
        const ts = e.ts ? e.ts.slice(11, 19) : "--:--:--";
        return (
          <div className="log-entry" key={i}>
            <span className="log-ts">{ts}</span>
            <span className={`log-level log-level-${e.level}`}>{e.level}</span>
            <span className="log-msg">{e.message}</span>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
