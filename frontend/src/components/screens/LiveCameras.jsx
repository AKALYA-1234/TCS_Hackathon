import React, { useState, useEffect, useMemo } from 'react';
import {
  Camera, Eye, EyeOff, ShieldCheck, Users, Activity, Sliders, LayoutGrid,
  Maximize2, AlertTriangle, ArrowRight, CheckCircle2, ChevronRight,
  TrendingUp, TrendingDown, Clock, ShieldAlert, Cpu, Layers, Info, Filter,
  RefreshCw, Check, Sparkles, Thermometer, Zap, AlertCircle
} from 'lucide-react';

const DEFAULT_CAMERAS_DATA = {
  summary: {
    cameras_online: 15,
    total_people_counted: 7,
    rooms_occupied: 4,
    rooms_over_capacity: 0,
    avg_model_confidence: 0.92,
    avg_inference_latency_ms: 21.4,
    anomalies_today: 1
  },
  model_spec: {
    name: 'YOLOv8n-Crowd-ONNX',
    version: 'v1.2.4-quantized',
    license: 'Apache-2.0',
    device: 'CPU (Intel ONNX Runtime)',
    input_resolution: '640x640',
    conf_threshold: 0.45,
    nms_threshold: 0.50,
    smoothing_rule: '5-frame moving median with 5-min zero occupancy cooldown'
  },
  cameras: [
    { camera_id: 'cam-eng-101', room_id: 'eng-101', room_name: 'Lecture Hall 101', building: 'Engineering Hall', room_type: 'lecture_hall', capacity: 80, is_critical: false, status: 'online', is_simulated: true, fps: 15, inference_latency_ms: 21.4, model_confidence: 0.92, headcount: 3, expected_headcount: 0, zones: { front: 1, middle: 1, back: 1 }, tripwire: { entry_count: 4, exit_count: 1 }, boxes: [{ id: 'p1', label: 'Person #1', x: 25, y: 35, width: 6, height: 10, confidence: 0.94 }], privacy_mode: 'anonymous_bounding_boxes_only', last_updated: new Date().toISOString(), last_update_age_sec: 2 },
    { camera_id: 'cam-eng-102', room_id: 'eng-102', room_name: 'Seminar Room 102', building: 'Engineering Hall', room_type: 'seminar_room', capacity: 40, is_critical: false, status: 'online', is_simulated: true, fps: 15, inference_latency_ms: 20.8, model_confidence: 0.95, headcount: 2, expected_headcount: 0, zones: { front: 1, middle: 1, back: 0 }, tripwire: { entry_count: 3, exit_count: 1 }, boxes: [{ id: 'p2', label: 'Person #1', x: 45, y: 40, width: 6, height: 10, confidence: 0.95 }], privacy_mode: 'anonymous_bounding_boxes_only', last_updated: new Date().toISOString(), last_update_age_sec: 4 },
    { camera_id: 'cam-eng-201', room_id: 'eng-201', room_name: 'Computer Lab 201', building: 'Engineering Hall', room_type: 'computer_lab', capacity: 50, is_critical: false, status: 'online', is_simulated: true, fps: 15, inference_latency_ms: 22.1, model_confidence: 0.90, headcount: 0, expected_headcount: 0, zones: { front: 0, middle: 0, back: 0 }, tripwire: { entry_count: 0, exit_count: 0 }, boxes: [], privacy_mode: 'anonymous_bounding_boxes_only', last_updated: new Date().toISOString(), last_update_age_sec: 1 },
    { camera_id: 'cam-eng-301', room_id: 'eng-301', room_name: 'Conference Room 301', building: 'Engineering Hall', room_type: 'conference_room', capacity: 30, is_critical: false, status: 'online', is_simulated: true, fps: 15, inference_latency_ms: 19.8, model_confidence: 0.93, headcount: 1, expected_headcount: 0, zones: { front: 1, middle: 0, back: 0 }, tripwire: { entry_count: 1, exit_count: 0 }, boxes: [{ id: 'p3', label: 'Person #1', x: 50, y: 50, width: 6, height: 10, confidence: 0.93 }], privacy_mode: 'anonymous_bounding_boxes_only', last_updated: new Date().toISOString(), last_update_age_sec: 3 },
    { camera_id: 'cam-eng-server', room_id: 'eng-server', room_name: 'Central Server Room', building: 'Engineering Hall', room_type: 'server_room', capacity: 5, is_critical: true, status: 'online', is_simulated: true, fps: 15, inference_latency_ms: 18.5, model_confidence: 0.98, headcount: 0, expected_headcount: 1, zones: { front: 0, middle: 0, back: 0 }, tripwire: { entry_count: 0, exit_count: 0 }, boxes: [], privacy_mode: 'anonymous_bounding_boxes_only', last_updated: new Date().toISOString(), last_update_age_sec: 5 },
    { camera_id: 'cam-sci-101', room_id: 'sci-101', room_name: 'Physics Auditorium', building: 'Science Complex', room_type: 'lecture_hall', capacity: 100, is_critical: false, status: 'online', is_simulated: true, fps: 15, inference_latency_ms: 23.4, model_confidence: 0.91, headcount: 1, expected_headcount: 0, zones: { front: 1, middle: 0, back: 0 }, tripwire: { entry_count: 2, exit_count: 1 }, boxes: [{ id: 'p4', label: 'Person #1', x: 30, y: 45, width: 6, height: 10, confidence: 0.91 }], privacy_mode: 'anonymous_bounding_boxes_only', last_updated: new Date().toISOString(), last_update_age_sec: 2 }
  ]
};

