import { useState, useEffect } from 'react';
import { HashRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useJarvisWS } from './store/useJarvisWS';
import {
  Activity, Cpu, BrainCircuit, Terminal,
  BarChart2, Shield, Zap, Wifi, WifiOff
} from 'lucide-react';

// Pages
import CommandCenter3D from './pages/CommandCenter3D.jsx';
import NeuralMatrix from './pages/NeuralMatrix.jsx';
import AIBoardroom from './pages/AIBoardroom.jsx';
import LiveTerminal from './pages/LiveTerminal.jsx';
import RiskDesk from './pages/RiskDesk.jsx';

function AnimatedRoutes({ data, connected }) {
  const location = useLocation();
  
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<PageWrapper><CommandCenter3D data={data} connected={connected} /></PageWrapper>} />
        <Route path="/neural" element={<PageWrapper><NeuralMatrix data={data} /></PageWrapper>} />
        <Route path="/ai" element={<PageWrapper><AIBoardroom data={data} /></PageWrapper>} />
        <Route path="/terminal" element={<PageWrapper><LiveTerminal data={data} /></PageWrapper>} />
        <Route path="/risk" element={<PageWrapper><RiskDesk data={data} /></PageWrapper>} />
      </Routes>
    </AnimatePresence>
  );
}

function PageWrapper({ children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 15, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -15, scale: 0.98 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{ height: '100%', width: '100%', overflow: 'hidden' }}
    >
      {children}
    </motion.div>
  );
}

