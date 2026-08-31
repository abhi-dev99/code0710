import React, { useState, useEffect } from 'react';
import { Activity, ShieldAlert, Cpu, Network } from 'lucide-react';

export default function App() {
  const [health, setHealth] = useState<any>(null);
  
  useEffect(() => {
    fetch('http://localhost:8000/api/health')
      .then(r => r.json())
      .then(data => setHealth(data))
      .catch(e => console.error("API error", e));
  }, []);

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
        <div className="col-span-2 bg-gray-900 border border-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-300 flex items-center gap-2">
            <Activity className="text-red-400" /> Live Transaction Stream
          </h2>
          <div className="h-96 bg-gray-950 rounded border border-gray-800 flex items-center justify-center text-gray-600 relative overflow-hidden">
            <div className="absolute inset-0 opacity-10 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-400 via-gray-900 to-gray-950"></div>
            <p className="z-10">[ WebSocket Stream Connecting... ]</p>
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
