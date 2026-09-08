import { useState, useEffect, useRef } from 'react';
import { useJarvisWS } from './store/useJarvisWS';
import { Activity, Cpu, Shield, BrainCircuit, Terminal, Target, ArrowUpRight, ArrowDownRight, Zap } from 'lucide-react';
import { motion } from 'framer-motion';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler);

const PART_NAMES = [
  "Part1_Breakout", "Part2_Neural", "Part3_Institutional", "Part4_Backtest",
  "Part5_Fusion", "Part6_Backtest", "Part7_LiveData", "Part8_Pattern",
  "Part9_Adaptive", "Part10_Execution", "Part11_Confidence", "Part12_Execution"
];

// --- TRADINGVIEW-STYLE CHART COMPONENT ---
function TradingViewChart({ data }) {
  const eqData = data?.stats?.equity_curve || [];
  
  const chartData = {
    labels: eqData.map((_, i) => i.toString()),
    datasets: [{
      fill: true,
      data: eqData,
      borderColor: '#00e5ff',
      backgroundColor: (context) => {
        const ctx = context.chart.ctx;
        const gradient = ctx.createLinearGradient(0, 0, 0, context.chart.height);
        gradient.addColorStop(0, 'rgba(0, 229, 255, 0.4)');
        gradient.addColorStop(1, 'rgba(0, 229, 255, 0.0)');
        return gradient;
      },
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 4,
      pointHoverBackgroundColor: '#fff',
      pointHoverBorderColor: '#00e5ff',
      tension: 0.1,
    }],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { 
      legend: { display: false }, 
      tooltip: { 
        enabled: true,
        mode: 'index',
        intersect: false,
        backgroundColor: 'rgba(0,0,0,0.8)',
        titleColor: '#808080',
        bodyColor: '#00e5ff',
        borderColor: 'rgba(0, 229, 255, 0.3)',
        borderWidth: 1,
        displayColors: false
      } 
    },
    scales: { 
      x: { display: false }, 
      y: { 
        display: true, 
        position: 'right',
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        border: { display: false },
        ticks: { color: '#808080', font: { family: 'monospace', size: 10 } }
      } 
    },
    interaction: { mode: 'nearest', axis: 'x', intersect: false },
    animation: { duration: 0 }
  };

  if (eqData.length === 0) {
    return <div className="w-full h-full flex items-center justify-center text-gray-600 font-mono text-xs">Waiting for equity data...</div>;
  }

  return (
    <div className="w-full h-full pt-8 pb-2 pl-2 pr-2">
      <Line data={chartData} options={chartOptions} />
    </div>
  );
}

