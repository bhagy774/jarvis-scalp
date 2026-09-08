import { useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Terminal } from 'lucide-react';

function classifyLine(line) {
  const l = line.toUpperCase();
  if (l.includes('ERROR') || l.includes('❌') || l.includes('🔴')) return 'error';
  if (l.includes('WARNING') || l.includes('⚠️')) return 'warn';
  if (l.includes('✅') || l.includes('SUCCESS')) return 'success';
  if (l.includes('💎 SIGNAL') || l.includes('CONSENSUS_EXECUTE')) return 'signal';
  if (l.includes('⚛️ QUANTUM') || l.includes('QUANTUM')) return 'quantum';
  if (l.includes('HEDGE') || l.includes('🛡️')) return 'warn';
  return 'normal';
}

const LINE_COLORS = {
  error:   '#f87171',
  warn:    '#fbbf24',
  success: '#4ade80',
  signal:  '#00e5ff',
  quantum: '#c084fc',
  normal:  '#94a3b8',
};

const LINE_BG = {
  error:   'rgba(239,68,68,0.06)',
  warn:    'rgba(245,158,11,0.06)',
  success: 'rgba(34,197,94,0.06)',
  signal:  'rgba(0,229,255,0.08)',
  quantum: 'rgba(168,85,247,0.06)',
  normal:  'transparent',
};

export default function LiveTerminal({ data }) {
  const termRef = useRef(null);
  const logs = data?.terminal_logs || [];

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight;
  }, [logs]);

  const lineCount = logs.length;
  const errorCount = logs.filter(l => classifyLine(l) === 'error').length;
  const signalCount = logs.filter(l => classifyLine(l) === 'signal').length;
  const quantumCount = logs.filter(l => classifyLine(l) === 'quantum').length;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px', gap: '16px', overflow: 'hidden' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Terminal size={18} color="var(--c-cyan)" />
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '16px', fontWeight: 700, color: 'var(--c-cyan)', letterSpacing: '0.1em', textShadow: '0 0 15px rgba(0,229,255,0.4)' }}>
            LIVE TERMINAL STREAM
          </h1>
        </div>
        <div style={{ display: 'flex', gap: '8px', fontFamily: 'var(--font-mono)', fontSize: '10px' }}>
          {[
            { label: 'LINES', count: lineCount, color: 'var(--c-text-muted)' },
            { label: '⚛️ QUANTUM', count: quantumCount, color: 'var(--c-purple)' },
            { label: '💎 SIGNALS', count: signalCount, color: 'var(--c-cyan)' },
            { label: '❌ ERRORS', count: errorCount, color: 'var(--c-red)' },
          ].map(s => (
            <div key={s.label} style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '4px 10px', borderRadius: '6px',
              background: 'rgba(255,255,255,0.04)', border: '1px solid var(--c-border)',
            }}>
              <span style={{ color: 'var(--c-text-dim)' }}>{s.label}:</span>
              <span style={{ color: s.color, fontWeight: 700 }}>{s.count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Terminal window */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        style={{
          flex: 1,
          background: '#030407',
          border: '1px solid rgba(0,229,255,0.15)',
          borderRadius: '16px',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 0 40px rgba(0,229,255,0.05), inset 0 1px 0 rgba(0,229,255,0.1)',
        }}
      >
        {/* Window title bar */}
        <div style={{
          height: '36px',
          borderBottom: '1px solid var(--c-border)',
          background: 'rgba(8,12,20,0.9)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '0 14px',
          flexShrink: 0,
        }}>
          <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444' }} />
          <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#f59e0b' }} />
          <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#22c55e' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--c-text-muted)', marginLeft: '8px' }}>
            jarvis_terminal.log — stdout capture
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--c-green)', boxShadow: '0 0 8px rgba(34,197,94,0.8)', animation: 'pulse-green 2s infinite' }} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--c-green)' }}>STREAMING</span>
          </div>
        </div>

        {/* Log lines */}
        <div
          ref={termRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '12px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '1px',
          }}
        >
          {logs.length === 0 ? (
            <div style={{ color: 'var(--c-text-dim)', fontFamily: 'var(--font-mono)', fontSize: '12px', padding: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--c-cyan)' }}>$</span>
              <span style={{ animation: 'pulse 1.5s infinite' }}>Waiting for jarvis_FIXED.py stdout stream...</span>
            </div>
          ) : logs.map((line, i) => {
            const cls = classifyLine(line);
            const isImportant = cls === 'signal' || cls === 'error';
            return (
              <div key={i} style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11.5px',
                lineHeight: '1.6',
                color: LINE_COLORS[cls],
                background: isImportant ? LINE_BG[cls] : 'transparent',
                borderRadius: isImportant ? '4px' : '0',
                padding: isImportant ? '2px 6px' : '0 2px',
                borderLeft: cls === 'signal' ? '2px solid var(--c-cyan)' : cls === 'quantum' ? '2px solid var(--c-purple)' : 'none',
                paddingLeft: (cls === 'signal' || cls === 'quantum') ? '8px' : '2px',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                transition: 'background 0.2s',
              }}>
                {line.trimEnd()}
              </div>
            );
          })}
          {/* Blinking cursor */}
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--c-cyan)', animation: 'pulse 1s infinite' }}>▋</div>
        </div>
      </motion.div>
    </div>
  );
}
