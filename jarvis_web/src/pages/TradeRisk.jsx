import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler
);

export default function TradeRisk({ data }) {
  const eqData = data?.stats?.equity_curve || [];
  
  const chartData = {
    labels: eqData.map((_, i) => i.toString()),
    datasets: [
      {
        fill: true,
        label: 'Equity',
        data: eqData,
        borderColor: '#00e5ff',
        backgroundColor: (context) => {
          const ctx = context.chart.ctx;
          const gradient = ctx.createLinearGradient(0, 0, 0, 300);
          gradient.addColorStop(0, 'rgba(0, 229, 255, 0.2)');
          gradient.addColorStop(1, 'rgba(0, 229, 255, 0)');
          return gradient;
        },
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.4,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { display: false },
      y: { 
        grid: { color: 'rgba(255,255,255,0.05)' },
        ticks: { color: 'rgba(255,255,255,0.4)', font: { family: 'Share Tech Mono' } }
      }
    },
    animation: { duration: 0 }
  };

  const t = data?.trades?.[0];

  return (
    <div className="p-8 h-full flex flex-col gap-6">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-orbitron font-bold text-gray-100">Trade & Risk Desk</h2>
          <p className="text-sm text-gray-400 mt-1">Live equity curve and active exposure.</p>
        </div>
      </div>

      {/* Chart Panel */}
      <div className="glass-panel rounded-xl p-6 h-72">
        <Line data={chartData} options={chartOptions} />
      </div>

      {/* Active Trade Panel */}
      <div className="glass-panel rounded-xl p-8 flex-1">
        <h3 className="font-orbitron text-lg text-cyan-400 mb-6">Active Contract</h3>
        
        {t ? (
          <div className="flex flex-col md:flex-row gap-12">
            <div className="flex-1">
              <div className="flex items-center gap-4 mb-6">
                <span className="text-3xl font-orbitron font-bold">{t.symbol}</span>
                <span className={`px-3 py-1 rounded text-sm font-bold border ${t.direction === 'LONG' ? 'border-green-500 text-green-400 bg-green-500/10' : 'border-red-500 text-red-400 bg-red-500/10'}`}>
                  {t.direction}
                </span>
              </div>
              
              <div className="grid grid-cols-2 gap-8 font-mono text-sm">
                <div>
                  <div className="text-gray-500 mb-1">ENTRY PRICE</div>
                  <div className="text-xl">${t.entry?.toLocaleString() || 0}</div>
                </div>
                <div>
                  <div className="text-gray-500 mb-1">CURRENT PRICE</div>
                  <div className="text-xl text-cyan-400">${t.current?.toLocaleString() || 0}</div>
                </div>
              </div>
            </div>

            <div className="flex-1 border-l border-white/10 pl-12 flex flex-col justify-center gap-6">
              <div>
                <div className="flex justify-between font-mono text-sm mb-2">
                  <span className="text-green-400">TAKE PROFIT</span>
                  <span>${t.tp?.toLocaleString() || 0}</span>
                </div>
                <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-green-500 shadow-[0_0_10px_#00ff66]" 
                    style={{ width: `${Math.max(0, Math.min(100, (t.current-t.entry)/(t.tp-t.entry)*100))}%` }}
                  ></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between font-mono text-sm mb-2">
                  <span className="text-red-400">STOP LOSS</span>
                  <span>${t.sl?.toLocaleString() || 0}</span>
                </div>
                <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-red-500 shadow-[0_0_10px_#ff2a55]" 
                    style={{ width: `${Math.max(0, Math.min(100, (t.entry-t.current)/(t.entry-t.sl)*100))}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-gray-500 font-mono">
            No active positions.
          </div>
        )}
      </div>
    </div>
  );
}
