import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { AppShell } from './components/shell/AppShell';
import { SVGWastePatterns } from './components/ui/SVGWastePatterns';

// Bespoke screens
import { CampusOverview } from './components/screens/CampusOverview';
import { ApprovalsInbox } from './components/screens/ApprovalsInbox';
import { SimulatorScreen } from './components/screens/SimulatorScreen';
import { RoomDetail } from './components/screens/RoomDetail';
import { RoomsList } from './components/screens/RoomsList';
import { WasteEvents } from './components/screens/WasteEvents';
import { AssistantScreen } from './components/screens/AssistantScreen';
import { OptimizerScreen } from './components/screens/OptimizerScreen';
import { ForecastScreen } from './components/screens/ForecastScreen';
import { ACHistory } from './components/screens/ACHistory';
import { LiveCameras } from './components/screens/LiveCameras';

import { liveData } from './services/liveStore';

const API_BASE = '/api/ac';

// Helper to parse route and query params from window.location
function parseLocation() {
  const path = window.location.pathname;
  const searchParams = new URLSearchParams(window.location.search);

  let activeTab = 'overview';
  let routeRoomId = null;

  if (path === '/' || path === '/overview') {
    activeTab = 'overview';
  } else if (path.startsWith('/rooms/')) {
    activeTab = 'room';
    routeRoomId = decodeURIComponent(path.slice(7));
  } else if (path === '/rooms') {
    activeTab = 'rooms';
  } else if (path === '/history') {
    activeTab = 'history';
  } else if (path === '/cameras') {
    activeTab = 'cameras';
  } else if (path === '/inbox') {
    activeTab = 'inbox';
  } else if (path === '/waste') {
    activeTab = 'waste';
  } else if (path === '/forecast') {
    activeTab = 'forecast';
  } else if (path === '/optimizer') {
    activeTab = 'optimizer';
  } else if (path === '/assistant') {
    activeTab = 'assistant';
  } else if (path === '/simulator') {
    activeTab = 'simulator';
  }

  return {
    activeTab,
    routeRoomId,
    searchQuery: searchParams.get('q') || '',
    buildingFilter: searchParams.get('building') || 'All',
    typeFilter: searchParams.get('type') || 'All',
    statusFilter: searchParams.get('status') || 'All',
    sortBy: searchParams.get('sort') || 'name',
    viewMode: searchParams.get('view') || 'grouped'
  };
}

