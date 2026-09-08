import { motion } from 'framer-motion';
import { Shield, Target, TrendingUp, AlertTriangle, Activity } from 'lucide-react';
import { Line, Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, PointElement, LineElement, Tooltip, Filler } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Tooltip, Filler);

function RiskMeter({ label, value, max = 100, color = 'var(--c-cyan)', icon }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {icon}
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--c-text-muted)', letterSpacing: '0.1em' }}>{label}</span>
        </div>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: '16px', fontWeight: 700, color }}>{value.toFixed ? value.toFixed(1) : value}</span>
      </div>
      <div style={{ height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden' }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 1, ease: 'easeOut' }}
          style={{ height: '100%', background: `linear-gradient(90deg, ${color}, ${color}aa)`, borderRadius: '3px', boxShadow: `0 0 8px ${color}` }}
        />
      </div>
    </div>
  );
}

function PnLChart({ trades }) {
  if (!trades || trades.length === 0) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--c-text-dim)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
      No trade history
    </div>
  );
  // Mock per-trade PnL data
  const pnls = trades.slice(0, 20).map(t => t.pnl || 0);
  const chartData = {
    labels: pnls.map((_, i) => `T${i + 1}`),
    datasets: [{
      data: pnls,
      backgroundColor: pnls.map(p => p >= 0 ? 'rgba(34,197,94,0.7)' : 'rgba(239,68,68,0.7)'),
      borderColor: pnls.map(p => p >= 0 ? '#22c55e' : '#ef4444'),
      borderWidth: 1,
      borderRadius: 4,
    }],
  };
  const opts = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: {
      backgroundColor: 'rgba(0,0,0,0.8)',
      bodyColor: '#e2e8f0',
      borderColor: 'rgba(255,255,255,0.1)',
      borderWidth: 1,
    }},
    scales: {
      x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#475569', font: { family: 'JetBrains Mono', size: 9 } }, border: { display: false } },
      y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#475569', font: { family: 'JetBrains Mono', size: 9 } }, border: { display: false } },
    },
    animation: { duration: 600 },
  };
  return <Bar data={chartData} options={opts} />;
}

