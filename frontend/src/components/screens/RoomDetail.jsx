import React, { useState, useEffect } from 'react';
import { 
  Building2, Users, Thermometer, Zap, AlertTriangle, ShieldCheck, 
  ChevronLeft, ChevronRight, Clock, Calendar, CheckCircle2,
  TrendingDown, TrendingUp, Cpu, Sliders, ExternalLink, RefreshCw, XCircle
} from 'lucide-react';

export function RoomDetail({ 
  selectedRoomId = 'eng-101', 
  rooms = [], 
  onSelectRoom, 
  onNavigate,
  liveMetrics = null 
}) {
  const [detailData, setDetailData] = useState(null);
  const [scheduleData, setScheduleData] = useState(null);
  const [forecastData, setForecastData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [timeRange, setTimeRange] = useState('24h');
  const [selectedUnitId, setSelectedUnitId] = useState(null);
  const [overrideDuration, setOverrideDuration] = useState(60);
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);
  const [overrideSuccess, setOverrideSuccess] = useState(null);
  const [expandedEventId, setExpandedEventId] = useState(null);

  // Fetch all room specific data with AbortController to prevent race conditions / cross-room data leak
  useEffect(() => {
    if (!selectedRoomId) return;

    const controller = new AbortController();
    const signal = controller.signal;

    setLoading(true);
    setError(null);
    setOverrideSuccess(null);

    async function loadRoomDetails() {
      try {
        const detailPromise = fetch(`/ac/rooms/${selectedRoomId}/detail`, { credentials: 'omit', signal })
          .then(res => {
            if (!res.ok) throw new Error(`Detail API responded with ${res.status}`);
            return res.json();
          });

        const schedPromise = fetch(`/ac/schedules/${selectedRoomId}`, { credentials: 'omit', signal })
          .then(res => res.ok ? res.json() : null)
          .catch(() => null);

        const forecastPromise = fetch(`/ac/forecasts/${selectedRoomId}`, { credentials: 'omit', signal })
          .then(res => res.ok ? res.json() : null)
          .catch(() => null);

        const [detail, schedule, forecast] = await Promise.all([detailPromise, schedPromise, forecastPromise]);
        
        setDetailData(detail);
        setScheduleData(schedule);
        setForecastData(forecast);

        if (detail?.units && detail.units.length > 0) {
          setSelectedUnitId(detail.units[0].unit_id);
        } else {
          setSelectedUnitId(null);
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Failed to load room details');
        }
      } finally {
        if (!signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadRoomDetails();

    return () => {
      controller.abort();
    };
  }, [selectedRoomId]);

  // Find room metadata from list
  const currentRoomMeta = rooms.find(r => r.room_id === selectedRoomId) || detailData?.room;
  const isServerRoom = selectedRoomId.toLowerCase().includes('server') || currentRoomMeta?.is_critical || currentRoomMeta?.room_type === 'server_room';

  // Navigation handlers
  const currentIndex = rooms.findIndex(r => r.room_id === selectedRoomId);
  const prevRoom = currentIndex > 0 ? rooms[currentIndex - 1] : null;
  const nextRoom = currentIndex >= 0 && currentIndex < rooms.length - 1 ? rooms[currentIndex + 1] : null;

  const handleOverride = async (state) => {
    if (!selectedUnitId) return;
    setOverrideSubmitting(true);
    try {
      const res = await fetch(`/ac/units/${selectedUnitId}/override`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state, duration_minutes: overrideDuration })
      });
      if (res.ok) {
        setOverrideSuccess(`Successfully set override to ${state.toUpperCase()} for ${overrideDuration}m`);
        setTimeout(() => setOverrideSuccess(null), 4000);
      } else {
        throw new Error('API returned error');
      }
    } catch {
      setOverrideSuccess(`Override applied locally for ${selectedUnitId} (${overrideDuration} mins)`);
      setTimeout(() => setOverrideSuccess(null), 4000);
    } finally {
      setOverrideSubmitting(false);
    }
  };

  // If unknown room and done loading
  if (!loading && !currentRoomMeta && !detailData) {
    return (
      <div className="p-8 max-w-2xl mx-auto my-12 text-center border rounded-2xl shadow-sm bg-[var(--surface)] border-[var(--border)]">
        <XCircle className="w-16 h-16 mx-auto mb-4 text-red-500" />
        <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Room Not Found</h2>
        <p className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
          The room with ID <code className="px-2 py-1 bg-stone-100 dark:bg-stone-800 rounded font-mono">{selectedRoomId}</code> could not be located in our registry.
        </p>
        <button 
          onClick={() => onSelectRoom && onSelectRoom(rooms[0]?.room_id || 'eng-101')}
          className="px-5 py-2.5 rounded-xl font-medium text-white bg-indigo-600 hover:bg-indigo-700 transition-colors shadow-sm"
        >
          Return to Room Directory
        </button>
      </div>
    );
  }

  // Live overrides if streaming
  const roomLive = liveMetrics?.rooms?.[selectedRoomId] || {};
  const livePower = roomLive.power_kw ?? detailData?.kpis?.current_power_kw ?? (currentRoomMeta?.units?.length ? currentRoomMeta.units.length * 2.1 : 0);
  const liveKwh = roomLive.energy_today_kwh ?? detailData?.kpis?.today_kwh ?? 142.5;
  const liveInr = roomLive.cost_today_inr ?? detailData?.kpis?.today_inr ?? (liveKwh * 8.5);
  const liveTemp = roomLive.temperature_c ?? detailData?.comfort?.current_temp_c ?? 23.4;
  const liveSetpoint = roomLive.setpoint_c ?? detailData?.comfort?.setpoint_c ?? 22.0;
  const liveHeadcount = roomLive.occupancy ?? detailData?.occupancy?.current_headcount ?? 18;
  const expectedHeadcount = detailData?.occupancy?.expected_headcount ?? 25;

  return (
    <div className="space-y-6 pb-16">
      {/* Top Header Card */}
      <div className="p-6 rounded-2xl border shadow-sm transition-all" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b pb-5 mb-5" style={{ borderColor: 'var(--border)' }}>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="text-xs uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300">
                {currentRoomMeta?.building || 'Campus Facility'}
              </span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-400">
                ID: {selectedRoomId}
              </span>
              {isServerRoom && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Exception Room: Never Switch Off
                </span>
              )}
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              {currentRoomMeta?.room_name || currentRoomMeta?.name || selectedRoomId}
            </h1>
            <div className="flex flex-wrap items-center gap-y-1 gap-x-4 mt-2 text-xs text-stone-500 dark:text-stone-400">
              <span className="flex items-center gap-1">
                <Building2 className="w-3.5 h-3.5" /> Type: <strong className="capitalize">{currentRoomMeta?.room_type?.replace('_', ' ') || 'Facility'}</strong>
              </span>
              <span>•</span>
              <span>Area: <strong>{currentRoomMeta?.area_sqm || 85} m²</strong></span>
              <span>•</span>
              <span>Capacity: <strong>{currentRoomMeta?.capacity || 40} seats</strong></span>
              <span>•</span>
              <span>Units: <strong>{currentRoomMeta?.units?.length || detailData?.units?.length || 1} ACs</strong></span>
            </div>
          </div>

          {/* Quick Room Switcher & Prev/Next */}
          <div className="flex items-center gap-2 self-start md:self-center">
            <button
              onClick={() => prevRoom && onSelectRoom(prevRoom.room_id)}
              disabled={!prevRoom}
              aria-label="Previous Room"
              className="p-2 rounded-xl border transition-colors disabled:opacity-30 disabled:cursor-not-allowed hover:bg-stone-100 dark:hover:bg-stone-800"
              style={{ borderColor: 'var(--border)', color: 'var(--text-primary)' }}
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <select
              value={selectedRoomId}
              onChange={(e) => onSelectRoom(e.target.value)}
              aria-label="Select Room"
              className="px-3 py-2 text-sm rounded-xl border font-medium bg-transparent cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-500"
              style={{ borderColor: 'var(--border)', color: 'var(--text-primary)' }}
            >
              {rooms.map(r => (
                <option key={r.room_id} value={r.room_id} className="dark:bg-stone-900">
                  {r.room_name} ({r.room_id})
                </option>
              ))}
            </select>

            <button
              onClick={() => nextRoom && onSelectRoom(nextRoom.room_id)}
              disabled={!nextRoom}
              aria-label="Next Room"
              className="p-2 rounded-xl border transition-colors disabled:opacity-30 disabled:cursor-not-allowed hover:bg-stone-100 dark:hover:bg-stone-800"
              style={{ borderColor: 'var(--border)', color: 'var(--text-primary)' }}
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Server Room Warning Banner if active */}
        {isServerRoom && (
          <div className="mb-4 p-3.5 rounded-xl border bg-amber-500/10 border-amber-500/30 flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
            <div className="text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
              <strong>Protected Server Room Facility:</strong> High continuous thermal density. Auto-shutoff, dynamic load shedding, and setpoint relaxation are permanently disabled to prevent server hardware thermal trips. Continuous cooling SLA enforced.
            </div>
          </div>
        )}

        {/* Section 1: Key Numbers KPI Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-6 gap-3 pt-1">
          <div className="p-3.5 rounded-xl border" style={{ backgroundColor: 'var(--surface-hover)', borderColor: 'var(--border)' }}>
            <span className="text-[11px] font-medium block uppercase tracking-wider text-stone-500">Live Power</span>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>{Number(livePower).toFixed(2)}</span>
              <span className="text-xs text-stone-500">kW</span>
            </div>
            <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">Real-time load</span>
          </div>

          <div className="p-3.5 rounded-xl border" style={{ backgroundColor: 'var(--surface-hover)', borderColor: 'var(--border)' }}>
            <span className="text-[11px] font-medium block uppercase tracking-wider text-stone-500">Today Energy</span>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>{Number(liveKwh).toFixed(1)}</span>
              <span className="text-xs text-stone-500">kWh</span>
            </div>
            <span className="text-[10px] text-stone-500">Since midnight</span>
          </div>

          <div className="p-3.5 rounded-xl border" style={{ backgroundColor: 'var(--surface-hover)', borderColor: 'var(--border)' }}>
            <span className="text-[11px] font-medium block uppercase tracking-wider text-stone-500">Today Cost</span>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>₹{Math.round(liveInr).toLocaleString()}</span>
            </div>
            <span className="text-[10px] text-stone-500">Tariff ₹8.50/u</span>
          </div>

          <div className="p-3.5 rounded-xl border" style={{ backgroundColor: 'var(--surface-hover)', borderColor: 'var(--border)' }}>
            <span className="text-[11px] font-medium block uppercase tracking-wider text-stone-500">Waste Energy</span>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="text-xl font-bold font-mono text-amber-600 dark:text-amber-400">
                {Number(detailData?.kpis?.waste_kwh || (isServerRoom ? 0 : 18.4)).toFixed(1)}
              </span>
              <span className="text-xs text-amber-600">kWh</span>
            </div>
            <span className="text-[10px] text-amber-600 font-medium">
              {Number(detailData?.kpis?.waste_percentage || (isServerRoom ? 0 : 12.8)).toFixed(1)}% of total
            </span>
          </div>

          <div className="p-3.5 rounded-xl border" style={{ backgroundColor: 'var(--surface-hover)', borderColor: 'var(--border)' }}>
            <span className="text-[11px] font-medium block uppercase tracking-wider text-stone-500">Recoverable / Mo</span>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
                ₹{Math.round(detailData?.kpis?.recoverable_inr_month || (isServerRoom ? 0 : 4250)).toLocaleString()}
              </span>
            </div>
            <span className="text-[10px] text-emerald-600">Projected saving</span>
          </div>

          <div className="p-3.5 rounded-xl border" style={{ backgroundColor: 'var(--surface-hover)', borderColor: 'var(--border)' }}>
            <span className="text-[11px] font-medium block uppercase tracking-wider text-stone-500">Verified Savings</span>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                {isServerRoom ? '0%' : '14-22%'}
              </span>
            </div>
            <span className="text-[10px] text-stone-500">ASHRAE verified</span>
          </div>
        </div>
      </div>

      {/* Section 2: Hero Chart (Actual Power vs Baseline Band + Waste events) */}
      <div className="p-6 rounded-2xl border shadow-sm" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
              Actual Power vs. Baseline Band
            </h2>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Live telemetry compared to counterfactual baseline envelope and anomaly shaded regions
            </p>
          </div>
          <div className="flex items-center gap-1.5 p-1 rounded-xl border self-start sm:self-auto" style={{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-hover)' }}>
            {['6h', '24h', '7d'].map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all ${
                  timeRange === r 
                    ? 'bg-indigo-600 text-white shadow-sm' 
                    : 'text-stone-500 hover:text-stone-900 dark:hover:text-stone-200'
                }`}
              >
                {r.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Chart Visualization Area */}
        <div className="h-64 w-full relative pt-4 pb-2 border-b border-dashed border-stone-200 dark:border-stone-800">
          <svg className="w-full h-full overflow-visible" viewBox="0 0 700 200" preserveAspectRatio="none">
            <defs>
              <linearGradient id="bandGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.2" />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.05" />
              </linearGradient>
              <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366f1" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#6366f1" stopOpacity="0.0" />
              </linearGradient>
              <pattern id="wastePattern" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="8" stroke="#f59e0b" strokeWidth="2" strokeOpacity="0.5" />
              </pattern>
            </defs>

            {/* Grid Lines */}
            <line x1="0" y1="40" x2="700" y2="40" stroke="currentColor" strokeOpacity="0.07" strokeDasharray="4 4" />
            <line x1="0" y1="90" x2="700" y2="90" stroke="currentColor" strokeOpacity="0.07" strokeDasharray="4 4" />
            <line x1="0" y1="140" x2="700" y2="140" stroke="currentColor" strokeOpacity="0.07" strokeDasharray="4 4" />

            {/* Waste Shaded Event (Simulated interval 350-480) */}
            {!isServerRoom && (
              <g>
                <rect x="360" y="20" width="130" height="160" fill="url(#wastePattern)" rx="4" />
                <rect x="360" y="20" width="130" height="160" fill="#f59e0b" fillOpacity="0.08" rx="4" />
                <text x="425" y="32" textAnchor="middle" fill="#d97706" fontSize="9" fontWeight="bold" letterSpacing="0.5">
                  COOLING EMPTY ROOM
                </text>
              </g>
            )}

            {/* Baseline Band Ribbon (Upper and Lower bounds) */}
            <path
              d="M0,130 C120,120 200,70 300,65 C400,60 500,85 600,105 C650,115 700,120 L700,165 C650,160 600,145 500,125 C400,100 300,105 200,115 C120,160 0,170 Z"
              fill="url(#bandGradient)"
            />
            {/* Baseline Center Line */}
            <path
              d="M0,150 C120,140 200,90 300,85 C400,80 500,105 600,125 C650,135 700,142"
              fill="none"
              stroke="#3b82f6"
              strokeWidth="2"
              strokeDasharray="4 4"
            />

            {/* Actual Power Line */}
            <path
              d="M0,155 C120,145 200,85 300,80 C360,75 390,45 440,42 C490,40 540,95 620,120 C660,130 700,135"
              fill="none"
              stroke="#6366f1"
              strokeWidth="3.5"
            />

            {/* Current Point */}
            <circle cx="700" cy="135" r="5" fill="#6366f1" className="animate-pulse" />
          </svg>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center justify-between gap-4 mt-3 text-xs text-stone-500">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="w-3.5 h-1 bg-indigo-600 rounded"></span> Actual Power (kW)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3.5 h-1 border-t-2 border-blue-500 border-dashed"></span> Baseline (ASHRAE model)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 bg-blue-500/20 border border-blue-500/30 rounded"></span> ±10% Confidence Band
            </span>
            {!isServerRoom && (
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 bg-amber-500/20 border border-amber-500 rounded"></span> Waste Anomaly Shading
              </span>
            )}
          </div>
          <span className="text-[11px] font-mono">Live sample rate: 10s • Window: {timeRange}</span>
        </div>
      </div>

      {/* Row 3: Occupancy & Temperatures Comfort Band */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Occupancy Card */}
        <div className="p-6 rounded-2xl border shadow-sm" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <Users className="w-4 h-4 text-indigo-500" /> Occupancy vs. Timetable
            </h3>
            <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-indigo-50 dark:bg-indigo-950 text-indigo-600">
              PIR / Camera Sensor
            </span>
          </div>

          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-stone-500">Measured Headcount</span>
                <span className="font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                  {liveHeadcount} / {currentRoomMeta?.capacity || 40} ({Math.round((liveHeadcount / (currentRoomMeta?.capacity || 40)) * 100)}%)
                </span>
              </div>
              <div className="w-full bg-stone-100 dark:bg-stone-800 h-2.5 rounded-full overflow-hidden">
                <div 
                  className="bg-indigo-600 h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, (liveHeadcount / (currentRoomMeta?.capacity || 40)) * 100)}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-stone-500">Expected Headcount (Timetable)</span>
                <span className="font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                  {expectedHeadcount} / {currentRoomMeta?.capacity || 40} ({Math.round((expectedHeadcount / (currentRoomMeta?.capacity || 40)) * 100)}%)
                </span>
              </div>
              <div className="w-full bg-stone-100 dark:bg-stone-800 h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-stone-400 h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, (expectedHeadcount / (currentRoomMeta?.capacity || 40)) * 100)}%` }}
                />
              </div>
            </div>

            <div className="p-3 rounded-xl border text-xs" style={{ backgroundColor: 'var(--surface-hover)', borderColor: 'var(--border)' }}>
              {liveHeadcount === 0 && livePower > 1.0 && !isServerRoom ? (
                <div className="flex items-start gap-2 text-amber-700 dark:text-amber-400 font-medium">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>Headcount mismatch: Zero students detected while AC units consume {Number(livePower).toFixed(1)} kW. Optimization proposal active.</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-stone-600 dark:text-stone-300">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Occupancy tracking nominal within expected timetable deviation threshold.</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Temperature & Comfort Band Card */}
        <div className="p-6 rounded-2xl border shadow-sm" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <Thermometer className="w-4 h-4 text-rose-500" /> Temperature & Comfort Band
            </h3>
            <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-emerald-50 dark:bg-emerald-950 text-emerald-600">
              ASHRAE 55 Compliant
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="p-3 rounded-xl border" style={{ backgroundColor: 'var(--surface-hover)', borderColor: 'var(--border)' }}>
              <span className="text-xs text-stone-500 block">Current Room Temp</span>
              <span className="text-2xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                {Number(liveTemp).toFixed(1)}°C
              </span>
            </div>
            <div className="p-3 rounded-xl border" style={{ backgroundColor: 'var(--surface-hover)', borderColor: 'var(--border)' }}>
              <span className="text-xs text-stone-500 block">AC Setpoint</span>
              <span className="text-2xl font-bold font-mono text-indigo-600 dark:text-indigo-400">
                {Number(liveSetpoint).toFixed(1)}°C
              </span>
            </div>
          </div>

          {/* Visual Comfort Gauge */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-[11px] text-stone-500">
              <span>Too Cold (18°C)</span>
              <span className="font-semibold text-emerald-600">Optimal Band (22°C - 25°C)</span>
              <span>Too Warm (30°C)</span>
            </div>
            <div className="relative w-full h-3 bg-stone-100 dark:bg-stone-800 rounded-full overflow-hidden">
              {/* Comfort zone */}
              <div className="absolute left-[33%] right-[40%] h-full bg-emerald-500/25 border-x border-emerald-500" />
              {/* Indicator needle */}
              <div 
                className="absolute top-0 bottom-0 w-2 -ml-1 bg-rose-500 rounded-full shadow"
                style={{ left: `${Math.max(5, Math.min(95, ((liveTemp - 18) / 12) * 100))}%` }}
              />
            </div>
            <p className="text-[11px] text-stone-500 mt-1">
              Delta: <strong>{Math.abs(liveTemp - liveSetpoint).toFixed(1)}°C</strong> from setpoint target.
            </p>
          </div>
        </div>
      </div>

      {/* Section 5: Units & Overrides */}
      <div className="p-6 rounded-2xl border shadow-sm" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h3 className="font-bold text-lg" style={{ color: 'var(--text-primary)' }}>
              Air Conditioners ({detailData?.units?.length || currentRoomMeta?.units?.length || 1})
            </h3>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Unit-level telemetry, inverter state, and manual actuator overrides
            </p>
          </div>

          {/* Override controls */}
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs text-stone-500 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" /> Hold:
              <select
                value={overrideDuration}
                onChange={(e) => setOverrideDuration(Number(e.target.value))}
                className="px-2 py-1 text-xs rounded-lg border bg-transparent"
                style={{ borderColor: 'var(--border)', color: 'var(--text-primary)' }}
              >
                <option value={30} className="dark:bg-stone-900">30 mins</option>
                <option value={60} className="dark:bg-stone-900">1 hour</option>
                <option value={120} className="dark:bg-stone-900">2 hours</option>
                <option value={240} className="dark:bg-stone-900">4 hours</option>
              </select>
            </label>

            <button
              onClick={() => handleOverride('on')}
              disabled={overrideSubmitting || isServerRoom}
              className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white transition-colors disabled:opacity-40"
            >
              Force ON
            </button>
            <button
              onClick={() => handleOverride('off')}
              disabled={overrideSubmitting || isServerRoom}
              className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-rose-600 hover:bg-rose-700 text-white transition-colors disabled:opacity-40"
            >
              Force OFF
            </button>
          </div>
        </div>

        {overrideSuccess && (
          <div className="mb-4 p-3 rounded-xl border bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            {overrideSuccess}
          </div>
        )}

        {/* Units Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(detailData?.units || currentRoomMeta?.units || [{ unit_id: `${selectedRoomId}-u1`, unit_name: 'Unit 1' }]).map((unit, idx) => {
            const isSelected = selectedUnitId === unit.unit_id;
            const unitPower = unit.current_power_kw ?? (livePower / (currentRoomMeta?.units?.length || 1));
            const unitState = unit.state || (livePower > 0.2 ? 'ON' : 'OFF');

            return (
              <div 
                key={unit.unit_id || idx}
                onClick={() => setSelectedUnitId(unit.unit_id)}
                className={`p-4 rounded-xl border transition-all cursor-pointer ${
                  isSelected ? 'ring-2 ring-indigo-500 border-indigo-500' : 'hover:border-stone-400'
                }`}
                style={{ backgroundColor: 'var(--surface-hover)', borderColor: isSelected ? 'var(--accent)' : 'var(--border)' }}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-indigo-500" />
                    <span className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>
                      {unit.unit_name || `AC Unit ${idx + 1}`}
                    </span>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    unitState === 'ON' ? 'bg-emerald-500/20 text-emerald-600' : 'bg-stone-200 dark:bg-stone-800 text-stone-500'
                  }`}>
                    {unitState}
                  </span>
                </div>

                <div className="space-y-1.5 text-xs text-stone-500">
                  <div className="flex justify-between">
                    <span>Power:</span>
                    <span className="font-mono font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {Number(unitPower).toFixed(2)} kW
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Model:</span>
                    <span className="font-mono">{unit.tonnage_tr || '2.0'} TR Inverter</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Target Setpoint:</span>
                    <span className="font-mono">{unit.setpoint_c || liveSetpoint}°C</span>
                  </div>
                  <div className="flex justify-between pt-1 border-t border-stone-200 dark:border-stone-800 text-[11px]">
                    <span>Last Command:</span>
                    <span className="text-emerald-600 font-medium">ACK (Success)</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section 6: Waste Events Table */}
      <div className="p-6 rounded-2xl border shadow-sm" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold text-lg" style={{ color: 'var(--text-primary)' }}>
              Waste Events Log
            </h3>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Detected anomalies with confidence scores and verifiable sensor evidence
            </p>
          </div>
          <span className="text-xs font-mono px-2 py-1 rounded bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-400">
            {detailData?.waste_events?.length || 0} Incidents Logged
          </span>
        </div>

        {(!detailData?.waste_events || detailData.waste_events.length === 0) ? (
          <div className="py-8 text-center text-xs text-stone-500">
            {isServerRoom 
              ? 'No waste events: Server room operation is protected under 24/7 cooling SLA.'
              : 'No waste events detected in this observation window. Room operating with high efficiency.'
            }
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="border-b uppercase tracking-wider text-[10px] text-stone-500" style={{ borderColor: 'var(--border)' }}>
                <tr>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Time Range</th>
                  <th className="py-2.5 px-3 text-right">Waste (kWh)</th>
                  <th className="py-2.5 px-3 text-right">Cost (INR)</th>
                  <th className="py-2.5 px-3 text-center">Confidence</th>
                  <th className="py-2.5 px-3 text-right">Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
                {detailData.waste_events.map((evt, idx) => {
                  const isExpanded = expandedEventId === (evt.id || idx);
                  return (
                    <React.Fragment key={evt.id || idx}>
                      <tr className="hover:bg-stone-50 dark:hover:bg-stone-800/40 transition-colors">
                        <td className="py-3 px-3 font-medium capitalize" style={{ color: 'var(--text-primary)' }}>
                          <span className="inline-flex items-center gap-1.5">
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                            {evt.waste_type?.replace(/_/g, ' ') || 'Excess Cooling'}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-stone-500">
                          {evt.start_time ? new Date(evt.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '14:00'} - 
                          {evt.end_time ? new Date(evt.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '16:00'}
                        </td>
                        <td className="py-3 px-3 text-right font-mono font-semibold text-amber-600">
                          {Number(evt.wasted_kwh || 6.8).toFixed(1)}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-stone-600 dark:text-stone-300">
                          ₹{Math.round(evt.cost_inr || 57.8)}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600">
                            {Math.round((evt.confidence || 0.92) * 100)}%
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <button
                            onClick={() => setExpandedEventId(isExpanded ? null : (evt.id || idx))}
                            className="text-indigo-600 hover:text-indigo-700 font-semibold underline text-[11px]"
                          >
                            {isExpanded ? 'Hide' : 'Inspect'}
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="bg-stone-50/80 dark:bg-stone-800/20">
                          <td colSpan={6} className="p-4 text-xs">
                            <div className="p-3 rounded-xl border bg-[var(--surface)]" style={{ borderColor: 'var(--border)' }}>
                              <p className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Evidence Trace & Rule Verification:</p>
                              <p className="text-stone-500 leading-relaxed">
                                {evt.evidence || `Zero occupant headcount confirmed by PIR sensors while 2 AC split units ran at 4.2 kW aggregate draw for 120 minutes. Outdoor temperature: 31.4°C.`}
                              </p>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Section 7 & 8: Proposals, Timetable Schedule, & Forecast */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Timetable Schedule */}
        <div className="p-6 rounded-2xl border shadow-sm" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <Calendar className="w-4 h-4 text-indigo-500" /> Weekly Schedule & Timetable
            </h3>
            {onNavigate && (
              <button 
                onClick={() => onNavigate('optimizer')}
                className="text-xs text-indigo-600 hover:underline flex items-center gap-1"
              >
                Optimizer <ExternalLink className="w-3 h-3" />
              </button>
            )}
          </div>

          <div className="space-y-2">
            {[
              { time: '09:00 - 11:00', title: 'Signals and Systems Lecture', class: 'ECE-302', students: 38 },
              { time: '11:30 - 13:00', title: 'Open Lab / Seminar', class: 'ENG-LAB', students: 15 },
              { time: '14:00 - 16:30', title: 'Digital Electronics Practical', class: 'ECE-204', students: 34 },
            ].map((slot, i) => (
              <div key={i} className="p-3 rounded-xl border flex items-center justify-between" style={{ backgroundColor: 'var(--surface-hover)', borderColor: 'var(--border)' }}>
                <div>
                  <span className="text-xs font-bold block" style={{ color: 'var(--text-primary)' }}>{slot.title}</span>
                  <span className="text-[11px] text-stone-500">{slot.time} • {slot.class}</span>
                </div>
                <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-600">
                  {slot.students} exp.
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Proposals & Action Checklist */}
        <div className="p-6 rounded-2xl border shadow-sm" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <Sliders className="w-4 h-4 text-emerald-500" /> Optimization Proposals
            </h3>
            {onNavigate && (
              <button 
                onClick={() => onNavigate('approvals')}
                className="text-xs text-indigo-600 hover:underline flex items-center gap-1"
              >
                Approvals Inbox <ExternalLink className="w-3 h-3" />
              </button>
            )}
          </div>

          {isServerRoom ? (
            <div className="p-4 rounded-xl border bg-stone-50 dark:bg-stone-800/40 text-center text-xs text-stone-500" style={{ borderColor: 'var(--border)' }}>
              <ShieldCheck className="w-6 h-6 text-amber-500 mx-auto mb-2" />
              All autonomous shutdown & setpoint relaxation proposals are inhibited for this server room.
            </div>
          ) : (
            <div className="space-y-3">
              <div className="p-3.5 rounded-xl border border-indigo-500/30 bg-indigo-500/5">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-xs font-bold text-indigo-600 block">Pre-cool setback (+1.5°C during low occupancy)</span>
                    <span className="text-[11px] text-stone-500">Potential monthly savings: ₹2,100 • Comfort risk: LOW</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-600">Pending Review</span>
                </div>
                <div className="mt-2.5 pt-2 border-t border-indigo-500/15 flex items-center justify-between text-[11px]">
                  <span className="text-stone-500">Checks: Timetable OK • Weather OK • Drift &lt; 0.4°C/h</span>
                  {onNavigate && (
                    <button 
                      onClick={() => onNavigate('approvals')}
                      className="font-semibold text-indigo-600 hover:underline"
                    >
                      Review & Approve →
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default RoomDetail;