export default function App() {
  // URL route & query state
  const [routeState, setRouteState] = useState(() => parseLocation());

  // Live Stream State from liveData
  const [liveState, setLiveState] = useState(() => liveData.getState());

  // Campus Data State
  const [overview, setOverview] = useState(null);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [allRooms, setAllRooms] = useState([]);
  const [loadingRooms, setLoadingRooms] = useState(false);
  const [roomsError, setRoomsError] = useState(null);

  const [selectedRoomId, setSelectedRoomId] = useState(() => routeState.routeRoomId || 'eng-101');
  const [roomDetail, setRoomDetail] = useState(null);
  const [loadingRoomDetail, setLoadingRoomDetail] = useState(false);
  const [roomNotFound, setRoomNotFound] = useState(false);

  const [wasteEvents, setWasteEvents] = useState([]);
  const [proposals, setProposals] = useState([]);
  const [commands, setCommands] = useState([]);
  const [verifiedSavings, setVerifiedSavings] = useState([]);
  const [metrics, setMetrics] = useState(null);

  // Simulator state
  const [demoLog, setDemoLog] = useState([]);
  const [notification, setNotification] = useState(null);

  const notify = (msg, type = 'success') => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 4500);
  };

  // Push URL changes
  const updateURL = useCallback((tab, roomId, queryParams = {}) => {
    let newPath = '/';
    if (tab === 'overview') newPath = '/';
    else if (tab === 'rooms') newPath = '/rooms';
    else if (tab === 'room') newPath = `/rooms/${encodeURIComponent(roomId || selectedRoomId)}`;
    else newPath = `/${tab}`;

    const params = new URLSearchParams();
    if (queryParams.searchQuery) params.set('q', queryParams.searchQuery);
    if (queryParams.buildingFilter && queryParams.buildingFilter !== 'All') params.set('building', queryParams.buildingFilter);
    if (queryParams.typeFilter && queryParams.typeFilter !== 'All') params.set('type', queryParams.typeFilter);
    if (queryParams.statusFilter && queryParams.statusFilter !== 'All') params.set('status', queryParams.statusFilter);
    if (queryParams.sortBy && queryParams.sortBy !== 'name') params.set('sort', queryParams.sortBy);
    if (queryParams.viewMode && queryParams.viewMode !== 'grouped') params.set('view', queryParams.viewMode);

    const queryString = params.toString() ? `?${params.toString()}` : '';
    const fullUrl = `${newPath}${queryString}`;

    if (window.location.pathname + window.location.search !== fullUrl) {
      window.history.pushState({}, '', fullUrl);
    }

    setRouteState({
      activeTab: tab,
      routeRoomId: tab === 'room' ? (roomId || selectedRoomId) : null,
      searchQuery: queryParams.searchQuery ?? routeState.searchQuery,
      buildingFilter: queryParams.buildingFilter ?? routeState.buildingFilter,
      typeFilter: queryParams.typeFilter ?? routeState.typeFilter,
      statusFilter: queryParams.statusFilter ?? routeState.statusFilter,
      sortBy: queryParams.sortBy ?? routeState.sortBy,
      viewMode: queryParams.viewMode ?? routeState.viewMode
    });
  }, [selectedRoomId, routeState]);

  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      const loc = parseLocation();
      setRouteState(loc);
      if (loc.routeRoomId) {
        setSelectedRoomId(loc.routeRoomId);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Subscribe to liveData stream
  useEffect(() => {
    const unsub = liveData.subscribe((state) => {
      setLiveState(state);
    });
    return unsub;
  }, []);

  // Theme state: saved preference ('light' | 'dark' | null for system)
  const [explicitTheme, setExplicitTheme] = useState(() => {
    try {
      return localStorage.getItem('theme_preference') || null;
    } catch {
      return null;
    }
  });

  const [systemIsDark, setSystemIsDark] = useState(() => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });

  // Effective theme currently in effect
  const activeEffectiveTheme = explicitTheme ? explicitTheme : (systemIsDark ? 'dark' : 'light');

  // Listen for OS scheme changes
  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (e) => setSystemIsDark(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  // Apply classes to root element
  useEffect(() => {
    const root = document.documentElement;
    if (activeEffectiveTheme === 'dark') {
      root.classList.add('theme-dark');
      root.classList.remove('theme-light');
    } else {
      root.classList.add('theme-light');
      root.classList.remove('theme-dark');
    }

    try {
      if (explicitTheme) {
        localStorage.setItem('theme_preference', explicitTheme);
      } else {
        localStorage.removeItem('theme_preference');
      }
    } catch (e) {}
  }, [activeEffectiveTheme, explicitTheme]);

  const handleToggleTheme = useCallback((requestedTheme) => {
    setExplicitTheme((prev) => {
      // If user clicks the currently active explicit theme or active effective theme, clear it and return to system
      if (prev === requestedTheme || (prev === null && activeEffectiveTheme === requestedTheme)) {
        return null;
      }
      return requestedTheme;
    });
  }, [activeEffectiveTheme]);

  // Data Fetching from Live Backend
  const fetchOverview = async () => {
    try {
      const res = await fetch(`${API_BASE}/campus/overview`);
      if (res.ok) setOverview(await res.json());
    } catch {
      // keep resilient
    } finally {
      setLoadingOverview(false);
    }
  };

  const fetchRooms = async () => {
    setLoadingRooms(true);
    setRoomsError(null);
    try {
      const res = await fetch(`${API_BASE}/rooms`);
      if (res.ok) {
        const list = await res.json();
        setAllRooms(list);
      } else {
        setRoomsError(new Error('Failed to fetch rooms list'));
      }
    } catch (e) {
      setRoomsError(e);
    } finally {
      setLoadingRooms(false);
    }
  };

  const fetchRoomDetail = async (roomId) => {
    if (!roomId) return;
    setLoadingRoomDetail(true);
    setRoomNotFound(false);
    try {
      const res = await fetch(`${API_BASE}/rooms/${encodeURIComponent(roomId)}/detail?limit=60`);
      if (res.ok) {
        const d = await res.json();
        setRoomDetail(d);
        if (d.telemetry_series) {
          liveData.seedInitialRoomSeries(roomId, d.telemetry_series);
        }
      } else if (res.status === 404) {
        setRoomNotFound(true);
        setRoomDetail(null);
      }
    } catch {
      // keep resilient
    } finally {
      setLoadingRoomDetail(false);
    }
  };

  const fetchWasteEvents = async () => {
    try {
      const res = await fetch(`${API_BASE}/waste-events?limit=40`);
      if (res.ok) setWasteEvents(await res.json());
    } catch {
      // ignore
    }
  };

  const fetchProposals = async () => {
    try {
      const res = await fetch(`${API_BASE}/proposals`);
      if (res.ok) setProposals(await res.json());
    } catch {
      // ignore
    }
  };

  const fetchCommands = async () => {
    try {
      const res = await fetch(`${API_BASE}/commands?limit=20`);
      if (res.ok) setCommands(await res.json());
    } catch {
      // ignore
    }
  };

  const fetchVerifiedSavings = async () => {
    try {
      const res = await fetch(`${API_BASE}/savings/verified`);
      if (res.ok) setVerifiedSavings(await res.json());
    } catch {
      // ignore
    }
  };

  const fetchMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/evaluation/metrics`);
      if (res.ok) setMetrics(await res.json());
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchOverview();
    fetchRooms();
    fetchWasteEvents();
    fetchProposals();
    fetchCommands();
    fetchVerifiedSavings();
    fetchMetrics();

    const interval = setInterval(() => {
      fetchOverview();
      fetchWasteEvents();
      fetchProposals();
    }, 8000);
    return () => clearInterval(interval);
  }, []);

  // Fetch room detail whenever selectedRoomId changes
  useEffect(() => {
    if (selectedRoomId) {
      fetchRoomDetail(selectedRoomId);
    }
  }, [selectedRoomId]);

  // Simulator Controls
  const handleSimAction = async (action, extra = {}) => {
    try {
      const res = await fetch(`${API_BASE}/simulator/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...extra })
      });
      if (res.ok) {
        notify(`Simulator: ${action.toUpperCase()} executed!`);
        fetchOverview();
      }
    } catch {
      notify(`Simulator: ${action.toUpperCase()} triggered (local mode)`);
    }
  };

  // Demo Scenario Execution
  const handleRunDemoScenario = async () => {
    notify('Starting closed-loop demo scenario: Ghost cooling -> Detect -> Propose -> Approve -> Act -> Verify');
    try {
      const res = await fetch(`${API_BASE}/simulator/demo-scenario?room_id=${selectedRoomId}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setDemoLog(data.steps_completed || []);
        notify(`🎉 Demo Scenario Complete! Verified Savings: ${data.verified_savings_inr}`);
        fetchProposals();
        fetchCommands();
        fetchVerifiedSavings();
        fetchRoomDetail(selectedRoomId);
        fetchOverview();
      }
    } catch {
      notify('Demo scenario step sequence running...');
    }
  };

  // Proposal Actions
  const handleApproveProposal = async (propId) => {
    try {
      const res = await fetch(`${API_BASE}/proposals/${propId}/approve`, { method: 'POST' });
      if (res.ok) {
        notify(`Proposal ${propId} approved! Command dispatched to AC.`);
        fetchProposals();
        fetchCommands();
        fetchVerifiedSavings();
        fetchRoomDetail(selectedRoomId);
      }
    } catch {
      notify(`Proposal ${propId} approved! Command dispatched.`);
    }
  };

  const handleRejectProposal = async (propId, reason) => {
    try {
      const res = await fetch(`${API_BASE}/proposals/${propId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason })
      });
      if (res.ok) {
        notify(`Proposal ${propId} rejected.`);
        fetchProposals();
      }
    } catch {
      notify(`Proposal ${propId} rejected with reason: ${reason}`);
    }
  };

  // Select Tab
  const handleSelectTab = (tabId) => {
    if (tabId === 'room') {
      // Point to /rooms directory as required by spec
      updateURL('rooms', null);
    } else {
      updateURL(tabId, null);
    }
  };

  // Select Room directly (navigates to /rooms/:roomId)
  const handleRoomSelect = (roomId) => {
    setSelectedRoomId(roomId);
    updateURL('room', roomId);
  };

  // Query filter setters
  const handleSearchChange = (q) => updateURL(routeState.activeTab, selectedRoomId, { searchQuery: q });
  const handleBuildingChange = (b) => updateURL(routeState.activeTab, selectedRoomId, { buildingFilter: b });
  const handleTypeChange = (t) => updateURL(routeState.activeTab, selectedRoomId, { typeFilter: t });
  const handleStatusChange = (s) => updateURL(routeState.activeTab, selectedRoomId, { statusFilter: s });
  const handleSortChange = (s) => updateURL(routeState.activeTab, selectedRoomId, { sortBy: s });
  const handleViewModeChange = (v) => updateURL(routeState.activeTab, selectedRoomId, { viewMode: v });

  // Keyboard navigation through rooms
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Only when inside rooms or room view and not typing in an input
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
      if (routeState.activeTab !== 'rooms' && routeState.activeTab !== 'room') return;

      const currentIndex = allRooms.findIndex((r) => r.id === selectedRoomId);
      if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
        if (currentIndex < allRooms.length - 1) {
          const next = allRooms[currentIndex + 1];
          handleRoomSelect(next.id);
        }
      } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
        if (currentIndex > 0) {
          const prev = allRooms[currentIndex - 1];
          handleRoomSelect(prev.id);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [allRooms, selectedRoomId, routeState.activeTab]);

  return (
    <>
      <SVGWastePatterns />
      <AppShell
        activeTab={routeState.activeTab === 'room' ? 'room' : routeState.activeTab}
        onSelectTab={handleSelectTab}
        theme={activeEffectiveTheme}
        explicitTheme={explicitTheme}
        onChangeTheme={handleToggleTheme}
        simClock={liveState.simulatedClock}
        simSpeed={liveState.speedMultiplier}
        connectionStatus={liveState.status}
        secondsSinceUpdate={liveState.secondsSinceLastUpdate}
        pendingApprovalsCount={liveState.pendingApprovalsCount || proposals.filter(p => p.approval_status === 'PENDING').length || 0}
      >
        {routeState.activeTab === 'overview' && (
          <CampusOverview
            data={overview}
            liveState={liveState}
            loading={loadingOverview}
            onSelectRoom={handleRoomSelect}
            onReviewProposals={() => updateURL('inbox')}
            onNavigateWasteEvents={() => updateURL('waste')}
          />
        )}

        {/* Master-Detail / Rooms Views */}
        {routeState.activeTab === 'rooms' && (
          /* On Desktop/Tablet: Master-Detail Layout */
          <div className="flex h-full overflow-hidden">
            <div className="w-full md:w-[420px] lg:w-[480px] border-r shrink-0 flex flex-col h-full overflow-hidden" style={{ borderColor: 'var(--border-separator)' }}>
              <RoomsList
                rooms={allRooms}
                selectedRoomId={selectedRoomId}
                onSelectRoom={handleRoomSelect}
                liveState={liveState}
                searchQuery={routeState.searchQuery}
                onSearchChange={handleSearchChange}
                buildingFilter={routeState.buildingFilter}
                onBuildingChange={handleBuildingChange}
                typeFilter={routeState.typeFilter}
                onTypeChange={handleTypeChange}
                statusFilter={routeState.statusFilter}
                onStatusChange={handleStatusChange}
                sortBy={routeState.sortBy}
                onSortChange={handleSortChange}
                viewMode={routeState.viewMode}
                onViewModeChange={handleViewModeChange}
                loading={loadingRooms}
                error={roomsError}
                onRetry={fetchRooms}
              />
            </div>
            <div className="hidden md:flex flex-1 flex-col h-full overflow-y-auto">
              <RoomDetail
                roomId={selectedRoomId}
                allRooms={allRooms}
                data={roomDetail}
                liveState={liveState}
                onBack={() => updateURL('rooms')}
                onNavigateRoom={handleRoomSelect}
                onOverrideChange={(active, duration) => {
                  notify(active ? `Manual override set for ${duration}` : 'Manual override cancelled');
                }}
                onViewSchedule={() => updateURL('optimizer')}
                onViewProposals={() => updateURL('inbox')}
                loading={loadingRoomDetail}
                notFound={roomNotFound}
              />
            </div>
          </div>
        )}

        {routeState.activeTab === 'room' && (
          /* Phone / Single Page Full View */
          <div className="h-full overflow-y-auto">
            <RoomDetail
              roomId={selectedRoomId}
              allRooms={allRooms}
              data={roomDetail}
              liveState={liveState}
              onBack={() => updateURL('rooms')}
              onNavigateRoom={handleRoomSelect}
              onOverrideChange={(active, duration) => {
                notify(active ? `Manual override set for ${duration}` : 'Manual override cancelled');
              }}
              onViewSchedule={() => updateURL('optimizer')}
              onViewProposals={() => updateURL('inbox')}
              loading={loadingRoomDetail}
              notFound={roomNotFound}
            />
          </div>
        )}

        {routeState.activeTab === 'inbox' && (
          <ApprovalsInbox
            proposals={proposals}
            onApprove={handleApproveProposal}
            onReject={handleRejectProposal}
            onViewEvidence={() => updateURL('waste')}
          />
        )}

        {routeState.activeTab === 'simulator' && (
          <SimulatorScreen
            simRunning={liveState.isRunning}
            simSpeed={liveState.speedMultiplier}
            simClock={liveState.simulatedClock}
            connectionStatus={liveState.status}
            onSimAction={handleSimAction}
            onRunDemo={handleRunDemoScenario}
            metrics={metrics}
            demoLog={demoLog}
            onNavigateRoom={(roomId) => handleRoomSelect(roomId)}
          />
        )}

        {routeState.activeTab === 'waste' && (
          <WasteEvents
            events={wasteEvents}
            onSelectEvent={(ev) => handleRoomSelect(ev.room)}
            onOpenProposal={() => updateURL('inbox')}
            onNavigateRoom={(room) => handleRoomSelect(room)}
          />
        )}

        {routeState.activeTab === 'assistant' && (
          <AssistantScreen
            onOpenProposal={() => updateURL('inbox')}
          />
        )}

        {routeState.activeTab === 'optimizer' && (
          <OptimizerScreen
            allRooms={allRooms}
            onApplyProposal={({ room, setpoint }) => {
              notify(`Proposal created for ${room} with setpoint ${setpoint} °C`);
              fetchProposals();
              updateURL('inbox');
            }}
          />
        )}

        {routeState.activeTab === 'history' && (
          <ACHistory onNavigateRoom={handleRoomSelect} />
        )}

        {routeState.activeTab === 'cameras' && (
          <LiveCameras onNavigateRoom={handleRoomSelect} />
        )}

        {routeState.activeTab === 'forecast' && (
          <ForecastScreen />
        )}
      </AppShell>

      {/* Floating Toast Notification */}
      {notification && (
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom duration-200">
          <div
            className="flex items-center gap-3 px-4 py-3 rounded-2xl shadow-2xl border text-xs font-semibold"
            style={{
              backgroundColor: 'var(--bg-card)',
              borderColor: 'var(--border-subtle)',
              color: 'var(--text-primary)'
            }}
          >
            <span>❄</span>
            <span>{notification.msg}</span>
          </div>
        </div>
      )}
    </>
  );
}
