import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Play, Pause, RotateCcw, FastForward, SkipForward, SkipBack,
  Sliders, ShieldCheck, Download, Upload, BarChart3, Clock,
  Flame, Sun, AlertTriangle, CheckCircle2, ChevronDown, ChevronRight,
  TrendingDown, Info, RefreshCw, Zap, Users, ArrowUpRight, Eye
} from 'lucide-react';
import { Button } from '../ui/BaseComponents';

// Campus room metadata catalog
const ROOM_CATALOG = [
  { id: 'eng-101', name: 'Advanced Computing Lab', building: 'Engineering', type: 'Lab', cap: 40, kw: 5.0, crit: false },
  { id: 'eng-102', name: 'Software Engineering Lab', building: 'Engineering', type: 'Lab', cap: 35, kw: 4.5, crit: false },
  { id: 'eng-server', name: 'Central Server Room', building: 'Engineering', type: 'Server Room', cap: 5, kw: 6.5, crit: true },
  { id: 'sci-201', name: 'Organic Chemistry Lab', building: 'Science', type: 'Lab', cap: 30, kw: 4.0, crit: false },
  { id: 'sci-202', name: 'Physics Demo Hall', building: 'Science', type: 'Lecture Hall', cap: 120, kw: 10.0, crit: false },
  { id: 'adm-301', name: 'Senate Boardroom', building: 'Admin', type: 'Boardroom', cap: 25, kw: 3.5, crit: false },
  { id: 'adm-302', name: 'Principal Office', building: 'Admin', type: 'Office', cap: 10, kw: 2.5, crit: false },
  { id: 'lib-401', name: 'Library Reading Floor', building: 'Library', type: 'Library', cap: 150, kw: 12.0, crit: false }
];