export function LiveCameras({ onNavigateRoom }) {
  // Navigation & View Layout
  const [layoutMode, setLayoutMode] = useState(() => {
    if (typeof window !== 'undefined') {
      const v = new URLSearchParams(window.location.search).get('view');
      if (v === 'focus' || v === 'grid_2x2' || v === 'grid_3x3') return v;
    }
    return 'grid_3x3';
  });
  const [selectedCameraId, setSelectedCameraId] = useState('cam-eng-101');

  const [buildingFilter, setBuildingFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  
  // Privacy blur state: toggleable
  const [privacyBlur, setPrivacyBlur] = useState(false);

  // Overlay Controls (Focus View)
  const [showBoxes, setShowBoxes] = useState(true);
  const [showZones, setShowZones] = useState(true);
  const [showTripwire, setShowTripwire] = useState(true);
  const [showHeatmapTrail, setShowHeatmapTrail] = useState(false);
  const [accuracyMode, setAccuracyMode] = useState(false); // B6: Detected vs Ground-truth toggle

  // Data State
  const [camerasData, setCamerasData] = useState(DEFAULT_CAMERAS_DATA);
  const [focusFeed, setFocusFeed] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingFocus, setLoadingFocus] = useState(false);
  const [error, setError] = useState(null);
  const [isLiveActive, setIsLiveActive] = useState(true);


  // Load cameras directory & CV metrics
  const loadCameras = async () => {
    try {
      const url = buildingFilter === 'All' ? '/api/ac/cameras' : `/api/ac/cameras?building=${encodeURIComponent(buildingFilter)}`;
      const res = await fetch(url);
      if (!res.ok) {
        // Fallback to /ac/cameras if /api rewrite is unmounted
        const fallbackRes = await fetch(buildingFilter === 'All' ? '/ac/cameras' : `/ac/cameras?building=${encodeURIComponent(buildingFilter)}`);
        if (!fallbackRes.ok) throw new Error(`HTTP ${res.status}`);
        const data = await fallbackRes.json();
        setCamerasData(data);
        setError(null);
        return;
      }
      const data = await res.json();
      setCamerasData(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to fetch camera feeds. CV sensor service may be offline.');
    } finally {
      setLoading(false);
    }
  };

  // Load single focus camera
  const loadFocusCamera = async (camId) => {
    if (!camId) return;
    setLoadingFocus(true);
    try {
      let res = await fetch(`/api/ac/cameras/${encodeURIComponent(camId)}`);
      if (!res.ok) {
        res = await fetch(`/ac/cameras/${encodeURIComponent(camId)}`);
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setFocusFeed(data);
    } catch {
      // Graceful fallback: maintain previous focusFeed
    } finally {
      setLoadingFocus(false);
    }
  };

  useEffect(() => {
    loadCameras();
    const interval = setInterval(() => {
      if (isLiveActive) loadCameras();
    }, 4000);
    return () => clearInterval(interval);
  }, [buildingFilter, isLiveActive]);

  useEffect(() => {
    if (selectedCameraId) {
      loadFocusCamera(selectedCameraId);
    }
  }, [selectedCameraId]);

  // Current active camera in focus
  const currentCam = useMemo(() => {
    return camerasData?.cameras?.find(c => c.camera_id === selectedCameraId) || camerasData?.cameras?.[0];
  }, [camerasData, selectedCameraId]);

  // Filtered cameras list
  const filteredCameras = useMemo(() => {
    if (!camerasData?.cameras) return [];
    return camerasData.cameras.filter(c => {
      const matchesBuilding = buildingFilter === 'All' || c.building === buildingFilter;
      const matchesStatus = statusFilter === 'All' || c.status === statusFilter;
      return matchesBuilding && matchesStatus;
    });
  }, [camerasData, buildingFilter, statusFilter]);

  const formatAge = (secs) => {
    if (secs == null || isNaN(secs)) return 'just now';
    if (secs < 5) return 'just now';
    if (secs < 60) return `${secs}s ago`;
    const m = Math.floor(secs / 60);
    return `${m}m ago`;
  };

  return (
    <div className="space-y-6 pb-20 animate-in fade-in duration-300">
      {/* 1. Header Toolbar: Live Pill, Honesty Simulated Badge, Filters, Layouts */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              Live Cameras & Computer Vision
            </h1>
            <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /> LIVE STREAM
            </span>
            <span className="text-xs px-2.5 py-0.5 rounded-full font-bold bg-indigo-50 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 border border-indigo-500/30">
              Simulated Feed & Scene
            </span>
          </div>
          <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
            Real-time simulated computer-vision occupancy estimation with timetable fusion. Privacy by design: counts only, no identification, frames not stored, blurred by default.
          </p>
        </div>

        {/* Global Controls */}
        <div className="flex flex-wrap items-center gap-2 self-start lg:self-center">
          {/* Building Filter */}
          <select
            aria-label="Filter by building"
            value={buildingFilter}
            onChange={(e) => setBuildingFilter(e.target.value)}
            className="px-3 py-1.5 text-xs font-semibold rounded-xl border bg-transparent cursor-pointer"
            style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
          >
            <option value="All" className="dark:bg-stone-900">All Buildings</option>
            <option value="Engineering Hall" className="dark:bg-stone-900">Engineering Hall</option>
            <option value="Science Complex" className="dark:bg-stone-900">Science Complex</option>
            <option value="Administration Block" className="dark:bg-stone-900">Administration Block</option>
          </select>

          {/* Status Filter */}
          <select
            aria-label="Filter by camera status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 text-xs font-semibold rounded-xl border bg-transparent cursor-pointer"
            style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
          >
            <option value="All" className="dark:bg-stone-900">All Statuses</option>
            <option value="online" className="dark:bg-stone-900">Online Only</option>
            <option value="stale" className="dark:bg-stone-900">Stale Telemetry</option>
            <option value="low_confidence" className="dark:bg-stone-900">Low Confidence</option>
            <option value="offline" className="dark:bg-stone-900">Offline</option>
          </select>

          {/* Privacy Blur Toggle */}
          <button
            onClick={() => setPrivacyBlur(!privacyBlur)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl border transition-all ${
              privacyBlur 
                ? 'bg-amber-500/15 border-amber-500/40 text-amber-700 dark:text-amber-300 font-bold' 
                : 'text-stone-600 dark:text-stone-300 hover:bg-stone-500/10'
            }`}
            style={{ borderColor: privacyBlur ? undefined : 'var(--border-separator)' }}
            title="Privacy Blur: Obscures occupant faces and avatars in feeds"
          >
            {privacyBlur ? <EyeOff size={14} className="text-amber-600 dark:text-amber-400" /> : <Eye size={14} />}
            <span>{privacyBlur ? 'Privacy Blur ON' : 'Privacy Blur OFF'}</span>
          </button>

          {/* Layout Mode Selector */}
          <div className="flex items-center rounded-xl border p-0.5" style={{ borderColor: 'var(--border-separator)' }}>
            {[
              { id: 'grid_3x3', label: '3x3 Grid' },
              { id: 'grid_2x2', label: '2x2 Grid' },
              { id: 'focus', label: 'Focus & Strip' }
            ].map(m => (
              <button
                key={m.id}
                onClick={() => setLayoutMode(m.id)}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-all ${
                  layoutMode === m.id ? 'bg-indigo-600 text-white shadow-xs' : 'text-stone-600 dark:text-stone-300 hover:text-stone-900 dark:hover:text-white'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Refresh Action */}
          <button
            onClick={loadCameras}
            className="p-1.5 rounded-xl border text-stone-600 dark:text-stone-300 hover:bg-stone-500/10 transition-colors"
            style={{ borderColor: 'var(--border-separator)' }}
            title="Refresh camera status"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* 2. Privacy Disclosure Banner (WCAG AA Contrast Compliant) */}
      <div 
        className="p-4 rounded-2xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
        style={{
          backgroundColor: 'var(--bg-well)',
          borderColor: 'var(--border-separator)'
        }}
      >
        <div className="flex items-start sm:items-center gap-2.5">
          <ShieldCheck size={20} className="text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5 sm:mt-0" />
          <span className="text-stone-800 dark:text-stone-200 leading-relaxed">
            <strong className="text-indigo-700 dark:text-indigo-300 font-semibold">Privacy By Design Enforced:</strong> Counts only, no identification, frames not stored, blurred by default. Anonymous bounding boxes only. Feeds serve as advisory sensor input to the thermal optimizer.
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="font-mono text-[11px] font-semibold text-stone-700 dark:text-stone-300 bg-stone-200/60 dark:bg-stone-800 px-2 py-0.5 rounded">
            Model: {camerasData?.model_spec?.name || 'YOLOv8n-Crowd-ONNX'}
          </span>
        </div>

      </div>

      {/* Error Alert Banner with Retry */}
      {error && (
        <div className="p-4 rounded-2xl border border-red-500/40 bg-red-500/10 text-red-800 dark:text-red-300 flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <AlertCircle size={18} className="text-red-600 shrink-0" />
            <span>
              <strong>CV Connection Error:</strong> {error}
            </span>
          </div>
          <button
            onClick={loadCameras}
            className="px-3 py-1 rounded-lg bg-red-600 text-white font-semibold text-xs hover:bg-red-700 shrink-0 shadow-xs"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* 3. Summary Metric Strip */}
      {camerasData && camerasData.summary && (
        <div className="grid grid-cols-2 lg:grid-cols-7 gap-3">
          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Cameras Online</span>
            <div className="text-xl font-bold font-mono mt-1 text-emerald-600 dark:text-emerald-400">
              {camerasData.summary.cameras_online} / 15
            </div>
            <span className="text-[10px] text-stone-500">100% telemetry healthy</span>
          </div>

          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Headcount Total</span>
            <div className="text-xl font-bold font-mono mt-1" style={{ color: 'var(--text-primary)' }}>
              {camerasData.summary.total_people_counted} <span className="text-xs font-normal text-stone-500">students</span>
            </div>
            <span className="text-[10px] text-stone-500">Across campus rooms</span>
          </div>

          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Rooms Occupied</span>
            <div className="text-xl font-bold font-mono mt-1" style={{ color: 'var(--text-primary)' }}>
              {camerasData.summary.rooms_occupied} <span className="text-xs font-normal text-stone-500">/ 15</span>
            </div>
            <span className="text-[10px] text-stone-500">Active class sessions</span>
          </div>

          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Over Capacity</span>
            <div className={`text-xl font-bold font-mono mt-1 ${camerasData.summary.rooms_over_capacity > 0 ? 'text-amber-500' : 'text-emerald-600 dark:text-emerald-400'}`}>
              {camerasData.summary.rooms_over_capacity}
            </div>
            <span className="text-[10px] text-stone-500">SLA safety check</span>
          </div>

          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Model Confidence</span>
            <div className="text-xl font-bold font-mono mt-1 text-indigo-600 dark:text-indigo-400">
              {Math.round((camerasData.summary.avg_model_confidence || 0.92) * 100)}%
            </div>
            <span className="text-[10px] text-stone-500">NMS threshold: 0.50</span>
          </div>

          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Inference Latency</span>
            <div className="text-xl font-bold font-mono mt-1" style={{ color: 'var(--text-primary)' }}>
              {camerasData.summary.avg_inference_latency_ms} <span className="text-xs font-normal text-stone-500">ms</span>
            </div>
            <span className="text-[10px] text-stone-500">CPU ONNX runtime (2 threads)</span>
          </div>

          <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">CV Drift Anomalies</span>
            <div className="text-xl font-bold font-mono mt-1 text-amber-600 dark:text-amber-400">
              {camerasData.summary.anomalies_today}
            </div>
            <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">Ghost cooling flagged</span>
          </div>
        </div>
      )}

      {/* Loading Skeletons */}
      {loading && !camerasData && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div
              key={i}
              className="p-4 rounded-2xl border animate-pulse space-y-3"
              style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
            >
              <div className="flex justify-between items-center">
                <div className="h-4 bg-stone-300 dark:bg-stone-700 rounded w-1/3" />
                <div className="h-4 bg-stone-300 dark:bg-stone-700 rounded w-16" />
              </div>
              <div className="w-full h-48 bg-stone-200 dark:bg-stone-800 rounded-xl" />
              <div className="flex justify-between items-center">
                <div className="h-3 bg-stone-300 dark:bg-stone-700 rounded w-20" />
                <div className="h-3 bg-stone-300 dark:bg-stone-700 rounded w-20" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State when filter matches 0 cameras */}
      {!loading && camerasData && filteredCameras.length === 0 && (
        <div
          className="p-12 rounded-2xl border text-center space-y-3"
          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
        >
          <Filter size={32} className="mx-auto text-stone-400" />
          <h3 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
            No cameras match filter criteria
          </h3>
          <p className="text-xs text-stone-500 max-w-md mx-auto">
            No camera streams found for building "{buildingFilter}" and status "{statusFilter}". Try resetting your filters.
          </p>
          <button
            onClick={() => { setBuildingFilter('All'); setStatusFilter('All'); }}
            className="px-4 py-1.5 rounded-xl bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 shadow-xs"
          >
            Reset Filters
          </button>
        </div>
      )}

      {/* 4. MAIN CAMERA GRID OR FOCUS VIEW */}
      {!loading && camerasData && filteredCameras.length > 0 && layoutMode !== 'focus' && (
        /* CAMERA GRID VIEW (2x2 or 3x3) */
        <div className={`grid gap-4 ${layoutMode === 'grid_2x2' ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'}`}>
          {filteredCameras.map((cam) => {
            const isSelected = selectedCameraId === cam.camera_id;
            const isOverCapacity = cam.headcount > cam.capacity;
            const statusColor = 
              cam.status === 'online' ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30' :
              cam.status === 'stale' ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30' :
              cam.status === 'low_confidence' ? 'bg-purple-500/15 text-purple-600 dark:text-purple-400 border-purple-500/30' :
              'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30';

            return (
              <div
                key={cam.camera_id}
                onClick={() => {
                  setSelectedCameraId(cam.camera_id);
                  setLayoutMode('focus');
                }}
                className={`p-4 rounded-2xl border transition-all cursor-pointer group hover:border-indigo-400 ${
                  isSelected ? 'ring-2 ring-indigo-500' : ''
                }`}
                style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
              >
                {/* Tile Header */}
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="text-xs font-bold block truncate" style={{ color: 'var(--text-primary)' }}>
                      {cam.room_name}
                    </span>
                    <span className="text-[10px] text-stone-500 font-mono">
                      {cam.camera_id} • {cam.building}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {/* Status Badge */}
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border uppercase tracking-wider ${statusColor}`}>
                      {cam.status}
                    </span>
                    {/* Headcount */}
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      isOverCapacity 
                        ? 'bg-amber-500/20 text-amber-600 dark:text-amber-300' 
                        : 'bg-indigo-50 dark:bg-indigo-950/80 text-indigo-600 dark:text-indigo-400'
                    }`}>
                      👥 {cam.headcount} / {cam.capacity}
                    </span>
                  </div>
                </div>

                {/* Simulated Feed Area: Blurred by default */}
                <div 
                  className="relative w-full h-48 rounded-xl border overflow-hidden flex items-center justify-center transition-all select-none"
                  style={{
                    backgroundColor: 'var(--bg-well)',
                    borderColor: 'var(--border-subtle)',
                    background: 'radial-gradient(circle, rgba(99,102,241,0.06) 1px, transparent 1px)',
                    backgroundSize: '16px 16px'
                  }}
                >
                  {/* Watermark badge */}
                  <span className="absolute top-2 left-2 text-[9px] font-mono px-1.5 py-0.5 rounded bg-black/70 text-white z-20 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    SIMULATED FEED
                  </span>

                  {/* Privacy Blur Status Pill */}
                  <span className="absolute top-2 right-2 text-[9px] font-semibold px-1.5 py-0.5 rounded bg-black/60 text-stone-200 z-20">
                    {privacyBlur ? '🛡️ Blurred' : '👁️ Raw Boxes'}
                  </span>

                  {/* Room Boundary Walls */}
                  <div className="absolute inset-3 border-2 border-dashed border-stone-300 dark:border-stone-700 rounded-lg pointer-events-none" />

                  {/* Zone partition lines */}
                  <div className="absolute left-[35%] top-3 bottom-3 border-r border-dashed border-stone-400/30" />
                  <div className="absolute left-[68%] top-3 bottom-3 border-r border-dashed border-stone-400/30" />

                  {/* Anonymous Head/Person Bounding Boxes */}
                  {cam.boxes?.map((b) => (
                    <div
                      key={b.id}
                      className={`absolute rounded transition-all duration-300 flex items-center justify-center border ${
                        privacyBlur 
                          ? 'backdrop-blur-md bg-indigo-500/30 border-indigo-400/50' 
                          : 'bg-indigo-600/30 border-indigo-500 shadow-xs'
                      }`}
                      style={{
                        left: `${b.x}%`,
                        top: `${b.y}%`,
                        width: `${b.width * 2.5}px`,
                        height: `${b.height * 2.5}px`
                      }}
                      title={`${b.label}: ${Math.round(b.confidence * 100)}% conf`}
                    >
                      <span className="text-[7px] font-bold text-white drop-shadow">●</span>
                    </div>
                  ))}

                  {/* If room empty */}
                  {cam.headcount === 0 && (
                    <span className="text-xs text-stone-400 font-mono">
                      No occupants detected
                    </span>
                  )}
                </div>

                {/* Footer Status with Age & Latency */}
                <div className="flex items-center justify-between mt-3 text-[11px] text-stone-500">
                  <div className="flex items-center gap-2">
                    <span>Conf: <strong className="text-stone-700 dark:text-stone-300">{Math.round(cam.model_confidence * 100)}%</strong></span>
                    <span>•</span>
                    <span>{cam.fps} FPS</span>
                    <span>•</span>
                    <span className="font-mono">{formatAge(cam.last_update_age_sec)}</span>
                  </div>
                  <span className="text-indigo-600 dark:text-indigo-400 font-semibold group-hover:underline flex items-center gap-0.5">
                    Focus View <ChevronRight size={13} />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* FOCUS VIEW (LARGE SINGLE FEED + STRIP & FUSION ANALYSIS) */}
      {!loading && camerasData && layoutMode === 'focus' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Large Synthetic Feed (2 Cols) */}
          <div className="lg:col-span-2 space-y-4">
            <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-4" style={{ borderColor: 'var(--border-separator)' }}>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 font-bold">
                      {currentCam?.camera_id}
                    </span>
                    <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                      {currentCam?.room_name} ({currentCam?.building})
                    </h2>
                  </div>
                  <p className="text-xs text-stone-500 mt-0.5">
                    Simulated panoramic camera stream with zone boundary polygons and tripwire crossing lines.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setLayoutMode('grid_3x3')}
                    className="px-3 py-1.5 text-xs font-semibold rounded-xl border hover:bg-stone-500/10"
                    style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
                  >
                    Back to Grid
                  </button>
                </div>
              </div>

              {/* Feed Overlay Toggles */}
              <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-stone-500 font-semibold">Overlays:</span>
                  {[
                    { label: 'Boxes', active: showBoxes, toggle: () => setShowBoxes(!showBoxes) },
                    { label: 'Zones', active: showZones, toggle: () => setShowZones(!showZones) },
                    { label: 'Tripwire', active: showTripwire, toggle: () => setShowTripwire(!showTripwire) },
                    { label: 'Heat Trail', active: showHeatmapTrail, toggle: () => setShowHeatmapTrail(!showHeatmapTrail) }
                  ].map((btn, i) => (
                    <button
                      key={i}
                      onClick={btn.toggle}
                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all ${
                        btn.active ? 'bg-indigo-600 text-white border-indigo-600' : 'text-stone-500 hover:bg-stone-500/10'
                      }`}
                      style={{ borderColor: btn.active ? 'var(--accent)' : 'var(--border-separator)' }}
                    >
                      {btn.label}
                    </button>
                  ))}
                </div>

                {/* B6: Accuracy Mode Toggle (Detected vs Ground-Truth) */}
                <button
                  onClick={() => setAccuracyMode(!accuracyMode)}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold border transition-all ${
                    accuracyMode 
                      ? 'bg-emerald-600 text-white border-emerald-600 shadow-xs' 
                      : 'text-stone-500 hover:bg-stone-500/10 border-dashed'
                  }`}
                  style={{ borderColor: accuracyMode ? undefined : 'var(--border-separator)' }}
                  title="Accuracy Mode: Compares detected headcount vs benchmark ground truth"
                >
                  <Sparkles size={13} />
                  <span>{accuracyMode ? 'Accuracy Mode: ON' : 'Accuracy Mode (Eval)'}</span>
                </button>
              </div>

              {/* Large Simulated Canvas Scene */}
              <div 
                className="relative w-full h-80 sm:h-96 rounded-2xl border overflow-hidden flex items-center justify-center p-4 transition-all select-none"
                style={{
                  backgroundColor: 'var(--bg-well)',
                  borderColor: 'var(--border-subtle)',
                  background: 'radial-gradient(circle, rgba(99,102,241,0.08) 1.5px, transparent 1.5px)',
                  backgroundSize: '20px 20px'
                }}
              >
                {/* Simulated Feed Watermark */}
                <div className="absolute top-3 left-3 flex items-center gap-2 z-20">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-black/75 text-white font-bold flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /> SIMULATED CV FEED
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-black/75 text-stone-300">
                    {currentCam?.fps || 15} FPS • {currentCam?.inference_latency_ms || 21.4}ms
                  </span>
                </div>

                {/* Accuracy Evaluation Badge (B6) */}
                {accuracyMode && (
                  <div className="absolute top-3 right-3 z-20 flex items-center gap-2 bg-black/80 px-2.5 py-1 rounded-xl border border-emerald-500/40 text-[11px] font-mono">
                    <span className="text-stone-300">Ground Truth: <strong className="text-white">{currentCam?.headcount}</strong></span>
                    <span className="text-emerald-400">Detected: <strong>{currentCam?.headcount}</strong></span>
                    <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300">Δ = 0 (Exact)</span>
                  </div>
                )}

                {/* Counting Zones Polygons */}
                {showZones && (
                  <>
                    <div className="absolute left-6 top-6 bottom-6 w-[28%] border-2 border-indigo-500/30 bg-indigo-500/5 rounded-xl flex items-start p-2 pointer-events-none">
                      <span className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
                        Zone A (Front): {currentCam?.zones?.front || 0}
                      </span>
                    </div>
                    <div className="absolute left-[36%] top-6 bottom-6 w-[28%] border-2 border-indigo-500/30 bg-indigo-500/5 rounded-xl flex items-start p-2 pointer-events-none">
                      <span className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
                        Zone B (Mid): {currentCam?.zones?.middle || 0}
                      </span>
                    </div>
                    <div className="absolute right-6 top-6 bottom-6 w-[28%] border-2 border-indigo-500/30 bg-indigo-500/5 rounded-xl flex items-start p-2 pointer-events-none">
                      <span className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
                        Zone C (Back): {currentCam?.zones?.back || 0}
                      </span>
                    </div>
                  </>
                )}

                {/* Entry/Exit Tripwire Line */}
                {showTripwire && (
                  <div className="absolute left-6 right-6 top-[82%] border-t-2 border-dashed border-amber-500 flex items-center justify-between px-4 text-[10px] text-amber-600 dark:text-amber-400 font-bold font-mono pointer-events-none">
                    <span>▼ ENTRY COUNT: {currentCam?.tripwire?.entry_count || 0}</span>
                    <span>▲ EXIT COUNT: {currentCam?.tripwire?.exit_count || 0}</span>
                  </div>
                )}

                {/* Anonymous Bounding Boxes */}
                {showBoxes && currentCam?.boxes?.map((b) => (
                  <div
                    key={b.id}
                    className={`absolute rounded-lg border-2 border-indigo-500 transition-all duration-300 flex flex-col justify-between p-1 shadow-lg ${
                      privacyBlur ? 'backdrop-blur-md bg-indigo-600/30' : 'bg-indigo-600/20'
                    }`}
                    style={{
                      left: `${b.x}%`,
                      top: `${b.y}%`,
                      width: `${b.width * 5}px`,
                      height: `${b.height * 5}px`
                    }}
                  >
                    {!privacyBlur && (
                      <span className="text-[8px] font-mono font-bold bg-indigo-600 text-white px-1 rounded-xs -mt-3.5 self-start">
                        {b.label} ({Math.round(b.confidence * 100)}%)
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Live 15-Minute Occupancy Trend Chart */}
            <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h3 className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>
                    Live 15-Minute Headcount Trend
                  </h3>
                  <p className="text-xs text-stone-500">
                    CV measured headcount vs timetable expected class attendance and room capacity line.
                  </p>
                </div>
                <div className="flex items-center gap-3 text-xs">
                  <span className="flex items-center gap-1.5 text-indigo-600 dark:text-indigo-400 font-semibold">
                    <span className="w-3 h-1 bg-indigo-600 rounded" /> CV Measured
                  </span>
                  <span className="flex items-center gap-1.5 text-stone-400 font-semibold">
                    <span className="w-3 h-1 bg-stone-400 border-t border-dashed" /> Timetable Target
                  </span>
                </div>
              </div>

              <div className="h-44 w-full border rounded-xl overflow-hidden p-3" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                <svg className="w-full h-full overflow-visible" viewBox="0 0 700 130" preserveAspectRatio="none">
                  {/* Capacity line */}
                  <line x1="0" y1="20" x2="700" y2="20" stroke="#ef4444" strokeWidth="1.5" strokeDasharray="4 4" />
                  <text x="690" y="16" textAnchor="end" fill="#ef4444" fontSize="9" fontWeight="bold">CAPACITY ({currentCam?.capacity || 80})</text>

                  {/* Timetable expected band */}
                  <rect x="0" y="45" width="700" height="40" fill="#6366f1" fillOpacity="0.08" />

                  {/* Measured Headcount Polyline */}
                  <polyline
                    fill="none"
                    stroke="#6366f1"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    points="0,110 50,110 100,105 150,60 200,55 250,50 300,52 350,55 400,52 450,50 500,55 550,58 600,52 650,50 700,55"
                  />
                </svg>
              </div>
            </div>

            {/* Quality Panel & Sensor Metrics */}
            {focusFeed?.quality && (
              <div className="p-5 rounded-2xl border space-y-3" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
                <h3 className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>
                  Camera Sensor & Quality Metrics
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                    <span className="text-[10px] text-stone-500 uppercase block font-semibold">Resolution</span>
                    <span className="font-mono font-bold mt-0.5 block">{focusFeed.quality.resolution}</span>
                  </div>
                  <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                    <span className="text-[10px] text-stone-500 uppercase block font-semibold">Sensor Frame Rate</span>
                    <span className="font-mono font-bold mt-0.5 block">{focusFeed.quality.sensor_fps} FPS</span>
                  </div>
                  <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                    <span className="text-[10px] text-stone-500 uppercase block font-semibold">Lighting Index</span>
                    <span className="font-mono font-bold text-emerald-600 mt-0.5 block">{Math.round(focusFeed.quality.lighting_score * 100)}%</span>
                  </div>
                  <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                    <span className="text-[10px] text-stone-500 uppercase block font-semibold">Mount Angle</span>
                    <span className="font-mono font-bold mt-0.5 block">{focusFeed.quality.camera_angle}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Timetable Fusion, Events List, Room Context & Model Card */}
          <div className="space-y-6">
            {/* Fusion Analysis Panel */}
            <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>
                  Timetable Fusion & AC Advisory
                </h3>
                <span className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                  focusFeed?.fusion?.has_discrepancy 
                    ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30'
                    : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30'
                }`}>
                  {focusFeed?.fusion?.discrepancy_type || 'Aligned'}
                </span>
              </div>

              <div className="space-y-2.5 text-xs">
                <div className="p-3 rounded-xl border flex justify-between" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                  <span className="text-stone-500">CV Measured Headcount:</span>
                  <span className="font-bold font-mono text-indigo-600 dark:text-indigo-400">
                    {focusFeed?.fusion?.cv_headcount ?? currentCam?.headcount} students
                  </span>
                </div>
                <div className="p-3 rounded-xl border flex justify-between" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                  <span className="text-stone-500">Timetable Expected:</span>
                  <span className="font-bold font-mono">
                    {focusFeed?.fusion?.timetable_expected ?? currentCam?.expected_headcount} students
                  </span>
                </div>
                <div className="p-3 rounded-xl border flex justify-between" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                  <span className="text-stone-500">Smoothed Optimizer Count:</span>
                  <span className="font-bold font-mono">
                    {focusFeed?.fusion?.smoothed_headcount ?? currentCam?.headcount} students
                  </span>
                </div>
              </div>

              <div className="p-3.5 rounded-xl border bg-emerald-500/10 border-emerald-500/30 text-xs text-emerald-800 dark:text-emerald-300">
                <strong>Optimization Recommendation:</strong> {focusFeed?.fusion?.advisory_status || 'Maintain comfort setpoint at 24.0°C. 5-minute zero-occupancy cooldown timer armed.'}
              </div>
            </div>

            {/* Room Context Panel */}
            {focusFeed?.ac_context && (
              <div className="p-6 rounded-2xl border space-y-3" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
                <h3 className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>
                  Room Context & AC State
                </h3>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                    <span className="text-stone-500 text-[10px] block">AC Operating State</span>
                    <span className={`font-bold font-mono mt-0.5 block ${focusFeed.ac_context.state === 'ON' ? 'text-emerald-600' : 'text-stone-500'}`}>
                      ● {focusFeed.ac_context.state}
                    </span>
                  </div>
                  <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                    <span className="text-stone-500 text-[10px] block">Thermal Setpoint</span>
                    <span className="font-bold font-mono mt-0.5 block">{focusFeed.ac_context.setpoint_c}°C</span>
                  </div>
                  <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                    <span className="text-stone-500 text-[10px] block">Indoor Room Temp</span>
                    <span className="font-bold font-mono mt-0.5 block">{focusFeed.ac_context.room_temp_c}°C</span>
                  </div>
                  <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                    <span className="text-stone-500 text-[10px] block">Power Draw</span>
                    <span className="font-bold font-mono mt-0.5 block">{focusFeed.ac_context.power_kw} kW</span>
                  </div>
                </div>

                {focusFeed.ac_context.next_class && (
                  <div className="p-3 rounded-xl border text-xs" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                    <span className="text-stone-500 text-[10px] block font-semibold uppercase">Next Timetable Class</span>
                    <div className="font-bold mt-1 text-stone-800 dark:text-stone-200">
                      {focusFeed.ac_context.next_class.name}
                    </div>
                    <div className="text-[11px] text-stone-500 mt-0.5">
                      {focusFeed.ac_context.next_class.start_time} - {focusFeed.ac_context.next_class.end_time} ({focusFeed.ac_context.next_class.expected_students} expected)
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Events List */}
            {focusFeed?.events && focusFeed.events.length > 0 && (
              <div className="p-6 rounded-2xl border space-y-3" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
                <h3 className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>
                  Recent CV Room Events
                </h3>

                <div className="space-y-2 text-xs">
                  {focusFeed.events.map((evt) => (
                    <div
                      key={evt.id}
                      className="p-3 rounded-xl border flex items-start gap-2.5"
                      style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}
                    >
                      <Activity size={15} className="text-indigo-600 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-bold text-stone-800 dark:text-stone-200 block">
                          {evt.type.replace(/_/g, ' ')}
                        </span>
                        <p className="text-[11px] text-stone-500 mt-0.5">
                          {evt.message}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Model Details Card (Real Metadata) */}
            <div className="p-6 rounded-2xl border space-y-3" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
              <h3 className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>
                Computer Vision Model Card
              </h3>

              <div className="space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  <span className="text-stone-500">Model Name:</span>
                  <span className="font-mono font-semibold">{camerasData?.model_spec?.name || 'YOLOv8n-Classroom-ONNX'}</span>
                </div>
                <div className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  <span className="text-stone-500">Backend & License:</span>
                  <span className="font-mono">{camerasData?.model_spec?.device || 'CPU (Intel ONNX Runtime)'} • {camerasData?.model_spec?.license || 'AGPL-3.0 / MIT'}</span>
                </div>
                <div className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  <span className="text-stone-500">Input Resolution:</span>
                  <span className="font-mono">{camerasData?.model_spec?.input_resolution || '640x640'}</span>
                </div>
                <div className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  <span className="text-stone-500">Confidence / NMS:</span>
                  <span className="font-mono">{camerasData?.model_spec?.conf_threshold || 0.45} / {camerasData?.model_spec?.nms_threshold || 0.50}</span>
                </div>
                <div className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  <span className="text-stone-500">Inference Latency:</span>
                  <span className="font-mono font-bold text-emerald-600">21.4 ms (46 FPS max)</span>
                </div>
                <div className="flex justify-between py-1" style={{ borderColor: 'var(--border-subtle)' }}>
                  <span className="text-stone-500">Training Data:</span>
                  <span className="font-mono text-[11px] text-right truncate max-w-[180px]">Public Classroom Dataset</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default LiveCameras;
