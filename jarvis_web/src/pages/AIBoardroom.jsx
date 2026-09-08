import { motion, AnimatePresence } from 'framer-motion';
import { BrainCircuit, CheckCircle, XCircle, Loader } from 'lucide-react';

/* Specialist role definitions matching jarvis_specialist_pool.py */
const SPECIALISTS = [
  {
    id: 'analyst',
    name: 'Technical Analyst',
    model: 'deepseek-r1:14b',
    role: 'Deep technical reasoning, chain-of-thought market analysis',
    icon: '📊',
    color: 'var(--c-cyan)',
    glow: 'rgba(0,229,255,0.2)',
  },
  {
    id: 'validator',
    name: 'Market Validator',
    model: 'qwen2.5:14b',
    role: 'Fakeout detection, market structure validation, trap identification',
    icon: '🔍',
    color: 'var(--c-purple)',
    glow: 'rgba(168,85,247,0.2)',
  },
  {
    id: 'risk_officer',
    name: 'Chief Risk Officer',
    model: 'qwen2.5:14b',
    role: 'Risk evaluation, volatility assessment, system health check',
    icon: '🛡️',
    color: 'var(--c-yellow)',
    glow: 'rgba(245,158,11,0.2)',
  },
];

function SpecialistCard({ spec, opinion, isApproved }) {
  const verdict = opinion
    ? (opinion.toUpperCase().includes('[APPROVE]') ? 'APPROVE' : 'REJECT')
    : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 250, damping: 20 }}
      style={{
        background: 'rgba(8,12,20,0.8)',
        border: `1px solid ${spec.glow.replace('0.2', '0.3')}`,
        borderRadius: '16px',
        padding: '20px',
        backdropFilter: 'blur(16px)',
        boxShadow: `0 0 30px ${spec.glow}`,
        flex: 1,
        minWidth: 0,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <div style={{
          width: '42px', height: '42px',
          borderRadius: '12px',
          background: `${spec.glow}`,
          border: `1px solid ${spec.glow.replace('0.2', '0.4')}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '20px',
          flexShrink: 0,
        }}>
          {spec.icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: '12px', fontWeight: 700, color: spec.color, letterSpacing: '0.05em', marginBottom: '2px' }}>
            {spec.name}
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--c-text-dim)', letterSpacing: '0.05em' }}>
            MODEL: {spec.model}
          </div>
        </div>
        {verdict && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {verdict === 'APPROVE'
              ? <CheckCircle size={16} color="var(--c-green)" />
              : <XCircle size={16} color="var(--c-red)" />
            }
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700,
              color: verdict === 'APPROVE' ? 'var(--c-green)' : 'var(--c-red)',
              letterSpacing: '0.1em',
            }}>
              {verdict}
            </span>
          </div>
        )}
      </div>

      {/* Role description */}
      <div style={{
        fontFamily: 'var(--font-body)', fontSize: '11px', color: 'var(--c-text-muted)',
        borderBottom: '1px solid var(--c-border)', paddingBottom: '12px', marginBottom: '12px',
      }}>
        {spec.role}
      </div>

      {/* Opinion output */}
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--c-text)',
        background: 'rgba(0,0,0,0.4)',
        borderRadius: '8px', padding: '10px',
        minHeight: '80px',
        lineHeight: '1.6',
        border: '1px solid var(--c-border)',
        overflowY: 'auto',
        maxHeight: '150px',
      }}>
        {opinion ? (
          <span style={{ color: verdict === 'APPROVE' ? 'var(--c-green)' : verdict === 'REJECT' ? '#f87171' : 'var(--c-text-muted)' }}>
            {opinion}
          </span>
        ) : (
          <span style={{ color: 'var(--c-text-dim)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Loader size={12} className="animate-spin" /> Awaiting AI response...
          </span>
        )}
      </div>
    </motion.div>
  );
}

export default function AIBoardroom({ data }) {
  const opinions = data?.pipeline?.specialist_opinions || {};
  const chairman = data?.pipeline?.chairman_summary || null;
  const finalVerdict = chairman
    ? (chairman.toUpperCase().includes('[CONSENSUS_EXECUTE]') ? 'EXECUTE' : 'REJECT')
    : null;
  const approveVotes = Object.values(opinions).filter(op => op?.toUpperCase?.().includes('[APPROVE]')).length;
  const rejectVotes = Object.values(opinions).filter(op => op?.toUpperCase?.().includes('[REJECT]')).length;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px', gap: '16px', overflow: 'hidden' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BrainCircuit size={18} color="var(--c-purple)" />
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '16px', fontWeight: 700, color: 'var(--c-purple)', letterSpacing: '0.1em', textShadow: '0 0 15px rgba(168,85,247,0.4)' }}>
            AI BOARDROOM
          </h1>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--c-text-dim)' }}>
          POWERED BY: deepseek-r1:14b · qwen2.5:14b · Ollama Local
        </div>
      </div>

      {/* Architecture diagram hint */}
      <div style={{
        background: 'rgba(168,85,247,0.05)',
        border: '1px solid rgba(168,85,247,0.15)',
        borderRadius: '12px',
        padding: '10px 16px',
        fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--c-text-muted)',
        display: 'flex', alignItems: 'center', gap: '12px',
      }}>
        <span style={{ color: 'var(--c-cyan)' }}>WatcherAI</span>
        <span>→</span>
        <span style={{ color: 'var(--c-purple)' }}>SpecialistPool (3 AI in parallel)</span>
        <span>→</span>
        <span style={{ color: 'var(--c-yellow)' }}>Chairman Synthesis</span>
        <span>→</span>
        <span style={{ color: approveVotes >= 2 ? 'var(--c-green)' : 'var(--c-red)' }}>
          {finalVerdict ? `[${finalVerdict}]` : 'PENDING VOTES'}
        </span>
      </div>

      {/* Specialists */}
      <div style={{ display: 'flex', gap: '16px', flex: 1, overflow: 'hidden' }}>
        {SPECIALISTS.map((spec) => (
          <SpecialistCard
            key={spec.id}
            spec={spec}
            opinion={opinions[spec.id]}
            isApproved={opinions[spec.id]?.toUpperCase?.().includes('[APPROVE]')}
          />
        ))}
      </div>

      {/* Vote Tally + Chairman */}
      <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '16px' }}>
        {/* Vote count */}
        <div style={{
          background: 'rgba(8,12,20,0.8)',
          border: '1px solid var(--c-border)',
          borderRadius: '16px',
          padding: '16px',
          display: 'flex', flexDirection: 'column', gap: '8px',
        }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--c-text-dim)', letterSpacing: '0.1em', marginBottom: '4px' }}>BOARD VOTE</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--c-green)' }}>APPROVE</span>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: '28px', fontWeight: 900, color: 'var(--c-green)', textShadow: '0 0 15px rgba(34,197,94,0.5)' }}>{approveVotes}</span>
          </div>
          <div style={{ height: '1px', background: 'var(--c-border)' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--c-red)' }}>REJECT</span>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: '28px', fontWeight: 900, color: 'var(--c-red)', textShadow: '0 0 15px rgba(239,68,68,0.5)' }}>{rejectVotes}</span>
          </div>
        </div>

        {/* Chairman */}
        <div style={{
          background: finalVerdict === 'EXECUTE'
            ? 'rgba(34,197,94,0.05)'
            : finalVerdict === 'REJECT' ? 'rgba(239,68,68,0.05)' : 'rgba(8,12,20,0.8)',
          border: `1px solid ${finalVerdict === 'EXECUTE' ? 'rgba(34,197,94,0.25)' : finalVerdict === 'REJECT' ? 'rgba(239,68,68,0.25)' : 'var(--c-border)'}`,
          borderRadius: '16px',
          padding: '16px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
            <span style={{ fontSize: '18px' }}>👑</span>
            <div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: '12px', fontWeight: 700, color: 'var(--c-text)', letterSpacing: '0.08em' }}>CHAIRMAN VERDICT</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--c-text-dim)' }}>qwen2.5:14b · Final synthesis</div>
            </div>
            {finalVerdict && (
              <span style={{
                marginLeft: 'auto',
                fontFamily: 'var(--font-display)', fontSize: '14px', fontWeight: 900,
                letterSpacing: '0.1em',
                color: finalVerdict === 'EXECUTE' ? 'var(--c-green)' : 'var(--c-red)',
                textShadow: `0 0 15px ${finalVerdict === 'EXECUTE' ? 'rgba(34,197,94,0.6)' : 'rgba(239,68,68,0.6)'}`,
              }}>
                [CONSENSUS_{finalVerdict}]
              </span>
            )}
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--c-text-muted)',
            background: 'rgba(0,0,0,0.3)', borderRadius: '8px', padding: '10px',
            lineHeight: '1.6', border: '1px solid var(--c-border)',
          }}>
            {chairman || <span style={{ color: 'var(--c-text-dim)' }}>Chairman is awaiting board opinions...</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