export function SimulatorScreen({
  onNavigateRoom
}) {
  // Preset list & selected preset
  const [presets, setPresets] = useState([]);
  const [selectedPresetId, setSelectedPresetId] = useState('preset-normal');

  // Scenario Builder state
  const [scenarioName, setScenarioName] = useState('Typical Campus Academic Day');
  const [seed, setSeed] = useState(42);
  const [durationHours, setDurationHours] = useState(24);
  const [stepMinutes, setStepMinutes] = useState(5);
  const [scope, setScope] = useState('all'); // 'all' or 'single'
  const [selectedSingleRoom, setSelectedSingleRoom] = useState('eng-101');

  // Weather Profile
  const [weatherPreset, setWeatherPreset] = useState('typical');
  const [hourlyTemp, setHourlyTemp] = useState([
    23.2, 22.8, 22.5, 22.4, 23.0, 24.2, 26.0, 28.5,
    30.8, 32.5, 33.8, 34.6, 35.0, 34.8, 34.2, 33.1,
    31.5, 29.8, 28.2, 27.0, 26.1, 25.2, 24.5, 23.8
  ]);
  const [tempShift, setTempShift] = useState(0);

  // Occupancy & Schedules
  const [attendancePct, setAttendancePct] = useState(85);
  const [isHoliday, setIsHoliday] = useState(false);

  // Control Modes to run in parallel
  const [selectedModes, setSelectedModes] = useState([
    'no_control', 'manual_schedule', 'optimizer', 'optimizer_auto_off'
  ]);
  const [activeViewingMode, setActiveViewingMode] = useState('optimizer');
  const [approvalPolicy, setApprovalPolicy] = useState('auto_approve_rule_passed');

  // Fault & Decoy Injections
  const [injectGhostCooling, setInjectGhostCooling] = useState(false);
  const [injectAfterHours, setInjectAfterHours] = useState(false);
  const [injectOvercooling, setInjectOvercooling] = useState(false);
  const [injectDecoy, setInjectDecoy] = useState(false);

  // UI Accordion collapse states
  const [collapsedSections, setCollapsedSections] = useState({
    scope: false,
    weather: false,
    occupancy: true,
    control: false,
    faults: true,
    tariff: true
  });

  const toggleSection = (s) => setCollapsedSections(p => ({ ...p, [s]: !p[s] }));

  // Run execution state
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [runError, setRunError] = useState(null);

  // Playback timeline state
  const [isPlaying, setIsPlaying] = useState(false);
  const [playheadIndex, setPlayheadIndex] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(60); // 1x, 10x, 60x, 600x
  const [timelineRoomFilter, setTimelineRoomFilter] = useState('all'); // 'all' or room_id
  const [viewCompareMode, setViewCompareMode] = useState(false);

  const playbackTimerRef = useRef(null);

  // Fetch presets on load
  useEffect(() => {
    fetch('/api/ac/simulation/presets')
      .then(res => res.json())
      .then(data => {
        setPresets(data);
      })
      .catch(err => console.error('Failed to load presets', err));
  }, []);

  // Run initial default scenario on first mount
  useEffect(() => {
    executeSimulationRun();
  }, []);

  // Handle Preset selection
  const handleSelectPreset = (pId) => {
    setSelectedPresetId(pId);
    if (pId === 'preset-heatwave') {
      setScenarioName('Severe Summer Heatwave (+4.5°C)');
      setWeatherPreset('heatwave');
      setHourlyTemp([
        27.7, 27.3, 27.0, 26.9, 27.5, 28.7, 30.5, 33.0,
        35.3, 37.0, 38.3, 39.1, 39.5, 39.3, 38.7, 37.6,
        36.0, 34.3, 32.7, 31.5, 30.6, 29.7, 29.0, 28.3
      ]);
      setInjectGhostCooling(false);
      setInjectAfterHours(false);
    } else if (pId === 'preset-holiday') {
      setScenarioName('Campus Public Holiday');
      setIsHoliday(true);
      setWeatherPreset('typical');
      setInjectGhostCooling(false);
    } else if (pId === 'preset-after-hours') {
      setScenarioName('After-Hours Waste & Ghost Cooling Injections');
      setInjectGhostCooling(true);
      setInjectAfterHours(true);
      setInjectDecoy(true);
      setIsHoliday(false);
    } else if (pId === 'preset-server-stress') {
      setScenarioName('Central Server Room Invariant Test');
      setScope('single');
      setSelectedSingleRoom('eng-server');
      setWeatherPreset('heatwave');
    } else {
      setScenarioName('Typical Campus Academic Day');
      setWeatherPreset('typical');
      setHourlyTemp([
        23.2, 22.8, 22.5, 22.4, 23.0, 24.2, 26.0, 28.5,
        30.8, 32.5, 33.8, 34.6, 35.0, 34.8, 34.2, 33.1,
        31.5, 29.8, 28.2, 27.0, 26.1, 25.2, 24.5, 23.8
      ]);
      setScope('all');
      setIsHoliday(false);
      setInjectGhostCooling(false);
      setInjectAfterHours(false);
    }
  };

  // Execute Sandboxed Simulation Run
  const executeSimulationRun = async () => {
    setIsRunning(true);
    setRunError(null);
    setIsPlaying(false);

    const faults = [];
    if (injectGhostCooling) {
      faults.push({ room_id: 'eng-101', fault_type: 'ghost_cooling', start_hour: 13.0, duration_hours: 2.5, severity: 1.0 });
    }
    if (injectAfterHours) {
      faults.push({ room_id: 'adm-301', fault_type: 'after_hours', start_hour: 21.0, duration_hours: 5.0, severity: 1.0 });
    }
    if (injectOvercooling) {
      faults.push({ room_id: 'sci-201', fault_type: 'overcooling', start_hour: 10.0, duration_hours: 2.0, severity: 1.0 });
    }

    const decoys = [];
    if (injectDecoy) {
      decoys.push({ room_id: 'sci-201', decoy_type: 'late_lab_exception', start_hour: 18.0, duration_hours: 3.0, expected_headcount: 15 });
    }

    const payload = {
      name: scenarioName,
      seed: Number(seed),
      duration_hours: Number(durationHours),
      step_minutes: Number(stepMinutes),
      scope: scope,
      selected_rooms: scope === 'single' ? [selectedSingleRoom] : ROOM_CATALOG.map(r => r.id),
      weather: {
        preset: weatherPreset,
        hourly_temp: hourlyTemp.map(t => Number(t) + Number(tempShift)),
        events: []
      },
      occupancy: {
        attendance_pct: Number(attendancePct),
        events: []
      },
      is_holiday: isHoliday,
      control_modes: selectedModes,
      approval_policy: approvalPolicy,
      faults: faults,
      decoys: decoys,
      tariff: {
        standard_rate: 8.50,
        peak_rate: 10.50,
        peak_start_hour: 18.0,
        peak_end_hour: 22.0
      }
    };

    try {
      const res = await fetch('/api/ac/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Simulation execution failed');
      }

      const data = await res.json();
      setRunResult(data);
      setPlayheadIndex(0);
    } catch (e) {
      setRunError(e.message);
    } finally {
      setIsRunning(false);
    }
  };

  // Playback Animation loop
  useEffect(() => {
    if (!isPlaying || !runResult) {
      if (playbackTimerRef.current) clearInterval(playbackTimerRef.current);
      return;
    }

    const modeRes = runResult.modes[activeViewingMode];
    if (!modeRes || !modeRes.timeline_steps.length) return;

    const totalSteps = modeRes.timeline_steps.length;
    const intervalMs = Math.max(16, 1000 / (playbackSpeed / 2));

    playbackTimerRef.current = setInterval(() => {
      setPlayheadIndex(prev => {
        if (prev >= totalSteps - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, intervalMs);

    return () => {
      if (playbackTimerRef.current) clearInterval(playbackTimerRef.current);
    };
  }, [isPlaying, playbackSpeed, runResult, activeViewingMode]);

  // Export handler
  const handleExport = (fmt) => {
    if (!runResult) return;
    window.open(`/api/ac/simulation/runs/${runResult.run_id}/export/${fmt}?mode=${activeViewingMode}`, '_blank');
  };

  // Current active mode evaluation
  const activeModeEval = runResult?.modes?.[activeViewingMode];
  const steps = activeModeEval?.timeline_steps || [];
  const currentStep = steps[playheadIndex] || steps[0];

  // Campus mini heatmap rooms at current playhead
  const currentStepRooms = currentStep?.rooms || {};

  return (
    <div className="space-y-6 animate-in fade-in duration-300 max-w-[1800px] mx-auto">
      {/* 1. Header & Sandboxed Banner */}
      <div>
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-extrabold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                Scenario Lab & Simulation
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                100% Sandboxed
              </span>
            </div>
            <p className="text-xs sm:text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
              Design multi-room campus operating scenarios, run 24h physics simulations in &lt;1 sec, and evaluate control modes side-by-side.
            </p>
          </div>

          {/* Quick Presets Bar */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 max-w-full">
            <span className="text-xs font-semibold mr-1 text-stone-500 shrink-0">Presets:</span>
            {presets.map(p => (
              <button
                key={p.id}
                onClick={() => handleSelectPreset(p.id)}
                className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all shrink-0 cursor-pointer border ${
                  selectedPresetId === p.id
                    ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                    : 'bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 border-stone-200 dark:border-stone-700 hover:border-stone-400'
                }`}
              >
                {p.name.split(' (')[0]}
              </button>
            ))}
          </div>
        </div>

        {/* Isolation Invariant Banner */}
        <div
          className="mt-4 p-3 rounded-xl flex items-center justify-between text-xs border"
          style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}
        >
          <div className="flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
            <ShieldCheck size={16} className="text-emerald-500 shrink-0" />
            <span>
              <strong style={{ color: 'var(--text-primary)' }}>Simulation Invariant:</strong> Nothing here writes to live telemetry, waste events, schedules, proposals, or live MQTT channels.
            </span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => handleExport('csv')}
              disabled={!runResult}
              className="flex items-center gap-1 px-2.5 py-1 rounded border text-[11px] font-semibold cursor-pointer hover:bg-stone-100 dark:hover:bg-stone-800 disabled:opacity-40"
              style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
            >
              <Download size={12} />
              <span>CSV</span>
            </button>
            <button
              onClick={() => handleExport('json')}
              disabled={!runResult}
              className="flex items-center gap-1 px-2.5 py-1 rounded border text-[11px] font-semibold cursor-pointer hover:bg-stone-100 dark:hover:bg-stone-800 disabled:opacity-40"
              style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
            >
              <Download size={12} />
              <span>JSON</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main 2-Column Grid: Left Builder (4 cols) & Right Running Timeline + Results (8 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN: SCENARIO BUILDER */}
        <div
          className="lg:col-span-4 p-5 rounded-[5px] border shadow-xs space-y-4"
          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
        >
          <div className="flex items-center justify-between border-b pb-3" style={{ borderColor: 'var(--border-subtle)' }}>
            <div className="flex items-center gap-2">
              <Sliders size={16} style={{ color: 'var(--accent)' }} />
              <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
                Scenario Builder
              </h2>
            </div>
            <button
              onClick={() => setSeed(Math.floor(Math.random() * 9000) + 100)}
              className="text-xs text-blue-500 hover:underline flex items-center gap-1"
            >
              <RefreshCw size={11} />
              <span>Random Seed</span>
            </button>
          </div>

          {/* Scenario Name & Seed */}
          <div className="space-y-2">
            <div>
              <label className="text-xs font-semibold text-stone-500">Scenario Name</label>
              <input
                type="text"
                value={scenarioName}
                onChange={e => setScenarioName(e.target.value)}
                className="w-full text-xs font-semibold p-2 mt-1 rounded-lg border bg-stone-50 dark:bg-stone-900 border-stone-200 dark:border-stone-700"
                style={{ color: 'var(--text-primary)' }}
              />
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="font-semibold text-stone-500">Seed (Deterministic)</label>
                <input
                  type="number"
                  value={seed}
                  onChange={e => setSeed(e.target.value)}
                  className="w-full p-1.5 mt-1 rounded border bg-stone-50 dark:bg-stone-900 border-stone-200 dark:border-stone-700 font-mono"
                  style={{ color: 'var(--text-primary)' }}
                />
              </div>
              <div>
                <label className="font-semibold text-stone-500">Duration</label>
                <select
                  value={durationHours}
                  onChange={e => setDurationHours(Number(e.target.value))}
                  className="w-full p-1.5 mt-1 rounded border bg-stone-50 dark:bg-stone-900 border-stone-200 dark:border-stone-700 font-semibold"
                  style={{ color: 'var(--text-primary)' }}
                >
                  <option value={1}>1 Hour</option>
                  <option value={6}>6 Hours</option>
                  <option value={24}>24 Hours (Full Day)</option>
                  <option value={72}>72 Hours (3 Days)</option>
                  <option value={168}>168 Hours (7 Days)</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 1: Scope */}
          <div className="border rounded-xl p-3" style={{ borderColor: 'var(--border-subtle)', backgroundColor: 'var(--bg-well)' }}>
            <div
              onClick={() => toggleSection('scope')}
              className="flex items-center justify-between cursor-pointer text-xs font-bold select-none"
              style={{ color: 'var(--text-primary)' }}
            >
              <span>Scope: {scope === 'all' ? 'All Campus Rooms (8)' : selectedSingleRoom}</span>
              {collapsedSections.scope ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
            </div>

            {!collapsedSections.scope && (
              <div className="mt-3 space-y-2 text-xs">
                <div className="flex gap-2">
                  <button
                    onClick={() => setScope('all')}
                    className={`flex-1 py-1.5 rounded font-semibold border ${
                      scope === 'all' ? 'bg-blue-600 text-white border-blue-600' : 'border-stone-300 dark:border-stone-700'
                    }`}
                  >
                    All 8 Rooms
                  </button>
                  <button
                    onClick={() => setScope('single')}
                    className={`flex-1 py-1.5 rounded font-semibold border ${
                      scope === 'single' ? 'bg-blue-600 text-white border-blue-600' : 'border-stone-300 dark:border-stone-700'
                    }`}
                  >
                    Single Room
                  </button>
                </div>

                {scope === 'single' && (
                  <select
                    value={selectedSingleRoom}
                    onChange={e => setSelectedSingleRoom(e.target.value)}
                    className="w-full p-2 rounded border bg-stone-50 dark:bg-stone-900 border-stone-300 dark:border-stone-700"
                  >
                    {ROOM_CATALOG.map(r => (
                      <option key={r.id} value={r.id}>
                        {r.name} ({r.id}) {r.crit ? '⭐ [CRITICAL]' : ''}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}
          </div>

          {/* Section 2: Weather Curve Editor */}
          <div className="border rounded-xl p-3" style={{ borderColor: 'var(--border-subtle)', backgroundColor: 'var(--bg-well)' }}>
            <div
              onClick={() => toggleSection('weather')}
              className="flex items-center justify-between cursor-pointer text-xs font-bold select-none"
              style={{ color: 'var(--text-primary)' }}
            >
              <span>Weather: {weatherPreset.toUpperCase()} (Peak {Math.max(...hourlyTemp) + tempShift}°C)</span>
              {collapsedSections.weather ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
            </div>

            {!collapsedSections.weather && (
              <div className="mt-3 space-y-3 text-xs">
                <div>
                  <div className="flex justify-between text-stone-500 mb-1">
                    <span>Bulk Temperature Shift:</span>
                    <span className="font-mono font-bold">{tempShift > 0 ? `+${tempShift}` : tempShift}°C</span>
                  </div>
                  <input
                    type="range"
                    min="-5"
                    max="6"
                    step="0.5"
                    value={tempShift}
                    onChange={e => setTempShift(Number(e.target.value))}
                    className="w-full accent-blue-500 cursor-pointer"
                  />
                </div>

                {/* Mini SVG Hourly Temperature Curve */}
                <div className="p-2 rounded bg-stone-100 dark:bg-stone-900 border border-stone-200 dark:border-stone-800">
                  <div className="flex justify-between text-[10px] text-stone-400 mb-1 font-mono">
                    <span>00:00 ({(hourlyTemp[0] + tempShift).toFixed(1)}°C)</span>
                    <span>14:00 ({(hourlyTemp[14] + tempShift).toFixed(1)}°C)</span>
                    <span>23:00 ({(hourlyTemp[23] + tempShift).toFixed(1)}°C)</span>
                  </div>
                  <svg viewBox="0 0 100 24" className="w-full h-8 overflow-visible">
                    <polygon
                      points={`0,24 ${hourlyTemp.map((t, idx) => `${(idx / 23) * 100},${24 - Math.max(2, Math.min(22, (t + tempShift - 18) * 1.0))}`).join(' ')} 100,24`}
                      fill="rgba(245, 158, 11, 0.2)"
                    />
                    <polyline
                      points={hourlyTemp.map((t, idx) => `${(idx / 23) * 100},${24 - Math.max(2, Math.min(22, (t + tempShift - 18) * 1.0))}`).join(' ')}
                      fill="none"
                      stroke="#F59E0B"
                      strokeWidth="2"
                    />
                  </svg>
                </div>
              </div>
            )}
          </div>

          {/* Section 3: Control Modes Selection */}
          <div className="border rounded-xl p-3" style={{ borderColor: 'var(--border-subtle)', backgroundColor: 'var(--bg-well)' }}>
            <div
              onClick={() => toggleSection('control')}
              className="flex items-center justify-between cursor-pointer text-xs font-bold select-none"
              style={{ color: 'var(--text-primary)' }}
            >
              <span>Control Modes ({selectedModes.length} Active)</span>
              {collapsedSections.control ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
            </div>

            {!collapsedSections.control && (
              <div className="mt-3 space-y-2 text-xs">
                {[
                  { id: 'no_control', label: '1. No Control (Fixed 22°C Static Schedule)' },
                  { id: 'manual_schedule', label: '2. Manual Schedule (Timetable on/off)' },
                  { id: 'optimizer', label: '3. Optimizer (Precool + Setpoint + Flywheel)' },
                  { id: 'optimizer_auto_off', label: '4. Optimizer + Auto-Off When Empty' }
                ].map(m => (
                  <label key={m.id} className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={selectedModes.includes(m.id)}
                      onChange={e => {
                        if (e.target.checked) {
                          setSelectedModes([...selectedModes, m.id]);
                        } else {
                          if (selectedModes.length > 1) {
                            setSelectedModes(selectedModes.filter(x => x !== m.id));
                          }
                        }
                      }}
                      className="accent-blue-500 rounded"
                    />
                    <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{m.label}</span>
                  </label>
                ))}

                <div className="pt-2 border-t mt-2" style={{ borderColor: 'var(--border-subtle)' }}>
                  <label className="text-stone-500 block mb-1">Approval Policy in Simulation:</label>
                  <select
                    value={approvalPolicy}
                    onChange={e => setApprovalPolicy(e.target.value)}
                    className="w-full p-1.5 rounded border bg-stone-50 dark:bg-stone-900 border-stone-300 dark:border-stone-700"
                  >
                    <option value="auto_approve_rule_passed">Auto-approve Rule-Passed Only</option>
                    <option value="auto_approve_all">Auto-approve All Proposals</option>
                    <option value="reject_all">Reject All (Simulate Operator Veto)</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          {/* Section 4: Faults & Decoy Injections */}
          <div className="border rounded-xl p-3" style={{ borderColor: 'var(--border-subtle)', backgroundColor: 'var(--bg-well)' }}>
            <div
              onClick={() => toggleSection('faults')}
              className="flex items-center justify-between cursor-pointer text-xs font-bold select-none"
              style={{ color: 'var(--text-primary)' }}
            >
              <span>Faults & Decoy Injections ({injectGhostCooling ? 1 : 0 + injectAfterHours ? 1 : 0} Active)</span>
              {collapsedSections.faults ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
            </div>

            {!collapsedSections.faults && (
              <div className="mt-3 space-y-2 text-xs">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={injectGhostCooling}
                    onChange={e => setInjectGhostCooling(e.target.checked)}
                    className="accent-red-500 rounded"
                  />
                  <span>Inject Ghost Cooling in Lab 101 (13:00 - 15:30)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={injectAfterHours}
                    onChange={e => setInjectAfterHours(e.target.checked)}
                    className="accent-red-500 rounded"
                  />
                  <span>Inject After-Hours Overnight Leak in Boardroom</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={injectDecoy}
                    onChange={e => setInjectDecoy(e.target.checked)}
                    className="accent-blue-500 rounded"
                  />
                  <span>Authorized Decoy Event (Late Lab Study Session)</span>
                </label>
              </div>
            )}
          </div>

          {/* RUN BUTTON */}
          <Button
            variant="primary"
            size="lg"
            disabled={isRunning}
            onClick={executeSimulationRun}
            className="w-full font-bold justify-center shadow-md py-3 text-sm cursor-pointer"
          >
            {isRunning ? (
              <RefreshCw size={16} className="animate-spin mr-2" />
            ) : (
              <Zap size={16} className="mr-2 fill-current" />
            )}
            <span>{isRunning ? 'Simulating 24 Hours...' : 'Run Scenario Simulation'}</span>
          </Button>

          {runResult && (
            <div className="text-[11px] text-center text-stone-500 font-mono">
              Executed in {runResult.wall_clock_ms}ms · Hash: {runResult.state_hash.slice(0, 10)}
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: 24-HOUR RUNNING TIMELINE & RESULTS */}
        <div className="lg:col-span-8 space-y-6">
          {/* 1. PLAYBACK TIMELINE CONTROLLER */}
          <div
            className="p-5 rounded-[5px] border shadow-xs space-y-4"
            style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
          >
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b pb-3" style={{ borderColor: 'var(--border-subtle)' }}>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="w-10 h-10 rounded-full flex items-center justify-center bg-blue-600 hover:bg-blue-700 text-white font-bold cursor-pointer transition-all shadow-sm"
                  title={isPlaying ? 'Pause simulation' : 'Play simulation playback'}
                >
                  {isPlaying ? <Pause size={18} /> : <Play size={18} className="ml-0.5" fill="currentColor" />}
                </button>

                <div>
                  <div className="text-xl font-mono font-extrabold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                    {currentStep?.time_str || '00:00'}
                  </div>
                  <div className="text-[10px] text-stone-500 font-semibold uppercase tracking-wider">
                    Simulated Timeline Playhead
                  </div>
                </div>
              </div>

              {/* Mode Selector & Speed Selector */}
              <div className="flex items-center gap-2">
                <div className="flex items-center p-0.5 rounded-lg border bg-stone-100 dark:bg-stone-900 text-xs font-semibold" style={{ borderColor: 'var(--border-subtle)' }}>
                  {selectedModes.map(m => (
                    <button
                      key={m}
                      onClick={() => setActiveViewingMode(m)}
                      className={`px-2 py-1 rounded text-[11px] font-bold transition-all cursor-pointer ${
                        activeViewingMode === m
                          ? 'bg-white dark:bg-stone-800 text-blue-600 shadow-xs'
                          : 'text-stone-500 hover:text-stone-800 dark:hover:text-stone-200'
                      }`}
                    >
                      {m === 'no_control' ? 'No Ctrl' : m === 'manual_schedule' ? 'Manual' : m === 'optimizer' ? 'Optimizer' : 'Opt+AutoOff'}
                    </button>
                  ))}
                </div>

                <select
                  value={playbackSpeed}
                  onChange={e => setPlaybackSpeed(Number(e.target.value))}
                  className="p-1.5 rounded-lg border text-xs font-bold bg-stone-100 dark:bg-stone-900 border-stone-200 dark:border-stone-800"
                  style={{ color: 'var(--text-primary)' }}
                >
                  <option value={10}>10x</option>
                  <option value={60}>60x</option>
                  <option value={300}>300x</option>
                  <option value={600}>600x</option>
                </select>
              </div>
            </div>

            {/* Scrubber Range Slider */}
            <div>
              <div className="flex justify-between text-xs text-stone-400 font-mono mb-1">
                <span>00:00 (Start)</span>
                <span className="font-bold text-blue-500">Playhead: {currentStep?.time_str}</span>
                <span>24:00 (End)</span>
              </div>
              <input
                type="range"
                min="0"
                max={Math.max(0, steps.length - 1)}
                value={playheadIndex}
                onChange={e => setPlayheadIndex(Number(e.target.value))}
                className="w-full accent-blue-600 h-2 bg-stone-200 dark:bg-stone-800 rounded-lg cursor-pointer"
              />
            </div>

            {/* Playhead 'NOW' Status Card */}
            <div
              className="p-3.5 rounded-xl border grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs"
              style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}
            >
              <div>
                <span className="text-[10px] text-stone-500 uppercase font-semibold">Campus Load</span>
                <div className="text-base font-extrabold font-mono" style={{ color: 'var(--text-primary)' }}>
                  {currentStep?.campus_power_kw || 0} kW
                </div>
                <div className="text-[10px] text-stone-400">Baseline: {currentStep?.campus_baseline_kw} kW</div>
              </div>

              <div>
                <span className="text-[10px] text-stone-500 uppercase font-semibold">Ambient Outdoor</span>
                <div className="text-base font-extrabold font-mono text-amber-600">
                  {currentStep?.outdoor_temp_c || 0}°C
                </div>
                <div className="text-[10px] text-stone-400">Humidity: {currentStep?.outdoor_humidity_pct}%</div>
              </div>

              <div>
                <span className="text-[10px] text-stone-500 uppercase font-semibold">Active Tariff</span>
                <div className="text-base font-extrabold font-mono text-blue-600">
                  ₹{currentStep?.tariff_rate}/kWh
                </div>
                <div className="text-[10px] text-stone-400">{currentStep?.is_peak_tariff ? 'Peak Window (18-22h)' : 'Standard Window'}</div>
              </div>

              <div>
                <span className="text-[10px] text-stone-500 uppercase font-semibold">Cumulative Cost</span>
                <div className="text-base font-extrabold font-mono text-emerald-600">
                  ₹{currentStep?.campus_running_inr || 0}
                </div>
                <div className="text-[10px] text-stone-400">Energy: {currentStep?.campus_running_kwh} kWh</div>
              </div>
            </div>

            {/* Mini Campus Heatmap Tiles Updating Live with Playhead */}
            <div>
              <div className="flex items-center justify-between text-xs font-bold mb-2 text-stone-500">
                <span>Room State at Playhead ({currentStep?.time_str})</span>
                <span className="text-[10px] font-normal">Click room to inspect in Room Detail</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {ROOM_CATALOG.map(r => {
                  const rData = currentStepRooms[r.id] || {};
                  const isCooling = rData.state === 'cooling';
                  const isPrecool = rData.state === 'precool';
                  const isOff = rData.state === 'off' || !rData.state;

                  return (
                    <button
                      key={r.id}
                      onClick={() => onNavigateRoom?.(r.id)}
                      className="p-2 rounded-lg border text-left transition-all hover:border-blue-500 cursor-pointer"
                      style={{
                        backgroundColor: isCooling ? 'rgba(0, 98, 204, 0.08)' : isPrecool ? 'rgba(245, 158, 11, 0.08)' : 'var(--bg-card)',
                        borderColor: rData.waste_flag ? '#EF4444' : isCooling ? 'var(--accent)' : 'var(--border-subtle)'
                      }}
                    >
                      <div className="flex justify-between items-center text-[11px] font-bold">
                        <span className="truncate">{r.name.split(' ')[0]}</span>
                        <span className={`w-2 h-2 rounded-full ${rData.waste_flag ? 'bg-red-500 animate-ping' : isCooling ? 'bg-blue-500' : isPrecool ? 'bg-amber-500' : 'bg-stone-300'}`} />
                      </div>
                      <div className="text-xs font-mono font-extrabold mt-1">
                        {rData.room_temp_c || 24.0}°C · {rData.power_kw || 0} kW
                      </div>
                      <div className="text-[10px] text-stone-400 flex justify-between">
                        <span>Set: {rData.setpoint_c || 24}°C</span>
                        <span>{rData.occupancy || 0} occ</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Synced SVG Chart: Campus Power kW & Baseline kW across 24h with Vertical Playhead */}
            <div className="p-3 rounded-xl border bg-stone-50 dark:bg-stone-900/50" style={{ borderColor: 'var(--border-subtle)' }}>
              <div className="flex justify-between items-center text-xs font-bold text-stone-500 mb-2">
                <span>Campus Load Profile (24h)</span>
                <div className="flex items-center gap-3 text-[11px]">
                  <span className="flex items-center gap-1"><span className="w-2.5 h-0.5 bg-blue-600 inline-block" /> Actual Power</span>
                  <span className="flex items-center gap-1"><span className="w-2.5 h-0.5 bg-stone-400 inline-block stroke-dasharray" /> Counterfactual Baseline</span>
                </div>
              </div>

              <div className="relative h-28 w-full">
                <svg viewBox="0 0 100 50" preserveAspectRatio="none" className="w-full h-full overflow-visible">
                  {/* Grid Lines */}
                  <line x1="0" y1="12.5" x2="100" y2="12.5" stroke="rgba(128,128,128,0.15)" strokeWidth="0.5" />
                  <line x1="0" y1="25" x2="100" y2="25" stroke="rgba(128,128,128,0.15)" strokeWidth="0.5" />
                  <line x1="0" y1="37.5" x2="100" y2="37.5" stroke="rgba(128,128,128,0.15)" strokeWidth="0.5" />

                  {/* Baseline Polyline */}
                  {steps.length > 0 && (
                    <polyline
                      points={steps.map((s, idx) => `${(idx / (steps.length - 1)) * 100},${50 - Math.min(48, (s.campus_baseline_kw / 60.0) * 45)}`).join(' ')}
                      fill="none"
                      stroke="#9CA3AF"
                      strokeWidth="1"
                      strokeDasharray="2,2"
                    />
                  )}

                  {/* Power Polyline & Area */}
                  {steps.length > 0 && (
                    <>
                      <polygon
                        points={`0,50 ${steps.map((s, idx) => `${(idx / (steps.length - 1)) * 100},${50 - Math.min(48, (s.campus_power_kw / 60.0) * 45)}`).join(' ')} 100,50`}
                        fill="rgba(0, 98, 204, 0.15)"
                      />
                      <polyline
                        points={steps.map((s, idx) => `${(idx / (steps.length - 1)) * 100},${50 - Math.min(48, (s.campus_power_kw / 60.0) * 45)}`).join(' ')}
                        fill="none"
                        stroke="#0062CC"
                        strokeWidth="1.8"
                      />
                    </>
                  )}

                  {/* Vertical Moving Playhead Line */}
                  {steps.length > 0 && (
                    <line
                      x1={(playheadIndex / (steps.length - 1)) * 100}
                      y1="0"
                      x2={(playheadIndex / (steps.length - 1)) * 100}
                      y2="50"
                      stroke="#EF4444"
                      strokeWidth="1.5"
                    />
                  )}
                </svg>
              </div>
            </div>
          </div>

          {/* 2. RESULTS & COMPARISON EVALUATION */}
          {activeModeEval && (
            <div className="space-y-6">
              {/* Primary KPI Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-4 rounded-[5px] border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
                  <span className="text-[11px] font-semibold text-stone-500 uppercase tracking-wider">Total Energy</span>
                  <div className="text-2xl font-mono font-extrabold mt-1" style={{ color: 'var(--text-primary)' }}>
                    {activeModeEval.total_energy_kwh} <span className="text-xs font-bold text-stone-400">kWh</span>
                  </div>
                  <div className="text-[11px] text-stone-500 mt-1">Peak: {activeModeEval.peak_demand_kw} kW at {activeModeEval.peak_demand_time}</div>
                </div>

                <div className="p-4 rounded-[5px] border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
                  <span className="text-[11px] font-semibold text-stone-500 uppercase tracking-wider">Total Cost</span>
                  <div className="text-2xl font-mono font-extrabold mt-1 text-emerald-600">
                    ₹{activeModeEval.total_cost_inr}
                  </div>
                  <div className="text-[11px] text-stone-500 mt-1">Peak tariff: ₹{activeModeEval.peak_tariff_cost_inr}</div>
                </div>

                <div className="p-4 rounded-[5px] border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
                  <span className="text-[11px] font-semibold text-stone-500 uppercase tracking-wider">Energy Saved</span>
                  <div className="text-2xl font-mono font-extrabold mt-1 text-blue-600">
                    {activeModeEval.energy_saved_vs_no_control_kwh} <span className="text-xs font-bold text-stone-400">kWh</span>
                  </div>
                  <div className="text-[11px] text-emerald-600 font-bold mt-1">Saved: ₹{activeModeEval.cost_saved_vs_no_control_inr} vs baseline</div>
                </div>

                <div className="p-4 rounded-[5px] border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
                  <span className="text-[11px] font-semibold text-stone-500 uppercase tracking-wider">Comfort Health</span>
                  <div className="text-2xl font-mono font-extrabold mt-1 text-amber-600">
                    {activeModeEval.comfort_violation_minutes} <span className="text-xs font-bold text-stone-400">mins</span>
                  </div>
                  <div className="text-[11px] text-stone-500 mt-1">Worst deviation: {activeModeEval.worst_comfort_deviation_c}°C</div>
                </div>
              </div>

              {/* Savings Waterfall Breakdown */}
              <div
                className="p-5 rounded-[5px] border shadow-xs"
                style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
              >
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
                      Optimization Savings Waterfall
                    </h3>
                    <p className="text-xs text-stone-500">Decomposition of energy reduction mechanisms across the 24h run</p>
                  </div>
                  <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-500/15 text-blue-600">
                    Assumption: 4% savings / °C
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-3 rounded-xl border bg-stone-50 dark:bg-stone-900" style={{ borderColor: 'var(--border-subtle)' }}>
                    <span className="text-stone-500 font-semibold">Flywheel Coasting Shut-off</span>
                    <div className="text-lg font-mono font-extrabold text-blue-600 mt-1">
                      {activeModeEval.savings_waterfall?.shutoff_kwh || 0} kWh
                    </div>
                    <div className="text-[10px] text-stone-400">Thermal coasting 15m prior to class end</div>
                  </div>

                  <div className="p-3 rounded-xl border bg-stone-50 dark:bg-stone-900" style={{ borderColor: 'var(--border-subtle)' }}>
                    <span className="text-stone-500 font-semibold">Setpoint Relaxation (24.5°C)</span>
                    <div className="text-lg font-mono font-extrabold text-emerald-600 mt-1">
                      {activeModeEval.savings_waterfall?.setpoint_relax_kwh || 0} kWh
                    </div>
                    <div className="text-[10px] text-stone-400">Relaxed from 22.0°C within ASHRAE band</div>
                  </div>

                  <div className="p-3 rounded-xl border bg-stone-50 dark:bg-stone-900" style={{ borderColor: 'var(--border-subtle)' }}>
                    <span className="text-stone-500 font-semibold">Auto-Off When Empty</span>
                    <div className="text-lg font-mono font-extrabold text-indigo-600 mt-1">
                      {activeModeEval.savings_waterfall?.auto_off_kwh || 0} kWh
                    </div>
                    <div className="text-[10px] text-stone-400">Shutdown after 20m zero occupancy</div>
                  </div>

                  <div className="p-3 rounded-xl border bg-stone-50 dark:bg-stone-900" style={{ borderColor: 'var(--border-subtle)' }}>
                    <span className="text-stone-500 font-semibold">Dynamic Precooling</span>
                    <div className="text-lg font-mono font-extrabold text-amber-600 mt-1">
                      {activeModeEval.savings_waterfall?.precool_kwh || 0} kWh
                    </div>
                    <div className="text-[10px] text-stone-400">Off-peak precooling before heat peak</div>
                  </div>
                </div>
              </div>

              {/* Side-by-Side Control Modes Comparison Table */}
              <div
                className="p-5 rounded-[5px] border shadow-xs"
                style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
              >
                <h3 className="text-base font-bold mb-3" style={{ color: 'var(--text-primary)' }}>
                  Multi-Mode Side-by-Side Comparison
                </h3>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="border-b text-stone-400" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="pb-2 font-semibold">Control Mode</th>
                        <th className="pb-2 font-semibold font-mono">Total kWh</th>
                        <th className="pb-2 font-semibold font-mono">Cost (INR)</th>
                        <th className="pb-2 font-semibold font-mono">kWh Saved</th>
                        <th className="pb-2 font-semibold font-mono">INR Saved</th>
                        <th className="pb-2 font-semibold font-mono">Peak kW</th>
                        <th className="pb-2 font-semibold">Comfort Violations</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-200 dark:divide-stone-800">
                      {Object.values(runResult.modes).map(m => (
                        <tr
                          key={m.mode}
                          className={`transition-colors ${activeViewingMode === m.mode ? 'bg-blue-500/10 font-bold' : ''}`}
                        >
                          <td className="py-2.5 font-bold" style={{ color: 'var(--text-primary)' }}>{m.mode_label}</td>
                          <td className="py-2.5 font-mono">{m.total_energy_kwh}</td>
                          <td className="py-2.5 font-mono">₹{m.total_cost_inr}</td>
                          <td className="py-2.5 font-mono text-blue-600">{m.energy_saved_vs_no_control_kwh}</td>
                          <td className="py-2.5 font-mono text-emerald-600">₹{m.cost_saved_vs_no_control_inr}</td>
                          <td className="py-2.5 font-mono">{m.peak_demand_kw}</td>
                          <td className="py-2.5">
                            <span className={`px-2 py-0.5 rounded ${m.comfort_violation_minutes > 0 ? 'bg-amber-500/15 text-amber-600' : 'bg-emerald-500/15 text-emerald-600'}`}>
                              {m.comfort_violation_minutes} mins
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Per-Room Results Table */}
              <div
                className="p-5 rounded-[5px] border shadow-xs"
                style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
                    Per-Room Simulation Outcomes ({activeModeEval.mode_label})
                  </h3>
                  <span className="text-xs text-stone-500">Sorted by consumption</span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="border-b text-stone-400" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="pb-2 font-semibold">Room Name</th>
                        <th className="pb-2 font-semibold font-mono">Energy (kWh)</th>
                        <th className="pb-2 font-semibold font-mono">Cost (INR)</th>
                        <th className="pb-2 font-semibold font-mono">Peak kW</th>
                        <th className="pb-2 font-semibold font-mono">Wasted kWh</th>
                        <th className="pb-2 font-semibold">Comfort Violations</th>
                        <th className="pb-2 text-right">Inspect</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-200 dark:divide-stone-800">
                      {Object.values(activeModeEval.room_kpis || {}).map(rk => (
                        <tr key={rk.room_id} className="hover:bg-stone-50 dark:hover:bg-stone-900">
                          <td className="py-2 font-bold" style={{ color: 'var(--text-primary)' }}>
                            {rk.name} <span className="text-stone-400 font-normal">({rk.room_id})</span>
                          </td>
                          <td className="py-2 font-mono">{rk.total_kwh}</td>
                          <td className="py-2 font-mono">₹{rk.cost_inr}</td>
                          <td className="py-2 font-mono">{rk.peak_kw}</td>
                          <td className="py-2 font-mono text-amber-600">{rk.waste_kwh}</td>
                          <td className="py-2">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] ${rk.comfort_violation_mins > 0 ? 'bg-amber-500/15 text-amber-600' : 'bg-emerald-500/15 text-emerald-600'}`}>
                              {rk.comfort_violation_mins}m
                            </span>
                          </td>
                          <td className="py-2 text-right">
                            <button
                              onClick={() => onNavigateRoom?.(rk.room_id)}
                              className="text-blue-500 hover:underline flex items-center gap-0.5 ml-auto cursor-pointer"
                            >
                              <span>View</span>
                              <ArrowUpRight size={12} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
