import { useState, useEffect, useRef, useMemo } from 'react';

// LIVEFIRE TERMINAL  -  LiveFire Edition
// Dense, monospace, amber-on-black, keyboard-driven. No rounded corners. Data first.

const API = 'http://127.0.0.1:8000';

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
  const inputRef = useRef(null);

  // clock
  const [now, setNow] = useState(new Date());
  useEffect(() => { const id = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(id); }, []);

  // poll health/ledger/rounds
  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [h, l, r, v] = await Promise.all([
          fetch(`${API}/api/health`).then(r => r.json()),
          fetch(`${API}/api/ledger?limit=80`).then(r => r.json()),
          fetch(`${API}/api/rounds?limit=20`).then(r => r.json()),
          fetch(`${API}/api/vectors`).then(r => r.json()),
        ]);
        setHealth(h);
        setLedger(l.campaigns || []);
        setVStats(l.vector_stats || []);
        setRounds(r.rounds || []);
        setVectors(v.vectors || []);
      } catch {}
    };
    fetchAll();
    const id = setInterval(fetchAll, 2500);
    return () => clearInterval(id);
  }, []);

  const pushLog = (m) => setLog(s => [...s.slice(-18), `${new Date().toLocaleTimeString('en-GB')}  ${m}`]);

  const run = async (kind) => {
    if (running) return;
    setRunning(true);
    const body = kind === 'tournament'
      ? { rail_profile: profile, n_benign: 2400, seed: Math.floor(Math.random()*9000)+100, squad_size: 8, generations: 2 }
      : { rail_profile: profile, n_benign: 2400, seed: Math.floor(Math.random()*9000)+100 };
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

  const onCmd = (e) => {
    if (e.key !== 'Enter') return;
    const c = cmd.trim().toUpperCase();
    setCmd('');
    if (!c) return;
    pushLog(`> ${c}`);
    if (c === 'HELP') pushLog('CMDS: RUN | TOUR | CLEAR | EXPORT | PROFILE [card_intl|eu_psd2|us_cnp|upi_in] | HELP');
    else if (c === 'RUN' || c === 'RUN <GO>') run('round');
    else if (c === 'TOUR' || c === 'TOUR <GO>') run('tournament');
    else if (c === 'CLEAR') setLog(['SCREEN CLEARED']);
    else if (c.startsWith('PROFILE')) { const p=c.split(' ')[1]?.toLowerCase(); if(p) { setProfile(p); pushLog(`PROFILE  -  ${p}`);} }
    else if (c === 'EXPORT') window.open(`${API}/api/ledger/export`, '_blank');
    else pushLog(`UNKNOWN: ${c}  -  TYPE HELP`);
  };

  const cols = useMemo(() => ledger.slice(0, 24), [ledger]);

  return (
    <div className="min-h-screen bg-black text-amber-500 font-mono text-[12px] leading-[1.35] flex flex-col select-none" style={{ fontFamily: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace' }}>
      {/* TOP BAR  -  LiveFire style */}
      <div className="h-[28px] bg-[#FF8C00] text-black flex items-center px-2 gap-3 font-black tracking-widest text-[11px] shrink-0">
        <span className="bg-black text-[#FF8C00] px-2 py-[1px]">LIVEFIRE</span>
        <span>CODE0710</span>
        <span className="opacity-60">|</span>
        <span className="font-mono font-bold">{now.toLocaleDateString('en-GB')} {now.toLocaleTimeString('en-GB')}</span>
        <span className="opacity-60">|</span>
        <span>{health ? `${health.vectors} VECTORS  -  ${health.rail_profiles?.join('/')}` : 'CONNECTING...'}</span>
        <span className="ml-auto flex items-center gap-2">
          <span className={`w-2 h-2 inline-block ${health?.ensemble_ready ? 'bg-black' : 'bg-red-600'}`} style={{ boxShadow: '0 0 4px rgba(0,0,0,0.5)' }} />
          {health?.ensemble_ready ? 'ENS READY' : 'ENS COLD'}
          <span className="bg-black text-[#FF8C00] px-2 ml-2">{profile.toUpperCase()}</span>
          <span className={`px-2 ${health?.llm_configured ? 'bg-black text-[#FF8C00]' : 'bg-red-600 text-white'}`}>{health?.llm_configured ? 'LLM:OX-ALPHA' : 'LLM:TEMPLATE'}</span>
        </span>
      </div>

      {/* FUNCTION KEYS */}
      <div className="h-[22px] bg-[#1a1a1a] border-y border-[#333] flex items-center px-1 gap-[2px] text-[10px] shrink-0">
        {[
          ['F1', 'RUN'], ['F2', 'TOUR'], ['F9', 'EXPORT'], ['ESC', 'CLEAR'],
        ].map(([k, v]) => (
          <span key={k} className="flex items-center gap-1 px-2 py-[2px] bg-black border border-[#333]">
            <span className="bg-[#FF8C00] text-black px-1 font-black">{k}</span> {v}
          </span>
        ))}
        <span className="ml-auto text-[#666]">VECTORS {vectors.length}  -  LEDGER {health?.ledger_campaigns || 0}  -  PROFILE {profile}  -  TYPE HELP &lt;GO&gt;</span>
      </div>

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
            <button onClick={() => run('tournament')} disabled={running} className="bg-black border border-[#FF8C00] text-[#FF8C00] px-3 py-[2px] font-black disabled:opacity-50">F2 TOURNAMENT (10 - )</button>
            <select value={profile} onChange={e=>setProfile(e.target.value)} className="bg-black border border-[#333] text-[#FF8C00] px-2 py-[2px] outline-none">
              <option value="card_intl">CARD_INTL</option>
              <option value="eu_psd2">EU_PSD2</option>
              <option value="us_cnp">US_CNP</option>
              <option value="upi_in">UPI_IN</option>
            </select>
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
        <span className="bg-[#FF8C00] text-black px-2 py-[1px] font-black text-[10px]">GO</span>
        <span className="text-[#444] text-[10px] hidden sm:inline">LIVEFIRE TERMINAL  -  LIVEFIRE  -  CODE0710</span>
      </div>
    </div>
  );
}
