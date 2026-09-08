import { useState, useEffect } from 'react';

// Connect to the JARVIS HUD Server WebSocket
export function useJarvisWS() {
  const [data, setData] = useState({
    parts: {},
    trades: [],
    stats: { wins: 0, losses: 0, win_rate: 0, total_pnl: 0, equity_curve: [] },
    health: {},
    pipeline: { watcher_active: false, specialist_opinions: {}, quantum_status: '', hedge_status: '' },
    terminal_logs: [],
    chat_history: [],
    system_online: true,
  });
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let ws;
    let reconnectTimeout;

    const connect = () => {
      ws = new WebSocket(`ws://localhost:7788/ws`);
      
      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'STATE_UPDATE') {
            setData(prev => ({
              ...prev,
              ...message.data,
              stats: { ...prev.stats, ...(message.data.stats || {}) },
              pipeline: { ...prev.pipeline, ...(message.data.pipeline || {}) },
            }));
          }
        } catch (e) {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Try to reconnect every 2 seconds
        reconnectTimeout = setTimeout(connect, 2000);
      };
      
      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      if (ws) ws.close();
      clearTimeout(reconnectTimeout);
    };
  }, []);

  return { data, connected };
}
