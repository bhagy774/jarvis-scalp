import { useState, useRef, useEffect } from 'react';
import { Send, Terminal } from 'lucide-react';

export default function LogsChat({ data }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'JARVIS Online. Awaiting your command, sir.' }
  ]);
  const [input, setInput] = useState('');
  const chatEndRef = useRef(null);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    // Optimistic UI update
    setMessages(prev => [...prev, { role: 'user', content: input }]);
    setInput('');
    
    // Simulate API call to jarvis_hud_server for chat (which we built previously)
    fetch('http://localhost:7788/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: input })
    })
    .then(res => res.json())
    .then(data => {
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
    })
    .catch(err => {
      setMessages(prev => [...prev, { role: 'assistant', content: '[Error: Connection to AI core lost]' }]);
    });
  };

  // Compile all thoughts into a linear log
  const allLogs = Object.entries(data?.parts || {}).map(([name, p]) => ({
    name: name.replace('Part', 'P'),
    raw: p.raw,
    ts: p.ts || Date.now()
  })).sort((a, b) => b.ts - a.ts).slice(0, 50);

  return (
    <div className="h-full flex">
      {/* Left: System Logs */}
      <div className="w-1/2 border-r border-white/5 p-6 flex flex-col">
        <div className="flex items-center gap-3 mb-6 text-cyan-400">
          <Terminal size={20} />
          <h2 className="font-orbitron font-bold">System Telemetry</h2>
        </div>
        
        <div className="flex-1 glass-panel rounded-xl p-4 overflow-y-auto font-mono text-[11px] leading-relaxed flex flex-col gap-3">
          {allLogs.map((log, i) => (
            <div key={i} className="border-l-2 border-cyan-500/50 pl-3 py-1">
              <span className="text-gray-500 mr-2">[{new Date(log.ts).toLocaleTimeString()}]</span>
              <span className="text-cyan-400 font-bold mr-2">{log.name}</span>
              <span className="text-gray-300">{log.raw}</span>
            </div>
          ))}
          {allLogs.length === 0 && (
            <div className="text-gray-500">Waiting for system telemetry...</div>
          )}
        </div>
      </div>

      {/* Right: Chatbot */}
      <div className="w-1/2 p-6 flex flex-col">
        <div className="flex items-center gap-3 mb-6 text-purple-400">
          <div className="w-2 h-2 rounded-full bg-purple-500 shadow-[0_0_10px_#b400ff] animate-pulse" />
          <h2 className="font-orbitron font-bold">Direct Override Chat</h2>
        </div>
        
        <div className="flex-1 glass-panel rounded-xl flex flex-col overflow-hidden">
          {/* Messages Area */}
          <div className="flex-1 p-6 overflow-y-auto flex flex-col gap-6">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-2xl px-5 py-3 ${
                  msg.role === 'user' 
                    ? 'bg-cyan-500/20 text-cyan-50 border border-cyan-500/30' 
                    : 'bg-white/5 text-gray-200 border border-white/10'
                }`}>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
          
          {/* Input Area */}
          <div className="p-4 border-t border-white/5 bg-black/20">
            <form onSubmit={handleSend} className="relative">
              <input 
                type="text" 
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Ask JARVIS..."
                className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-4 pr-12 text-sm text-white focus:outline-none focus:border-cyan-500/50 transition-colors"
              />
              <button 
                type="submit"
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-gray-400 hover:text-cyan-400 transition-colors"
              >
                <Send size={18} />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
