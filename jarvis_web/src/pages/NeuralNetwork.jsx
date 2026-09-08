import { motion } from 'framer-motion';

const PART_NAMES = [
  "Part1_Breakout", "Part2_Neural", "Part3_Institutional", "Part4_Backtest",
  "Part5_Fusion", "Part6_Backtest", "Part7_LiveData", "Part8_Pattern",
  "Part9_Adaptive", "Part10_Execution", "Part11_Confidence", "Part12_Execution"
];

function PartCard({ name, data, index }) {
  const dir = data?.direction || 'NEUTRAL';
  const conf = data?.confidence || 0;
  
  const colors = {
    BULLISH: 'border-green-500/50 bg-green-500/10 text-green-400',
    BEARISH: 'border-red-500/50 bg-red-500/10 text-red-400',
    NEUTRAL: 'border-yellow-500/50 bg-yellow-500/10 text-yellow-400'
  };

  const progressColors = {
    BULLISH: 'bg-green-400',
    BEARISH: 'bg-red-400',
    NEUTRAL: 'bg-yellow-400'
  };

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.05 }}
      className="glass-panel rounded-xl p-5 hover:bg-white/5 transition-colors cursor-pointer group"
    >
      <div className="flex justify-between items-start mb-4">
        <h3 className="font-mono text-sm text-gray-200 group-hover:text-cyan-400 transition-colors">
          {name.replace('Part', 'P')}
        </h3>
        <div className={`text-[10px] font-bold px-2 py-1 rounded-md border ${colors[dir]}`}>
          {dir}
        </div>
      </div>
      
      <div className="mb-4">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-500 font-mono">Confidence</span>
          <span className="text-gray-300 font-mono">{conf.toFixed(0)}%</span>
        </div>
        <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <motion.div 
            initial={{ width: 0 }}
            animate={{ width: `${conf}%` }}
            transition={{ duration: 1 }}
            className={`h-full rounded-full ${progressColors[dir]}`}
          />
        </div>
      </div>

      <div className="text-[10px] text-gray-500 font-mono leading-relaxed line-clamp-3">
        {data?.raw || 'Awaiting telemetry...'}
      </div>
    </motion.div>
  );
}

export default function NeuralNetwork({ data }) {
  return (
    <div className="p-8">
      <div className="mb-8">
        <h2 className="text-2xl font-orbitron font-bold text-gray-100">Neural Network Topography</h2>
        <p className="text-sm text-gray-400 mt-1">Live consensus monitor across 12 analytical nodes.</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {PART_NAMES.map((name, i) => (
          <PartCard 
            key={name} 
            name={name} 
            data={data.parts?.[name]} 
            index={i} 
          />
        ))}
      </div>
    </div>
  );
}
