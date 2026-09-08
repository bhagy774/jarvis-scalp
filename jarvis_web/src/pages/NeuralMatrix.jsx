import { motion } from 'framer-motion';
import { Cpu } from 'lucide-react';

const PARTS_META = {
  "Part1_Breakout":      { label: "P1 · Breakout AI",        desc: "13-brain breakout pattern detection",     icon: "⚡" },
  "Part2_Neural":        { label: "P2 · Neural Network",      desc: "14 GPU neural nets + ML ensemble",        icon: "🧠" },
  "Part3_Institutional": { label: "P3 · Institutional",       desc: "Big player flow & MTF analysis",          icon: "🏦" },
  "Part4_Backtest":      { label: "P4 · Backtest Engine",     desc: "GPU institutional backtesting",           icon: "📊" },
  "Part5_Fusion":        { label: "P5 · Signal Fusion",       desc: "Multi-timeframe signal consensus",        icon: "🔀" },
  "Part6_Backtest":      { label: "P6 · Comprehensive BT",    desc: "Full strategy backtester",                icon: "📈" },
  "Part7_LiveData":      { label: "P7 · Live Data Engine",    desc: "Real-time market data ingestion",         icon: "📡" },
  "Part8_Pattern":       { label: "P8 · Pattern Recognition", desc: "GPU candlestick pattern AI",              icon: "🔍" },
  "Part9_Adaptive":      { label: "P9 · Adaptive Learning",   desc: "Self-improving ML strategy optimizer",    icon: "🎯" },
  "Part10_Execution":    { label: "P10 · Execution Engine",   desc: "Telegram & order routing system",         icon: "🚀" },
  "Part11_Confidence":   { label: "P11 · Confidence Engine",  desc: "Unified confidence scoring + Ollama adj", icon: "✅" },
  "Part12_Execution":    { label: "P12 · Order Execution",    desc: "GPU order execution & analytics",         icon: "⚙️" },
};

function PartCard({ name, partData, index }) {
  const meta = PARTS_META[name] || { label: name, desc: 'GPU engine', icon: '⚡' };
  const dir = partData?.direction || 'NEUTRAL';
  const conf = partData?.confidence || 0;
  const ts = partData?.ts;

  const isBull = dir === 'BULLISH';
  const isBear = dir === 'BEARISH';

  const dirColor = isBull ? 'var(--c-green)' : isBear ? 'var(--c-red)' : 'var(--c-yellow)';
  const bgGlow = isBull ? 'rgba(34,197,94,0.05)' : isBear ? 'rgba(239,68,68,0.05)' : 'rgba(245,158,11,0.03)';
  const borderColor = isBull ? 'rgba(34,197,94,0.2)' : isBear ? 'rgba(239,68,68,0.2)' : 'rgba(245,158,11,0.15)';

  // Confidence bar segments (10 blocks)
  const filled = Math.round(conf / 10);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, type: 'spring', stiffness: 300, damping: 25 }}
      style={{
        background: bgGlow,
        border: `1px solid ${borderColor}`,
        borderRadius: '12px',
        padding: '14px',
        position: 'relative',
        overflow: 'hidden',
        backdropFilter: 'blur(10px)',
        transition: 'border-color 0.5s, background 0.5s',
      }}
    >
      {/* Top row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '16px' }}>{meta.icon}</span>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 600, color: 'var(--c-text)', letterSpacing: '0.03em' }}>
              {meta.label}
            </div>
            <div style={{ fontFamily: 'var(--font-body)', fontSize: '10px', color: 'var(--c-text-dim)', marginTop: '1px' }}>
              {meta.desc}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', flex: 'column', alignItems: 'flex-end', gap: '4px' }}>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700,
            color: dirColor, letterSpacing: '0.08em',
            textShadow: `0 0 10px ${dirColor}`,
            background: `${dirColor}15`,
            border: `1px solid ${dirColor}40`,
            padding: '2px 8px', borderRadius: '5px',
          }}>
            {dir}
          </span>
        </div>
      </div>

      {/* Confidence bar */}
      <div style={{ marginBottom: '6px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--c-text-dim)', letterSpacing: '0.1em' }}>CONFIDENCE</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700, color: dirColor }}>{conf.toFixed(1)}%</span>
        </div>
        <div style={{ display: 'flex', gap: '2px' }}>
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} style={{
              flex: 1, height: '4px', borderRadius: '2px',
              background: i < filled ? dirColor : 'rgba(255,255,255,0.08)',
              boxShadow: i < filled ? `0 0 4px ${dirColor}` : 'none',
              transition: 'background 0.3s',
            }} />
          ))}
        </div>
      </div>

      {/* Raw output snippet */}
      {partData?.raw && (
        <div style={{
          fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--c-text-dim)',
          background: 'rgba(0,0,0,0.3)', borderRadius: '6px', padding: '5px 7px',
          overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis',
        }}>
          {partData.raw}
        </div>
      )}

      {/* Timestamp */}
      {ts && (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', color: 'var(--c-text-dim)', marginTop: '6px', textAlign: 'right' }}>
          {new Date(ts).toLocaleTimeString('en-US', { hour12: false })}
        </div>
      )}

      {/* Background fill effect */}
      <div style={{
        position: 'absolute', top: 0, left: 0, bottom: 0, width: `${conf}%`,
        background: `linear-gradient(90deg, ${dirColor}08, transparent)`,
        pointerEvents: 'none', transition: 'width 1s ease',
      }} />
    </motion.div>
  );
}