export default function App() {
  const { data, connected } = useJarvisWS();
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const bullishCount = Object.values(data?.parts || {}).filter(p => p.direction === 'BULLISH').length;
  const bearishCount = Object.values(data?.parts || {}).filter(p => p.direction === 'BEARISH').length;
  const totalParts = Object.keys(data?.parts || {}).length;
  const consensus = bullishCount > bearishCount ? 'BULLISH' : bearishCount > bullishCount ? 'BEARISH' : 'NEUTRAL';

  return (
    <HashRouter>
      <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--c-bg)' }}>

        {/* ── SIDEBAR NAV ── */}
        <nav style={{
          width: '68px',
          borderRight: '1px solid var(--c-border)',
          background: 'rgba(8,12,20,0.9)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '16px 0',
          gap: '8px',
          flexShrink: 0,
          zIndex: 50,
        }}>
          {/* Logo */}
          <div style={{ marginBottom: '16px', textAlign: 'center' }}>
            <div style={{
              width: '40px', height: '40px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, rgba(0,229,255,0.2), rgba(168,85,247,0.2))',
              border: '1px solid rgba(0,229,255,0.3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 20px rgba(0,229,255,0.2)',
              margin: '0 auto',
            }}>
              <Zap size={20} color="var(--c-cyan)" />
            </div>
          </div>

          <NavLinkIcon to="/" icon={<Activity size={18} />} label="HQ" />
          <NavLinkIcon to="/neural" icon={<Cpu size={18} />} label="Matrix" />
          <NavLinkIcon to="/ai" icon={<BrainCircuit size={18} />} label="AI Board" />
          <NavLinkIcon to="/terminal" icon={<Terminal size={18} />} label="Terminal" />
          <NavLinkIcon to="/risk" icon={<Shield size={18} />} label="Risk" />

          {/* Status at bottom */}
          <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
            <div title={connected ? 'Live' : 'Offline'} style={{
              width: '8px', height: '8px', borderRadius: '50%',
              background: connected ? 'var(--c-green)' : 'var(--c-red)',
              boxShadow: connected ? '0 0 10px rgba(34,197,94,0.8)' : '0 0 10px rgba(239,68,68,0.8)',
            }} />
          </div>
        </nav>

        {/* ── MAIN AREA ── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {/* ── TOP STATUS BAR ── */}
          <header style={{
            height: '48px',
            borderBottom: '1px solid var(--c-border)',
            background: 'rgba(8,12,20,0.8)',
            backdropFilter: 'blur(20px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 20px',
            flexShrink: 0,
            zIndex: 40,
          }}>
            {/* Left: System Title */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <span style={{ fontFamily: 'var(--font-display)', fontSize: '13px', fontWeight: 700, color: 'var(--c-cyan)', letterSpacing: '0.15em', textShadow: '0 0 15px rgba(0,229,255,0.5)' }}>
                JARVIS ELITE v7.0
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--c-text-dim)', letterSpacing: '0.1em' }}>
                HFT QUANT TERMINAL
              </span>
            </div>

            {/* Center: Consensus */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: 'var(--c-text-muted)' }}>SYSTEM CONSENSUS:</span>
                <span style={{
                  fontWeight: 700,
                  color: consensus === 'BULLISH' ? 'var(--c-green)' : consensus === 'BEARISH' ? 'var(--c-red)' : 'var(--c-yellow)',
                  textShadow: `0 0 12px ${consensus === 'BULLISH' ? 'rgba(34,197,94,0.6)' : consensus === 'BEARISH' ? 'rgba(239,68,68,0.6)' : 'rgba(245,158,11,0.5)'}`,
                  letterSpacing: '0.1em',
                }}>
                  {totalParts > 0 ? consensus : 'SCANNING...'}
                </span>
              </div>
              <div style={{ width: '1px', height: '16px', background: 'var(--c-border)' }} />
              <span style={{ color: 'var(--c-green)' }}>↑ {bullishCount}</span>
              <span style={{ color: 'var(--c-red)' }}>↓ {bearishCount}</span>
              <span style={{ color: 'var(--c-text-muted)' }}>/ {totalParts} ENGINES</span>
              <div style={{ width: '1px', height: '16px', background: 'var(--c-border)' }} />
              <span style={{ color: 'var(--c-text-muted)' }}>PnL:</span>
              <span style={{ color: (data?.stats?.total_pnl || 0) >= 0 ? 'var(--c-green)' : 'var(--c-red)', fontWeight: 700 }}>
                {(data?.stats?.total_pnl || 0) >= 0 ? '+' : ''}${(data?.stats?.total_pnl || 0).toFixed(2)}
              </span>
              <div style={{ width: '1px', height: '16px', background: 'var(--c-border)' }} />
              <span style={{ color: 'var(--c-text-muted)' }}>WIN RATE:</span>
              <span style={{ color: 'var(--c-cyan)', fontWeight: 700 }}>{(data?.stats?.win_rate || 0).toFixed(1)}%</span>
            </div>

            {/* Right: Status & Time */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {connected ? <Wifi size={12} color="var(--c-green)" /> : <WifiOff size={12} color="var(--c-red)" />}
                <span style={{ color: connected ? 'var(--c-green)' : 'var(--c-red)' }}>
                  {connected ? 'LIVE' : 'OFFLINE'}
                </span>
              </div>
              <span style={{ color: 'var(--c-text-dim)' }}>|</span>
              <span style={{ color: 'var(--c-text-muted)', letterSpacing: '0.05em' }}>
                {time.toLocaleTimeString('en-US', { hour12: false })}
              </span>
            </div>
          </header>

          {/* ── PAGE CONTENT ── */}
          <main style={{ flex: 1, overflow: 'hidden' }}>
            <AnimatedRoutes data={data} connected={connected} />
          </main>
        </div>
      </div>
    </HashRouter>
  );
}

function NavLinkIcon({ to, icon, label }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      style={({ isActive }) => ({
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '4px',
        padding: '8px 6px',
        borderRadius: '10px',
        border: '1px solid transparent',
        textDecoration: 'none',
        width: '52px',
        cursor: 'pointer',
        transition: 'all 0.2s',
        color: isActive ? 'var(--c-cyan)' : 'var(--c-text-dim)',
        background: isActive ? 'rgba(0,229,255,0.1)' : 'transparent',
        borderColor: isActive ? 'rgba(0,229,255,0.2)' : 'transparent',
        boxShadow: isActive ? '0 0 15px rgba(0,229,255,0.1)' : 'none',
      })}
    >
      {icon}
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', letterSpacing: '0.05em', fontWeight: 600 }}>{label}</span>
    </NavLink>
  );
}