export default function RiskDesk({ data }) {
  const t = data?.trades?.[0] || null;
  const stats = data?.stats || {};
  const totalTrades = (stats.wins || 0) + (stats.losses || 0);
  const winRate = stats.win_rate || 0;
  const maxDrawdown = 5.2; // from system config
  const pnl = stats.total_pnl || 0;

  // TP/SL R:R ratio
  let rrRatio = null;
  if (t?.entry && t?.tp && t?.sl) {
    const reward = Math.abs(t.tp - t.entry);
    const risk = Math.abs(t.sl - t.entry);
    rrRatio = risk > 0 ? (reward / risk).toFixed(2) : null;
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px', gap: '16px', overflow: 'hidden' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <Shield size={18} color="var(--c-yellow)" />
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '16px', fontWeight: 700, color: 'var(--c-yellow)', letterSpacing: '0.1em', textShadow: '0 0 15px rgba(245,158,11,0.4)' }}>
          RISK & EXECUTION DESK
        </h1>
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '320px 1fr', gap: '16px', overflow: 'hidden' }}>

        {/* LEFT: Active Trade + Risk Metrics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'hidden' }}>

          {/* Active Trade */}
          <motion.div
            initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
            style={{
              background: 'rgba(8,12,20,0.8)',
              border: t ? `1px solid ${(['LONG','CALL','BUY'].includes(t.direction?.toUpperCase())) ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}` : '1px solid var(--c-border)',
              borderRadius: '16px',
              padding: '20px',
              backdropFilter: 'blur(16px)',
            }}
          >
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--c-text-dim)', letterSpacing: '0.15em', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Target size={12} color="var(--c-cyan)" />
              ACTIVE POSITION
              {t && <span style={{ marginLeft: 'auto', color: 'var(--c-green)', fontSize: '9px', background: 'rgba(34,197,94,0.1)', padding: '2px 8px', borderRadius: '5px', border: '1px solid rgba(34,197,94,0.3)' }}>LIVE</span>}
            </div>

            {t ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {/* Symbol + Direction */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '12px', borderBottom: '1px solid var(--c-border)' }}>
                  <span style={{ fontFamily: 'var(--font-display)', fontSize: '22px', fontWeight: 900, color: 'var(--c-text)' }}>{t.symbol}</span>
                  <span style={{
                    fontFamily: 'var(--font-display)', fontSize: '14px', fontWeight: 700,
                    color: (['LONG','CALL','BUY'].includes(t.direction?.toUpperCase())) ? 'var(--c-green)' : 'var(--c-red)',
                    letterSpacing: '0.1em',
                  }}>{t.direction}</span>
                </div>

                {/* Price data */}
                {[
                  { label: 'ENTRY', value: `$${t.entry?.toLocaleString()}`, color: 'var(--c-cyan)' },
                  { label: 'CURRENT', value: `$${t.current?.toLocaleString()}`, color: 'var(--c-text)' },
                  { label: 'TARGET (TP)', value: `$${t.tp?.toLocaleString()}`, color: 'var(--c-green)' },
                  { label: 'STOP (SL)', value: `$${t.sl?.toLocaleString()}`, color: 'var(--c-red)' },
                  { label: 'UNREALIZED P&L', value: `${(t.pnl || 0) >= 0 ? '+' : ''}$${(t.pnl || 0).toFixed(2)}`, color: (t.pnl || 0) >= 0 ? 'var(--c-green)' : 'var(--c-red)' },
                  ...(rrRatio ? [{ label: 'RISK/REWARD', value: `1:${rrRatio}`, color: 'var(--c-yellow)' }] : []),
                ].map(row => (
                  <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--c-text-dim)', letterSpacing: '0.1em' }}>{row.label}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 700, color: row.color }}>{row.value}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '20px', color: 'var(--c-text-dim)', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                <Activity size={24} color="var(--c-text-dim)" style={{ margin: '0 auto 8px' }} />
                No active position
              </div>
            )}
          </motion.div>

          {/* Risk metrics */}
          <motion.div
            initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}
            style={{ background: 'rgba(8,12,20,0.8)', border: '1px solid var(--c-border)', borderRadius: '16px', padding: '20px', backdropFilter: 'blur(16px)' }}
          >
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--c-text-dim)', letterSpacing: '0.15em', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={12} color="var(--c-yellow)" />
              RISK METRICS
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <RiskMeter label="WIN RATE" value={winRate} max={100} color="var(--c-cyan)" icon={<TrendingUp size={11} color="var(--c-cyan)" />} />
              <RiskMeter label="POSITION SIZE %" value={1.2} max={5} color="var(--c-yellow)" icon={<Target size={11} color="var(--c-yellow)" />} />
              <RiskMeter label="MAX DRAWDOWN %" value={maxDrawdown} max={20} color="var(--c-red)" icon={<AlertTriangle size={11} color="var(--c-red)" />} />
            </div>
          </motion.div>
        </div>

        {/* RIGHT: Stats + P&L Chart */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'hidden' }}>
          {/* Stat cards */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
            {[
              { label: 'TOTAL TRADES', value: totalTrades, color: 'var(--c-cyan)' },
              { label: 'WINS', value: stats.wins || 0, color: 'var(--c-green)' },
              { label: 'LOSSES', value: stats.losses || 0, color: 'var(--c-red)' },
              { label: 'NET P&L', value: `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(0)}`, color: pnl >= 0 ? 'var(--c-green)' : 'var(--c-red)' },
            ].map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.06 }}
                style={{ background: 'rgba(8,12,20,0.8)', border: '1px solid var(--c-border)', borderRadius: '14px', padding: '16px', backdropFilter: 'blur(16px)', textAlign: 'center' }}
              >
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--c-text-dim)', letterSpacing: '0.12em', marginBottom: '8px' }}>{s.label}</div>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: '26px', fontWeight: 900, color: s.color, textShadow: `0 0 15px ${s.color}50` }}>{s.value}</div>
              </motion.div>
            ))}
          </motion.div>

          {/* P&L Bar chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
            style={{ flex: 1, background: 'rgba(8,12,20,0.8)', border: '1px solid var(--c-border)', borderRadius: '16px', padding: '16px', backdropFilter: 'blur(16px)', overflow: 'hidden' }}
          >
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--c-text-muted)', letterSpacing: '0.12em', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Activity size={12} color="var(--c-cyan)" />
              PER-TRADE P&L DISTRIBUTION
            </div>
            <div style={{ height: 'calc(100% - 36px)' }}>
              <PnLChart trades={data?.trades || []} />
            </div>
          </motion.div>

          {/* Hedge Advisor */}
          {data?.pipeline?.hedge_status && (
            <motion.div
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
              style={{
                background: 'rgba(245,158,11,0.05)',
                border: '1px solid rgba(245,158,11,0.25)',
                borderRadius: '12px',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
              }}
            >
              <span style={{ fontSize: '16px' }}>🛡️</span>
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--c-yellow)', letterSpacing: '0.12em', marginBottom: '3px' }}>HEDGE ADVISOR</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--c-text-muted)' }}>{data.pipeline.hedge_status}</div>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
