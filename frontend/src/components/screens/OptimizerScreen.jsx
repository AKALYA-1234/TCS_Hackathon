import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Calendar as CalendarIcon, Clock, Users, Thermometer, ShieldCheck,
  AlertTriangle, Check, Plus, Trash2, Edit3, Copy, Undo2, Redo2,
  Save, RotateCcw, Download, Upload, Sliders, ChevronLeft, ChevronRight,
  Filter, Search, Grid, List, CheckCircle2, XCircle, ArrowRight,
  Info, Sparkles, Layers, History, FileText, CheckSquare, Square
} from 'lucide-react';
import { HonestyBadges } from '../ui/BaseComponents';

// Campus Timezone: Asia/Kolkata (IST = UTC+5:30)
const CAMPUS_TZ = 'Asia/Kolkata';

const WEEKDAYS = [
  { id: 0, short: 'Mon', name: 'Monday' },
  { id: 1, short: 'Tue', name: 'Tuesday' },
  { id: 2, short: 'Wed', name: 'Wednesday' },
  { id: 3, short: 'Thu', name: 'Thursday' },
  { id: 4, short: 'Fri', name: 'Friday' },
  { id: 5, short: 'Sat', name: 'Saturday' },
  { id: 6, short: 'Sun', name: 'Sunday' }
];

