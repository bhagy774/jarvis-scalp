import React, { useRef, useEffect, useState, useMemo, createRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Html, Line } from '@react-three/drei';
import * as THREE from 'three';
import { motion, AnimatePresence } from 'framer-motion';
import { useJarvisWS } from '../store/useJarvisWS';

// ─────────────────────────────────────────────────────────────────────────────
// System Architecture Data (mirrors actual jarvis system)
// ─────────────────────────────────────────────────────────────────────────────
const SYSTEM_NODES = [
  // 12 GPU Parts — arranged in a wide arc on the left
  { id: 'P1',  label: 'P1·Breakout',     part: 'Part1_Breakout',      x: -6.5, y:  3.5, z: 0, type: 'part',      color: '#00e5ff' },
  { id: 'P2',  label: 'P2·Neural',       part: 'Part2_Neural',        x: -6.5, y:  2.2, z: 0, type: 'part',      color: '#00e5ff' },
  { id: 'P3',  label: 'P3·Institutional',part: 'Part3_Institutional',  x: -6.5, y:  0.9, z: 0, type: 'part',      color: '#00e5ff' },
  { id: 'P4',  label: 'P4·Backtest',     part: 'Part4_Backtest',      x: -6.5, y: -0.4, z: 0, type: 'part',      color: '#00e5ff' },
  { id: 'P5',  label: 'P5·Fusion',       part: 'Part5_Fusion',        x: -6.5, y: -1.7, z: 0, type: 'part',      color: '#00e5ff' },
  { id: 'P6',  label: 'P6·BT',          part: 'Part6_Backtest',      x: -6.5, y: -3.0, z: 0, type: 'part',      color: '#00e5ff' },
  { id: 'P7',  label: 'P7·LiveData',    part: 'Part7_LiveData',      x:  6.5, y:  3.5, z: 0, type: 'part',      color: '#00e5ff' },
  { id: 'P8',  label: 'P8·Pattern',     part: 'Part8_Pattern',       x:  6.5, y:  2.2, z: 0, type: 'part',      color: '#00e5ff' },
  { id: 'P9',  label: 'P9·Adaptive',    part: 'Part9_Adaptive',      x:  6.5, y:  0.9, z: 0, type: 'part',      color: '#00e5ff' },
  { id: 'P10', label: 'P10·Exec',       part: 'Part10_Execution',    x:  6.5, y: -0.4, z: 0, type: 'part',      color: '#00e5ff' },
  { id: 'P11', label: 'P11·Confidence', part: 'Part11_Confidence',   x:  6.5, y: -1.7, z: 0, type: 'part',      color: '#00e5ff' },
  { id: 'P12', label: 'P12·Order',      part: 'Part12_Execution',    x:  6.5, y: -3.0, z: 0, type: 'part',      color: '#00e5ff' },

  // Core Pipeline
  { id: 'BUS',      label: 'Cognitive Bus',  part: null, x: 0,    y:  3.0, z: 0, type: 'bus',      color: '#a855f7' },
  { id: 'WATCHER',  label: 'Watcher AI',     part: null, x: 0,    y:  1.0, z: 0, type: 'watcher',  color: '#f59e0b' },
  { id: 'SPEC',     label: 'Specialist Pool',part: null, x: 0,    y: -0.8, z: 0, type: 'specialist',color: '#ec4899' },
  { id: 'CHAIRMAN', label: 'Chairman AI',    part: null, x: 0,    y: -2.5, z: 0, type: 'chairman', color: '#22c55e' },
];

// Connections: [from, to]
const CONNECTIONS = [
  // Parts → CognitiveBus
  ['P1','BUS'],['P2','BUS'],['P3','BUS'],['P4','BUS'],['P5','BUS'],['P6','BUS'],
  ['P7','BUS'],['P8','BUS'],['P9','BUS'],['P10','BUS'],['P11','BUS'],['P12','BUS'],
  // Pipeline
  ['BUS','WATCHER'],
  ['WATCHER','SPEC'],
  ['SPEC','CHAIRMAN'],
];

