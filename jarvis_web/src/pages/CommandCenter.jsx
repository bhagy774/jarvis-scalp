import { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Environment, Sphere, Torus, Points, PointMaterial } from '@react-three/drei';
import * as THREE from 'three';
import { motion } from 'framer-motion';
import { TrendingUp, Percent, DollarSign } from 'lucide-react';

function BrainCore() {
  const meshRef = useRef();
  
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = state.clock.elapsedTime * 0.2;
      meshRef.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.5) * 0.1;
    }
  });

  return (
    <group ref={meshRef}>
      {/* Inner glowing sphere */}
      <Sphere args={[1.5, 32, 32]}>
        <meshStandardMaterial 
          color="#00e5ff" 
          emissive="#00e5ff" 
          emissiveIntensity={2} 
          wireframe 
          transparent 
          opacity={0.3} 
        />
      </Sphere>
      
      {/* Outer data rings */}
      <Torus args={[2.5, 0.02, 16, 100]} rotation={[Math.PI/2, 0, 0]}>
        <meshStandardMaterial color="#00e5ff" emissive="#00e5ff" emissiveIntensity={1} />
      </Torus>
      <Torus args={[2.8, 0.01, 16, 100]} rotation={[Math.PI/2, 0, 0]}>
        <meshStandardMaterial color="#b400ff" emissive="#b400ff" emissiveIntensity={0.5} transparent opacity={0.5} />
      </Torus>
    </group>
  );
}

function DataParticles() {
  const ref = useRef();
  const sphere = new Float32Array(2000 * 3);
  for(let i=0; i<2000*3; i+=3) {
    const r = 4 + Math.random() * 2;
    const theta = 2 * Math.PI * Math.random();
    const phi = Math.acos(2 * Math.random() - 1);
    sphere[i] = r * Math.sin(phi) * Math.cos(theta);
    sphere[i+1] = r * Math.sin(phi) * Math.sin(theta);
    sphere[i+2] = r * Math.cos(phi);
  }

  useFrame((state, delta) => {
    ref.current.rotation.x -= delta / 10;
    ref.current.rotation.y -= delta / 15;
  });

  return (
    <group rotation={[0, 0, Math.PI / 4]}>
      <Points ref={ref} positions={sphere} stride={3} frustumCulled={false}>
        <PointMaterial transparent color="#00e5ff" size={0.02} sizeAttenuation={true} depthWrite={false} />
      </Points>
    </group>
  );
}

export default function CommandCenter({ data }) {
  const getSignal = () => {
    if (!data.parts) return { text: 'WAITING', color: 'text-gray-400', glow: '' };
    const votes = Object.values(data.parts).map(v => v.direction);
    const bull = votes.filter(v => v === 'BULLISH').length;
    const bear = votes.filter(v => v === 'BEARISH').length;
    
    if (bull >= 5) return { text: 'STRONG BUY', color: 'text-green-400', glow: 'glow-green' };
    if (bear >= 5) return { text: 'STRONG SELL', color: 'text-red-400', glow: 'glow-red' };
    return { text: 'NEUTRAL', color: 'text-yellow-400', glow: '' };
  };

  const signal = getSignal();
  const t = data.trades?.[0] || {};
  const pnl = t.pnl || 0;

  return (
    <div className="h-full w-full flex flex-col p-8 relative">
      {/* 3D Canvas Background for this page */}
      <div className="absolute inset-0 z-0">
        <Canvas camera={{ position: [0, 2, 8], fov: 45 }}>
          <ambientLight intensity={0.2} />
          <pointLight position={[10, 10, 10]} intensity={1} color="#00e5ff" />
          <BrainCore />
          <DataParticles />
          <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.5} />
        </Canvas>
      </div>

      {/* Floating UI */}
      <div className="z-10 flex-1 flex flex-col justify-end">
        <div className="grid grid-cols-3 gap-6">
          
          {/* Card 1: Signal */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className={`glass-panel rounded-xl p-6 relative overflow-hidden ${signal.glow}`}
          >
            <div className="flex items-center gap-3 text-gray-400 mb-2">
              <TrendingUp size={16} />
              <span className="text-sm font-medium">Active Signal</span>
            </div>
            <div className={`font-orbitron text-3xl font-bold tracking-wider ${signal.color}`}>
              {signal.text}
            </div>
            {/* Sparkline decoration */}
            <svg className="absolute bottom-0 left-0 w-full h-12 opacity-30" preserveAspectRatio="none" viewBox="0 0 100 100">
              <path d="M0,100 L0,80 Q25,90 50,50 T100,20 L100,100 Z" fill="url(#grad1)"></path>
              <defs>
                <linearGradient id="grad1" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="currentColor" stopOpacity="1" />
                  <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
                </linearGradient>
              </defs>
            </svg>
          </motion.div>

          {/* Card 2: Win Rate */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-panel rounded-xl p-6"
          >
            <div className="flex items-center gap-3 text-gray-400 mb-2">
              <Percent size={16} />
              <span className="text-sm font-medium">Win Rate</span>
            </div>
            <div className="font-orbitron text-3xl font-bold tracking-wider text-cyan-400">
              {data.stats?.win_rate?.toFixed(1) || 0}%
            </div>
            <div className="text-xs text-gray-500 mt-1 font-mono">
              W: {data.stats?.wins || 0} / L: {data.stats?.losses || 0}
            </div>
          </motion.div>

          {/* Card 3: PnL */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-panel rounded-xl p-6"
          >
            <div className="flex items-center gap-3 text-gray-400 mb-2">
              <DollarSign size={16} />
              <span className="text-sm font-medium">Current Trade PnL</span>
            </div>
            <div className={`font-orbitron text-3xl font-bold tracking-wider ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {pnl >= 0 ? '+' : '-'}${Math.abs(pnl).toFixed(2)}
            </div>
            <div className="text-xs text-gray-500 mt-1 font-mono">
              Entry: ${t.entry || 0}
            </div>
          </motion.div>

        </div>
      </div>
    </div>
  );
}