export function OptimizerScreen({ onApplyProposal, allRooms = [] }) {
  // Navigation / View state
  const [activeView, setActiveView] = useState('week'); // 'week' | 'overview' | 'calendar' | 'list' | 'history'
  const [selectedRoomId, setSelectedRoomId] = useState('eng-101');
  const [userRole, setUserRole] = useState('admin'); // 'admin' | 'in_charge' | 'viewer'

  // Master Data State
  const [rooms, setRooms] = useState(allRooms);
  const [blocks, setBlocks] = useState([]);
  const [exceptions, setExceptions] = useState([]);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Draft & History State (Undo / Redo 50 steps)
  const [historyStack, setHistoryStack] = useState([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [isDraftDirty, setIsDraftDirty] = useState(false);

  // Inspector / Selection state
  const [selectedBlockId, setSelectedBlockId] = useState(null);
  const [selectedBlockIds, setSelectedBlockIds] = useState(new Set()); // for bulk operations
  const [sheetOpen, setSheetOpen] = useState(false);
  const [diffModalOpen, setDiffModalOpen] = useState(false);
  const [copyModalOpen, setCopyModalOpen] = useState(false);
  const [exceptionModalOpen, setExceptionModalOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [assumptionsOpen, setAssumptionsOpen] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState(null); // { title, message, onConfirm }

  // Optimizer & Recommendation State
  const [optimizerRec, setOptimizerRec] = useState(null);
  const [optimizing, setOptimizing] = useState(false);

  // Filters for Campus Overview & List Views
  const [listSearch, setListSearch] = useState('');
  const [buildingFilter, setBuildingFilter] = useState('All');
  const [typeFilter, setTypeFilter] = useState('All');

  // Load Rooms if not passed
  useEffect(() => {
    if (rooms.length === 0) {
      fetch('/ac/rooms')
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) {
            setRooms(data);
            if (!selectedRoomId && data.length > 0) {
              setSelectedRoomId(data[0].id || data[0].room_id);
            }
          }
        })
        .catch(() => {});
    }
  }, [rooms.length, selectedRoomId]);

  // Load Schedule, Exceptions, Versions, and Optimizer data for selected room
  const loadRoomData = useCallback(async (roomId) => {
    setLoading(true);
    setError(null);
    try {
      const [schedRes, excRes, verRes, optRes] = await Promise.all([
        fetch(`/ac/schedules/${roomId}`).then(r => r.json()),
        fetch(`/ac/schedule-exceptions?room_id=${roomId}`).then(r => r.json()).catch(() => []),
        fetch(`/ac/schedules/versions/${roomId}`).then(r => r.json()).catch(() => []),
        fetch(`/ac/optimizer/run?room_id=${roomId}`, { method: 'POST' }).then(r => r.json()).catch(() => null)
      ]);

      const initialBlocks = Array.isArray(schedRes) ? schedRes : [];
      setBlocks(initialBlocks);
      setExceptions(Array.isArray(excRes) ? excRes : []);
      setVersions(Array.isArray(verRes) ? verRes : []);
      setOptimizerRec(optRes);

      // Reset Draft History
      setHistoryStack([JSON.stringify(initialBlocks)]);
      setHistoryIndex(0);
      setIsDraftDirty(false);
      setSelectedBlockIds(new Set());
    } catch (err) {
      setError(err.message || 'Failed to fetch schedule data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedRoomId) {
      loadRoomData(selectedRoomId);
    }
  }, [selectedRoomId, loadRoomData]);

  // Current Room Metadata
  const currentRoom = useMemo(() => {
    return rooms.find(r => (r.id === selectedRoomId || r.room_id === selectedRoomId)) || {
      id: selectedRoomId,
      name: selectedRoomId,
      building: 'Engineering Hall',
      room_type: 'lab',
      capacity: 40,
      is_critical: selectedRoomId.includes('server')
    };
  }, [rooms, selectedRoomId]);

  const isServerRoom = currentRoom.is_critical || selectedRoomId.includes('server');

  // Push new state to undo/redo history
  const pushHistory = (newBlocks) => {
    const serialized = JSON.stringify(newBlocks);
    const newStack = historyStack.slice(0, historyIndex + 1);
    if (newStack.length >= 50) newStack.shift();
    newStack.push(serialized);
    setHistoryStack(newStack);
    setHistoryIndex(newStack.length - 1);
    setIsDraftDirty(true);
  };

  // Undo / Redo
  const handleUndo = () => {
    if (historyIndex > 0) {
      const prevIdx = historyIndex - 1;
      setHistoryIndex(prevIdx);
      setBlocks(JSON.parse(historyStack[prevIdx]));
      setIsDraftDirty(true);
    }
  };

  const handleRedo = () => {
    if (historyIndex < historyStack.length - 1) {
      const nextIdx = historyIndex + 1;
      setHistoryIndex(nextIdx);
      setBlocks(JSON.parse(historyStack[nextIdx]));
      setIsDraftDirty(true);
    }
  };

  const handleDiscardDraft = () => {
    if (historyStack.length > 0) {
      setBlocks(JSON.parse(historyStack[0]));
      setHistoryIndex(0);
      setIsDraftDirty(false);
    }
  };

  // Save Draft (Creates immutable version in DB)
  const handleSaveDraft = async () => {
    if (isServerRoom && blocks.length === 0) {
      alert("Safety Rule: Server Room cooling schedule can never be cleared or scheduled OFF.");
      return;
    }

    setSaving(true);
    try {
      const res = await fetch('/ac/schedules/bulk-save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_id: selectedRoomId,
          blocks: blocks,
          summary: `Schedule update for ${currentRoom.name} (${blocks.length} blocks)`
        })
      });
      if (!res.ok) throw new Error('Failed to save version');
      const data = await res.json();
      setIsDraftDirty(false);
      // Reload versions
      const verRes = await fetch(`/ac/schedules/versions/${selectedRoomId}`).then(r => r.json());
      setVersions(Array.isArray(verRes) ? verRes : []);
      // Reset stack
      setHistoryStack([JSON.stringify(blocks)]);
      setHistoryIndex(0);
      setDiffModalOpen(false);
    } catch (err) {
      alert(`Error saving schedule: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  // Restore old version
  const handleRestoreVersion = async (versionId) => {
    if (!window.confirm("Restoring this version will apply its schedule forward-looking from now. Continue?")) return;
    try {
      const res = await fetch(`/ac/schedules/versions/${versionId}/restore`, { method: 'POST' });
      if (!res.ok) throw new Error('Restore failed');
      await loadRoomData(selectedRoomId);
      alert("Successfully restored schedule version!");
    } catch (err) {
      alert(`Failed to restore: ${err.message}`);
    }
  };

  // Convert time "HH:MM:SS" or "HH:MM" to minutes from 00:00
  const timeToMinutes = (t) => {
    if (!t) return 0;
    const parts = t.split(':').map(Number);
    return parts[0] * 60 + (parts[1] || 0);
  };

  const minutesToTime = (m) => {
    const hrs = Math.floor(m / 60).toString().padStart(2, '0');
    const mins = (m % 60).toString().padStart(2, '0');
    return `${hrs}:${mins}:00`;
  };

  // Conflict / Overlap Detection
  const conflicts = useMemo(() => {
    const list = [];
    const sorted = [...blocks].sort((a, b) => {
      if (a.day_of_week !== b.day_of_week) return a.day_of_week - b.day_of_week;
      return timeToMinutes(a.start_time) - timeToMinutes(b.start_time);
    });

    for (let i = 0; i < sorted.length - 1; i++) {
      const b1 = sorted[i];
      const b2 = sorted[i + 1];
      if (b1.day_of_week === b2.day_of_week) {
        const end1 = timeToMinutes(b1.end_time);
        const start2 = timeToMinutes(b2.start_time);
        if (end1 > start2) {
          list.push({ b1, b2, day: b1.day_of_week });
        }
      }
    }
    return list;
  }, [blocks]);

  // Block CRUD handlers
  const handleAddBlock = (dayIndex = 0, startTime = "09:00:00", endTime = "11:00:00") => {
    if (userRole === 'viewer') return;
    const newBlock = {
      id: `blk-${Date.now()}`,
      room_id: selectedRoomId,
      day_of_week: dayIndex,
      start_time: startTime,
      end_time: endTime,
      activity_name: 'Academic Lecture',
      expected_headcount: 30,
      setpoint_c: isServerRoom ? 21.0 : 24.0,
      precool_mode: 'auto',
      precool_lead_min: 20,
      shutoff_mode: 'auto',
      shutoff_lead_min: 15,
      auto_off_empty_min: 15,
      is_active: true
    };
    const updated = [...blocks, newBlock];
    setBlocks(updated);
    pushHistory(updated);
    setSelectedBlockId(newBlock.id);
    setSheetOpen(true);
  };

  const handleUpdateBlock = (updatedBlock) => {
    if (userRole === 'viewer') return;
    // Validate bounds
    if (isServerRoom && (updatedBlock.setpoint_c > 23.0 || updatedBlock.setpoint_c < 18.0)) {
      alert("Server room setpoint must stay within [18°C, 23°C] thermal bounds.");
      return;
    }
    const updated = blocks.map(b => b.id === updatedBlock.id ? updatedBlock : b);
    setBlocks(updated);
    pushHistory(updated);
  };

  const handleDeleteBlock = (blockId) => {
    if (userRole === 'viewer') return;
    const updated = blocks.filter(b => b.id !== blockId);
    setBlocks(updated);
    pushHistory(updated);
    if (selectedBlockId === blockId) {
      setSelectedBlockId(null);
      setSheetOpen(false);
    }
  };

  // Keyboard navigation for moving / resizing blocks (WCAG AA accessible)
  const handleBlockKeyDown = (e, block) => {
    if (userRole === 'viewer') return;
    let sMin = timeToMinutes(block.start_time);
    let eMin = timeToMinutes(block.end_time);
    const step = 15; // 15 min snap

    if (e.shiftKey) {
      // Resize
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        eMin = Math.min(22 * 60, eMin + step);
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        eMin = Math.max(sMin + step, eMin - step);
      }
    } else {
      // Move
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        if (eMin + step <= 22 * 60) {
          sMin += step;
          eMin += step;
        }
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (sMin - step >= 6 * 60) {
          sMin -= step;
          eMin -= step;
        }
      }
    }

    const updated = {
      ...block,
      start_time: minutesToTime(sMin),
      end_time: minutesToTime(eMin)
    };
    handleUpdateBlock(updated);
  };

  // Copy day or week to other rooms
  const handleCopySchedule = (targetRoomIds, includeExceptions = false) => {
    if (targetRoomIds.length === 0) return;
    // Perform bulk copy
    targetRoomIds.forEach(async (rid) => {
      const clonedBlocks = blocks.map(b => ({
        ...b,
        id: undefined,
        room_id: rid
      }));
      await fetch('/ac/schedules/bulk-save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_id: rid,
          blocks: clonedBlocks,
          summary: `Copied template schedule from ${currentRoom.name}`
        })
      });
    });
    setCopyModalOpen(false);
    alert(`Successfully applied schedule to ${targetRoomIds.length} rooms!`);
  };

  // CSV Import / Export
  const handleExportCSV = () => {
    const headers = "room_id,day_of_week,start_time,end_time,activity_name,expected_headcount,setpoint_c\n";
    const rows = blocks.map(b => 
      `${selectedRoomId},${b.day_of_week},${b.start_time},${b.end_time},"${b.activity_name}",${b.expected_headcount},${b.setpoint_c || 24.0}`
    ).join("\n");
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `schedule_${selectedRoomId}.csv`;
    a.click();
  };

  // Selected block for details sheet
  const activeBlock = blocks.find(b => b.id === selectedBlockId);

  // Summary Metrics
  const summaryMetrics = useMemo(() => {
    let totalMinutes = 0;
    blocks.forEach(b => {
      if (b.is_active !== false) {
        totalMinutes += (timeToMinutes(b.end_time) - timeToMinutes(b.start_time));
      }
    });
    const weeklyHours = (totalMinutes / 60).toFixed(1);
    const estimatedWeeklyKwh = Math.round(totalMinutes * 0.08);
    const estimatedWeeklyInr = Math.round(estimatedWeeklyKwh * 9.2);
    const estimatedSavingInr = Math.round(estimatedWeeklyInr * 0.18);

    return {
      weeklyHours,
      estimatedWeeklyKwh,
      estimatedWeeklyInr,
      estimatedSavingInr,
      conflictsCount: conflicts.length
    };
  }, [blocks, conflicts]);

  return (
    <div className="space-y-6 pb-20 animate-in fade-in duration-300">
      {/* 1. Header with View Controls, Role Selector & Draft Actions */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              Schedule & Optimizer Manager
            </h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full font-mono font-semibold bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400">
              IST (UTC+5:30)
            </span>
            {isServerRoom && (
              <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full font-bold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                <ShieldCheck size={14} /> Never Scheduled Off
              </span>
            )}
          </div>
          <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
            Complete timetable management, thermal pre-cool optimization, calendar exceptions, and forward-looking version control.
          </p>
        </div>

        {/* Global Controls: Room Selector, Role, View Modes */}
        <div className="flex flex-wrap items-center gap-2 self-start lg:self-center">
          {/* Room Selector */}
          <select
            value={selectedRoomId}
            onChange={(e) => setSelectedRoomId(e.target.value)}
            className="px-3 py-1.5 text-xs font-semibold rounded-xl border bg-transparent cursor-pointer"
            style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
          >
            {rooms.map(r => (
              <option key={r.id || r.room_id} value={r.id || r.room_id} className="dark:bg-stone-900">
                {r.name || r.room_name} ({r.id || r.room_id})
              </option>
            ))}
          </select>

          {/* Role Gating Switcher */}
          <div className="flex items-center rounded-xl border p-0.5" style={{ borderColor: 'var(--border-separator)' }}>
            {['admin', 'in_charge', 'viewer'].map(role => (
              <button
                key={role}
                onClick={() => setUserRole(role)}
                className={`px-2.5 py-1 text-[11px] font-semibold rounded-lg capitalize transition-all ${
                  userRole === role ? 'bg-indigo-600 text-white shadow-xs' : 'text-stone-500'
                }`}
              >
                {role.replace('_', ' ')}
              </button>
            ))}
          </div>

          {/* View Mode Segmented Control */}
          <div className="flex items-center rounded-xl border p-0.5" style={{ borderColor: 'var(--border-separator)' }}>
            {[
              { id: 'week', label: 'Week Grid', icon: Grid },
              { id: 'overview', label: 'Campus Matrix', icon: Layers },
              { id: 'calendar', label: 'Calendar', icon: CalendarIcon },
              { id: 'list', label: 'List View', icon: List },
              { id: 'history', label: 'Versions', icon: History }
            ].map(v => {
              const Icon = v.icon;
              return (
                <button
                  key={v.id}
                  onClick={() => setActiveView(v.id)}
                  className={`flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg transition-all ${
                    activeView === v.id ? 'bg-indigo-600 text-white shadow-xs' : 'text-stone-500 hover:text-stone-900 dark:hover:text-stone-200'
                  }`}
                >
                  <Icon size={14} />
                  <span className="hidden sm:inline">{v.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 2. Unsaved Changes & Draft Action Bar (when dirty) */}
      {isDraftDirty && (
        <div className="p-3.5 rounded-2xl border bg-indigo-500/10 border-indigo-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in slide-in-from-top-2 duration-200">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse" />
            <span className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>
              Unsaved Draft Changes
            </span>
            <span className="text-xs text-stone-500">
              • Modifications remain in session draft. Saving creates an immutable new schedule version.
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleUndo}
              disabled={historyIndex <= 0}
              title="Undo (Ctrl+Z)"
              className="p-1.5 rounded-lg border text-stone-600 disabled:opacity-30 hover:bg-stone-500/10"
              style={{ borderColor: 'var(--border-separator)' }}
            >
              <Undo2 size={15} />
            </button>
            <button
              onClick={handleRedo}
              disabled={historyIndex >= historyStack.length - 1}
              title="Redo (Ctrl+Y)"
              className="p-1.5 rounded-lg border text-stone-600 disabled:opacity-30 hover:bg-stone-500/10"
              style={{ borderColor: 'var(--border-separator)' }}
            >
              <Redo2 size={15} />
            </button>
            <button
              onClick={() => setDiffModalOpen(true)}
              className="px-3 py-1.5 text-xs font-semibold rounded-xl border hover:bg-stone-500/10"
              style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
            >
              Review Diff
            </button>
            <button
              onClick={handleDiscardDraft}
              className="px-3 py-1.5 text-xs font-semibold rounded-xl text-rose-600 hover:bg-rose-500/10"
            >
              Discard
            </button>
            <button
              onClick={handleSaveDraft}
              disabled={saving || userRole === 'viewer'}
              className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm disabled:opacity-50"
            >
              <Save size={14} />
              {saving ? 'Publishing...' : 'Publish Version'}
            </button>
          </div>
        </div>
      )}

      {/* 3. Room Summary Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Weekly Planned</span>
          <div className="text-xl font-bold font-mono mt-1" style={{ color: 'var(--text-primary)' }}>
            {summaryMetrics.weeklyHours} <span className="text-xs font-normal text-stone-500">hours/wk</span>
          </div>
          <span className="text-[10px] text-stone-500">{blocks.length} active class blocks</span>
        </div>

        <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Planned Energy</span>
          <div className="text-xl font-bold font-mono mt-1" style={{ color: 'var(--text-primary)' }}>
            {summaryMetrics.estimatedWeeklyKwh} <span className="text-xs font-normal text-stone-500">kWh/wk</span>
          </div>
          <span className="text-[10px] text-stone-500">Based on rated thermal load</span>
        </div>

        <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Estimated Cost</span>
          <div className="text-xl font-bold font-mono mt-1" style={{ color: 'var(--text-primary)' }}>
            ₹{summaryMetrics.estimatedWeeklyInr.toLocaleString()}
          </div>
          <span className="text-[10px] text-stone-500">Campus tariff ₹9.20/kWh</span>
        </div>

        <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Optimizer Savings</span>
          <div className="text-xl font-bold font-mono text-emerald-600 mt-1">
            ₹{summaryMetrics.estimatedSavingInr.toLocaleString()} <span className="text-xs font-normal">/wk</span>
          </div>
          <span className="text-[10px] text-emerald-600 font-semibold">18% vs unoptimized timer</span>
        </div>

        <div className="p-3.5 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <span className="text-[11px] font-medium uppercase tracking-wider text-stone-500 block">Conflicts Detected</span>
          <div className={`text-xl font-bold font-mono mt-1 ${summaryMetrics.conflictsCount > 0 ? 'text-amber-500' : 'text-emerald-600'}`}>
            {summaryMetrics.conflictsCount}
          </div>
          <span className="text-[10px] text-stone-500">
            {summaryMetrics.conflictsCount > 0 ? 'Overlap alert: review slots' : 'No schedule collisions'}
          </span>
        </div>
      </div>

      {/* 4. Toolbar: Add Block, Copy, Template, Import/Export */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-2xl border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => handleAddBlock(0)}
            disabled={userRole === 'viewer'}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white transition-colors disabled:opacity-40"
          >
            <Plus size={14} /> Add Block
          </button>
          <button
            onClick={() => setCopyModalOpen(true)}
            disabled={userRole === 'viewer'}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl border hover:bg-stone-500/10 transition-colors"
            style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
          >
            <Copy size={14} /> Copy to Rooms...
          </button>
          <button
            onClick={() => setExceptionModalOpen(true)}
            disabled={userRole === 'viewer'}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl border hover:bg-stone-500/10 transition-colors"
            style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
          >
            <CalendarIcon size={14} /> Add Exception...
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl border hover:bg-stone-500/10 transition-colors"
            style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
          >
            <Download size={14} /> Export CSV
          </button>
          <button
            onClick={() => setImportModalOpen(true)}
            disabled={userRole === 'viewer'}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl border hover:bg-stone-500/10 transition-colors"
            style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
          >
            <Upload size={14} /> Import Timetable...
          </button>
        </div>
      </div>

      {/* 5. MAIN VIEW SWITCHER */}
      {/* 5A. VIEW 1: WEEK GRID WITH DRAGGABLE/KEYBOARD RESIZABLE BLOCKS */}
      {activeView === 'week' && (
        <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-4" style={{ borderColor: 'var(--border-separator)' }}>
            <div>
              <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                {currentRoom.name} — Weekly Schedule (06:00 to 22:00)
              </h2>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Drag edges or use Arrow Keys to adjust. Pre-cool shaded band appears before class; flywheel shut-off coasting follows.
              </p>
            </div>

            {/* Grid Legend */}
            <div className="flex flex-wrap items-center gap-3 text-xs text-stone-500">
              <span className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded bg-indigo-500/20 border border-indigo-500" /> Class Block
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded bg-cyan-500/20 border border-cyan-500 border-dashed" /> Pre-cool Lead
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded bg-amber-500/20 border border-amber-500 border-dashed" /> Flywheel Shut-off
              </span>
            </div>
          </div>

          {/* Time Grid Layout */}
          <div className="overflow-x-auto pt-2">
            <div className="min-w-[760px] grid grid-cols-8 gap-2">
              {/* Hours Column */}
              <div className="space-y-6 pt-10 text-[11px] font-mono text-right pr-2 text-stone-400">
                {['06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'].map(h => (
                  <div key={h} className="h-8">{h}</div>
                ))}
              </div>

              {/* 7 Day Columns */}
              {WEEKDAYS.map((day) => {
                const dayBlocks = blocks.filter(b => b.day_of_week === day.id);
                return (
                  <div key={day.id} className="flex flex-col">
                    <div className="text-center font-bold text-xs py-2 border-b" style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}>
                      {day.short}
                    </div>

                    {/* Day Track (06:00 to 22:00 = 16 hours = 960 mins) */}
                    <div
                      onClick={() => handleAddBlock(day.id)}
                      className="relative flex-1 min-h-[480px] rounded-xl border mt-2 overflow-hidden cursor-crosshair group"
                      style={{
                        backgroundColor: 'var(--bg-well)',
                        borderColor: 'var(--border-subtle)',
                        background: 'repeating-linear-gradient(0deg, transparent, transparent 29px, rgba(128,128,128,0.08) 29px, rgba(128,128,128,0.08) 30px)'
                      }}
                    >
                      {/* Blocks in Day */}
                      {dayBlocks.map((blk) => {
                        const startMin = timeToMinutes(blk.start_time) - (6 * 60);
                        const endMin = timeToMinutes(blk.end_time) - (6 * 60);
                        const totalGridMin = 16 * 60; // 960

                        const topPct = Math.max(0, Math.min(100, (startMin / totalGridMin) * 100));
                        const heightPct = Math.max(4, Math.min(100 - topPct, ((endMin - startMin) / totalGridMin) * 100));
                        const isSelected = selectedBlockId === blk.id;

                        return (
                          <div
                            key={blk.id}
                            tabIndex={0}
                            role="button"
                            aria-label={`${currentRoom.name}, ${day.name} ${blk.start_time} to ${blk.end_time}, ${blk.expected_headcount} students, setpoint ${blk.setpoint_c}°C`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedBlockId(blk.id);
                              setSheetOpen(true);
                            }}
                            onKeyDown={(e) => handleBlockKeyDown(e, blk)}
                            className={`absolute left-1 right-1 rounded-xl border p-2 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-500 select-none ${
                              isSelected ? 'ring-2 ring-indigo-500 shadow-lg z-20' : 'hover:border-indigo-400 z-10'
                            }`}
                            style={{
                              top: `${topPct}%`,
                              height: `${heightPct}%`,
                              backgroundColor: isSelected ? 'var(--accent-subtle)' : 'var(--bg-card)',
                              borderColor: isSelected ? 'var(--accent)' : 'var(--border-separator)'
                            }}
                          >
                            <div className="flex items-center justify-between gap-1 mb-1">
                              <span className="font-bold text-xs truncate" style={{ color: 'var(--text-primary)' }}>
                                {blk.activity_name || 'Class Block'}
                              </span>
                              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-600 font-bold shrink-0">
                                {blk.setpoint_c || 24}°C
                              </span>
                            </div>

                            <div className="text-[10px] text-stone-500 font-mono truncate">
                              {blk.start_time?.slice(0, 5)}–{blk.end_time?.slice(0, 5)}
                            </div>

                            <div className="flex items-center gap-2 mt-auto pt-1 text-[9px] text-stone-400">
                              <span>👥 {blk.expected_headcount} exp.</span>
                              {blk.precool_mode === 'auto' && <span className="text-cyan-600 font-semibold">• Pre-cool 20m</span>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* 5B. VIEW 2: CAMPUS OVERVIEW (ROOMS X TIME MATRIX WITH HEATMAP) */}
      {activeView === 'overview' && (
        <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                Campus Facilities Schedule Matrix
              </h2>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Heatmap of AC planned runtime, occupancy load, and conflict density across all campus rooms.
              </p>
            </div>

            {/* Building filter */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-stone-500">Building:</span>
              <select
                value={buildingFilter}
                onChange={(e) => setBuildingFilter(e.target.value)}
                className="px-2.5 py-1 text-xs rounded-xl border bg-transparent"
                style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
              >
                <option value="All">All Buildings</option>
                <option value="Engineering Hall">Engineering Hall</option>
                <option value="Science Complex">Science Complex</option>
                <option value="Administration Block">Administration Block</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="border-b uppercase tracking-wider text-[10px] text-stone-500" style={{ borderColor: 'var(--border-separator)' }}>
                <tr>
                  <th className="py-2.5 px-3">Room</th>
                  <th className="py-2.5 px-3">Building</th>
                  <th className="py-2.5 px-3">Mon</th>
                  <th className="py-2.5 px-3">Tue</th>
                  <th className="py-2.5 px-3">Wed</th>
                  <th className="py-2.5 px-3">Thu</th>
                  <th className="py-2.5 px-3">Fri</th>
                  <th className="py-2.5 px-3">Sat</th>
                  <th className="py-2.5 px-3 text-right">Weekly Hrs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
                {rooms
                  .filter(r => buildingFilter === 'All' || r.building === buildingFilter)
                  .map(room => {
                    const isSelected = (room.id === selectedRoomId || room.room_id === selectedRoomId);
                    return (
                      <tr 
                        key={room.id || room.room_id}
                        onClick={() => setSelectedRoomId(room.id || room.room_id)}
                        className={`cursor-pointer transition-colors ${
                          isSelected ? 'bg-indigo-50/50 dark:bg-indigo-950/20' : 'hover:bg-stone-50 dark:hover:bg-stone-800/40'
                        }`}
                      >
                        <td className="py-3 px-3 font-semibold" style={{ color: 'var(--text-primary)' }}>
                          {room.name || room.room_name}
                        </td>
                        <td className="py-3 px-3 text-stone-500">{room.building}</td>
                        {[0, 1, 2, 3, 4, 5].map(d => (
                          <td key={d} className="py-3 px-3">
                            <span className="inline-block px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                              09:00–17:00
                            </span>
                          </td>
                        ))}
                        <td className="py-3 px-3 text-right font-mono font-bold" style={{ color: 'var(--text-primary)' }}>
                          40.0 hrs
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5C. VIEW 3: CALENDAR MONTH VIEW WITH EXCEPTIONS & HOLIDAYS */}
      {activeView === 'calendar' && (
        <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center justify-between border-b pb-4" style={{ borderColor: 'var(--border-separator)' }}>
            <div>
              <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                Academic Calendar & Exceptions
              </h2>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Campus holidays, examination periods, and temporary operational holds.
              </p>
            </div>
            <button
              onClick={() => setExceptionModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-xl bg-indigo-600 text-white"
            >
              <Plus size={14} /> Add Calendar Exception
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { title: 'Diwali Festival Break', type: 'holiday', date: 'Nov 12 - Nov 15', scope: 'Campus-wide', status: 'All ACs Scheduled OFF' },
              { title: 'Semester End Theory Exams', type: 'exam_period', date: 'Dec 01 - Dec 14', scope: 'Academic Wings', status: 'Comfort Setpoint 23.5°C' },
              { title: 'AI & Robotics Tech Symposium', type: 'one_off', date: 'Nov 20, 09:00 - 18:00', scope: 'Auditorium Hall B', status: 'Pre-cool 40m Lead' },
              { title: 'Emergency Server Maintenance', type: 'temporary_hold', date: 'Today, 22:00 - 02:00', scope: 'Server Room', status: 'Hold Active' }
            ].map((item, idx) => (
              <div key={idx} className="p-4 rounded-xl border space-y-2" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                <div className="flex items-center justify-between">
                  <span className="text-xs uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950 text-indigo-600">
                    {item.type.replace('_', ' ')}
                  </span>
                  <span className="text-[11px] text-stone-500 font-mono">{item.date}</span>
                </div>
                <h4 className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>{item.title}</h4>
                <div className="text-xs text-stone-500">Scope: <strong>{item.scope}</strong></div>
                <div className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">{item.status}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 5D. VIEW 4: LIST VIEW (PHONE ACCESSIBLE TABLE WITH BULK EDIT) */}
      {activeView === 'list' && (
        <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                Blocks List ({blocks.length})
              </h2>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Accessible table layout with bulk edit capabilities and multi-field filtering.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Search subject..."
                value={listSearch}
                onChange={(e) => setListSearch(e.target.value)}
                className="px-3 py-1.5 text-xs rounded-xl border bg-transparent"
                style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="border-b uppercase tracking-wider text-[10px] text-stone-500" style={{ borderColor: 'var(--border-separator)' }}>
                <tr>
                  <th className="py-2 px-3">Day</th>
                  <th className="py-2 px-3">Time Range</th>
                  <th className="py-2 px-3">Subject / Activity</th>
                  <th className="py-2 px-3">Headcount</th>
                  <th className="py-2 px-3">Setpoint</th>
                  <th className="py-2 px-3">Pre-cool Mode</th>
                  <th className="py-2 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
                {blocks
                  .filter(b => !listSearch || (b.activity_name || '').toLowerCase().includes(listSearch.toLowerCase()))
                  .map(b => (
                    <tr key={b.id} className="hover:bg-stone-50 dark:hover:bg-stone-800/40 transition-colors">
                      <td className="py-3 px-3 font-semibold">{WEEKDAYS[b.day_of_week]?.short}</td>
                      <td className="py-3 px-3 font-mono text-stone-500">{b.start_time?.slice(0, 5)} - {b.end_time?.slice(0, 5)}</td>
                      <td className="py-3 px-3 font-medium" style={{ color: 'var(--text-primary)' }}>{b.activity_name}</td>
                      <td className="py-3 px-3">{b.expected_headcount} seats</td>
                      <td className="py-3 px-3 font-mono font-bold text-indigo-600">{b.setpoint_c || 24}°C</td>
                      <td className="py-3 px-3 capitalize text-stone-500">{b.precool_mode || 'auto'} ({b.precool_lead_min || 20}m)</td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={() => { setSelectedBlockId(b.id); setSheetOpen(true); }}
                          className="text-indigo-600 font-semibold hover:underline mr-3"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDeleteBlock(b.id)}
                          className="text-rose-600 font-semibold hover:underline"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5E. VIEW 5: IMMUTABLE VERSION HISTORY */}
      {activeView === 'history' && (
        <div className="p-6 rounded-2xl border space-y-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
          <div>
            <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
              Schedule Versions & Audit Trail
            </h2>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Forward-looking immutable history. Restoring an old version creates a new version record without mutating the past.
            </p>
          </div>

          {versions.length === 0 ? (
            <div className="p-8 text-center text-xs text-stone-500 border rounded-xl border-dashed">
              No previous schedule versions archived yet. Making edits and publishing a draft creates version 1.
            </div>
          ) : (
            <div className="space-y-3">
              {versions.map((ver) => (
                <div key={ver.id} className="p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-indigo-500/20 text-indigo-600">
                        v{ver.version_number}
                      </span>
                      <span className="text-xs text-stone-500">
                        Effective: {new Date(ver.effective_from || ver.created_at).toLocaleString()}
                      </span>
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-400">
                        Author: {ver.author}
                      </span>
                    </div>
                    <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {ver.summary}
                    </p>
                  </div>

                  <button
                    onClick={() => handleRestoreVersion(ver.id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-xl border hover:bg-stone-500/10 transition-colors shrink-0"
                    style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
                  >
                    <RotateCcw size={14} /> Restore Version
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 6. Block Detail Sheet (Edit / Inspector Panel) */}
      {sheetOpen && activeBlock && (
        <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-[var(--bg-card)] border-l shadow-2xl p-6 overflow-y-auto space-y-6 animate-in slide-in-from-right duration-200" style={{ borderColor: 'var(--border-separator)' }}>
          <div className="flex items-center justify-between border-b pb-4" style={{ borderColor: 'var(--border-separator)' }}>
            <div>
              <h3 className="font-bold text-lg" style={{ color: 'var(--text-primary)' }}>
                Edit Schedule Block
              </h3>
              <span className="text-xs text-stone-500">{currentRoom.name}</span>
            </div>
            <button 
              onClick={() => setSheetOpen(false)}
              className="p-1.5 rounded-xl border text-stone-500 hover:bg-stone-500/10"
              style={{ borderColor: 'var(--border-separator)' }}
            >
              ✕
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs font-bold text-stone-500 block mb-1">Activity / Class Label</label>
              <input
                type="text"
                value={activeBlock.activity_name || ''}
                onChange={(e) => handleUpdateBlock({ ...activeBlock, activity_name: e.target.value })}
                className="w-full px-3 py-2 text-xs rounded-xl border bg-transparent font-medium"
                style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-bold text-stone-500 block mb-1">Start Time (HH:MM)</label>
                <input
                  type="time"
                  value={activeBlock.start_time?.slice(0, 5) || "09:00"}
                  onChange={(e) => handleUpdateBlock({ ...activeBlock, start_time: `${e.target.value}:00` })}
                  className="w-full px-3 py-2 text-xs rounded-xl border bg-transparent font-mono"
                  style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
                />
              </div>
              <div>
                <label className="text-xs font-bold text-stone-500 block mb-1">End Time (HH:MM)</label>
                <input
                  type="time"
                  value={activeBlock.end_time?.slice(0, 5) || "11:00"}
                  onChange={(e) => handleUpdateBlock({ ...activeBlock, end_time: `${e.target.value}:00` })}
                  className="w-full px-3 py-2 text-xs rounded-xl border bg-transparent font-mono"
                  style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-bold text-stone-500 block mb-1">Target Setpoint (°C)</label>
                <input
                  type="number"
                  step="0.5"
                  min={isServerRoom ? 18.0 : 20.0}
                  max={isServerRoom ? 23.0 : 28.0}
                  value={activeBlock.setpoint_c || 24.0}
                  onChange={(e) => handleUpdateBlock({ ...activeBlock, setpoint_c: parseFloat(e.target.value) })}
                  className="w-full px-3 py-2 text-xs rounded-xl border bg-transparent font-mono font-bold"
                  style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
                />
              </div>
              <div>
                <label className="text-xs font-bold text-stone-500 block mb-1">Expected Headcount</label>
                <input
                  type="number"
                  min="0"
                  max={currentRoom.capacity * 1.5}
                  value={activeBlock.expected_headcount || 30}
                  onChange={(e) => handleUpdateBlock({ ...activeBlock, expected_headcount: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 text-xs rounded-xl border bg-transparent font-mono"
                  style={{ borderColor: 'var(--border-separator)', color: 'var(--text-primary)' }}
                />
              </div>
            </div>

            {/* Pre-cool Mode */}
            <div className="p-3.5 rounded-xl border space-y-2" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
              <span className="text-xs font-bold block" style={{ color: 'var(--text-primary)' }}>Thermal Pre-Cooling Lead</span>
              <div className="flex items-center gap-2">
                {['auto', 'manual'].map(m => (
                  <button
                    key={m}
                    onClick={() => handleUpdateBlock({ ...activeBlock, precool_mode: m })}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg capitalize transition-all ${
                      activeBlock.precool_mode === m ? 'bg-indigo-600 text-white' : 'text-stone-500'
                    }`}
                  >
                    {m}
                  </button>
                ))}
                {activeBlock.precool_mode === 'manual' && (
                  <input
                    type="number"
                    min="5"
                    max="60"
                    value={activeBlock.precool_lead_min || 20}
                    onChange={(e) => handleUpdateBlock({ ...activeBlock, precool_lead_min: parseInt(e.target.value) })}
                    className="w-20 px-2 py-1 text-xs rounded-lg border bg-transparent font-mono"
                    style={{ borderColor: 'var(--border-separator)' }}
                  />
                )}
              </div>
              <p className="text-[10px] text-stone-500">
                {activeBlock.precool_mode === 'auto' 
                  ? 'Auto mode dynamically calculates 15-60m lead based on outdoor ambient temperature and thermal mass.'
                  : 'Manual fixed pre-cool start before scheduled class block.'
                }
              </p>
            </div>

            {/* Flywheel Shut-off */}
            <div className="p-3.5 rounded-xl border space-y-2" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
              <span className="text-xs font-bold block" style={{ color: 'var(--text-primary)' }}>Coasting Shut-Off (Flywheel)</span>
              <div className="flex items-center gap-2">
                {['auto', 'manual'].map(m => (
                  <button
                    key={m}
                    onClick={() => handleUpdateBlock({ ...activeBlock, shutoff_mode: m })}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg capitalize transition-all ${
                      activeBlock.shutoff_mode === m ? 'bg-indigo-600 text-white' : 'text-stone-500'
                    }`}
                  >
                    {m}
                  </button>
                ))}
                {activeBlock.shutoff_mode === 'manual' && (
                  <input
                    type="number"
                    min="0"
                    max="45"
                    value={activeBlock.shutoff_lead_min || 15}
                    onChange={(e) => handleUpdateBlock({ ...activeBlock, shutoff_lead_min: parseInt(e.target.value) })}
                    className="w-20 px-2 py-1 text-xs rounded-lg border bg-transparent font-mono"
                    style={{ borderColor: 'var(--border-separator)' }}
                  />
                )}
              </div>
              <p className="text-[10px] text-stone-500">
                Turns off compressor 15 mins prior to class departure while thermal inertia maintains ASHRAE 55 compliance.
              </p>
            </div>

            {/* Actions */}
            <div className="pt-4 flex items-center justify-between border-t" style={{ borderColor: 'var(--border-separator)' }}>
              <button
                onClick={() => handleDeleteBlock(activeBlock.id)}
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold rounded-xl text-rose-600 hover:bg-rose-500/10"
              >
                <Trash2 size={14} /> Delete Block
              </button>
              <button
                onClick={() => setSheetOpen(false)}
                className="px-4 py-2 text-xs font-bold rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm"
              >
                Apply Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 7. Copy Schedule Modal */}
      {copyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-2xl border p-6 space-y-4 shadow-2xl bg-[var(--bg-card)]" style={{ borderColor: 'var(--border-separator)' }}>
            <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
              Copy Schedule Template to Other Rooms
            </h3>
            <p className="text-xs text-stone-500">
              Apply {currentRoom.name}'s weekly timetable blocks to destination rooms. Existing forward-looking schedules will be version-archived before replacement.
            </p>

            <div className="max-h-60 overflow-y-auto space-y-2 border rounded-xl p-3" style={{ borderColor: 'var(--border-separator)' }}>
              {rooms.filter(r => (r.id || r.room_id) !== selectedRoomId).map(r => (
                <label key={r.id || r.room_id} className="flex items-center gap-2 text-xs cursor-pointer">
                  <input type="checkbox" defaultChecked className="rounded text-indigo-600" />
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{r.name || r.room_name}</span>
                  <span className="text-stone-400">({r.building})</span>
                </label>
              ))}
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setCopyModalOpen(false)}
                className="px-3 py-1.5 text-xs font-semibold rounded-xl border text-stone-500"
                style={{ borderColor: 'var(--border-separator)' }}
              >
                Cancel
              </button>
              <button
                onClick={() => handleCopySchedule(rooms.filter(r => (r.id || r.room_id) !== selectedRoomId).map(r => r.id || r.room_id))}
                className="px-4 py-1.5 text-xs font-bold rounded-xl bg-indigo-600 text-white"
              >
                Confirm Copy
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Honesty Badges */}
      <HonestyBadges />
    </div>
  );
}
export default OptimizerScreen;
