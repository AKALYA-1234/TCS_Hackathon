import React, { useMemo } from 'react';
import {
  Search,
  Filter,
  ArrowUpDown,
  Building2,
  ChevronDown,
  ChevronRight,
  Zap,
  Users,
  Thermometer,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Sparkles,
  Layers,
  LayoutGrid,
  List
} from 'lucide-react';
import { HonestyBadges } from '../ui/BaseComponents';

export function RoomsList({
  rooms = [],
  selectedRoomId,
  onSelectRoom,
  liveState,
  searchQuery = '',
  onSearchChange,
  buildingFilter = 'All',
  onBuildingChange,
  typeFilter = 'All',
  onTypeChange,
  statusFilter = 'All',
  onStatusChange,
  sortBy = 'name',
  onSortChange,
  viewMode = 'grouped', // 'grouped' | 'flat'
  onViewModeChange,
  loading = false,
  error = null,
  onRetry
}) {
  const [collapsedBuildings, setCollapsedBuildings] = React.useState({});

  const toggleBuildingCollapse = (bldg) => {
    setCollapsedBuildings((prev) => ({
      ...prev,
      [bldg]: !prev[bldg]
    }));
  };

  // Derive live telemetry and status badges for each room
  const enrichedRooms = useMemo(() => {
    const activeAnomalies = liveState?.activeAnomalies || {};
    const roomSeries = liveState?.roomSeries || {};

    return rooms.map((room) => {
      const roomId = room.room_id || room.id;
      const roomName = room.room_name || room.name || roomId;
      const series = roomSeries[roomId] || [];
      const latest = series.length > 0 ? series[series.length - 1] : null;

      // Current power reading
      const currentPower = latest?.actual_power_kw ?? (room.units?.reduce((acc, u) => acc + (u.status === 'ON' ? (u.rated_kw * 0.45) : 0), 0) || 0.0);
      const baselineKw = latest?.baseline_kw ?? 0.05;
      const currentTemp = latest?.room_temp_c ?? room.target_temp_c ?? 24.0;
      const setTemp = latest?.set_temp_c ?? room.target_temp_c ?? 24.0;
      const headcount = latest?.occupancy ?? 0;
      const expectedHeadcount = room.room_type === 'lecture_hall' ? Math.round(room.capacity * 0.6) : (room.room_type === 'lab' ? 12 : 0);

      // Unit counts
      const totalUnits = room.units_count || (room.units ? room.units.length : 1);
      const onUnits = room.units?.filter((u) => u.status === 'ON').length ?? (currentPower > 0.5 ? totalUnits : 0);
      const isRoomOn = onUnits > 0 || currentPower > 0.3;

      // Anomaly check
      const anomalyType = activeAnomalies[room.id];
      const hasWaste = Boolean(anomalyType) || (currentPower > baselineKw + 1.0);

      // Today's kWh and INR estimation
      const todayKwh = Math.round(currentPower * 12 * 0.8 + 15);
      const wastePct = hasWaste ? (anomalyType === 'ghost_cooling' ? 82 : 45) : 8;
      const todayInr = Math.round(todayKwh * 9.2);

      // Status Badge determination
      let statusBadge = { label: 'Normal', color: 'var(--status-healthy)', bg: 'var(--status-healthy-bg)' };
      if (room.id === 'eng-server' || room.is_critical && room.room_type === 'server_room') {
        statusBadge = { label: 'Exception (Never Off)', color: 'var(--accent)', bg: 'var(--accent-subtle)' };
      } else if (room.manual_override_active) {
        statusBadge = { label: 'Override Active', color: 'var(--status-review)', bg: 'var(--status-review-bg)' };
      } else if (anomalyType) {
        const typeLabel = anomalyType === 'ghost_cooling' ? 'Ghost Cooling' : (anomalyType === 'overcooling' ? 'Overcooling' : 'Waste Detected');
        statusBadge = { label: typeLabel, color: 'var(--status-failed)', bg: 'var(--status-failed-bg)' };
      } else if (hasWaste) {
        statusBadge = { label: 'Waste Detected', color: 'var(--status-failed)', bg: 'var(--status-failed-bg)' };
      }

      return {
        ...room,
        id: roomId,
        name: roomName,
        currentPower,
        baselineKw,
        currentTemp,
        setTemp,
        headcount,
        expectedHeadcount,
        totalUnits,
        onUnits,
        isRoomOn,
        hasWaste,
        anomalyType,
        todayKwh,
        todayInr,
        wastePct,
        statusBadge,
        series: series.slice(-20)
      };
    });
  }, [rooms, liveState]);

  // Summary Metrics Bar
  const summary = useMemo(() => {
    const total = enrichedRooms.length;
    const roomsOn = enrichedRooms.filter((r) => r.isRoomOn).length;
    const roomsWaste = enrichedRooms.filter((r) => r.hasWaste).length;
    const awaitingApproval = liveState?.pendingApprovalsCount ?? 1;

    return { total, roomsOn, roomsWaste, awaitingApproval };
  }, [enrichedRooms, liveState]);

  // Filtering
  const filteredRooms = useMemo(() => {
    return enrichedRooms.filter((r) => {
      // Search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchName = (r.name || '').toLowerCase().includes(q);
        const matchId = (r.id || '').toLowerCase().includes(q);
        const matchBuilding = (r.building || '').toLowerCase().includes(q);
        if (!matchName && !matchId && !matchBuilding) return false;
      }
      // Building
      if (buildingFilter !== 'All' && r.building !== buildingFilter) {
        return false;
      }
      // Type
      if (typeFilter !== 'All' && r.room_type !== typeFilter) {
        return false;
      }
      // Status
      if (statusFilter === 'ON' && !r.isRoomOn) return false;
      if (statusFilter === 'OFF' && r.isRoomOn) return false;
      if (statusFilter === 'Waste' && !r.hasWaste) return false;
      if (statusFilter === 'Override' && !r.manual_override_active) return false;
      if (statusFilter === 'Exception' && r.id !== 'eng-server') return false;

      return true;
    });
  }, [enrichedRooms, searchQuery, buildingFilter, typeFilter, statusFilter]);

  // Sorting
  const sortedRooms = useMemo(() => {
    const list = [...filteredRooms];
    list.sort((a, b) => {
      if (sortBy === 'name') return a.name.localeCompare(b.name);
      if (sortBy === 'power') return b.currentPower - a.currentPower;
      if (sortBy === 'waste') return b.wastePct - a.wastePct;
      if (sortBy === 'kwh') return b.todayKwh - a.todayKwh;
      if (sortBy === 'inr') return b.todayInr - a.todayInr;
      return 0;
    });
    return list;
  }, [filteredRooms, sortBy]);

  // Group by Building
  const groupedRooms = useMemo(() => {
    const map = {};
    sortedRooms.forEach((r) => {
      map[r.building] = map[r.building] || [];
      map[r.building].push(r);
    });
    return map;
  }, [sortedRooms]);

  const uniqueBuildings = useMemo(() => {
    const set = new Set(rooms.map((r) => r.building));
    return ['All', ...Array.from(set)];
  }, [rooms]);

  const uniqueTypes = useMemo(() => {
    const set = new Set(rooms.map((r) => r.room_type));
    return ['All', ...Array.from(set)];
  }, [rooms]);

  // Mini Sparkline SVG Renderer
  const renderSparkline = (series, isWaste) => {
    if (!series || series.length < 2) {
      return (
        <div className="w-16 h-6 flex items-center justify-center opacity-40">
          <span className="w-12 h-0.5 bg-current opacity-30 rounded-full" />
        </div>
      );
    }
    const maxVal = Math.max(...series.map((s) => s.actual_power_kw || 1), 8);
    const w = 64;
    const h = 24;
    const points = series.map((s, idx) => {
      const x = (idx / (series.length - 1)) * w;
      const y = h - ((s.actual_power_kw || 0) / maxVal) * (h - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    const strokeColor = isWaste ? 'var(--status-failed)' : 'var(--accent)';

    return (
      <svg width={w} height={h} className="shrink-0 overflow-visible">
        <polyline
          fill="none"
          stroke={strokeColor}
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
      </svg>
    );
  };

  if (loading) {
    return (
      <div className="p-6 space-y-4 animate-pulse">
        <div className="h-8 bg-slate-200 dark:bg-slate-800 rounded-lg w-1/3" />
        <div className="h-16 bg-slate-200 dark:bg-slate-800 rounded-xl" />
        <div className="space-y-2">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-14 bg-slate-200 dark:bg-slate-800 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-12 text-center rounded-2xl border m-4" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
        <AlertTriangle size={36} className="mx-auto mb-3 opacity-60 text-amber-500" />
        <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
          Failed to load campus rooms
        </h3>
        <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
          {error.message || 'Network communication error connecting to AC Optimization telemetry service.'}
        </p>
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-2 text-xs font-bold rounded-lg cursor-pointer"
          style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 1. Header & Summary Strip */}
      <div className="p-4 sm:p-5 border-b space-y-4 shrink-0" style={{ borderColor: 'var(--border-separator)', backgroundColor: 'var(--bg-card)' }}>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                Campus Rooms
              </h1>
              <span
                className="text-xs font-bold px-2 py-0.5 rounded-full"
                style={{ backgroundColor: 'var(--bg-well)', color: 'var(--text-secondary)' }}
              >
                {rooms.length} rooms
              </span>
            </div>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
              Complete campus directory of monitored and optimized rooms across 3 buildings.
            </p>
          </div>

          <HonestyBadges />
        </div>

        {/* Summary Metric Counters */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-xs">
          <div className="p-2.5 rounded-xl border flex items-center justify-between" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Monitored</span>
            <span className="font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>{summary.total}</span>
          </div>
          <div className="p-2.5 rounded-xl border flex items-center justify-between" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Active (ON)</span>
            <span className="font-bold tabular-nums" style={{ color: 'var(--accent)' }}>{summary.roomsOn}</span>
          </div>
          <div className="p-2.5 rounded-xl border flex items-center justify-between" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Waste Flagged</span>
            <span className="font-bold tabular-nums" style={{ color: summary.roomsWaste > 0 ? 'var(--status-failed)' : 'var(--text-primary)' }}>{summary.roomsWaste}</span>
          </div>
          <div className="p-2.5 rounded-xl border flex items-center justify-between" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Pending Proposals</span>
            <span className="font-bold tabular-nums" style={{ color: 'var(--status-review)' }}>{summary.awaitingApproval}</span>
          </div>
        </div>

        {/* 2. Search, Filters, and Sorters Bar */}
        <div className="flex flex-col lg:flex-row gap-2.5 pt-1">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 opacity-40" style={{ color: 'var(--text-primary)' }} />
            <input
              type="text"
              id="rooms-search-input"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search by room name, id, or building..."
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border transition-all outline-none focus:ring-2 focus:ring-blue-500/30"
              style={{
                backgroundColor: 'var(--bg-well)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)'
              }}
            />
          </div>

          {/* Filter Dropdowns & View Toggles */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Building Filter */}
            <select
              value={buildingFilter}
              onChange={(e) => onBuildingChange(e.target.value)}
              className="text-xs px-2.5 py-1.5 rounded-lg border font-medium cursor-pointer outline-none"
              style={{
                backgroundColor: 'var(--bg-well)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)'
              }}
            >
              {uniqueBuildings.map((b) => (
                <option key={b} value={b}>
                  {b === 'All' ? 'All Buildings' : b}
                </option>
              ))}
            </select>

            {/* Type Filter */}
            <select
              value={typeFilter}
              onChange={(e) => onTypeChange(e.target.value)}
              className="text-xs px-2.5 py-1.5 rounded-lg border font-medium cursor-pointer outline-none"
              style={{
                backgroundColor: 'var(--bg-well)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)'
              }}
            >
              {uniqueTypes.map((t) => (
                <option key={t} value={t}>
                  {t === 'All' ? 'All Types' : t.replace('_', ' ')}
                </option>
              ))}
            </select>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => onStatusChange(e.target.value)}
              className="text-xs px-2.5 py-1.5 rounded-lg border font-medium cursor-pointer outline-none"
              style={{
                backgroundColor: 'var(--bg-well)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="All">All Statuses</option>
              <option value="ON">Rooms ON</option>
              <option value="OFF">Rooms Standby</option>
              <option value="Waste">With Waste</option>
              <option value="Override">Override Active</option>
              <option value="Exception">Exception (Server Room)</option>
            </select>

            {/* Sort Filter */}
            <select
              value={sortBy}
              onChange={(e) => onSortChange(e.target.value)}
              className="text-xs px-2.5 py-1.5 rounded-lg border font-medium cursor-pointer outline-none"
              style={{
                backgroundColor: 'var(--bg-well)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="name">Sort: Name</option>
              <option value="power">Sort: Power (kW)</option>
              <option value="waste">Sort: Waste %</option>
              <option value="kwh">Sort: Energy (kWh)</option>
              <option value="inr">Sort: Cost (INR)</option>
            </select>

            {/* View Mode Toggle */}
            <div
              className="inline-flex p-0.5 rounded-lg border"
              style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}
            >
              <button
                onClick={() => onViewModeChange('grouped')}
                className={`p-1 rounded cursor-pointer ${viewMode === 'grouped' ? 'shadow-xs' : ''}`}
                style={{
                  backgroundColor: viewMode === 'grouped' ? 'var(--bg-card)' : 'transparent',
                  color: viewMode === 'grouped' ? 'var(--text-primary)' : 'var(--text-tertiary)'
                }}
                title="Group by Building"
              >
                <Layers size={14} />
              </button>
              <button
                onClick={() => onViewModeChange('flat')}
                className={`p-1 rounded cursor-pointer ${viewMode === 'flat' ? 'shadow-xs' : ''}`}
                style={{
                  backgroundColor: viewMode === 'flat' ? 'var(--bg-card)' : 'transparent',
                  color: viewMode === 'flat' ? 'var(--text-primary)' : 'var(--text-tertiary)'
                }}
                title="Flat Table View"
              >
                <List size={14} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Rooms Scrollable Container */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
        {sortedRooms.length === 0 ? (
          <div
            className="p-12 text-center rounded-2xl border"
            style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
          >
            <Search size={32} className="mx-auto mb-2 opacity-30" style={{ color: 'var(--text-primary)' }} />
            <h3 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
              No rooms match your filter
            </h3>
            <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
              Try clearing search terms or selecting 'All Buildings' to view available rooms.
            </p>
          </div>
        ) : viewMode === 'grouped' ? (
          Object.entries(groupedRooms).map(([building, bldgRooms]) => {
            const isCollapsed = collapsedBuildings[building];
            const onCount = bldgRooms.filter((r) => r.isRoomOn).length;
            const wasteCount = bldgRooms.filter((r) => r.hasWaste).length;

            return (
              <div
                key={building}
                className="rounded-2xl border overflow-hidden transition-all"
                style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
              >
                {/* Building Header / Accordion trigger */}
                <button
                  onClick={() => toggleBuildingCollapse(building)}
                  className="w-full px-5 py-3.5 flex items-center justify-between text-left border-b cursor-pointer select-none transition-colors"
                  style={{
                    backgroundColor: 'var(--bg-well)',
                    borderColor: 'var(--border-subtle)'
                  }}
                >
                  <div className="flex items-center gap-2.5">
                    {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                    <Building2 size={16} className="opacity-70" style={{ color: 'var(--accent)' }} />
                    <span className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>
                      {building}
                    </span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ backgroundColor: 'var(--bg-card)', color: 'var(--text-secondary)' }}>
                      {bldgRooms.length} rooms
                    </span>
                  </div>

                  <div className="flex items-center gap-3 text-xs">
                    <span style={{ color: 'var(--text-secondary)' }}>
                      {onCount} ON
                    </span>
                    {wasteCount > 0 && (
                      <span className="font-bold px-2 py-0.5 rounded text-[11px]" style={{ backgroundColor: 'var(--status-failed-bg)', color: 'var(--status-failed)' }}>
                        {wasteCount} waste
                      </span>
                    )}
                  </div>
                </button>

                {/* Rooms List in this Building */}
                {!isCollapsed && (
                  <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
                    {bldgRooms.map((room) => {
                      const isSelected = selectedRoomId === room.id;

                      return (
                        <div
                          key={room.id}
                          id={`room-item-${room.id}`}
                          onClick={() => onSelectRoom(room.id)}
                          className={`p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer transition-all ${
                            isSelected ? 'ring-2 ring-inset ring-blue-500/70' : 'hover:bg-slate-50 dark:hover:bg-slate-800/40'
                          }`}
                          style={{
                            backgroundColor: isSelected ? 'var(--accent-subtle)' : 'transparent'
                          }}
                        >
                          {/* Room Identity & Badges */}
                          <div className="min-w-0 flex-1 space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-sm tracking-tight" style={{ color: 'var(--text-primary)' }}>
                                {room.name || room.id}
                              </span>
                              <span className="text-[11px] font-mono opacity-60" style={{ color: 'var(--text-tertiary)' }}>
                                {room.id}
                              </span>
                              <span
                                className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase"
                                style={{
                                  backgroundColor: room.statusBadge.bg,
                                  color: room.statusBadge.color
                                }}
                              >
                                {room.statusBadge.label}
                              </span>
                            </div>

                            <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
                              <span className="capitalize">{room.room_type.replace('_', ' ')}</span>
                              <span>·</span>
                              <span>{room.area_sqm} m²</span>
                              <span>·</span>
                              <span>Cap: {room.capacity}</span>
                              <span>·</span>
                              <span>{room.totalUnits} unit{room.totalUnits > 1 ? 's' : ''}</span>
                            </div>
                          </div>

                          {/* Live Telemetry Readings & Sparkline */}
                          <div className="flex items-center gap-5 sm:gap-6 justify-between sm:justify-end shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0" style={{ borderColor: 'var(--border-subtle)' }}>
                            {/* Temp & Headcount */}
                            <div className="text-right text-xs">
                              <div className="flex items-center gap-1 justify-end font-semibold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                                <Thermometer size={13} className="opacity-50" />
                                <span>{room.currentTemp.toFixed(1)}° / {room.setTemp.toFixed(1)}°</span>
                              </div>
                              <div className="flex items-center gap-1 justify-end text-[11px] tabular-nums" style={{ color: 'var(--text-tertiary)' }}>
                                <Users size={12} className="opacity-50" />
                                <span>{room.headcount} occ ({room.expectedHeadcount} exp)</span>
                              </div>
                            </div>

                            {/* Power & Waste Today */}
                            <div className="text-right text-xs min-w-[70px]">
                              <div className="font-bold text-sm tabular-nums" style={{ color: room.isRoomOn ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>
                                {room.currentPower.toFixed(2)} kW
                              </div>
                              <div className="text-[11px] font-semibold tabular-nums" style={{ color: room.hasWaste ? 'var(--status-failed)' : 'var(--text-tertiary)' }}>
                                {room.todayKwh} kWh ({room.wastePct}% w)
                              </div>
                            </div>

                            {/* Live Sparkline */}
                            <div className="hidden sm:block">
                              {renderSparkline(room.series, room.hasWaste)}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        ) : (
          /* Flat Table View */
          <div className="rounded-2xl border overflow-hidden" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
              {sortedRooms.map((room) => {
                const isSelected = selectedRoomId === room.id;

                return (
                  <div
                    key={room.id}
                    id={`room-item-${room.id}`}
                    onClick={() => onSelectRoom(room.id)}
                    className={`p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer transition-all ${
                      isSelected ? 'ring-2 ring-inset ring-blue-500/70' : 'hover:bg-slate-50 dark:hover:bg-slate-800/40'
                    }`}
                    style={{
                      backgroundColor: isSelected ? 'var(--accent-subtle)' : 'transparent'
                    }}
                  >
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>
                          {room.name || room.id}
                        </span>
                        <span className="text-[11px] font-mono opacity-60" style={{ color: 'var(--text-tertiary)' }}>
                          {room.id}
                        </span>
                        <span className="text-xs opacity-60" style={{ color: 'var(--text-secondary)' }}>
                          ({room.building})
                        </span>
                        <span
                          className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase"
                          style={{
                            backgroundColor: room.statusBadge.bg,
                            color: room.statusBadge.color
                          }}
                        >
                          {room.statusBadge.label}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
                        <span className="capitalize">{room.room_type.replace('_', ' ')}</span>
                        <span>·</span>
                        <span>{room.area_sqm} m²</span>
                        <span>·</span>
                        <span>Cap: {room.capacity}</span>
                        <span>·</span>
                        <span>{room.totalUnits} unit{room.totalUnits > 1 ? 's' : ''}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-5 sm:gap-6 justify-between sm:justify-end shrink-0">
                      <div className="text-right text-xs">
                        <div className="font-semibold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                          {room.currentTemp.toFixed(1)}° / {room.setTemp.toFixed(1)}°
                        </div>
                        <div className="text-[11px] tabular-nums" style={{ color: 'var(--text-tertiary)' }}>
                          {room.headcount} occ
                        </div>
                      </div>

                      <div className="text-right text-xs min-w-[70px]">
                        <div className="font-bold text-sm tabular-nums" style={{ color: room.isRoomOn ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>
                          {room.currentPower.toFixed(2)} kW
                        </div>
                        <div className="text-[11px] font-semibold tabular-nums" style={{ color: room.hasWaste ? 'var(--status-failed)' : 'var(--text-tertiary)' }}>
                          {room.todayKwh} kWh
                        </div>
                      </div>

                      <div className="hidden sm:block">
                        {renderSparkline(room.series, room.hasWaste)}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
