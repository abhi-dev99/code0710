import React, { useState, useEffect, useRef } from 'react';
import { Activity, ShieldAlert, BarChart2, Server, Play, Crosshair, AlertTriangle, Fingerprint, Database, GitBranch } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid, Legend } from 'recharts';

const API_BASE = 'http://localhost:8000';
const WS_BASE = 'ws://localhost:8000';

export default function App() {
  const [activeTab, setActiveTab] = useState<'feed' | 'analytics' | 'simulation'>('feed');
  const [health, setHealth] = useState<any>(null);
  
  // Data States
  const [stream, setStream] = useState<any[]>([]);
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [shapData, setShapData] = useState<{name: string, value: number}[]>([]);
  const [distribution, setDistribution] = useState(
    Array.from({length: 10}, (_, i) => ({ 
      bucket: `${(i/10).toFixed(1)}`, 
      benign: 0, 
      fraud: 0 
    }))
  );
  const [availableVectors, setAvailableVectors] = useState<any[]>([]);
  
  // Simulation Controls
  const [simConfig, setSimConfig] = useState({
    n_benign: 500,
    use_llm: true,
    generations: 3,
    squad_size: 5
  });
  const [isSimulating, setIsSimulating] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Fetch initial health and vectors
    fetch(`${API_BASE}/api/health`).then(r => r.json()).then(setHealth).catch(console.error);
    fetch(`${API_BASE}/api/vectors`).then(r => r.json()).then(data => setAvailableVectors(data.vectors || [])).catch(console.error);

    const connectWs = () => {
      const ws = new WebSocket(`${WS_BASE}/ws/stream`);
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'detect') {
            setStream(prev => [...prev, ...data.results].slice(-50)); // keep last 50
            
            // Bucket for distribution & anomalies
            setDistribution(prev => {
              const next = [...prev];
              data.results.forEach((res: any) => {
                const idx = Math.min(Math.floor(res.fused_score * 10), 9);
                if (res.flagged) next[idx].fraud += 1;
                else next[idx].benign += 1;
              });
              return next;
            });
            
            const newAnomalies = data.results.filter((r: any) => r.fused_score > 0.8);
            if (newAnomalies.length > 0) {
              setAnomalies(prev => [...newAnomalies, ...prev].slice(0, 20));
            }
            
          } else if (data.type === 'round_complete') {
            if (data.summary?.shap_why) {
              // Parse shap string: "feature (shap=1.23); ..."
              const parsed = data.summary.shap_why.split(';').map((part: string) => {
                const match = part.match(/(.+) \(shap=([\d.]+)\)/);
                return match ? { name: match[1].trim(), value: parseFloat(match[2]) } : null;
              }).filter(Boolean);
              setShapData(parsed);
            }
            fetch(`${API_BASE}/api/health`).then(r => r.json()).then(setHealth).catch(console.error);
            setIsSimulating(false);
          }
        } catch (e) {
          console.error(e);
        }
      };
      
      ws.onclose = () => setTimeout(connectWs, 3000);
      wsRef.current = ws;
    };
    
    connectWs();
    return () => { if (wsRef.current) wsRef.current.close(); };
  }, []);

  const runSimulation = async (type: 'round' | 'tournament') => {
    setIsSimulating(true);
    try {
      await fetch(`${API_BASE}/api/${type}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(simConfig)
      });
    } catch (e) {
      console.error(e);
      setIsSimulating(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-[#E5E5E5] flex flex-col font-sans">
      {/* Top Navbar / Macro Telemetry */}
      <header className="border-b border-[#171717] bg-[#0A0A0A] px-6 py-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="flex items-center gap-3">
          <ShieldAlert size={24} className="text-white" />
          <h1 className="text-xl font-semibold tracking-tight text-white">AEGIS // MASTER</h1>
        </div>
        
        {health && (
          <div className="flex gap-8 text-sm">
            <div className="flex flex-col">
              <span className="text-[#737373] uppercase text-xs font-semibold tracking-wider">Total Scanned</span>
              <span className="font-mono text-white text-base">{health.rounds_run * 1000}+ TXNs</span>
            </div>
            <div className="flex flex-col">
              <span className="text-[#737373] uppercase text-xs font-semibold tracking-wider">p50 Latency</span>
              <span className="font-mono text-white text-base">{health.detect_latency_ms?.p50_ms || '--'} ms</span>
            </div>
            <div className="flex flex-col">
              <span className="text-[#737373] uppercase text-xs font-semibold tracking-wider">Ensemble Status</span>
              <span className="text-white text-base flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${health.ensemble_ready ? 'bg-white' : 'bg-[#737373]'}`} />
                {health.ensemble_ready ? 'Active' : 'Offline'}
              </span>
            </div>
          </div>
        )}
      </header>

      {/* Tabs */}
      <div className="px-6 pt-6 flex gap-6 border-b border-[#171717] bg-black">
        {[
          { id: 'feed', label: 'Anomaly Ledger', icon: Activity },
          { id: 'analytics', label: 'Model Observability', icon: BarChart2 },
          { id: 'simulation', label: 'Tactical Controls', icon: Crosshair }
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id as any)}
            className={`pb-3 flex items-center gap-2 font-medium text-sm transition-colors ${activeTab === t.id ? 'tab-active' : 'tab-inactive'}`}
          >
            <t.icon size={16} /> {t.label}
          </button>
        ))}
      </div>

      {/* Main Content Area */}
      <main className="flex-1 p-6 overflow-hidden flex flex-col">
        {activeTab === 'feed' && (
          <div className="panel-elevated flex-1 overflow-hidden flex flex-col">
            <div className="p-5 border-b border-[#171717] flex justify-between items-center">
              <h2 className="text-lg font-semibold text-white">High-Risk Anomaly Ledger (Score &gt; 0.8)</h2>
              <span className="text-xs text-[#737373] font-mono">{anomalies.length} items in queue</span>
            </div>
            <div className="flex-1 overflow-auto">
              <table className="w-full text-sm text-left font-mono">
                <thead className="bg-[#0A0A0A] sticky top-0 shadow-sm">
                  <tr>
                    <th>TXN ID</th>
                    <th>FUSED SCORE</th>
                    <th>DECISION</th>
                  </tr>
                </thead>
                <tbody>
                  {anomalies.length === 0 && (
                    <tr>
                      <td colSpan={3} className="text-center py-12 text-[#737373] font-sans">
                        No high-risk anomalies detected in recent stream.
                      </td>
                    </tr>
                  )}
                  {anomalies.map((a, i) => (
                    <tr key={i} className="animate-slide-down">
                      <td className="text-[#A3A3A3]">{a.txn_id}</td>
                      <td>
                        <span className="bg-white text-black px-2 py-0.5 rounded font-bold">
                          {a.fused_score.toFixed(4)}
                        </span>
                      </td>
                      <td className="text-white font-bold flex items-center gap-2">
                        <AlertTriangle size={14} /> BLOCKED
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'analytics' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1">
            <div className="panel p-6 flex flex-col">
              <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                <GitBranch size={18} /> Model Confidence Distribution
              </h2>
              <div className="flex-1 min-h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={distribution}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
                    <XAxis dataKey="bucket" stroke="#737373" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#737373" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0A0A0A', borderColor: '#262626', color: '#FFF' }}
                      itemStyle={{ color: '#FFF' }}
                    />
                    <Legend />
                    <Area type="monotone" dataKey="benign" stroke="#737373" fill="#262626" fillOpacity={0.6} />
                    <Area type="monotone" dataKey="fraud" stroke="#FFFFFF" fill="#FFFFFF" fillOpacity={0.2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-[#737373] mt-4">Real-time density of fused scores. Malicious traffic clusters near 1.0.</p>
            </div>

            <div className="panel p-6 flex flex-col">
              <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                <Fingerprint size={18} /> SHAP Feature Impact
              </h2>
              {shapData.length > 0 ? (
                <div className="flex-1 min-h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={shapData} layout="vertical" margin={{ top: 0, right: 0, left: 40, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#262626" horizontal={true} vertical={false} />
                      <XAxis type="number" stroke="#737373" fontSize={12} hide />
                      <YAxis dataKey="name" type="category" stroke="#E5E5E5" fontSize={12} tickLine={false} axisLine={false} width={120} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#0A0A0A', borderColor: '#262626', color: '#FFF' }}
                        cursor={{fill: '#171717'}}
                      />
                      <Bar dataKey="value" fill="#FFFFFF" radius={[0, 4, 4, 0]} barSize={24} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center text-[#737373]">
                  Awaiting simulation completion to compute SHAP values...
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'simulation' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="panel p-6">
              <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                <Database size={18} /> Simulation Parameters
              </h2>
              
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-[#A3A3A3] mb-2">Benign Traffic Volume</label>
                  <input 
                    type="range" min="100" max="2000" step="100" 
                    value={simConfig.n_benign}
                    onChange={e => setSimConfig({...simConfig, n_benign: parseInt(e.target.value)})}
                    className="w-full accent-white"
                  />
                  <div className="text-right text-sm font-mono mt-1">{simConfig.n_benign} TXNs</div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-[#A3A3A3] mb-2">Red Agent LLM Synthesis</label>
                  <div className="flex items-center gap-3">
                    <button 
                      onClick={() => setSimConfig({...simConfig, use_llm: !simConfig.use_llm})}
                      className={`w-12 h-6 rounded-full transition-colors relative ${simConfig.use_llm ? 'bg-white' : 'bg-[#262626]'}`}
                    >
                      <div className={`absolute top-1 bg-black w-4 h-4 rounded-full transition-transform ${simConfig.use_llm ? 'translate-x-7' : 'translate-x-1'}`} />
                    </button>
                    <span className="text-sm">{simConfig.use_llm ? 'Active' : 'Bypassed (Templates Only)'}</span>
                  </div>
                </div>

                <div className="pt-4 border-t border-[#171717] space-y-4">
                  <h3 className="text-sm font-semibold text-white">Evolutionary GA Config</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-[#737373] mb-1">Generations</label>
                      <input type="number" value={simConfig.generations} onChange={e => setSimConfig({...simConfig, generations: parseInt(e.target.value)})} className="w-full" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-[#737373] mb-1">Squad Size</label>
                      <input type="number" value={simConfig.squad_size} onChange={e => setSimConfig({...simConfig, squad_size: parseInt(e.target.value)})} className="w-full" />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="panel p-6 flex flex-col justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                  <Play size={18} /> Launch Controls
                </h2>
                <p className="text-sm text-[#A3A3A3] mb-8 leading-relaxed">
                  Engage the co-evolution arena. <strong>Live-Fire Round</strong> will inject a static squad of threats alongside benign traffic. <strong>Evolutionary Tournament</strong> will engage the Genetic Algorithm to dynamically evolve threats over multiple generations to probe the model's decision boundaries.
                </p>
              </div>

              <div className="space-y-4">
                <button 
                  disabled={isSimulating}
                  onClick={() => runSimulation('round')}
                  className="w-full btn-secondary py-4 flex items-center justify-center gap-2 text-sm"
                >
                  <Crosshair size={16} /> Execute Live-Fire Round
                </button>
                <button 
                  disabled={isSimulating}
                  onClick={() => runSimulation('tournament')}
                  className="w-full btn-primary py-4 flex items-center justify-center gap-2 text-sm"
                >
                  {isSimulating ? <div className="w-5 h-5 border-2 border-black border-t-transparent rounded-full animate-spin" /> : <Play size={16} />}
                  {isSimulating ? 'Simulating...' : 'Trigger Evolutionary Tournament'}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
