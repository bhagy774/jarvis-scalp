import { useState, useEffect } from 'react';

const initialState = {
  parts: {}, trades: [],
  stats: { wins: 0, losses: 0, win_rate: 0, total_pnl: 0, equity_curve: [] },
  health: {},
  pipeline: { watcher_active: false, specialist_opinions: {}, quantum_status: '', hedge_status: '' },
  terminal_logs: [], chat_history: [], system_online: false,
};
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);

export function useJarvisWS() {
  const [data, setData] = useState(initialState);
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    let socket;
    let timer;
    let stopped = false;
    const connect = () => {
      if (stopped) return;
      const endpoint = import.meta.env.VITE_JARVIS_WS_URL ||
        `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
      try {
        socket = new WebSocket(endpoint);
      } catch {
        timer = setTimeout(connect, 2000);
        return;
      }
      const current = socket;
      current.onopen = () => { if (!stopped && socket === current) setConnected(true); };
      current.onmessage = event => {
        if (stopped || socket !== current) return;
        try {
          const message = JSON.parse(event.data);
          if (message.type !== 'STATE_UPDATE' || !isObject(message.data)) return;
          const update = message.data;
          setData(previous => {
            const next = { ...previous };
            for (const key of ['parts', 'health', 'stats', 'pipeline', 'oracle']) {
              if (isObject(update[key])) next[key] = { ...previous[key], ...update[key] };
            }
            for (const key of ['trades', 'terminal_logs', 'chat_history']) {
              if (Array.isArray(update[key])) next[key] = update[key].slice(-500);
            }
            if (!Array.isArray(next.stats.equity_curve)) next.stats.equity_curve = [];
            if (!isObject(next.pipeline.specialist_opinions)) next.pipeline.specialist_opinions = {};
            if (typeof update.system_online === 'boolean') next.system_online = update.system_online;
            return next;
          });
        } catch { /* Ignore malformed frames; keep the last valid state. */ }
      };
      current.onclose = () => {
        if (stopped || socket !== current) return;
        setConnected(false);
        timer = setTimeout(connect, 2000);
      };
      current.onerror = () => current.close();
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      if (socket) {
        socket.onclose = null;
        socket.onmessage = null;
        socket.close();
      }
    };
  }, []);
  return { data, connected };
}
