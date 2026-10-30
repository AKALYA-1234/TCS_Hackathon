/**
 * Centralized Live Streaming Client & Ring Buffer Store for AC Optimization.
 * Features:
 * - Server-Sent Events (SSE) connection to /api/ac/stream
 * - Exponential backoff reconnect with random jitter
 * - Heartbeat & Stale detector (marks STALE if no message received within threshold)
 * - Ring buffers for room-level telemetry (fixed window: last 6 hours of simulated time)
 * - Throttled UI flush (at most 2-4 times per second via requestAnimationFrame/timer)
 * - Tracks connection status: 'CONNECTING', 'LIVE', 'RECONNECTING', 'STALE', 'STOPPED'
 */

const MAX_RING_BUFFER_PER_ROOM = 80;
const STALE_TIMEOUT_MS = 6000;

class LiveDataManager {
  constructor() {
    this.status = 'CONNECTING'; // 'CONNECTING' | 'LIVE' | 'RECONNECTING' | 'STALE' | 'STOPPED'
    this.lastMessageTime = 0;
    this.secondsSinceLastUpdate = 0;
    this.eventSource = null;
    this.reconnectAttempts = 0;
    this.listeners = new Set();

    // Latest global state from stream
    this.state = {
      simulatedClock: 'Thu 29 Oct · 14:35',
      simulatedIso: null,
      speedMultiplier: 60,
      isRunning: true,
      totalPowerKw: 75.0,
      totalWasteKwh: 14.5,
      totalWasteInr: 152.25,
      wasteEventCount: 1,
      verifiedSavingsKwh: 14.5,
      verifiedSavingsInr: 152.25,
      pendingApprovalsCount: 1,
      activeAnomalies: {},
      // Keyed by room_id -> array of time-series objects {timestamp, actual_power_kw, baseline_kw, lower_bound_kw, upper_bound_kw, room_temp_c, set_temp_c, occupancy}
      roomSeries: {},
      // Latest telemetry per room
      latestByRoom: {}
    };

    // Buffer for pending batch
    this.pendingTelemetry = [];
    this.flushScheduled = false;

    // Stale checker interval
    this.staleInterval = setInterval(() => this.checkStale(), 1000);
  }

  subscribe(listener) {
    this.listeners.add(listener);
    // Immediate callback with current state
    listener(this.getState());
    return () => this.listeners.delete(listener);
  }

  notify() {
    const s = this.getState();
    this.listeners.forEach((fn) => {
      try {
        fn(s);
      } catch (err) {
        console.error('Error in live data listener:', err);
      }
    });
  }

  getState() {
    return {
      status: this.status,
      secondsSinceLastUpdate: this.secondsSinceLastUpdate,
      ...this.state
    };
  }

  connect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    this.status = this.reconnectAttempts > 0 ? 'RECONNECTING' : 'CONNECTING';
    this.notify();