// ─────────────────────────────────────────────────────────────────────────────
// 3D Node (Drifting organically)
// ─────────────────────────────────────────────────────────────────────────────
function Node3D({ node, partData, nodeRefState }) {
  const groupRef = useRef();
  const outerRef = useRef();
  const innerRef = useRef();
  const ringRef = useRef();

  const dir = partData?.direction || 'NEUTRAL';
  let nodeColor = node.color;
  if (node.type === 'part') {
    nodeColor = dir === 'BULLISH' ? '#22c55e' : dir === 'BEARISH' ? '#ef4444' : '#00e5ff';
  }

  const col = useMemo(() => new THREE.Color(nodeColor), [nodeColor]);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    
    // Orbital & Organic Drift Position
    if (node.type === 'part' && nodeRefState.isOrbital) {
      // Advance angle
      nodeRefState.orbitAngle += nodeRefState.orbitSpeed * 0.02;
      
      const dx = Math.sin(t * 0.4 + nodeRefState.phaseX) * 1.0;
      const dy = Math.cos(t * 0.3 + nodeRefState.phaseY) * 1.5;
      const dz = Math.sin(t * 0.5 + nodeRefState.phaseZ) * 1.0;
      
      // Calculate planet position
      nodeRefState.pos.set(
        Math.cos(nodeRefState.orbitAngle) * nodeRefState.orbitRadius + dx,
        nodeRefState.baseY + dy,
        Math.sin(nodeRefState.orbitAngle) * nodeRefState.orbitRadius + dz
      );
    } else {
      const dy = Math.sin(t * 0.8 + nodeRefState.phaseY) * 0.3;
      nodeRefState.pos.set(
        nodeRefState.basePos.x,
        nodeRefState.basePos.y + dy,
        nodeRefState.basePos.z
      );
    }

    if (groupRef.current) {
      groupRef.current.position.copy(nodeRefState.pos);
    }
    
    // Rotations & Scale
    if (outerRef.current) {
      if (node.type === 'watcher' || node.type === 'specialist') {
        outerRef.current.rotation.x = t * 0.5;
        outerRef.current.rotation.y = t * 0.8;
      } else if (node.type === 'chairman') {
        outerRef.current.rotation.y = t * 0.3;
      } else if (node.type === 'bus') {
        outerRef.current.rotation.z = t * 0.2;
        outerRef.current.rotation.x = t * 0.4;
      }
    }
    
    if (innerRef.current) {
      if (node.type === 'part') {
        innerRef.current.scale.setScalar(1 + Math.sin(t * 3 + node.x) * 0.1);
        innerRef.current.rotation.y = t * 1.5;
        innerRef.current.rotation.x = t * 0.5;
      } else {
        innerRef.current.rotation.y = -t * 0.5;
        innerRef.current.rotation.x = -t * 0.3;
      }
    }

    if (ringRef.current) {
      ringRef.current.rotation.z = t * 1.5;
      ringRef.current.rotation.x = Math.PI / 2 + Math.sin(t) * 0.2;
    }
  });

  const size = node.type === 'bus' ? 0.5 : node.type === 'watcher' ? 0.35 : node.type === 'specialist' ? 0.4 : node.type === 'chairman' ? 0.45 : 0.22;

  return (
    <group ref={groupRef}>
      {/* Glow halo */}
      <mesh>
        <sphereGeometry args={[size * 1.8, 16, 16]} />
        <meshStandardMaterial color={col} emissive={col} emissiveIntensity={0.2} transparent opacity={0.1} />
      </mesh>

      {/* Main Geometry based on type */}
      {node.type === 'bus' && (
        <group>
          <mesh ref={outerRef}>
            <torusKnotGeometry args={[size, 0.08, 64, 16]} />
            <meshStandardMaterial color={col} emissive={col} emissiveIntensity={1} wireframe />
          </mesh>
          <mesh ref={innerRef}>
            <sphereGeometry args={[size * 0.6, 16, 16]} />
            <meshStandardMaterial color={col} emissive={col} emissiveIntensity={2} />
          </mesh>
        </group>
      )}

      {node.type === 'watcher' && (
        <group>
          <mesh ref={outerRef}>
            <dodecahedronGeometry args={[size, 0]} />
            <meshStandardMaterial color={col} emissive={col} emissiveIntensity={0.8} wireframe />
          </mesh>
          <mesh ref={innerRef}>
            <dodecahedronGeometry args={[size * 0.5, 0]} />
            <meshStandardMaterial color={col} emissive={col} emissiveIntensity={2.5} />
          </mesh>
        </group>
      )}

      {node.type === 'specialist' && (
        <group>
          <mesh ref={outerRef}>
            <icosahedronGeometry args={[size, 0]} />
            <meshStandardMaterial color={col} emissive={col} emissiveIntensity={0.8} wireframe />
          </mesh>
          <mesh ref={ringRef}>
            <torusGeometry args={[size * 1.3, 0.02, 16, 64]} />
            <meshStandardMaterial color={col} emissive={col} emissiveIntensity={2} />
          </mesh>
          <mesh ref={innerRef}>
            <icosahedronGeometry args={[size * 0.6, 0]} />
            <meshStandardMaterial color={col} emissive={col} emissiveIntensity={2} />
          </mesh>
        </group>
      )}

      {node.type === 'chairman' && (
        <group>
          <mesh ref={outerRef}>
            <octahedronGeometry args={[size * 1.2, 0]} />
            <meshStandardMaterial color={col} emissive={col} emissiveIntensity={1} wireframe />
          </mesh>
          <mesh ref={innerRef}>
            <octahedronGeometry args={[size * 0.7, 0]} />
            <meshStandardMaterial color={col} emissive={col} emissiveIntensity={3} />
          </mesh>
        </group>
      )}

      {node.type === 'part' && (
        <group>
          <mesh ref={outerRef}>
            <boxGeometry args={[size, size, size]} />
            <meshStandardMaterial color={col} emissive={col} emissiveIntensity={0.5} wireframe />
          </mesh>
          <mesh ref={innerRef}>
            <boxGeometry args={[size * 0.6, size * 0.6, size * 0.6]} />
            <meshStandardMaterial color={col} emissive={col} emissiveIntensity={2.5} />
          </mesh>
        </group>
      )}

      {/* HTML Label */}
      <Html center distanceFactor={12} style={{ pointerEvents: 'none', whiteSpace: 'nowrap' }}>
        <div style={{
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: node.type === 'part' ? '9px' : '10px',
          fontWeight: 700,
          color: nodeColor,
          textShadow: `0 0 10px ${nodeColor}`,
          background: 'rgba(3,4,7,0.85)',
          padding: '2px 6px',
          borderRadius: '4px',
          border: `1px solid ${nodeColor}40`,
          letterSpacing: '0.04em',
          marginTop: size * 60 + 12 + 'px',
        }}>
          {node.label}
          {node.type === 'part' && partData?.confidence > 0 && (
            <span style={{ color: 'rgba(255,255,255,0.5)', marginLeft: '4px', fontSize: '8px' }}>
              {partData.confidence.toFixed(0)}%
            </span>
          )}
        </div>
      </Html>
    </group>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Dynamic Connection Line + Packets (Follows drifting nodes)
// ─────────────────────────────────────────────────────────────────────────────
function Connection({ from, to, color, packetCount = 2, active = true, nodeRefs }) {
  const geoRef = useRef();
  
  // Create refs for packet meshes manually to avoid prop drilling in useFrame
  const packets = useRef(Array.from({ length: packetCount }).map((_, i) => ({
    offset: i / packetCount,
    speed: 0.2 + Math.random() * 0.2,
    meshRef: createRef(),
  })));

  const col = useMemo(() => new THREE.Color(color), [color]);

  useFrame((state) => {
    const fromState = nodeRefs.current[from];
    const toState = nodeRefs.current[to];
    if (!fromState || !toState) return;

    const fromPos = fromState.pos;
    const toPos = toState.pos;

    // Recalculate dynamic bezier curve
    const midX = (fromPos.x + toPos.x) / 2;
    const midY = (fromPos.y + toPos.y) / 2;
    const dist = fromPos.distanceTo(toPos);
    const offset = dist * 0.25;
    const controlPoint = new THREE.Vector3(midX, midY + offset, (fromPos.z + toPos.z) / 2 + offset);
    
    const curve = new THREE.QuadraticBezierCurve3(fromPos, controlPoint, toPos);
    
    // Update line geometry points
    if (geoRef.current) {
      geoRef.current.setFromPoints(curve.getPoints(20));
    }

    // Update packets
    const t = state.clock.elapsedTime;
    packets.current.forEach(p => {
      if (p.meshRef.current) {
        const pt = (t * p.speed + p.offset) % 1;
        const pos = curve.getPoint(pt);
        p.meshRef.current.position.copy(pos);
        p.meshRef.current.scale.setScalar(1 + Math.sin(pt * Math.PI * 10) * 0.4);
        p.meshRef.current.material.opacity = Math.sin(pt * Math.PI) * 0.9 + 0.1;
      }
    });
  });

  if (!active) return null;

  return (
    <group>
      <line>
        <bufferGeometry ref={geoRef} />
        <lineBasicMaterial color={col} transparent opacity={0.3} />
      </line>
      {packets.current.map((p, i) => (
        <mesh key={i} ref={p.meshRef}>
          <sphereGeometry args={[0.06, 8, 8]} />
          <meshStandardMaterial color={col} emissive={col} emissiveIntensity={5} transparent />
        </mesh>
      ))}
    </group>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Scene
// ─────────────────────────────────────────────────────────────────────────────
function JarvisSystemScene({ data }) {
  const parts = data?.parts || {};
  
  // Store node positions and orbital/drift phases
  const nodeRefs = useRef({});
  if (Object.keys(nodeRefs.current).length === 0) {
    let partIndex = 0;
    const totalParts = SYSTEM_NODES.filter(n => n.type === 'part').length;
    
    SYSTEM_NODES.forEach(n => {
      const isPart = n.type === 'part';
      // Orbital mechanics for parts
      const orbitAngle = isPart ? (partIndex / totalParts) * Math.PI * 2 : 0;
      const orbitRadius = isPart ? 5.5 + Math.random() * 2.5 : 0;
      const orbitSpeed = isPart ? (Math.random() * 0.5 + 0.2) * (Math.random() > 0.5 ? 1 : -1) : 0;
      const baseY = isPart ? (Math.random() * 6 - 3) : n.y;
      
      if (isPart) partIndex++;
      
      nodeRefs.current[n.id] = {
        basePos: new THREE.Vector3(n.x, n.y, n.z),
        pos: new THREE.Vector3(n.x, n.y, n.z),
        phaseX: Math.random() * Math.PI * 2,
        phaseY: Math.random() * Math.PI * 2,
        phaseZ: Math.random() * Math.PI * 2,
        isOrbital: isPart,
        orbitAngle,
        orbitRadius,
        orbitSpeed,
        baseY,
      };
    });
  }

  // Map connections to colors based on their layer
  const connColorMap = {
    'BUS': '#a855f7',
    'WATCHER': '#f59e0b',
    'SPEC': '#ec4899',
    'CHAIRMAN': '#22c55e',
  };

  return (
    <>
      <ambientLight intensity={0.05} />
      <pointLight position={[0, 5, 5]} intensity={1.5} color="#a855f7" />
      <pointLight position={[-5, 0, 5]} intensity={1} color="#00e5ff" />
      <pointLight position={[5, 0, 5]} intensity={1} color="#00e5ff" />
      <pointLight position={[0, -5, 5]} intensity={1} color="#22c55e" />

      {/* All nodes */}
      {SYSTEM_NODES.map(node => (
        <Node3D
          key={node.id}
          node={node}
          partData={node.part ? parts[node.part] : null}
          nodeRefState={nodeRefs.current[node.id]}
        />
      ))}

      {/* All connections with animated data packets */}
      {CONNECTIONS.map(([from, to]) => {
        const toNode = SYSTEM_NODES.find(n => n.id === to);
        let color = '#00e5ff';
        if (to === 'BUS') color = '#a855f7';
        if (to === 'WATCHER') color = '#f59e0b';
        if (to === 'SPEC') color = '#ec4899';
        if (to === 'CHAIRMAN') color = '#22c55e';
        return (
          <Connection
            key={`${from}-${to}`}
            from={from}
            to={to}
            color={color}
            packetCount={to === 'BUS' ? 3 : 2}
            active
            nodeRefs={nodeRefs}
          />
        );
      })}

      <OrbitControls
        enableZoom
        enablePan={false}
        autoRotate
        autoRotateSpeed={0.2}
        minDistance={5}
        maxDistance={20}
        target={[0, 0, 0]}
      />
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Right panel legend
// ─────────────────────────────────────────────────────────────────────────────
function PipelineStatus({ data }) {
  const parts = data?.parts || {};
  const pipeline = data?.pipeline || {};
  const stats = data?.stats || {};
  const pnl = stats.total_pnl || 0;

  const layers = [
    {
      label: '12 GPU ENGINE PARTS',
      color: '#00e5ff',
      desc: 'Part1-12: Neural/Breakout/Institutional/Pattern/Adaptive etc.',
      sub: `${Object.keys(parts).length} active · Pub to CognitiveBus THOUGHTS topic`,
      status: Object.keys(parts).length > 0 ? '●  ONLINE' : '○  OFFLINE',
    },
    {
      label: 'COGNITIVE BUS',
      color: '#a855f7',
      desc: 'Pub/Sub message bus — THOUGHTS · HEALTH · SIGNALS',
      sub: `Last packet: ${pipeline.last_packet_ts ? new Date(pipeline.last_packet_ts).toLocaleTimeString('en-US', { hour12: false }) : '--:--:--'}`,
      status: pipeline.watcher_active ? '●  ACTIVE' : '○  STANDBY',
    },
    {
      label: 'WATCHER AI',
      color: '#f59e0b',
      desc: 'Parses THOUGHTS → Smart Context Packet for Specialist Pool',
      sub: 'Monitors: Part2,3,5,8,11 THOUGHTS + HEALTH + SIGNALS',
      status: pipeline.watcher_active ? '●  MONITORING' : '○  IDLE',
    },
    {
      label: 'SPECIALIST POOL',
      color: '#ec4899',
      desc: 'Analyst (deepseek-r1:14b) + Validator + Risk Officer (qwen2.5:14b) — parallel',
      sub: `Votes: ${Object.keys(pipeline.specialist_opinions || {}).length}/3 received`,
      status: Object.keys(pipeline.specialist_opinions || {}).length > 0 ? '●  IN SESSION' : '○  AWAITING',
    },
    {
      label: 'CHAIRMAN AI',
      color: '#22c55e',
      desc: 'qwen2.5:14b — Synthesizes 3 votes → [CONSENSUS_EXECUTE/REJECT]',
      sub: pipeline.chairman_summary ? pipeline.chairman_summary.substring(0, 60) + '...' : 'Awaiting board opinions...',
      status: pipeline.chairman_summary?.includes('CONSENSUS_EXECUTE') ? '●  EXECUTE' : pipeline.chairman_summary ? '●  REJECT' : '○  PENDING',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', height: '100%', overflowY: 'auto' }}>
      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '4px' }}>
        {[
          { label: 'NET P&L', value: `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(0)}`, color: pnl >= 0 ? '#22c55e' : '#ef4444' },
          { label: 'WIN RATE', value: `${(stats.win_rate || 0).toFixed(1)}%`, color: '#00e5ff' },
          { label: 'WINS', value: stats.wins || 0, color: '#22c55e' },
          { label: 'LOSSES', value: stats.losses || 0, color: '#ef4444' },
        ].map(s => (
          <div key={s.label} style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.07)',
            borderRadius: '10px',
            padding: '10px',
            textAlign: 'center',
          }}>
            <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '9px', color: '#475569', letterSpacing: '0.1em', marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'Orbitron, monospace', fontSize: '18px', fontWeight: 700, color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Pipeline layers */}
      {layers.map((layer, i) => (
        <motion.div
          key={layer.label}
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.1 }}
          style={{
            background: `${layer.color}08`,
            border: `1px solid ${layer.color}25`,
            borderLeft: `3px solid ${layer.color}`,
            borderRadius: '10px',
            padding: '10px 12px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '10px', fontWeight: 700, color: layer.color, letterSpacing: '0.05em' }}>
              {layer.label}
            </span>
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '9px', color: layer.status.includes('●') ? layer.color : '#475569' }}>
              {layer.status}
            </span>
          </div>
          <div style={{ fontFamily: 'Inter, sans-serif', fontSize: '10px', color: '#64748b', lineHeight: 1.4, marginBottom: '4px' }}>
            {layer.desc}
          </div>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '9px', color: '#334155', background: 'rgba(0,0,0,0.3)', padding: '3px 6px', borderRadius: '4px' }}>
            {layer.sub}
          </div>
        </motion.div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Export
// ─────────────────────────────────────────────────────────────────────────────
export default function CommandCenter3D({ data, connected }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', height: '100%', padding: '16px', gap: '16px' }}>

      {/* ── 3D JARVIS System Architecture ── */}
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        style={{
          position: 'relative',
          background: 'rgba(3,4,7,0.9)',
          border: '1px solid rgba(168,85,247,0.2)',
          borderRadius: '20px',
          overflow: 'hidden',
          boxShadow: '0 0 60px rgba(168,85,247,0.06)',
        }}
      >
        {/* Top label */}
        <div style={{
          position: 'absolute', top: '16px', left: '50%', transform: 'translateX(-50%)',
          zIndex: 10, textAlign: 'center', pointerEvents: 'none',
          background: 'rgba(3,4,7,0.8)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '8px',
          padding: '6px 16px',
        }}>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '10px', color: '#475569', letterSpacing: '0.3em', marginBottom: '2px' }}>
            LIVE SYSTEM ARCHITECTURE
          </div>
          <div style={{ fontFamily: 'Orbitron, monospace', fontSize: '13px', fontWeight: 700, color: '#a855f7', letterSpacing: '0.1em', textShadow: '0 0 15px rgba(168,85,247,0.6)' }}>
            JARVIS DATA FLOW
          </div>
        </div>

        {/* Legend bottom */}
        <div style={{
          position: 'absolute', bottom: '16px', left: '50%', transform: 'translateX(-50%)',
          zIndex: 10, display: 'flex', gap: '16px', pointerEvents: 'none',
          background: 'rgba(3,4,7,0.8)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: '8px',
          padding: '6px 16px',
          whiteSpace: 'nowrap',
        }}>
          {[
            { color: '#00e5ff', label: 'GPU Parts (12)' },
            { color: '#a855f7', label: '→ Cognitive Bus' },
            { color: '#f59e0b', label: '→ Watcher AI' },
            { color: '#ec4899', label: '→ Specialist Pool' },
            { color: '#22c55e', label: '→ Chairman' },
          ].map(l => (
            <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: l.color, boxShadow: `0 0 6px ${l.color}` }} />
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '9px', color: '#64748b' }}>{l.label}</span>
            </div>
          ))}
        </div>

        {/* 3D Canvas */}
        <Canvas
          camera={{ position: [0, 0, 14], fov: 50 }}
          style={{ width: '100%', height: '100%' }}
          gl={{ antialias: true, alpha: true }}
        >
          <JarvisSystemScene data={data} />
        </Canvas>

        {/* Scan-line overlay */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'linear-gradient(to bottom, transparent 50%, rgba(168,85,247,0.015) 50%)',
          backgroundSize: '100% 4px',
        }} />
      </motion.div>

      {/* ── Right Panel: Pipeline Status ── */}
      <motion.div
        initial={{ opacity: 0, x: 30 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        style={{
          background: 'rgba(8,12,20,0.7)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: '20px',
          padding: '16px',
          backdropFilter: 'blur(20px)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '10px', color: '#475569', letterSpacing: '0.2em', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: connected ? '#22c55e' : '#ef4444', boxShadow: `0 0 8px ${connected ? '#22c55e' : '#ef4444'}` }} />
          PIPELINE STATUS
        </div>
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <PipelineStatus data={data} />
        </div>
      </motion.div>
    </div>
  );
}