// --- BENTO GRID TERMINAL ---
export default function HFTTerminal() {
  const { data, connected } = useJarvisWS();
  const terminalRef = useRef(null);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [data?.terminal_logs]);

  const t = data?.trades?.[0] || null;
  const hedge = data?.pipeline?.hedge_status || "Hedge Advisor: STANDBY";

  // Framer Motion variants
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };
  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
  };

  return (
    <div className="h-screen w-screen bg-[#050505] text-gray-200 font-inter overflow-hidden flex flex-col relative">
      
      {/* Subtle Matrix/Grid Background */}
      <div className="absolute inset-0 z-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none" />
      <div className="absolute inset-0 z-0 bg-gradient-to-tr from-cyan-900/10 via-transparent to-purple-900/10 pointer-events-none" />

      {/* HEADER */}
      <header className="relative z-10 h-14 border-b border-white/5 bg-black/60 backdrop-blur-xl flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Zap size={16} />
          </div>
          <div>
            <h1 className="font-mono font-bold tracking-widest text-sm text-gray-100">JARVIS ELITE v7.0</h1>
            <p className="font-mono text-[10px] text-gray-500 uppercase tracking-widest">HFT Quant Terminal</p>
          </div>
        </div>
        
        {/* Signal Overview Banner */}
        {t && (
          <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-4 px-6 py-1.5 rounded-full border border-white/10 bg-black/50">
             <span className="text-xs font-mono text-gray-400">ACTIVE SIGNAL</span>
             <span className={`text-sm font-bold tracking-widest flex items-center gap-1 ${t.direction === 'CALL' || t.direction === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
               {t.direction === 'CALL' || t.direction === 'BUY' ? <ArrowUpRight size={16}/> : <ArrowDownRight size={16}/>}
               {t.direction}
             </span>
             <div className="w-px h-4 bg-white/20"></div>
             <span className="text-xs font-mono text-gray-400">CONF: {t.confidence || 0}%</span>
          </div>
        )}

        <div className="flex items-center gap-3 font-mono text-xs">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-white/5 border border-white/10">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 shadow-[0_0_8px_rgba(0,255,102,0.6)]' : 'bg-red-500 animate-pulse'}`} />
            <span className={connected ? 'text-gray-300' : 'text-red-400'}>{connected ? 'LIVE DATAFEED' : 'DISCONNECTED'}</span>
          </div>
        </div>
      </header>

      {/* BENTO GRID */}
      <motion.div 
        variants={container}
        initial="hidden"
        animate="show"
        className="relative z-10 flex-1 p-4 grid grid-cols-12 grid-rows-6 gap-4 h-[calc(100vh-3.5rem)]"
      >
        
        {/* PANEL 1: GPU Matrix (Left) */}
        <motion.div variants={item} className="col-span-3 row-span-6 rounded-2xl border border-white/10 bg-[#0a0a0a]/80 backdrop-blur-md p-4 flex flex-col shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2 text-gray-300">
              <Cpu size={16} className="text-cyan-400" />
              <h2 className="font-mono text-xs font-semibold tracking-wider">GPU ENGINE MATRIX</h2>
            </div>
            <div className="text-[10px] text-gray-500 font-mono">12 NODES</div>
          </div>
          
          <div className="flex-1 grid grid-cols-1 gap-2 overflow-y-auto custom-scrollbar pr-2">
            {PART_NAMES.map((name, i) => {
              const partData = data?.parts?.[name];
              const dir = partData?.direction || 'NEUTRAL';
              const conf = partData?.confidence || 0;
              
              let bgColor = 'bg-gray-800/50';
              let textColor = 'text-gray-500';
              let dotColor = 'bg-gray-500';
              
              if(dir === 'BULLISH') { bgColor = 'bg-green-950/30'; textColor = 'text-green-400'; dotColor = 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]'; }
              if(dir === 'BEARISH') { bgColor = 'bg-red-950/30'; textColor = 'text-red-400'; dotColor = 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]'; }

              return (
                <div key={name} className={`flex items-center justify-between p-3 rounded-xl border border-white/5 ${bgColor} transition-colors duration-500`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
                    <span className="font-mono text-[11px] text-gray-300">{name.replace('Part', 'P')}</span>
                  </div>
                  <div className={`font-mono text-[11px] font-bold ${textColor}`}>
                    {dir} {conf > 0 ? `${conf}%` : ''}
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>

        {/* PANEL 2: TradingView Chart (Center Top) */}
        <motion.div variants={item} className="col-span-6 row-span-4 rounded-2xl border border-white/10 bg-[#0a0a0a]/80 backdrop-blur-md p-1 relative overflow-hidden group">
          <div className="absolute top-4 left-4 z-10 pointer-events-none">
            <h2 className="font-mono text-xs text-gray-400 tracking-wider">EQUITY CURVE / PRICE TRACKER</h2>
          </div>
          {/* Subtle gradient behind chart */}
          <div className="absolute inset-0 bg-gradient-to-b from-cyan-900/5 to-transparent pointer-events-none" />
          <TradingViewChart data={data} />
        </motion.div>

        {/* PANEL 3: Cortex Reasoning (Right Top) */}
        <motion.div variants={item} className="col-span-3 row-span-3 rounded-2xl border border-purple-500/20 bg-gradient-to-b from-purple-900/10 to-[#0a0a0a]/80 backdrop-blur-md p-4 flex flex-col shadow-[0_0_30px_rgba(168,85,247,0.05)]">
          <div className="flex items-center gap-2 text-purple-400 mb-4">
            <BrainCircuit size={16} />
            <h2 className="font-mono text-xs font-semibold tracking-wider">CORTEX REASONING</h2>
          </div>
          <div className="flex-1 overflow-y-auto font-mono text-[11px] text-gray-300 leading-relaxed custom-scrollbar">
            {data?.terminal_logs?.slice(-40).filter(l => l.includes("AI RATIONALE:") || l.includes("→") || l.includes("Decision:") || l.includes("OLLAMA")).map((l, i) => (
              <div key={i} className="mb-3 border-l-2 border-purple-500/30 pl-3 opacity-90">{l}</div>
            ))}
            {!data?.terminal_logs?.some(l => l.includes("AI RATIONALE:")) && (
              <div className="text-gray-600 animate-pulse mt-4">Awaiting Cortex NLP generation...</div>
            )}
          </div>
        </motion.div>

        {/* PANEL 4: Hedge Advisor (Right Middle) */}
        <motion.div variants={item} className="col-span-3 row-span-1 rounded-2xl border border-yellow-500/20 bg-gradient-to-r from-yellow-900/10 to-[#0a0a0a]/80 backdrop-blur-md p-4 flex flex-col justify-center">
          <div className="flex items-center gap-2 text-yellow-500 mb-2">
            <Shield size={16} />
            <h2 className="font-mono text-xs font-semibold tracking-wider">HEDGE ADVISOR</h2>
          </div>
          <div className="font-mono text-[11px] text-gray-300 truncate">
            {hedge}
          </div>
        </motion.div>

        {/* PANEL 5: Execution Desk (Right Bottom) */}
        <motion.div variants={item} className="col-span-3 row-span-2 rounded-2xl border border-white/10 bg-[#0a0a0a]/80 backdrop-blur-md p-4 flex flex-col shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-green-500/5 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none" />
          
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2 text-green-400">
              <Target size={16} />
              <h2 className="font-mono text-xs font-semibold tracking-wider">EXECUTION DESK</h2>
            </div>
            {t && <span className="px-2 py-0.5 rounded bg-green-500/20 text-green-400 text-[10px] font-mono border border-green-500/30">LIVE</span>}
          </div>
          
          {t ? (
            <div className="flex flex-col justify-between flex-1 gap-2">
              <div className="flex justify-between items-end border-b border-white/5 pb-2">
                <span className="text-[10px] font-mono text-gray-500 tracking-widest">ENTRY PRICE</span>
                <span className="font-mono text-2xl font-bold text-white tracking-tight">${t.entry?.toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-end">
                <span className="text-[10px] font-mono text-green-500 tracking-widest">TARGET (TP)</span>
                <span className="font-mono text-sm text-green-400">${t.tp?.toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-end">
                <span className="text-[10px] font-mono text-red-500 tracking-widest">STOP (SL)</span>
                <span className="font-mono text-sm text-red-400">${t.sl?.toLocaleString()}</span>
              </div>
            </div>
          ) : (
             <div className="flex-1 flex flex-col items-center justify-center text-gray-600 font-mono text-xs text-center p-4 border border-white/5 rounded-xl border-dashed">
                <Activity size={24} className="mb-2 text-gray-700 animate-pulse" />
                AWAITING TRIGGERS
              </div>
          )}
        </motion.div>

        {/* PANEL 6: Terminal Feed (Center Bottom) */}
        <motion.div variants={item} className="col-span-6 row-span-2 rounded-2xl border border-white/10 bg-[#050505] p-3 flex flex-col shadow-inner relative overflow-hidden">
          <div className="flex items-center justify-between mb-2 pb-2 border-b border-white/5">
            <div className="flex items-center gap-2 text-gray-500">
              <Terminal size={14} />
              <h2 className="font-mono text-[10px] uppercase tracking-widest">jarvis_terminal.log</h2>
            </div>
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
          </div>
          <div 
            ref={terminalRef}
            className="flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed custom-scrollbar pl-1 pr-4"
          >
            {data?.terminal_logs?.map((line, i) => {
              // Proper syntax highlighting for terminal logs
              let color = "text-gray-400";
              let bg = "";
              
              if(line.includes("ERROR") || line.includes("🔴") || line.includes("❌")) { color = "text-red-400"; }
              else if(line.includes("WARNING")) { color = "text-yellow-400"; }
              else if(line.includes("✅") || line.includes("SUCCESS")) { color = "text-green-400"; }
              else if(line.includes("💎 SIGNAL")) { color = "text-cyan-400 font-bold"; bg="bg-cyan-500/10 px-1 rounded"; }
              else if(line.includes("⚛️ QUANTUM")) { color = "text-purple-400"; }
              else if(line.includes("HEDGE ADVISOR")) { color = "text-yellow-500 font-bold"; }
              else if(line.match(/\[\d{2}:\d{2}:\d{2}\]/)) { color = "text-gray-300"; } // Timestamp color
              
              return <div key={i} className={`${color} ${bg} break-words whitespace-pre-wrap leading-normal`}>{line}</div>;
            }) || <div className="text-gray-700 animate-pulse">Waiting for stdout stream...</div>}
          </div>
        </motion.div>

      </motion.div>

      {/* Global Custom Scrollbar styles */}
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
      `}} />
    </div>
  );
}