export default function NeuralMatrix({ data }) {
  const parts = data?.parts || {};
  const partNames = Object.keys(PARTS_META);

  const bullishCount = Object.values(parts).filter(p => p.direction === 'BULLISH').length;
  const bearishCount = Object.values(parts).filter(p => p.direction === 'BEARISH').length;
  const neutralCount = Object.values(parts).filter(p => p.direction === 'NEUTRAL').length;
  const avgConf = Object.values(parts).length > 0
    ? (Object.values(parts).reduce((a, p) => a + (p.confidence || 0), 0) / Object.values(parts).length).toFixed(1)
    : 0;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px', gap: '16px', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Cpu size={18} color="var(--c-cyan)" />
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '16px', fontWeight: 700, color: 'var(--c-cyan)', letterSpacing: '0.1em', textShadow: '0 0 15px rgba(0,229,255,0.4)' }}>
            NEURAL ENGINE MATRIX
          </h1>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--c-text-dim)', letterSpacing: '0.1em' }}>12 GPU ENGINES ACTIVE</span>
        </div>

        {/* Summary pills */}
        <div style={{ display: 'flex', gap: '8px', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
          {[
            { label: '↑ BULLISH', count: bullishCount, color: 'var(--c-green)', border: 'rgba(34,197,94,0.3)' },
            { label: '↓ BEARISH', count: bearishCount, color: 'var(--c-red)', border: 'rgba(239,68,68,0.3)' },
            { label: '— NEUTRAL', count: neutralCount, color: 'var(--c-yellow)', border: 'rgba(245,158,11,0.3)' },
            { label: 'AVG CONF', count: `${avgConf}%`, color: 'var(--c-cyan)', border: 'rgba(0,229,255,0.3)' },
          ].map(s => (
            <div key={s.label} style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '5px 12px', borderRadius: '8px',
              background: `${s.color}10`, border: `1px solid ${s.border}`,
            }}>
              <span style={{ color: 'var(--c-text-muted)', fontSize: '9px' }}>{s.label}</span>
              <span style={{ color: s.color, fontWeight: 700 }}>{s.count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Grid */}
      <div style={{
        flex: 1, overflowY: 'auto',
        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px',
        paddingRight: '6px',
      }}>
        {partNames.map((name, i) => (
          <PartCard key={name} name={name} partData={parts[name]} index={i} />
        ))}
      </div>
    </div>
  );
}