    try {
      this.eventSource = new EventSource('/api/ac/stream');

      this.eventSource.onopen = () => {
        this.reconnectAttempts = 0;
        this.status = this.state.isRunning ? 'LIVE' : 'STOPPED';
        this.lastMessageTime = Date.now();
        this.secondsSinceLastUpdate = 0;
        this.notify();
      };

      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleMessage(data);
        } catch (e) {
          // ignore corrupted frame
        }
      };

      this.eventSource.onerror = () => {
        if (this.eventSource) {
          this.eventSource.close();
          this.eventSource = null;
        }
        this.status = 'RECONNECTING';
        this.notify();
        this.scheduleReconnect();
      };
    } catch (e) {
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    this.reconnectAttempts += 1;
    // Exponential backoff with jitter: 1s, 2s, 4s, capped at 10s
    const baseDelay = Math.min(10000, 1000 * Math.pow(1.5, this.reconnectAttempts));
    const jitter = Math.random() * 500;
    const delay = baseDelay + jitter;

    setTimeout(() => {
      this.connect();
    }, delay);
  }

  checkStale() {
    if (this.lastMessageTime > 0) {
      const elapsed = Date.now() - this.lastMessageTime;
      this.secondsSinceLastUpdate = Math.floor(elapsed / 1000);

      if (elapsed > STALE_TIMEOUT_MS && this.status === 'LIVE') {
        this.status = 'STALE';
        this.notify();
      }
    }
  }

  handleMessage(msg) {
    this.lastMessageTime = Date.now();
    this.secondsSinceLastUpdate = 0;

    if (msg.type === 'SIM_TICK') {
      const isRunning = Boolean(msg.is_running);
      this.status = isRunning ? 'LIVE' : 'STOPPED';

      // Format simulated clock nicely: e.g. "Thu 29 Oct · 14:35"
      let formattedClock = this.state.simulatedClock;
      if (msg.simulated_clock) {
        try {
          const d = new Date(msg.simulated_clock);
          const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
          const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
          const dayName = days[d.getUTCDay()];
          const dayNum = d.getUTCDate();
          const monthName = months[d.getUTCMonth()];
          const hh = String(d.getUTCHours()).padStart(2, '0');
          const mm = String(d.getUTCMinutes()).padStart(2, '0');
          formattedClock = `${dayName} ${dayNum} ${monthName} · ${hh}:${mm}`;
        } catch {
          // fallback
        }
      }

      this.state.simulatedClock = formattedClock;
      this.state.simulatedIso = msg.simulated_clock;
      this.state.speedMultiplier = msg.speed_multiplier || this.state.speedMultiplier;
      this.state.isRunning = isRunning;
      this.state.totalPowerKw = msg.total_power_kw ?? this.state.totalPowerKw;
      this.state.totalWasteKwh = msg.total_waste_kwh ?? this.state.totalWasteKwh;
      this.state.totalWasteInr = msg.total_waste_inr ?? this.state.totalWasteInr;
      this.state.wasteEventCount = msg.waste_event_count ?? this.state.wasteEventCount;
      this.state.verifiedSavingsKwh = msg.verified_savings_kwh ?? this.state.verifiedSavingsKwh;
      this.state.verifiedSavingsInr = msg.verified_savings_inr ?? this.state.verifiedSavingsInr;
      this.state.pendingApprovalsCount = msg.pending_approvals_count ?? this.state.pendingApprovalsCount;
      this.state.activeAnomalies = msg.active_anomalies || {};

      if (Array.isArray(msg.telemetry)) {
        this.pendingTelemetry.push(...msg.telemetry);
      }

      this.scheduleFlush();
    }
  }

  scheduleFlush() {
    if (this.flushScheduled) return;
    this.flushScheduled = true;

    // Batch and flush at 4Hz (every 250ms) to ensure smooth animations without freezing
    setTimeout(() => {
      this.flushPendingData();
      this.flushScheduled = false;
    }, 250);
  }

  flushPendingData() {
    if (this.pendingTelemetry.length === 0) {
      this.notify();
      return;
    }

    const items = this.pendingTelemetry;
    this.pendingTelemetry = [];

    // Group items into roomSeries ring buffers
    items.forEach((item) => {
      const roomId = item.room_id;
      if (!roomId) return;

      if (!this.state.roomSeries[roomId]) {
        this.state.roomSeries[roomId] = [];
      }

      const series = this.state.roomSeries[roomId];
      const entry = {
        timestamp: item.timestamp,
        actual_power_kw: item.power_kw ?? 0.0,
        baseline_kw: item.baseline_kw ?? 0.0,
        lower_bound_kw: item.lower_bound_kw ?? 0.0,
        upper_bound_kw: item.upper_bound_kw ?? 0.0,
        set_temp_c: item.set_temp_c ?? 24.0,
        room_temp_c: item.room_temp_c ?? 24.0,
        outdoor_temp_c: item.outdoor_temp_c ?? 30.0,
        occupancy: item.occupancy ?? 0,
        on_off_status: item.on_off_status ?? 'OFF',
        scheduled_hours: Boolean(item.scheduled_hours)
      };

      // Deduplicate by timestamp
      const last = series[series.length - 1];
      if (!last || last.timestamp !== entry.timestamp) {
        series.push(entry);
        if (series.length > MAX_RING_BUFFER_PER_ROOM) {
          series.shift();
        }
      }

      this.state.latestByRoom[roomId] = entry;
    });

    this.notify();
  }

  seedInitialRoomSeries(roomId, initialSeries) {
    if (!Array.isArray(initialSeries) || initialSeries.length === 0) return;
    if (!this.state.roomSeries[roomId] || this.state.roomSeries[roomId].length === 0) {
      this.state.roomSeries[roomId] = initialSeries.slice(-MAX_RING_BUFFER_PER_ROOM);
      this.notify();
    }
  }

  destroy() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    if (this.staleInterval) {
      clearInterval(this.staleInterval);
    }
    this.listeners.clear();
  }
}

// Global Singleton Instance
export const liveData = new LiveDataManager();
liveData.connect();
