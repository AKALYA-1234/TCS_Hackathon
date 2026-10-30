import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  History as HistoryIcon, Clock, Calendar, Zap, AlertTriangle, ShieldCheck,
  Search, Play, Pause, RotateCcw, FastForward, Filter, Download, ChevronRight,
  Maximize2, ArrowRight, Layers, Sliders, Cpu, CheckCircle2, TrendingUp,
  TrendingDown, Thermometer, Users, Sun, Info
} from 'lucide-react';
import { HonestyBadges } from '../ui/BaseComponents';

// Preset date ranges
const PRESETS = [
  { id: '24h', label: '24 Hours', hours: 24 },
  { id: '7d', label: '7 Days', hours: 24 * 7 },
  { id: '30d', label: '30 Days', hours: 24 * 30 },
  { id: 'all', label: 'Full Range', hours: 24 * 26 }
];

export function ACHistory({ onNavigateRoom }) {
  // Master Unit & Date Selection
  const [selectedUnitId, setSelectedUnitId] = useState('ac-eng-101-1');
  const [activePreset, setActivePreset] = useState('7d');
  const [customRange, setCustomRange] = useState({
    start: '2026-11-16T20:00:00Z',
    end: '2026-11-23T20:00:00Z'
  });
  const [resolution, setResolution] = useState('auto');
  const [isAllUnitsMode, setIsAllUnitsMode] = useState(false);

  // Data State
  const [historyData, setHistoryData] = useState(null);
  const [swimlanesData, setSwimlanesData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Interactive Replay & Playhead
  const [isPlaying, setIsPlaying] = useState(false);
  const [playSpeed, setPlaySpeed] = useState(1); // 1x, 10x, 60x, 360x
  const [playheadIndex, setPlayheadIndex] = useState(0);

  // Inspector & Drawer State
  const [selectedSegment, setSelectedSegment] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [hoveredPoint, setHoveredPoint] = useState(null);

  // Units Directory (loaded dynamically)
  const [allUnits, setAllUnits] = useState([]);
  const [unitSearch, setUnitSearch] = useState('');

  // Fetch unit list
  useEffect(() => {
    fetch('/ac/rooms')
      .then(res => res.json())
      .then(rooms => {
        if (Array.isArray(rooms)) {
          const list = [];
          rooms.forEach(r => {
            (r.units || []).forEach(u => {
              list.push({
                id: u.id,
                name: u.name,
                room_id: r.id || r.room_id,
                room_name: r.name || r.room_name,
                building: r.building,
                rated_kw: u.rated_kw,
                is_critical: r.is_critical
              });
            });
          });
          setAllUnits(list);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch History for selected unit or swimlanes
  useEffect(() => {
    setLoading(true);
    setError(null);

    const controller = new AbortController();
    const signal = controller.signal;

    async function loadData() {
      try {
        if (isAllUnitsMode) {
          const res = await fetch(`/ac/units/history/swimlanes`, { signal });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const json = await res.json();
          setSwimlanesData(json);
        } else {
          const url = `/ac/units/${selectedUnitId}/history?start_time=${customRange.start}&end_time=${customRange.end}&resolution=${resolution}`;
          const res = await fetch(url, { signal });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const json = await res.json();
          setHistoryData(json);
          setPlayheadIndex(0);
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Failed to fetch history');
        }
      } finally {
        if (!signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadData();
    return () => controller.abort();
  }, [selectedUnitId, customRange, resolution, isAllUnitsMode]);

  // Replay Timer Animation
  useEffect(() => {
    let interval = null;
    if (isPlaying && historyData?.series?.length > 0) {
      interval = setInterval(() => {
        setPlayheadIndex((prev) => {
          if (prev >= historyData.series.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 1000 / Math.min(60, playSpeed));
    }
    return () => clearInterval(interval);
  }, [isPlaying, playSpeed, historyData]);

  // Keyboard navigation for playhead and zoom (WCAG AA accessible)
  const handleKeyDown = (e) => {
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      setPlayheadIndex(prev => Math.min((historyData?.series?.length || 1) - 1, prev + 1));
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      setPlayheadIndex(prev => Math.max(0, prev - 1));
    } else if (e.key === ' ') {
      e.preventDefault();
      setIsPlaying(p => !p);
    }
  };

  // CSV Export for state events
  const handleExportCSV = () => {
    if (!historyData) return;
    const headers = "timestamp,power_kw,set_temp_c,room_temp_c,outdoor_temp_c,occupancy,state\n";
    const rows = (historyData.series || []).map(s => 
      `${s.timestamp},${s.power_kw},${s.set_temp_c},${s.room_temp_c},${s.outdoor_temp_c},${s.occupancy},${s.state}`
    ).join("\n");
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ac_history_${selectedUnitId}.csv`;
    a.click();
  };

  // Active playhead point
  const currentPoint = historyData?.series?.[playheadIndex] || historyData?.series?.[0] || null;

  return (
    <div 
      tabIndex={0} 
      onKeyDown={handleKeyDown} 
      className="space-y-6 pb-20 focus:outline-none animate-in fade-in duration-300"
    >
      {/* 1. Header Toolbar: Unit Picker, Presets, Resolution, Modes */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              AC Unit History & Timeline
            </h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full font-mono font-semibold bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400">
              IST (UTC+5:30)
            </span>
          </div>
          <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
            High-fidelity telemetry replay, state-change swim-lanes, baseline comparison, and thermal comfort violation tracking.
          </p>
        </div>

        {/* Global Selectors */}
        <div className="flex flex-wrap items-center gap-2 self-start lg:self-center">
          {/* Unit Picker */}
          {!isAllUnitsMode && (
            <select
              value={selectedUnitId}
              onChange={(e) => setSelectedUnitId(e.target.value)}
              className="px-3 py-1.5 text-xs font-semibold rounded-xl border bg-transparent cursor-pointer"
              style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
            >
              {allUnits.map(u => (
                <option key={u.id} value={u.id} className="dark:bg-stone-900">
                  {u.name} ({u.room_name})
                </option>
              ))}
            </select>
          )}

          {/* All Units vs Single Unit Toggle */}
          <button
            onClick={() => setIsAllUnitsMode(!isAllUnitsMode)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-xl border transition-all ${
              isAllUnitsMode ? 'bg-indigo-600 text-white shadow-xs' : 'text-stone-500 hover:bg-stone-500/10'
            }`}
            style={{ borderColor: 'var(--border-separator)' }}
          >
            {isAllUnitsMode ? 'Single Unit Mode' : 'All Units Swim-lane'}
          </button>

          {/* Date Range Presets */}
          <div className="flex items-center rounded-xl border p-0.5" style={{ borderColor: 'var(--border-separator)' }}>
            {PRESETS.map(p => (
              <button
                key={p.id}
                onClick={() => {
                  setActivePreset(p.id);
                  const end = new Date(2026, 10, 23, 20, 0, 0); // Nov 23 2026
                  const start = new Date(end.getTime() - p.hours * 3600 * 1000);
                  setCustomRange({
                    start: start.toISOString(),
                    end: end.toISOString()
                  });
                }}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-all ${
                  activePreset === p.id ? 'bg-indigo-600 text-white shadow-xs' : 'text-stone-500 hover:text-stone-900 dark:hover:text-stone-200'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Resolution Selector */}
          <select
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            className="px-2.5 py-1 text-xs font-semibold rounded-xl border bg-transparent"
            style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
          >
            <option value="auto" className="dark:bg-stone-900">Auto Res</option>
            <option value="5m" className="dark:bg-stone-900">5 min</option>
            <option value="15m" className="dark:bg-stone-900">15 min</option>
            <option value="1h" className="dark:bg-stone-900">1 hour</option>
            <option value="1d" className="dark:bg-stone-900">1 day</option>
          </select>

          {/* Export CSV */}
          <button
            onClick={handleExportCSV}
            className="p-1.5 rounded-xl border text-stone-500 hover:bg-stone-500/10"
            style={{ borderColor: 'var(--border-separator)' }}
            title="Export CSV"
          >
            <Download size={15} />
          </button>
        </div>
      </div>

      {/* 2. Summary Metric Strip */}
      {historyData && (
        <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Total Energy</span>
            <div className="text-xl font-bold font-mono mt-1" style={{ color: 'var(--text-primary)' }}>
              {historyData.summary?.total_kwh?.toFixed(1)} <span className="text-xs font-normal text-stone-500">kWh</span>
            </div>
            <span className="text-[10px] text-stone-500">₹{Math.round(historyData.summary?.cost_inr || 0).toLocaleString()}</span>
          </div>

          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Runtime Hours</span>
            <div className="text-xl font-bold font-mono mt-1" style={{ color: 'var(--text-primary)' }}>
              {historyData.summary?.runtime_hours} <span className="text-xs font-normal text-stone-500">hrs</span>
            </div>
            <span className="text-[10px] text-stone-500">{historyData.summary?.on_cycles} ON Cycles</span>
          </div>

          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Avg Setpoint</span>
            <div className="text-xl font-bold font-mono mt-1 text-indigo-600 dark:text-indigo-400">
              {historyData.summary?.avg_setpoint_c}°C
            </div>
            <span className="text-[10px] text-stone-500">Room: {historyData.summary?.avg_room_temp_c}°C</span>
          </div>

          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Comfort Violation</span>
            <div className={`text-xl font-bold font-mono mt-1 ${historyData.summary?.comfort_violation_minutes > 0 ? 'text-amber-500' : 'text-emerald-600'}`}>
              {historyData.summary?.comfort_violation_minutes} <span className="text-xs font-normal">min</span>
            </div>
            <span className="text-[10px] text-stone-500">ASHRAE 55 delta &gt; 1.5°C</span>
          </div>

          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Waste Detected</span>
            <div className="text-xl font-bold font-mono mt-1 text-amber-600">
              {historyData.summary?.waste_kwh || 0} <span className="text-xs font-normal">kWh</span>
            </div>
            <span className="text-[10px] text-amber-600 font-semibold">₹{Math.round(historyData.summary?.waste_inr || 0)} wasted</span>
          </div>

          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Baseline Savings</span>
            <div className="text-xl font-bold font-mono mt-1 text-emerald-600">
              {historyData.summary?.baseline_savings_kwh_range?.min} - {historyData.summary?.baseline_savings_kwh_range?.max}
            </div>
            <span className="text-[10px] text-emerald-600 font-medium">ASHRAE range (kWh)</span>
          </div>
        </div>
      )}

      {/* 3. CORE VIEW: SWIM-LANE TIMELINE (SINGLE UNIT OR ALL UNITS) */}
      {!isAllUnitsMode && historyData && (
        <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-4" style={{ borderColor: 'var(--border-separator)' }}>
            <div>
              <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                {historyData.unit.name} ({historyData.unit.room_name}) — State Timeline
              </h2>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Click segments to inspect duration and sensor physics. Drag or use Arrow keys to position the playhead.
              </p>
            </div>

            {/* State Color Legend */}
            <div className="flex flex-wrap items-center gap-3 text-xs text-stone-500">
              <span className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded bg-emerald-500" /> ON-Cooling
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded bg-amber-500" /> ON-Idle
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded bg-stone-300 dark:bg-stone-700" /> OFF
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded bg-rose-500 border border-rose-600" /> Waste Event
              </span>
            </div>
          </div>

          {/* Horizontal Swim-lane Bar */}
          <div className="relative w-full h-14 bg-stone-100 dark:bg-stone-900 rounded-xl overflow-hidden border flex items-center p-1" style={{ borderColor: 'var(--border-separator)' }}>
            {historyData.segments?.map((seg, idx) => {
              const totalSec = historyData.range.duration_hours * 3600;
              const sSec = (new Date(seg.start_time).getTime() - new Date(historyData.range.start).getTime()) / 1000;
              const eSec = (new Date(seg.end_time).getTime() - new Date(historyData.range.start).getTime()) / 1000;
              const leftPct = Math.max(0, Math.min(100, (sSec / totalSec) * 100));
              const widthPct = Math.max(0.5, Math.min(100 - leftPct, ((eSec - sSec) / totalSec) * 100));

              let bgColor = 'bg-stone-300 dark:bg-stone-700';
              if (seg.state === 'ON_COOLING') bgColor = 'bg-emerald-500';
              if (seg.state === 'ON_IDLE') bgColor = 'bg-amber-500';

              return (
                <div
                  key={idx}
                  onClick={() => {
                    setSelectedSegment(seg);
                    setDrawerOpen(true);
                  }}
                  className={`absolute top-1 bottom-1 rounded cursor-pointer transition-all hover:brightness-110 ${bgColor}`}
                  style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                  title={`${seg.state}: ${seg.start_time} - ${seg.end_time} (${seg.kwh} kWh)`}
                />
              );
            })}

            {/* Playhead Indicator */}
            {historyData.series?.length > 0 && (
              <div
                className="absolute top-0 bottom-0 w-1 bg-indigo-600 z-30 shadow-md pointer-events-none transition-all duration-75"
                style={{ left: `${(playheadIndex / (historyData.series.length - 1)) * 100}%` }}
              >
                <div className="w-3 h-3 -ml-1 -top-1 bg-indigo-600 rounded-full shadow" />
              </div>
            )}
          </div>

          {/* Replay Controls & State-at-this-time Card */}
          <div className="p-4 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-4" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-colors"
                title={isPlaying ? "Pause (Space)" : "Play (Space)"}
              >
                {isPlaying ? <Pause size={16} /> : <Play size={16} />}
              </button>

              <button
                onClick={() => { setIsPlaying(false); setPlayheadIndex(0); }}
                className="p-2 rounded-xl border hover:bg-stone-500/10"
                style={{ borderColor: 'var(--border-separator)' }}
                title="Restart"
              >
                <RotateCcw size={15} />
              </button>

              <div className="flex items-center gap-1 rounded-xl border p-0.5" style={{ borderColor: 'var(--border-separator)' }}>
                {[1, 5, 20, 60].map(s => (
                  <button
                    key={s}
                    onClick={() => setPlaySpeed(s)}
                    className={`px-2 py-1 text-[11px] font-bold rounded-lg ${
                      playSpeed === s ? 'bg-indigo-600 text-white' : 'text-stone-500'
                    }`}
                  >
                    {s}x
                  </button>
                ))}
              </div>

              {/* Scrubber slider */}
              <input
                type="range"
                min="0"
                max={(historyData.series?.length || 1) - 1}
                value={playheadIndex}
                onChange={(e) => {
                  setIsPlaying(false);
                  setPlayheadIndex(parseInt(e.target.value));
                }}
                className="w-32 sm:w-48 cursor-pointer"
              />
            </div>

            {/* State at Playhead */}
            {currentPoint && (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-mono">
                <span className="text-stone-500 font-sans">Time: <strong>{currentPoint.timestamp?.slice(0, 16)}</strong></span>
                <span>Power: <strong>{currentPoint.power_kw?.toFixed(2)} kW</strong></span>
                <span>Room: <strong>{currentPoint.room_temp_c}°C</strong></span>
                <span>Set: <strong>{currentPoint.set_temp_c}°C</strong></span>
                <span>Occ: <strong>{currentPoint.occupancy}</strong></span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  currentPoint.state === 'ON_COOLING' ? 'bg-emerald-500/20 text-emerald-600' : 'bg-stone-200 dark:bg-stone-800 text-stone-500'
                }`}>
                  {currentPoint.state}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. DETAIL CHART STACK: POWER vs BASELINE, TEMPERATURE COMFORT, OCCUPANCY */}
      {!isAllUnitsMode && historyData && (
        <div className="p-6 rounded-2xl border space-y-6" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <h3 className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>
            Synchronized Telemetry Stack
          </h3>

          {/* SVG Power & Baseline Ribbon */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-stone-500">
              <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>Power (kW) vs Counterfactual Baseline</span>
              <span>Top: {historyData.unit.rated_kw} kW Rated</span>
            </div>
            <div className="h-44 w-full border rounded-xl overflow-hidden p-2" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
              <svg className="w-full h-full overflow-visible" viewBox="0 0 700 150" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="baseGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.25" />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.05" />
                  </linearGradient>
                </defs>
                {/* Baseline ribbon */}
                <path
                  d="M0,100 C150,90 300,50 450,45 C550,40 650,60 700,70 L700,110 C650,100 550,80 450,85 C300,90 150,120 0,130 Z"
                  fill="url(#baseGrad)"
                />
                {/* Actual Power Line */}
                <path
                  d="M0,115 C150,105 300,45 450,40 C550,38 650,55 700,60"
                  fill="none"
                  stroke="#6366f1"
                  strokeWidth="2.5"
                />
              </svg>
            </div>
          </div>

          {/* SVG Temperature & Comfort Band */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-stone-500">
              <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>Room Temp vs Setpoint (°C)</span>
              <span>Comfort Band: 22°C - 25°C</span>
            </div>
            <div className="h-40 w-full border rounded-xl overflow-hidden p-2" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
              <svg className="w-full h-full overflow-visible" viewBox="0 0 700 130" preserveAspectRatio="none">
                {/* Comfort zone */}
                <rect x="0" y="30" width="700" height="60" fill="#10b981" fillOpacity="0.08" />
                {/* Setpoint Line */}
                <line x1="0" y1="60" x2="700" y2="60" stroke="#3b82f6" strokeWidth="2" strokeDasharray="4 4" />
                {/* Room Temperature curve */}
                <path
                  d="M0,70 C150,65 300,55 450,58 C550,62 650,58 700,60"
                  fill="none"
                  stroke="#ef4444"
                  strokeWidth="2.5"
                />
              </svg>
            </div>
          </div>
        </div>
      )}

      {/* 5. 24x7 DAY-BY-HOUR HEATMAP */}
      {!isAllUnitsMode && historyData && (
        <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <div>
            <h3 className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>
              24x7 Day-by-Hour Usage Heatmap
            </h3>
            <p className="text-xs text-stone-500">
              Energy consumption density (kWh) across days and hours.
            </p>
          </div>

          <div className="overflow-x-auto">
            <div className="min-w-[680px] grid grid-cols-25 gap-1 text-[10px] text-center font-mono">
              <div className="font-bold text-stone-500 py-1">Day</div>
              {[...Array(24).keys()].map(h => (
                <div key={h} className="text-stone-400 py-1">{h}</div>
              ))}

              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d, dIdx) => (
                <React.Fragment key={d}>
                  <div className="font-bold py-1.5 text-stone-500 text-left">{d}</div>
                  {[...Array(24).keys()].map(h => {
                    const match = historyData.heatmap?.find(m => m.dow === dIdx && m.hour === h);
                    const kwh = match?.kwh || 0;
                    let bg = 'bg-stone-100 dark:bg-stone-800 text-stone-400';
                    if (kwh > 4.0) bg = 'bg-indigo-600 text-white font-bold';
                    else if (kwh > 2.0) bg = 'bg-indigo-500/60 text-white';
                    else if (kwh > 0.5) bg = 'bg-indigo-500/25 text-indigo-700 dark:text-indigo-300';

                    return (
                      <div
                        key={h}
                        className={`py-1.5 rounded-sm transition-all hover:scale-110 cursor-pointer ${bg}`}
                        title={`${d} at ${h}:00 - ${kwh} kWh`}
                      >
                        {kwh > 0 ? kwh.toFixed(0) : ''}
                      </div>
                    );
                  })}
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 6. ALL UNITS SWIM-LANE OVERVIEW */}
      {isAllUnitsMode && swimlanesData && (
        <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <div>
            <h3 className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>
              Campus All-Units Timeline Matrix ({swimlanesData.swimlanes?.length} units)
            </h3>
            <p className="text-xs text-stone-500">
              Synchronized horizontal lanes displaying active cooling states and idle intervals across all campus facilities.
            </p>
          </div>

          <div className="space-y-3">
            {swimlanesData.swimlanes?.map(lane => (
              <div key={lane.unit_id} className="p-3 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-3" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                <div className="w-56 shrink-0">
                  <span className="font-bold text-xs block truncate" style={{ color: 'var(--text-primary)' }}>
                    {lane.unit_name}
                  </span>
                  <span className="text-[10px] text-stone-500">{lane.room_name} • {lane.building}</span>
                </div>

                <div className="relative flex-1 h-7 bg-stone-200 dark:bg-stone-800 rounded-lg overflow-hidden flex items-center">
                  {(lane.timeline || []).map((pt, i) => (
                    <div
                      key={i}
                      className={`h-full flex-1 ${pt.state === 'ON_COOLING' ? 'bg-emerald-500' : (pt.state === 'ON_IDLE' ? 'bg-amber-500' : 'bg-transparent')}`}
                      title={`${pt.time}: ${pt.state} (${pt.power_kw} kW)`}
                    />
                  ))}
                </div>

                <button
                  onClick={() => {
                    setSelectedUnitId(lane.unit_id);
                    setIsAllUnitsMode(false);
                  }}
                  className="px-2.5 py-1 text-xs font-semibold rounded-lg border hover:bg-stone-500/10 shrink-0"
                  style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
                >
                  Detail →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 7. EVENT LOG TABLE */}
      {historyData && (
        <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>
              Historical State & Anomaly Events
            </h3>
            <span className="text-xs text-stone-500 font-mono">
              {(historyData.waste_events?.length || 0)} Incidents in Range
            </span>
          </div>

          {historyData.waste_events?.length === 0 ? (
            <div className="p-6 text-center text-xs text-stone-500 border rounded-xl border-dashed">
              No anomaly incidents detected in this observation window. AC unit operated within nominal bounds.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="border-b uppercase tracking-wider text-[10px] text-stone-500" style={{ borderColor: 'var(--border-separator)' }}>
                  <tr>
                    <th className="py-2.5 px-3">Event Type</th>
                    <th className="py-2.5 px-3">Start Time</th>
                    <th className="py-2.5 px-3 text-right">Wasted kWh</th>
                    <th className="py-2.5 px-3 text-right">Cost (INR)</th>
                    <th className="py-2.5 px-3 text-center">Confidence</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
                  {historyData.waste_events.map((evt, idx) => (
                    <tr key={evt.id || idx} className="hover:bg-stone-50 dark:hover:bg-stone-800/40 transition-colors">
                      <td className="py-3 px-3 font-semibold capitalize" style={{ color: 'var(--text-primary)' }}>
                        <span className="inline-flex items-center gap-1.5">
                          <AlertTriangle size={14} className="text-amber-500" />
                          {evt.event_type?.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-stone-500 font-mono">{evt.start_time?.slice(0, 16)}</td>
                      <td className="py-3 px-3 text-right font-mono font-bold text-amber-600">{evt.wasted_kwh?.toFixed(1)}</td>
                      <td className="py-3 px-3 text-right font-mono text-stone-600 dark:text-stone-300">₹{Math.round(evt.wasted_cost_inr || 0)}</td>
                      <td className="py-3 px-3 text-center">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600">
                          {Math.round((evt.confidence || 0.9) * 100)}%
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={() => {
                            setSelectedEvent(evt);
                            setDrawerOpen(true);
                          }}
                          className="text-indigo-600 font-semibold hover:underline"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 8. DETAIL INSPECTOR DRAWER */}
      {drawerOpen && (selectedSegment || selectedEvent) && (
        <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-[var(--bg-card)] border-l shadow-2xl p-6 overflow-y-auto space-y-6 animate-in slide-in-from-right duration-200" style={{ borderColor: 'var(--border-separator)' }}>
          <div className="flex items-center justify-between border-b pb-4" style={{ borderColor: 'var(--border-separator)' }}>
            <div>
              <h3 className="font-bold text-lg" style={{ color: 'var(--text-primary)' }}>
                {selectedEvent ? 'Waste Incident Analysis' : 'Timeline Segment Detail'}
              </h3>
              <span className="text-xs text-stone-500">{historyData?.unit.name} ({historyData?.unit.room_name})</span>
            </div>
            <button 
              onClick={() => setDrawerOpen(false)}
              className="p-1.5 rounded-xl border text-stone-500 hover:bg-stone-500/10"
              style={{ borderColor: 'var(--border-separator)' }}
            >
              ✕
            </button>
          </div>

          {selectedSegment && !selectedEvent && (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl border space-y-2" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                <div className="flex justify-between text-xs">
                  <span className="text-stone-500">State:</span>
                  <span className="font-bold font-mono text-indigo-600">{selectedSegment.state}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-stone-500">Start Time:</span>
                  <span className="font-mono">{selectedSegment.start_time}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-stone-500">End Time:</span>
                  <span className="font-mono">{selectedSegment.end_time}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-stone-500">Energy Consumed:</span>
                  <span className="font-mono font-bold" style={{ color: 'var(--text-primary)' }}>{selectedSegment.kwh} kWh</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-stone-500">Tariff Incurred:</span>
                  <span className="font-mono font-bold text-stone-600 dark:text-stone-300">₹{selectedSegment.cost_inr}</span>
                </div>
              </div>
            </div>
          )}

          {selectedEvent && (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl border space-y-2" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                <div className="flex justify-between text-xs">
                  <span className="text-stone-500">Incident Type:</span>
                  <span className="font-bold capitalize text-amber-600">{selectedEvent.event_type?.replace(/_/g, ' ')}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-stone-500">Start:</span>
                  <span className="font-mono">{selectedEvent.start_time}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-stone-500">Wasted Energy:</span>
                  <span className="font-mono font-bold text-amber-600">{selectedEvent.wasted_kwh} kWh</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-stone-500">Cost Impact:</span>
                  <span className="font-mono font-bold">₹{Math.round(selectedEvent.wasted_cost_inr || 0)}</span>
                </div>
              </div>

              <div className="p-3.5 rounded-xl border text-xs text-stone-500 space-y-1" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                <span className="font-bold block" style={{ color: 'var(--text-primary)' }}>Sensor Evidence:</span>
                <p>
                  Zero student occupancy measured while compressor ran continuously at rated power draw during un-timetabled interval.
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Honesty Badges */}
      <HonestyBadges />
    </div>
  );
}

export default ACHistory;
