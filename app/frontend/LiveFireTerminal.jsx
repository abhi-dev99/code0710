import { useState, useEffect, useRef, useMemo } from 'react';

// LIVEFIRE TERMINAL  -  LiveFire Edition
// Dense, monospace, amber-on-black, keyboard-driven. No rounded corners. Data first.

const API = typeof window !== 'undefined' && window.location.port !== '3000' ? '' : (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000');

export default function LiveFire() {
  const [health, setHealth] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [vStats, setVStats] = useState([]);
  const [rounds, setRounds] = useState([]);
  const [vectors, setVectors] = useState([]);
  const [running, setRunning] = useState(false);
  const [cmd, setCmd] = useState('');
  const [log, setLog] = useState(['LIVEFIRE LIVEFIRE TERMINAL v1.0  -  TYPE HELP <GO>']);
  const [selected, setSelected] = useState(null);
  const [profile, setProfile] = useState('card_intl');
  const [selVecs, setSelVecs] = useState(new Set());
  const [squadSize, setSquadSize] = useState(10);
  const [generations, setGenerations] = useState(2);
  const [nBenign, setNBenign] = useState(2400);
  const [showDetect, setShowDetect] = useState(false);
  const [detectInput, setDetectInput] = useState(JSON.stringify([
    { txn_id: 'demo-benign', user_id: 'u_alice', device_id: 'dev_alice_1', merchant_id: 'm_grocery', channel: 'card_present', amount: 42.5, timestamp: new Date(Date.now() - 3600e3).toISOString(), location_distance_km: 3 },
    { txn_id: 'demo-attack', user_id: 'u_burst', device_id: 'dev_shared_x', merchant_id: 'm_electronics', channel: 'card_not_present', amount: 4980, timestamp: new Date().toISOString(), location_distance_km: 1450 },
  ], null, 1));
  const [detectOut, setDetectOut] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [llmBaseUrl, setLlmBaseUrl] = useState('https://openrouter.ai/api/v1');
  const [llmApiKey, setLlmApiKey] = useState('');
  const [llmModel, setLlmModel] = useState('google/gemini-3-flash-preview');
  const [llmOut, setLlmOut] = useState(null);
  const [screen, setScreen] = useState('blotter'); // 'blotter' | 'taxonomy' | 'rails' | 'multirail' | 'realdata'
  const [multiRail, setMultiRail] = useState(null);
  const [multiRailBusy, setMultiRailBusy] = useState(false);
  const [profiles, setProfiles] = useState({});
  const [realMetrics, setRealMetrics] = useState(null);
  const inputRef = useRef(null);

  // clock
  const [now, setNow] = useState(new Date());
  useEffect(() => { const id = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(id); }, []);

  // poll health/ledger/rounds
  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [h, l, r, v, p] = await Promise.all([
          fetch(`${API}/api/health`).then(r => r.json()),
          fetch(`${API}/api/ledger?limit=80`).then(r => r.json()),
          fetch(`${API}/api/rounds?limit=20`).then(r => r.json()),
          fetch(`${API}/api/vectors`).then(r => r.json()),
          fetch(`${API}/api/profiles`).then(r => r.json()),
        ]);
        setHealth(h);
        setLedger(l.campaigns || []);
        setVStats(l.vector_stats || []);
        setRounds(r.rounds || []);
        setProfiles(p || {});
        setVectors(v.vectors || []);
        setSelVecs(prev => prev.size ? prev : new Set((v.vectors || []).slice(0, 4).map(x => x.id)));
      } catch {}
    };
    fetchAll();
    const id = setInterval(fetchAll, 2500);
    return () => clearInterval(id);
  }, []);

  // real-backbone credibility metrics never change at runtime -- fetch once, not on the hot poll
  useEffect(() => {
    fetch(`${API}/api/real-metrics`).then(r => r.ok ? r.json() : null).then(setRealMetrics).catch(() => setRealMetrics(null));
  }, []);

  const toggleVec = (id) => setSelVecs(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const pushLog = (m) => setLog(s => [...s.slice(-18), `${new Date().toLocaleTimeString('en-GB')}  ${m}`]);

  const run = async (kind) => {
    if (running) return;
    setRunning(true);
    const vids = selVecs.size ? [...selVecs] : null;
    const body = kind === 'tournament'
      ? { rail_profile: profile, vector_ids: vids, n_benign: nBenign, seed: Math.floor(Math.random()*9000)+100, squad_size: squadSize, generations }
      : { rail_profile: profile, vector_ids: vids, n_benign: nBenign, seed: Math.floor(Math.random()*9000)+100 };
    const ep = kind === 'tournament' ? '/api/tournament' : '/api/round';
    pushLog(`${kind.toUpperCase()} ${profile.toUpperCase()}  -  SENDING`);
    try {
      const res = await fetch(`${API}${ep}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || 'error');
      if (kind === 'tournament') {
        pushLog(`TOURNAMENT ESCALATION ${j.escalation?.map(x=>(x*100).toFixed(1)+'%').join('  -  ')}  RED ADV ${(j.red_advantage*100).toFixed(1)}%`);
      } else {
        pushLog(`HOLD-OUT ${j.held_out_vector}  DET ${(j.held_out_detection_rate*100).toFixed(1)}%  FP ${(j.benign_fp_rate*100).toFixed(2)}%  F1 ${j.overall?.f1}`);
      }
    } catch (e) { pushLog(`ERR ${e.message}`); }
    setRunning(false);
  };

  const runExport = () => { window.open(`${API}/api/ledger/export`, '_blank'); pushLog('EXPORT  -  LEDGER CSV DOWNLOAD STARTED'); };
  const runClear = () => setLog(['SCREEN CLEARED']);

  const runDetect = async () => {
    let txns;
    try { txns = JSON.parse(detectInput); }
    catch { setDetectOut({ error: 'invalid JSON' }); return; }
    try {
      const res = await fetch(`${API}/api/detect`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ transactions: txns }) });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || 'error');
      setDetectOut(j);
      pushLog(`DETECT  -  ${j.results.length} TXNS SCORED  -  ${j.results.filter(r=>r.flagged).length} FLAGGED`);
    } catch (e) { setDetectOut({ error: e.message }); pushLog(`ERR ${e.message}`); }
  };

  const saveLlm = async () => {
    setLlmOut({ pending: true });
    try {
      const res = await fetch(`${API}/api/llm-config`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_url: llmBaseUrl, api_key: llmApiKey, model_strategy: llmModel }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || 'error');
      setLlmOut({ ok: true, model: j.models.strategy });
      setLlmApiKey('');
      pushLog(`SETTINGS  -  LLM PROVIDER SAVED  -  ${j.models.strategy.split(',')[0].trim()}`);
    } catch (e) { setLlmOut({ error: e.message }); pushLog(`ERR ${e.message}`); }
  };

  const runMultiRailScreen = async () => {
    setMultiRailBusy(true);
    try {
      const vids = selVecs.size ? [...selVecs] : null;
      const res = await fetch(`${API}/api/multi-rail`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rail_profile: 'card_intl', vector_ids: vids, n_benign: Math.min(nBenign, 1500) }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || 'error');
      setMultiRail(j);
      pushLog('MULTI-RAIL  -  ALL 4 PROFILES SCORED');
    } catch (e) { pushLog(`ERR ${e.message}`); }
    setMultiRailBusy(false);
  };

  const submitCmd = () => {
    const c = cmd.trim().toUpperCase();
    setCmd('');
    if (!c) return;
    pushLog(`> ${c}`);
    if (c === 'HELP') pushLog('CMDS: RUN|TOUR|CLEAR|EXPORT|DETECT|SETTINGS|TAXONOMY|RAILS|MULTIRAIL|BLOTTER|PROFILE [rail] | KEYS: F1 RUN,F2 TOUR,F3 TAXO,F4 RAILS,F5 MULTI,F9 EXPORT,F10 DETECT,F11 SETTINGS,ESC');
    else if (c === 'RUN' || c === 'RUN <GO>') run('round');
    else if (c === 'TOUR' || c === 'TOUR <GO>') run('tournament');
    else if (c === 'CLEAR') runClear();
    else if (c.startsWith('PROFILE')) { const p=c.split(' ')[1]?.toLowerCase(); if(p) { setProfile(p); pushLog(`PROFILE  -  ${p}`);} }
    else if (c === 'EXPORT') runExport();
    else if (c === 'DETECT') setShowDetect(s => !s);
    else if (c === 'SETTINGS') setShowSettings(s => !s);
    else if (c === 'TAXONOMY' || c === 'TAXO') setScreen('taxonomy');
    else if (c === 'RAILS') setScreen('rails');
    else if (c === 'MULTIRAIL' || c === 'MULTI') { setScreen('multirail'); if (!multiRail) runMultiRailScreen(); }
    else if (c === 'BLOTTER') setScreen('blotter');
    else pushLog(`UNKNOWN: ${c}  -  TYPE HELP`);
  };

  const onCmd = (e) => { if (e.key === 'Enter') submitCmd(); };

  // real keyboard-driven controls, matching the F-key badges shown in the UI
  useEffect(() => {
    const fkeys = ['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F9', 'F10', 'F11', 'Escape'];
    const onKey = (e) => {
      if (document.activeElement === inputRef.current && !fkeys.includes(e.key)) return;
      if (e.key === 'F1') { e.preventDefault(); run('round'); }
      else if (e.key === 'F2') { e.preventDefault(); run('tournament'); }
      else if (e.key === 'F3') { e.preventDefault(); setScreen('taxonomy'); }
      else if (e.key === 'F4') { e.preventDefault(); setScreen('rails'); }
      else if (e.key === 'F5') { e.preventDefault(); setScreen('multirail'); if (!multiRail) runMultiRailScreen(); }
      else if (e.key === 'F6') { e.preventDefault(); setScreen('realdata'); }
      else if (e.key === 'F9') { e.preventDefault(); runExport(); }
      else if (e.key === 'F10') { e.preventDefault(); setShowDetect(s => !s); }
      else if (e.key === 'F11') { e.preventDefault(); setShowSettings(s => !s); }
      else if (e.key === 'Escape') {
        e.preventDefault();
        if (showSettings) setShowSettings(false);
        else if (showDetect) setShowDetect(false);
        else if (screen !== 'blotter') setScreen('blotter');
        else runClear();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [running, selVecs, squadSize, generations, nBenign, profile, showDetect, showSettings, screen, multiRail]);

  const cols = useMemo(() => ledger.slice(0, 24), [ledger]);

  return (
    <div className="min-h-screen bg-black text-amber-500 font-mono text-[12px] leading-[1.35] flex flex-col select-none relative" style={{ fontFamily: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace' }}>
      {showDetect && (
        <div className="absolute inset-0 z-50 bg-black/80 flex items-start justify-center pt-12" onClick={() => setShowDetect(false)}>
          <div className="bg-[#0a0a0a] border border-[#FF8C00] w-[560px] max-w-[92vw]" onClick={e => e.stopPropagation()}>
            <div className="h-[24px] bg-[#FF8C00] text-black px-2 flex items-center justify-between font-black text-[11px] tracking-widest">
              <span>DETECT  -  SCORE TRANSACTIONS WITH LIVE ENSEMBLE</span>
              <button onClick={() => setShowDetect(false)} className="px-2 hover:bg-black hover:text-[#FF8C00]">X</button>
            </div>
            <div className="p-2">
              <textarea value={detectInput} onChange={e=>setDetectInput(e.target.value)}
                className="w-full h-[140px] bg-black border border-[#333] text-[#FF8C00] p-2 text-[11px] font-mono outline-none" />
              <button onClick={runDetect} className="w-full mt-2 bg-[#FF8C00] text-black py-[4px] font-black">SCORE  &lt;GO&gt;</button>
              {detectOut && (
                detectOut.error ? <div className="mt-2 text-red-500 text-[11px]">ERR {detectOut.error}</div> : (
                  <div className="mt-2 text-[11px]">
                    <div className="text-[#666] mb-1">blue={detectOut.blue_version}  threshold={detectOut.threshold}  {detectOut.latency_ms?.total}ms</div>
                    <table className="w-full">
                      <thead><tr className="text-[#666] text-left"><th>TXN</th><th>FLAGGED</th><th>FUSED</th><th>NOVELTY</th></tr></thead>
                      <tbody>
                        {detectOut.results.map(r => (
                          <tr key={r.txn_id}>
                            <td className="truncate max-w-[140px]">{r.txn_id}</td>
                            <td className={r.flagged ? 'text-red-500 font-bold' : 'text-[#00FF00]'}>{String(r.flagged)}</td>
                            <td>{r.fused_score}</td>
                            <td>{r.novelty_flag ? 'YES' : 'no'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      )}
      {showSettings && (
        <div className="absolute inset-0 z-50 bg-black/80 flex items-start justify-center pt-12" onClick={() => setShowSettings(false)}>
          <div className="bg-[#0a0a0a] border border-[#FF8C00] w-[520px] max-w-[92vw]" onClick={e => e.stopPropagation()}>
            <div className="h-[24px] bg-[#FF8C00] text-black px-2 flex items-center justify-between font-black text-[11px] tracking-widest">
              <span>SETTINGS  -  LLM PROVIDER &amp; API KEY</span>
              <button onClick={() => setShowSettings(false)} className="px-2 hover:bg-black hover:text-[#FF8C00]">X</button>
            </div>
            <div className="p-3 text-[11px]">
              <div className="text-[#666] mb-2">Bring your own key -- any OpenAI-compatible endpoint. Kept in the server process only, never written to disk or echoed back.</div>
              <div className="text-[#666] mb-1">CURRENT: {health?.llm_configured ? <span className="text-[#00FF00]">{health.llm_info?.models?.strategy?.split(',')[0].trim()}</span> : <span className="text-red-500">not configured</span>}</div>
              <label className="block mt-2 text-[#666]">BASE URL</label>
              <input value={llmBaseUrl} onChange={e=>setLlmBaseUrl(e.target.value)}
                className="w-full bg-black border border-[#333] text-[#FF8C00] p-1 outline-none font-mono" />
              <label className="block mt-2 text-[#666]">API KEY</label>
              <input type="password" value={llmApiKey} onChange={e=>setLlmApiKey(e.target.value)} placeholder="sk-or-..."
                className="w-full bg-black border border-[#333] text-[#FF8C00] p-1 outline-none font-mono" />
              <label className="block mt-2 text-[#666]">MODEL (e.g. google/gemini-3-flash-preview, openai/gpt-5, anthropic/claude-5-sonnet)</label>
              <input value={llmModel} onChange={e=>setLlmModel(e.target.value)}
                className="w-full bg-black border border-[#333] text-[#FF8C00] p-1 outline-none font-mono" />
              <button onClick={saveLlm} disabled={!llmApiKey || llmOut?.pending}
                className="w-full mt-3 bg-[#FF8C00] text-black py-[4px] font-black disabled:opacity-50">
                {llmOut?.pending ? 'TESTING...' : 'TEST & SAVE  <GO>'}
              </button>
              {llmOut && !llmOut.pending && (
                llmOut.error
                  ? <div className="mt-2 text-red-500">ERR {llmOut.error}</div>
                  : <div className="mt-2 text-[#00FF00]">SAVED -- {llmOut.model}</div>
              )}
            </div>
          </div>
        </div>
      )}
      {/* TOP BAR  -  LiveFire style */}
      <div className="h-[28px] bg-[#FF8C00] text-black flex items-center px-2 gap-3 font-black tracking-widest text-[11px] shrink-0">
        <svg viewBox="0 0 780 230" style={{ height: 20, width: 'auto' }} aria-label="LiveFire">
          <text x="8" y="178" fontFamily="'Helvetica Neue', Arial, sans-serif" fontSize="172" fontWeight="800" letterSpacing="-6" fill="#000000">Li</text>
          <text x="772" y="178" fontFamily="'Helvetica Neue', Arial, sans-serif" fontSize="172" fontWeight="800" letterSpacing="-6" fill="#000000" textAnchor="end">eFire</text>
          <g transform="translate(185,18) scale(1.55,2.55)">
            <path d="M43 75 42.7 75C41.4 74.9 40.3 73.9 40 72.6L33.1 36 28.8 49C28.4 50.2 27.3 51 26 51L8 51 8 45 23.8 45 31.1 23.1C31.5 21.8 32.8 21 34.1 21.1 35.4 21.2 36.6 22.2 36.8 23.5L43.8 61 54 34C54.5 32.8 55.6 32 56.9 32.1 58.2 32.2 59.3 33 59.7 34.3L65.4 53 71.8 46C72.4 45.4 73.2 45 74 45L88 45 88 51 75.3 51 66.2 61C65.5 61.8 64.4 62.1 63.3 61.9 62.2 61.7 61.4 60.9 61.1 59.8L56.6 44.4 45.8 73.1C45.4 74.2 44.2 75 43 75Z" fill="#000000"/>
          </g>
        </svg>
        <span>CODE0710</span>
        <span className="opacity-60">|</span>
        <span className="font-mono font-bold">{now.toLocaleDateString('en-GB')} {now.toLocaleTimeString('en-GB')}</span>
        <span className="opacity-60">|</span>
        <span>{health ? `${health.vectors} VECTORS  -  ${health.rail_profiles?.join('/')}` : 'CONNECTING...'}</span>
        <span className="ml-auto flex items-center gap-2">
          <span className={`w-2 h-2 inline-block ${health?.ensemble_ready ? 'bg-black' : 'bg-red-600'}`} style={{ boxShadow: '0 0 4px rgba(0,0,0,0.5)' }} />
          {health?.ensemble_ready ? 'ENS READY' : 'ENS COLD'}
          <span className="bg-black text-[#FF8C00] px-2 ml-2">{profile.toUpperCase()}</span>
          <button onClick={() => setShowSettings(true)} title="Configure LLM provider/key"
            className={`px-2 cursor-pointer hover:opacity-80 ${health?.llm_configured ? 'bg-black text-[#FF8C00]' : 'bg-red-600 text-white'}`}>
            LLM:{health?.llm_configured ? (health.llm_info?.models?.strategy?.split(',')[0].trim().toUpperCase() || 'ON') : 'TEMPLATE'}
          </button>
        </span>
      </div>

      {/* FUNCTION KEYS -- real buttons + real keyboard shortcuts (see the keydown effect above) */}
      <div className="h-[22px] bg-[#1a1a1a] border-y border-[#333] flex items-center px-1 gap-[2px] text-[10px] shrink-0">
        {[
          ['F1', 'RUN', () => run('round'), running],
          ['F2', 'TOUR', () => run('tournament'), running],
          ['F3', 'TAXONOMY', () => setScreen('taxonomy'), false],
          ['F4', 'RAILS', () => setScreen('rails'), false],
          ['F5', 'MULTI-RAIL', () => { setScreen('multirail'); if (!multiRail) runMultiRailScreen(); }, false],
          ['F6', 'REAL DATA', () => setScreen('realdata'), false],
          ['F9', 'EXPORT', runExport, false],
          ['ESC', 'CLEAR', runClear, false],
        ].map(([k, v, fn, dis]) => (
          <button key={k} onClick={fn} disabled={dis} title={`Keyboard: ${k}`}
            className={`flex items-center gap-1 px-2 py-[2px] border cursor-pointer disabled:opacity-40 disabled:cursor-wait ${
              (k === 'F3' && screen === 'taxonomy') || (k === 'F4' && screen === 'rails') || (k === 'F5' && screen === 'multirail') || (k === 'F6' && screen === 'realdata')
                ? 'bg-[#FF8C00] text-black border-[#FF8C00]' : 'bg-black border-[#333] hover:border-[#FF8C00] hover:bg-[#161200]'}`}>
            <span className="bg-[#FF8C00] text-black px-1 font-black">{k}</span> {v}
          </button>
        ))}
        <button onClick={() => setShowDetect(s => !s)} title="Score custom transactions"
          className={`flex items-center gap-1 px-2 py-[2px] border cursor-pointer ${showDetect ? 'bg-[#FF8C00] text-black border-[#FF8C00]' : 'bg-black border-[#333] hover:border-[#FF8C00] hover:bg-[#161200]'}`}>
          <span className={showDetect ? 'bg-black text-[#FF8C00] px-1 font-black' : 'bg-[#FF8C00] text-black px-1 font-black'}>F10</span> DETECT
        </button>
        <button onClick={() => setShowSettings(s => !s)} title="Configure LLM provider/key"
          className={`flex items-center gap-1 px-2 py-[2px] border cursor-pointer ${showSettings ? 'bg-[#FF8C00] text-black border-[#FF8C00]' : 'bg-black border-[#333] hover:border-[#FF8C00] hover:bg-[#161200]'}`}>
          <span className={showSettings ? 'bg-black text-[#FF8C00] px-1 font-black' : 'bg-[#FF8C00] text-black px-1 font-black'}>F11</span> SETTINGS
        </button>
        <span className="ml-auto text-[#666]">VECTORS {vectors.length}  -  LEDGER {health?.ledger_campaigns || 0}  -  PROFILE {profile}  -  TYPE HELP &lt;GO&gt;</span>
      </div>

      {/* VECTOR SELECT -- which vectors the next RUN/TOUR fields (last selected = held out) */}
      <div className="h-[24px] bg-[#111] border-b border-[#333] flex items-center px-1 gap-1 text-[10px] shrink-0 overflow-x-auto">
        <span className="text-[#666] px-1 shrink-0">VECTORS</span>
        {vectors.map(v => (
          <button key={v.id} onClick={() => toggleVec(v.id)}
            title={v.name}
            className={`shrink-0 px-1.5 py-[1px] border font-mono ${selVecs.has(v.id) ? 'bg-[#FF8C00] text-black border-[#FF8C00] font-black' : 'bg-black text-[#666] border-[#333] hover:border-[#555]'}`}>
            {v.id}
          </button>
        ))}
        <span className="text-[#444] shrink-0 ml-1">({selVecs.size || 'all'} selected, last = held-out)</span>
        <span className="ml-auto shrink-0 flex gap-1">
          {['blotter', 'taxonomy', 'rails', 'multirail', 'realdata'].map(s => (
            <button key={s} onClick={() => { setScreen(s); if (s === 'multirail' && !multiRail) runMultiRailScreen(); }}
              className={`px-2 py-[1px] border uppercase ${screen === s ? 'bg-[#FF8C00] text-black border-[#FF8C00] font-black' : 'bg-black text-[#666] border-[#333]'}`}>
              {s}
            </button>
          ))}
        </span>
      </div>

      {screen === 'taxonomy' && (
        <div className="flex-1 bg-black overflow-auto min-h-0">
          <div className="h-[20px] bg-[#111] border-b border-[#333] flex items-center px-2 text-[10px] tracking-widest font-bold text-[#FF8C00] sticky top-0">
            TAXONOMY  -  ATTACK ATLAS ({vectors.length} VECTORS)
          </div>
          <div className="grid grid-cols-12 gap-0 px-2 py-[3px] bg-[#0a0a0a] border-b border-[#333] text-[10px] text-[#666] font-bold sticky top-[20px]">
            <span className="col-span-1">ID</span><span className="col-span-2">NAME</span><span className="col-span-2">CATEGORY</span>
            <span className="col-span-4">MECHANISM</span><span className="col-span-2">SIGNALS</span><span className="col-span-1 text-right">DIFF/NOV</span>
          </div>
          {vectors.map(v => (
            <div key={v.id} onClick={() => toggleVec(v.id)}
              className={`grid grid-cols-12 gap-0 px-2 py-[5px] text-[11px] border-b border-[#1a1a1a] cursor-pointer hover:bg-[#111] ${selVecs.has(v.id) ? 'bg-[#1a1200]' : ''}`}>
              <span className="col-span-1 font-black text-[#FF8C00]">{v.id}</span>
              <span className="col-span-2 truncate">{v.name}</span>
              <span className="col-span-2 truncate text-[#888]">{v.category}</span>
              <span className="col-span-4 text-[#999] leading-[1.3]">{v.mechanism}</span>
              <span className="col-span-2 text-[#666] truncate">{(v.signals||[]).join(', ')}</span>
              <span className="col-span-1 text-right font-mono text-[#666]">{v.difficulty}/{v.novelty}</span>
            </div>
          ))}
        </div>
      )}

      {screen === 'rails' && (
        <div className="flex-1 bg-black overflow-auto min-h-0 p-2">
          <div className="text-[#FF8C00] text-[10px] font-bold tracking-widest mb-2">RAILS  -  {Object.keys(profiles).length} GLOBAL PROFILES</div>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(profiles).map(([key, p]) => (
              <div key={key} className={`border p-2 text-[11px] ${profile === key ? 'border-[#FF8C00]' : 'border-[#333]'}`}>
                <div className="flex justify-between items-center mb-1">
                  <span className="font-black text-[#FF8C00]">{p.display_name || key}</span>
                  <button onClick={() => setProfile(key)} className={`px-2 py-[1px] text-[10px] border ${profile === key ? 'bg-[#FF8C00] text-black border-[#FF8C00] font-black' : 'border-[#333] text-[#666]'}`}>{profile === key ? 'ACTIVE' : 'SELECT'}</button>
                </div>
                <div className="text-[#666]">CURRENCY <b className="text-white">{p.currency}</b>  TZ <b className="text-white">{p.timezone}</b></div>
                <div className="text-[#666]">SCA STEP-UP <b className="text-white">{String(p.sca_step_up)}</b>  CHARGEBACKS <b className="text-white">{String(p.chargebacks)}</b></div>
                <div className="text-[#666] mt-1">CHANNELS</div>
                {Object.entries(p.channels || {}).map(([cn, c]) => (
                  <div key={cn} className="pl-2 text-[#999] font-mono">{cn}: max {c.max} -- {(c.categories||[]).slice(0,3).join(', ')}</div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {screen === 'multirail' && (
        <div className="flex-1 bg-black overflow-auto min-h-0 p-2">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[#FF8C00] text-[10px] font-bold tracking-widest">MULTI-RAIL  -  SAME VECTORS, EVERY RAIL</span>
            <button onClick={runMultiRailScreen} disabled={multiRailBusy} className="px-3 py-[3px] bg-[#FF8C00] text-black font-black text-[10px] disabled:opacity-50">{multiRailBusy ? 'RUNNING...' : 'RE-RUN'}</button>
          </div>
          {!multiRail ? <div className="text-[#444] p-4 text-center">{multiRailBusy ? 'SCORING ALL 4 RAILS...' : 'NO DATA -- HIT RE-RUN'}</div> : (
            <table className="w-full text-[11px]">
              <thead><tr className="text-[#666] text-left border-b border-[#333]"><th className="py-1">RAIL</th><th>HELD-OUT DET</th><th>BENIGN FP</th><th>F1</th></tr></thead>
              <tbody>
                {Object.entries(multiRail).map(([rail, r]) => (
                  <tr key={rail} className="border-b border-[#1a1a1a]">
                    <td className="py-1 font-black text-[#FF8C00]">{rail}</td>
                    {r.error ? <td colSpan={3} className="text-red-500">{r.error}</td> : (<>
                      <td className={r.held_out_detection_rate > 0.5 ? 'text-[#00FF00]' : 'text-red-500'}>{(r.held_out_detection_rate*100).toFixed(1)}%</td>
                      <td>{(r.benign_fp_rate*100).toFixed(2)}%</td>
                      <td>{r.overall?.f1}</td>
                    </>)}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {screen === 'realdata' && (
        <div className="flex-1 bg-black overflow-auto min-h-0 p-2">
          <div className="text-[#FF8C00] text-[10px] font-bold tracking-widest mb-2">REAL DATA  -  ULB HOLDOUT, NO SYNTHETIC (HONEST CREDIBILITY NUMBER)</div>
          {!realMetrics ? (
            <div className="text-[#444] p-4 text-center">NOT TRAINED YET -- RUN: python defense/train_real_backbone.py</div>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-2 mb-3">
                <div className="border border-[#333] p-3 text-center">
                  <div className="text-[24px] font-black text-[#00FF00]">{realMetrics.roc_auc}</div>
                  <div className="text-[10px] text-[#666] tracking-widest mt-1">ROC-AUC</div>
                </div>
                <div className="border border-[#333] p-3 text-center">
                  <div className="text-[24px] font-black text-[#FF8C00]">{realMetrics.average_precision}</div>
                  <div className="text-[10px] text-[#666] tracking-widest mt-1">AVG PRECISION</div>
                </div>
                <div className="border border-[#333] p-3 text-center">
                  <div className="text-[24px] font-black">{(realMetrics.n_test / 1000).toFixed(0)}k</div>
                  <div className="text-[10px] text-[#666] tracking-widest mt-1">REAL TEST TXNS</div>
                </div>
              </div>
              <div className="text-[11px] text-[#999] mb-3 leading-[1.4]">{realMetrics.honesty_note}</div>
              {realMetrics.capture_clock_ablation && (
                <div className="border-l-2 border-[#FF8C00] pl-2 text-[11px] text-[#999] mb-3 leading-[1.4]">
                  <span className="text-[#FF8C00] font-bold">CAPTURE-CLOCK ABLATION  -  </span>
                  {realMetrics.capture_clock_ablation.note}
                  <div className="font-mono text-[#666] mt-1">
                    with time: ROC {realMetrics.capture_clock_ablation.roc_auc_with_time} / AP {realMetrics.capture_clock_ablation.average_precision_with_time}
                    {'   '}without: ROC {realMetrics.capture_clock_ablation.roc_auc_without_time} / AP {realMetrics.capture_clock_ablation.average_precision_without_time}
                  </div>
                </div>
              )}
              <div className="text-[10px] text-[#555] font-mono">
                dataset={realMetrics.dataset}  n_train={realMetrics.n_train}  seed={realMetrics.seed}  artifact={realMetrics.artifact}
              </div>
            </>
          )}
        </div>
      )}

      {screen === 'blotter' && (
      <div className="flex-1 grid grid-cols-12 gap-[1px] bg-[#222] p-[1px] min-h-0">
        {/* LEFT  -  BLOTTER */}
        <div className="col-span-8 bg-black flex flex-col min-h-0">
          <div className="h-[20px] bg-[#111] border-b border-[#333] flex items-center px-2 text-[10px] tracking-widest font-bold">
            <span className="text-[#FF8C00]">BLOTTER  -  ROBUSTNESS LEDGER</span>
            <span className="ml-auto text-[#666]">{cols.length} CAMPAIGNS  -  LAST 24 SHOWN  -  CLICK ROW  -  DETAIL</span>
          </div>
          <div className="grid grid-cols-12 gap-0 px-2 py-[3px] bg-[#0a0a0a] border-b border-[#333] text-[10px] text-[#666] font-bold tracking-widest">
            <span className="col-span-3">VECTOR</span>
            <span>RAIL</span>
            <span className="text-right">TXNs</span>
            <span className="text-right">DROP</span>
            <span className="text-right col-span-2">DET RATE</span>
            <span className="col-span-4">EVASION NOTES</span>
          </div>
          <div className="flex-1 overflow-auto divide-y divide-[#1a1a1a]">
            {cols.length === 0 ? (
              <div className="p-6 text-center text-[#444]">NO CAMPAIGNS  -  HIT F1 RUN</div>
            ) : cols.map((c, i) => (
              <div key={c.id || i} onClick={() => setSelected(c)} className={`grid grid-cols-12 gap-0 px-2 py-[4px] hover:bg-[#111] cursor-pointer text-[11px] ${selected?.id===c.id ? 'bg-[#1a1200] !text-[#FFB000]' : i%2===0 ? 'bg-black' : 'bg-[#080808]'}`}>
                <span className="col-span-3 truncate font-bold">{c.vector}</span>
                <span className="text-[#888]">{c.rail_profile}</span>
                <span className="text-right font-mono">{c.n_txns}</span>
                <span className="text-right font-mono text-[#666]">{c.n_dropped}</span>
                <span className={`text-right col-span-2 font-mono font-black ${c.detection_rate < 0.4 ? 'text-red-500' : c.detection_rate < 0.7 ? 'text-[#FF8C00]' : 'text-[#00FF00]'}`}>{(c.detection_rate*100).toFixed(1)}%</span>
                <span className="col-span-4 truncate text-[#777]">{c.evasion_notes || ' - '}</span>
              </div>
            ))}
          </div>
          <div className="h-[20px] bg-[#111] border-t border-[#333] flex items-center px-2 gap-2 text-[10px]">
            <button onClick={() => run('round')} disabled={running} className="bg-[#FF8C00] text-black px-3 py-[2px] font-black disabled:opacity-50">F1 RUN</button>
            <button onClick={() => run('tournament')} disabled={running} className="bg-black border border-[#FF8C00] text-[#FF8C00] px-3 py-[2px] font-black disabled:opacity-50">F2 TOURNAMENT ({squadSize}&times;{generations})</button>
            <select value={profile} onChange={e=>setProfile(e.target.value)} className="bg-black border border-[#333] text-[#FF8C00] px-2 py-[2px] outline-none">
              <option value="card_intl">CARD_INTL</option>
              <option value="eu_psd2">EU_PSD2</option>
              <option value="us_cnp">US_CNP</option>
              <option value="upi_in">UPI_IN</option>
            </select>
            <label className="flex items-center gap-1 text-[#666]">BENIGN
              <input type="number" min={400} max={20000} step={200} value={nBenign} onChange={e=>setNBenign(+e.target.value)}
                className="w-16 bg-black border border-[#333] text-[#FF8C00] px-1 py-[1px] outline-none" />
            </label>
            <label className="flex items-center gap-1 text-[#666]">SQUAD
              <input type="number" min={2} max={32} value={squadSize} onChange={e=>setSquadSize(+e.target.value)}
                className="w-10 bg-black border border-[#333] text-[#FF8C00] px-1 py-[1px] outline-none" />
            </label>
            <label className="flex items-center gap-1 text-[#666]">GENS
              <input type="number" min={1} max={5} value={generations} onChange={e=>setGenerations(+e.target.value)}
                className="w-10 bg-black border border-[#333] text-[#FF8C00] px-1 py-[1px] outline-none" />
            </label>
            <span className="ml-auto text-[#555]">DETECT LAT {health?.detect_latency_ms ? `${health.detect_latency_ms.p50_ms}/${health.detect_latency_ms.p99_ms}ms` : ' - '}  -  LLM {health?.llm_configured ? 'ON' : 'OFF'}</span>
          </div>
        </div>

        {/* RIGHT STACK */}
        <div className="col-span-4 flex flex-col gap-[1px] bg-[#222] min-h-0">
          {/* VECTOR REPORT CARD */}
          <div className="bg-black flex flex-col" style={{ flex: 1 }}>
            <div className="h-[20px] bg-[#111] border-b border-[#333] px-2 flex items-center text-[10px] font-bold tracking-widest">
              <span className="text-[#FF8C00]">VECTOR REPORT CARD</span>
            </div>
            <div className="grid grid-cols-3 gap-0 px-2 py-[3px] bg-[#0a0a0a] border-b border-[#333] text-[10px] text-[#666] font-bold">
              <span>VECTOR</span><span className="text-right">ATT</span><span className="text-right">AVG DET</span>
            </div>
            <div className="overflow-auto divide-y divide-[#1a1a1a] flex-1">
              {vStats.slice(0, 14).map(v => (
                <div key={v.vector} className="grid grid-cols-3 px-2 py-[3px] text-[11px] hover:bg-[#111]">
                  <span className="truncate">{v.vector?.slice(0, 22)}</span>
                  <span className="text-right font-mono">{v.attempts}</span>
                  <span className={`text-right font-mono font-bold ${v.avg_detection < 0.4 ? 'text-red-500' : v.avg_detection < 0.7 ? 'text-[#FF8C00]' : 'text-[#00FF00]'}`}>{(v.avg_detection*100).toFixed(1)}%</span>
                </div>
              ))}
              {vStats.length===0 && <div className="p-4 text-center text-[#444] text-[11px]">NO STATS</div>}
            </div>
          </div>

          {/* ROUND HISTORY */}
          <div className="bg-black flex flex-col" style={{ flex: 1 }}>
            <div className="h-[20px] bg-[#111] border-b border-[#333] px-2 flex items-center text-[10px] font-bold tracking-widest">
              <span className="text-[#FF8C00]">ROUND HISTORY  -  BLUE EVOLUTION</span>
            </div>
            <div className="overflow-auto flex-1 divide-y divide-[#1a1a1a]">
              {rounds.slice(0, 8).map((r,i) => (
                <div key={i} className="px-2 py-[4px] text-[11px]">
                  <div className="flex justify-between"><span className="text-[#666] font-mono">{(r.ts||'').slice(11,19)}</span><span className="font-mono font-bold" style={{color: r.f1>0.7?'#00FF00': r.f1>0.4?'#FF8C00':'#FF0000'}}>F1 {r.f1?.toFixed(3)}</span></div>
                  <div className="text-[#777] truncate">{r.notes?.slice(0,88)}</div>
                  <div className="font-mono text-[#555]">TP {r.tp} FP {r.fp} FN {r.fn} TN {r.tn}</div>
                </div>
              ))}
              {rounds.length===0 && <div className="p-4 text-center text-[#444] text-[11px]">NO ROUNDS  -  RUN ONE</div>}
            </div>
          </div>

          {/* SELECTED DETAIL */}
          <div className="bg-black border-t border-[#222]" style={{ minHeight: selected ? 140 : 40 }}>
            <div className="h-[20px] bg-[#FF8C00] text-black px-2 flex items-center text-[10px] font-black tracking-widest">
              DETAIL {selected ? ` -  ${selected.vector}` : ' -  SELECT ROW'}
            </div>
            {selected ? (
              <div className="p-2 text-[11px] leading-[1.4]">
                <div className="grid grid-cols-3 gap-2 font-mono">
                  <span>RAIL <b className="text-white">{selected.rail_profile}</b></span>
                  <span>TXNS <b className="text-white">{selected.n_txns}</b></span>
                  <span>DET <b style={{color: selected.detection_rate<0.4?'#FF0000': selected.detection_rate<0.7?'#FF8C00':'#00FF00'}}>{(selected.detection_rate*100).toFixed(1)}%</b></span>
                </div>
                <div className="mt-2 p-2 bg-[#0a0a0a] border border-[#222] text-[#999] whitespace-pre-wrap break-words max-h-[80px] overflow-auto">{selected.evasion_notes || ' - '}{selected.plan_json ? `\nPLAN ${selected.plan_json.slice(0, 400)}` : ''}</div>
              </div>
            ) : <div className="p-2 text-[#444]">Click a blotter row.</div>}
          </div>
        </div>
      </div>
      )}

      {/* LOG TAPE */}
      <div className="h-[110px] bg-[#0a0a0a] border-t border-[#333] flex flex-col shrink-0">
        <div className="h-[16px] bg-[#111] border-b border-[#333] px-2 flex items-center text-[10px] font-bold tracking-widest text-[#666]">
          LOG TAPE  -  SYSTEM MESSAGES
        </div>
        <div className="flex-1 overflow-auto p-1 font-mono text-[11px] leading-[1.3]">
          {log.map((l,i) => <div key={i} className="text-[#888]"><span className="text-[#333]">{String(i).padStart(2,'0')}</span> {l}</div>)}
        </div>
      </div>

      {/* COMMAND LINE  -  LiveFire <GO> */}
      <div className="h-[26px] bg-black border-t border-[#FF8C00] flex items-center px-2 gap-2 shrink-0">
        <span className="text-[#FF8C00] font-black"> - </span>
        <input
          ref={inputRef}
          value={cmd}
          onChange={e=>setCmd(e.target.value)}
          onKeyDown={onCmd}
          placeholder="TYPE COMMAND  -  HELP | RUN | TOUR | PROFILE | EXPORT   -  ENTER <GO>"
          className="flex-1 bg-transparent outline-none text-[#FF8C00] placeholder:text-[#444] font-mono text-[12px]"
        />
        <button onClick={submitCmd} className="bg-[#FF8C00] text-black px-2 py-[1px] font-black text-[10px] hover:bg-white">GO</button>
        <span className="text-[#444] text-[10px] hidden sm:inline">LIVEFIRE TERMINAL  -  LIVEFIRE  -  CODE0710</span>
      </div>
    </div>
  );
}
