import React, { useState, useEffect, useRef } from 'react';
import { Activity, ShieldAlert, Cpu, Network } from 'lucide-react';

export default function App() {
  const [health, setHealth] = useState<any>(null);
  const [stream, setStream] = useState<string[]>([
    '[ System Initialized. Awaiting live-fire telemetry... ]'
  ]);
  const wsRef = useRef<WebSocket | null>(null);
  const streamEndRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    fetch('http://localhost:8000/api/health')
      .then(r => r.json())
      .then(data => setHealth(data))
      .catch(e => console.error("API error", e));

    const connectWs = () => {
      const ws = new WebSocket('ws://localhost:8000/ws/stream');
      
      ws.onopen = () => {
        setStream(prev => [...prev, '[ WebSocket Connected: 🟢 ]']);
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'detect') {
            const logs = data.results.map((r: any) => 
              `> TXN: ${r.txn_id} | FUSED: ${r.fused_score} | FLAG: ${r.flagged ? '🟥 MULE' : '🟩 BENIGN'}`
            );
            setStream(prev => {
                const updated = [...prev, ...logs];
                // Keep only last 100 logs to prevent lag
                return updated.slice(-100);
            });
          } else if (data.type === 'round_complete') {
            setStream(prev => [...prev, `[ Round Complete. Benign: ${data.summary.benign_total}, Vectors: ${data.summary.vectors_run} ]`]);
          }
        } catch (e) {
          console.error('WS Parse Error', e);
        }
      };
      
      ws.onclose = () => {
        setStream(prev => [...prev, '[ WebSocket Disconnected: 🔴 Reconnecting in 3s... ]']);
        setTimeout(connectWs, 3000);
      };
      
      wsRef.current = ws;
    };
    
    connectWs();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Auto-scroll to bottom of stream
  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [stream]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-8 font-mono">
      <header className="mb-8 border-b border-gray-800 pb-4 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tighter text-blue-400 flex items-center gap-2">
            <ShieldAlert size={28} /> AEGIS LIVEFIRE ARENA
          </h1>
          <p className="text-gray-500 mt-1">Adversarial Co-Evolution Payment Security</p>
        </div>
        <div className="flex gap-4">
          <div className="bg-gray-900 px-4 py-2 rounded text-sm border border-gray-800">
            <span className="text-gray-400">STATUS: </span>
            <span className="text-emerald-400 font-bold">ONLINE</span>
          </div>
        </div>
      </header>
      
      <main className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="col-span-2 bg-gray-900 border border-gray-800 rounded-lg p-6 flex flex-col">
          <h2 className="text-xl font-semibold mb-4 text-gray-300 flex items-center gap-2">
            <Activity className="text-red-400" /> Live Transaction Stream
          </h2>
          <div className="flex-1 min-h-[400px] max-h-[600px] bg-gray-950 rounded border border-gray-800 p-4 relative overflow-y-auto font-mono text-sm">
            <div className="absolute inset-0 opacity-5 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-400 via-gray-900 to-gray-950 pointer-events-none"></div>
            
            <div className="relative z-10 flex flex-col gap-1">
              {stream.map((log, i) => (
                <div key={i} className={`${log.includes('🟥') ? 'text-red-400' : log.includes('🟩') ? 'text-emerald-400' : 'text-gray-500'}`}>
                  {log}
                </div>
              ))}
              <div ref={streamEndRef} />
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-300 flex items-center gap-2">
              <Cpu className="text-blue-400" /> System Diagnostics
            </h2>
            {health ? (
              <ul className="space-y-3 text-sm">
                <li className="flex justify-between border-b border-gray-800 pb-2"><span className="text-gray-500">Rounds Run</span> <span className="font-bold">{health.rounds_run}</span></li>
                <li className="flex justify-between border-b border-gray-800 pb-2"><span className="text-gray-500">Ensemble Loaded</span> <span className={health.ensemble_ready ? "text-emerald-400 font-bold" : "text-red-400 font-bold"}>{health.ensemble_ready ? "YES" : "NO"}</span></li>
                <li className="flex justify-between border-b border-gray-800 pb-2"><span className="text-gray-500">LLM Configured</span> <span className="font-bold text-amber-400">{health.llm_configured ? "YES" : "TEMPLATE-ONLY"}</span></li>
                <li className="flex justify-between"><span className="text-gray-500">p50 Latency</span> <span className="font-bold">{health.detect_latency_ms?.p50_ms || "--"} ms</span></li>
              </ul>
            ) : (
              <p className="text-gray-500 text-sm">Loading telemetry...</p>
            )}
          </div>
          
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
             <h2 className="text-xl font-semibold mb-4 text-gray-300 flex items-center gap-2">
              <Network className="text-purple-400" /> Intelligence Tiers
            </h2>
            <ul className="space-y-3 text-sm text-gray-400">
              <li className="flex items-center justify-between"><span>Graph Core (NetworkX)</span> <span className="text-emerald-400">Active</span></li>
              <li className="flex items-center justify-between"><span>Semantic Classifier (NLP)</span> <span className="text-emerald-400">Active</span></li>
              <li className="flex items-center justify-between"><span>Ensemble (XGBoost)</span> <span className="text-emerald-400">Active</span></li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}
