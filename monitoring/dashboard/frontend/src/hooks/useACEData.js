import { useEffect, useRef, useState } from "react";

const WS_URL = "ws://localhost:8000/ws";

const DEFAULT_STATE = {
  status: "offline",
  uptime_start: null,
  equity: 10000,
  daily_pnl: 0,
  daily_pnl_pct: 0,
  current_session: "outside",
  session_is_active: false,
  trades_today: 0,
  trades_this_session: 0,
  win_rate: 0,
  prices: {},
  agents: {},
  amd_phase: "UNKNOWN",
  confluence_score: 0,
  open_positions: [],
  mission_log: [],
  kill_switch_active: false,
};

export function useACEData() {
  const [data, setData] = useState(DEFAULT_STATE);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const retryRef = useRef(null);

  const connect = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data);
        setData((prev) => ({ ...prev, ...payload }));
      } catch {
        // ignore malformed frames
      }
    };

    ws.onclose = () => {
      setConnected(false);
      retryRef.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  };

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, []);

  return { data, connected };
}
