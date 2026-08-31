import React, { useState, useEffect, useRef } from 'react';
import { Activity, ShieldAlert, Cpu, Network, Server, Zap, CheckCircle2, AlertOctagon } from 'lucide-react';

export default function App() {
  const [health, setHealth] = useState<any>(null);
  const [stream, setStream] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const streamEndRef = useRef<HTMLDivElement>(null);
  
  const [status, setStatus] = useState<'CONNECTING' | 'ONLINE' | 'OFFLINE'>('CONNECTING');
  
  useEffect(() => {
    fetch('http://localhost:8000/api/health')
      .then(r => r.json())
      .then(data => setHealth(data))
      .catch(e => console.error("API error", e));

    const connectWs = () => {
      const ws = new WebSocket('ws://localhost:8000/ws/stream');
      
      ws.onopen = () => {
        setStatus('ONLINE');
        setStream(prev => [...prev, { type: 'system', msg: 'Secure WebSocket uplink established.' }]);
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'detect') {
            setStream(prev => {
                const updated = [...prev, ...data.results];
                return updated.slice(-100);
            });
          } else if (data.type === 'round_complete') {
            setStream(prev => [...prev, { type: 'system', msg: `Round Complete. Benign: ${data.summary.benign_total}, Vectors: ${data.summary.vectors_run}` }]);
          }
        } catch (e) {
          console.error('WS Parse Error', e);
        }
      };
      
      ws.onclose = () => {
        setStatus('OFFLINE');
        setStream(prev => [...prev, { type: 'system', msg: 'Uplink lost. Re-establishing connection...' }]);
        setTimeout(connectWs, 3000);
      };
      
      wsRef.current = ws;
    };
    
    connectWs();
    
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [stream]);

  return (
    <div className="min-h-screen p-4 md:p-8 flex flex-col gap-8 max-w-7xl mx-auto">
      {/* Header */}
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between glass-panel px-8 py-6 rounded-2xl gap-4">
        <div className="flex items-center gap-5">
          <div className="p-3 bg-blue-500/10 rounded-2xl border border-blue-500/20">
            <ShieldAlert className="text-blue-400" size={36} />
          </div>
          <div>
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-gradient-blue mb-1">
              AEGIS LIVEFIRE ARENA
            </h1>
            <p className="text-slate-400 text-sm font-medium tracking-wide uppercase">Adversarial Co-Evolution Payment Security</p>
          </div>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3 px-5 py-2.5 glass-panel-light rounded-full text-sm font-semibold tracking-wide">
            <span className="text-slate-500 uppercase text-xs font-bold">Uplink Status</span>
            {status === 'ONLINE' ? (
              <span className="text-emerald-400 flex items-center gap-2">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                </span>
                SECURE
              </span>
            ) : status === 'OFFLINE' ? (
              <span className="text-rose-400 flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-500"></span> OFFLINE
              </span>
            ) : (
              <span className="text-amber-400 flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500 animate-pulse"></span> CONNECTING
              </span>
            )}
          </div>
        </div>
      </header>
      
      <main className="grid grid-cols-1 lg:grid-cols-3 gap-8 h-full">
        {/* Main Feed Column */}
        <div className="lg:col-span-2 flex flex-col h-full">
          <div className="glass-panel rounded-2xl p-6 glow-border flex flex-col h-[750px]">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-slate-100 flex items-center gap-3">
                <Activity className="text-blue-400" />
                Live Telemetry Feed
              </h2>
              <div className="flex gap-2">
                <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-xs font-bold rounded-full border border-emerald-500/20 flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  LIVE STREAM
                </span>
              </div>
            </div>
            
            <div className="flex-1 bg-[#090b14]/80 rounded-xl border border-slate-800/60 p-5 relative overflow-y-auto font-mono text-sm shadow-inner">
              <div className="flex flex-col gap-2.5">
                {stream.map((log, i) => (
                  <div key={i} className="animate-fade-slide">
                    {log.type === 'system' ? (
                      <div className="text-slate-500 italic flex items-center gap-2 border-l-2 border-slate-700/50 pl-4 py-1.5 bg-slate-800/10 rounded-r">
                        <Server size={14} /> {log.msg}
                      </div>
                    ) : (
                      <div className={`flex flex-col md:flex-row md:items-center gap-3 p-3 rounded-lg border transition-all ${log.flagged ? 'bg-rose-500/10 border-rose-500/30 text-rose-100 shadow-[0_0_15px_rgba(244,63,94,0.1)]' : 'bg-emerald-500/5 border-emerald-500/20 text-emerald-100'}`}>
                        <div className="flex items-center gap-3 w-full md:w-auto md:min-w-[120px]">
                            {log.flagged ? <AlertOctagon size={18} className="text-rose-500 shrink-0" /> : <CheckCircle2 size={18} className="text-emerald-500 shrink-0" />}
                            <span className="font-bold tracking-wider">{log.flagged ? 'MULE' : 'BENIGN'}</span>
                        </div>
                        <div className="flex-1 grid grid-cols-2 md:grid-cols-2 gap-4 items-center text-xs md:text-sm">
                          <span className="text-slate-400">TXN: <span className="text-slate-200">{log.txn_id}</span></span>
                          <span className="text-slate-400 flex items-center gap-2">SCORE: <span className={`px-2 py-0.5 rounded ${log.flagged ? 'bg-rose-500/20 text-rose-300 font-bold' : 'bg-emerald-500/10 text-emerald-400'}`}>{log.fused_score.toFixed(4)}</span></span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                <div ref={streamEndRef} />
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-8 flex flex-col">
          <div className="glass-panel rounded-2xl p-6 shadow-lg">
            <h2 className="text-xl font-bold mb-6 text-slate-100 flex items-center gap-3">
              <Cpu className="text-purple-400" />
              Engine Diagnostics
            </h2>
            {health ? (
              <div className="space-y-3">
                <div className="glass-panel-light rounded-xl p-4 flex justify-between items-center transition-all hover:bg-slate-800/40">
                  <span className="text-slate-400 text-sm font-medium">Rounds Run</span>
                  <span className="text-2xl font-bold text-slate-100 tracking-tight">{health.rounds_run}</span>
                </div>
                <div className="glass-panel-light rounded-xl p-4 flex justify-between items-center transition-all hover:bg-slate-800/40">
                  <span className="text-slate-400 text-sm font-medium">Ensemble Matrix</span>
                  <span className={`text-xs font-bold px-3 py-1.5 rounded-full tracking-wide ${health.ensemble_ready ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.15)]" : "bg-rose-500/20 text-rose-400 border border-rose-500/30"}`}>
                    {health.ensemble_ready ? "ACTIVE" : "OFFLINE"}
                  </span>
                </div>
                <div className="glass-panel-light rounded-xl p-4 flex justify-between items-center transition-all hover:bg-slate-800/40">
                  <span className="text-slate-400 text-sm font-medium">Red Agent LLM</span>
                  <span className="text-xs font-bold px-3 py-1.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 tracking-wide">
                    {health.llm_configured ? "CONNECTED" : "TEMPLATE MODE"}
                  </span>
                </div>
                <div className="glass-panel-light rounded-xl p-4 flex justify-between items-center transition-all hover:bg-slate-800/40">
                  <span className="text-slate-400 text-sm font-medium">p50 Inference</span>
                  <span className="text-lg font-bold text-blue-400 flex items-center gap-1.5">
                    <Zap size={18} className="text-blue-500" /> {health.detect_latency_ms?.p50_ms || "--"} ms
                  </span>
                </div>
              </div>
            ) : (
              <div className="animate-pulse space-y-3">
                {[1, 2, 3, 4].map(i => <div key={i} className="h-[72px] bg-slate-800/40 rounded-xl border border-slate-700/30"></div>)}
              </div>
            )}
          </div>
          
          <div className="glass-panel rounded-2xl p-6 glow-border flex-1 shadow-lg">
             <h2 className="text-xl font-bold mb-6 text-slate-100 flex items-center gap-3">
              <Network className="text-cyan-400" />
              Defense Topology
            </h2>
            <div className="space-y-4">
              {[
                { name: "Graph Centrality Tier", sub: "NetworkX", active: true },
                { name: "Semantic Classifier", sub: "TF-IDF / NLP", active: true },
                { name: "Ensemble Fusion", sub: "XGBoost", active: true }
              ].map((tier, i) => (
                <div key={i} className="glass-panel-light rounded-xl p-4 flex items-center justify-between border-l-4 border-l-cyan-400/80 transition-all hover:bg-slate-800/40 hover:border-l-cyan-400">
                  <div>
                    <div className="font-semibold text-slate-200 tracking-wide">{tier.name}</div>
                    <div className="text-xs text-slate-500 mt-1 font-mono">{tier.sub}</div>
                  </div>
                  <div className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500 shadow-[0_0_8px_rgba(34,211,238,0.8)]"></span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
