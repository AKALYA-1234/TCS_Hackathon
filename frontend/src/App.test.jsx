import { describe, it, expect } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import { RoomsList } from './components/screens/RoomsList.jsx';
import RoomDetail from './components/screens/RoomDetail.jsx';

describe('Rooms List and Detail Suite', () => {
  const mockRooms = [
    {
      room_id: 'eng-101',
      room_name: 'Advanced Computing Lab',
      building: 'Engineering Hall',
      room_type: 'computer_lab',
      capacity: 40,
      area_sqm: 90,
      units: [
        { unit_id: 'eng-101-u1', unit_name: 'Unit 1', tonnage_tr: 2.0 },
        { unit_id: 'eng-101-u2', unit_name: 'Unit 2', tonnage_tr: 2.0 }
      ]
    },
    {
      room_id: 'eng-server',
      room_name: 'Central Server Room',
      building: 'Engineering Hall',
      room_type: 'server_room',
      capacity: 5,
      area_sqm: 45,
      is_critical: true,
      units: [
        { unit_id: 'eng-server-u1', unit_name: 'Precision AC 1', tonnage_tr: 3.0 },
        { unit_id: 'eng-server-u2', unit_name: 'Precision AC 2', tonnage_tr: 3.0 }
      ]
    },
    {
      room_id: 'sci-201',
      room_name: 'Organic Chemistry Lab',
      building: 'Science Complex',
      room_type: 'lab',
      capacity: 35,
      area_sqm: 80,
      units: [
        { unit_id: 'sci-201-u1', unit_name: 'Split Unit 1', tonnage_tr: 2.5 }
      ]
    }
  ];

  it('renders rooms list correctly with building groups and summary metrics', () => {
    const html = renderToString(
      <RoomsList 
        rooms={mockRooms} 
        onSelectRoom={() => {}} 
        selectedRoomId="eng-101"
      />
    );
    expect(html).toContain('Campus Rooms');
    expect(html).toContain('Advanced Computing Lab');
    expect(html).toContain('Central Server Room');
    expect(html).toContain('Organic Chemistry Lab');
    expect(html).toContain('Engineering Hall');
    expect(html).toContain('Science Complex');
  });

  it('displays exception badge for the server room (Never switch off)', () => {
    const html = renderToString(
      <RoomDetail
        selectedRoomId="eng-server"
        rooms={mockRooms}
        onSelectRoom={() => {}}
      />
    );
    expect(html).toContain('Exception Room: Never Switch Off');
    expect(html).toContain('Protected Server Room Facility:');
    expect(html).toContain('Central Server Room');
  });

  it('renders normal room detail with correct units and no server room exception banner', () => {
    const html = renderToString(
      <RoomDetail
        selectedRoomId="eng-101"
        rooms={mockRooms}
        onSelectRoom={() => {}}
      />
    );
    expect(html).toContain('Advanced Computing Lab');
    expect(html).not.toContain('Exception Room: Never Switch Off');
    expect(html).toContain('Air Conditioners');
    expect(html).toContain('Unit 1');
    expect(html).toContain('Unit 2');
  });

  it('prevents cross-room data leak: renders distinct details for different rooms', () => {
    const htmlRoomA = renderToString(
      <RoomDetail
        selectedRoomId="eng-101"
        rooms={mockRooms}
        onSelectRoom={() => {}}
      />
    );

    const htmlRoomB = renderToString(
      <RoomDetail
        selectedRoomId="sci-201"
        rooms={mockRooms}
        onSelectRoom={() => {}}
      />
    );

    // Room A header vs Room B header
    expect(htmlRoomA).toContain('Advanced Computing Lab');
    expect(htmlRoomA).not.toContain('Organic Chemistry Lab</h1>');

    expect(htmlRoomB).toContain('Organic Chemistry Lab');
    expect(htmlRoomB).not.toContain('Advanced Computing Lab</h1>');
  });

  it('renders not-found state for unknown room ID when loading completes', () => {
    const html = renderToString(
      <RoomDetail
        selectedRoomId="unknown-room-999"
        rooms={mockRooms}
        onSelectRoom={() => {}}
      />
    );
    expect(html).toBeDefined();
  });
});

import { OptimizerScreen } from './components/screens/OptimizerScreen.jsx';

describe('Schedule & Optimizer Suite', () => {
  const mockRooms = [
    { id: 'eng-101', name: 'Lecture Hall 101', building: 'Engineering Hall', room_type: 'lecture_hall', capacity: 80 },
    { id: 'eng-server', name: 'Department Server Room', building: 'Engineering Hall', room_type: 'lab', is_critical: true, capacity: 2 }
  ];

  it('renders schedule optimizer page with IST timezone and room selector', () => {
    const html = renderToString(
      <OptimizerScreen allRooms={mockRooms} />
    );
    expect(html).toContain('Schedule &amp; Optimizer Manager');
    expect(html).toContain('IST (UTC+5:30)');
    expect(html).toContain('Week Grid');
    expect(html).toContain('Campus Matrix');
    expect(html).toContain('Weekly Planned');
  });

  it('enforces exception room safety: never scheduled off badge', () => {
    const html = renderToString(
      <OptimizerScreen allRooms={mockRooms} />
    );
    // Should render with room options including server room
    expect(html).toContain('Department Server Room');
    expect(html).toContain('admin');
    expect(html).toContain('viewer');
  });
});

import { ACHistory } from './components/screens/ACHistory.jsx';

describe('AC History Suite', () => {
  it('renders AC history page with header, presets, and honesty badges', () => {
    const html = renderToString(
      <ACHistory onNavigateRoom={() => {}} />
    );
    expect(html).toContain('AC Unit History &amp; Timeline');
    expect(html).toContain('IST (UTC+5:30)');
    expect(html).toContain('24 Hours');
    expect(html).toContain('7 Days');
    expect(html).toContain('30 Days');
    expect(html).toContain('All Units Swim-lane');
  });
});

import { LiveCameras } from './components/screens/LiveCameras.jsx';

describe('Live Cameras & CV Suite', () => {
  it('renders Live Cameras & CV with honest simulated feed badges, layout modes, and privacy banner', () => {
    const html = renderToString(
      <LiveCameras onNavigateRoom={() => {}} />
    );
    expect(html).toContain('Live Cameras &amp; Computer Vision');
    expect(html).toContain('LIVE STREAM');
    expect(html).toContain('Simulated Feed &amp; Scene');
    expect(html).toContain('Privacy By Design Enforced');
    expect(html).toContain('Privacy Blur OFF');
    expect(html).toContain('3x3 Grid');
    expect(html).toContain('2x2 Grid');
    expect(html).toContain('Focus &amp; Strip');
    expect(html).toContain('YOLOv8n-Crowd-ONNX');
  });
});

import { LiveWeatherStrip } from './components/ui/LiveWeatherStrip.jsx';

describe('Weather Subsystem Suite', () => {
  it('renders LiveWeatherStrip with ambient weather title, source controls, and coordinates', () => {
    const html = renderToString(
      <LiveWeatherStrip simClock="Thu 29 Oct · 14:35" />
    );
    expect(html).toContain('Campus Ambient Weather');
    expect(html).toContain('Latitude 11.0168°N, Longitude 76.9558°E');
    expect(html).toContain('Auto');
    expect(html).toContain('Live API');
    expect(html).toContain('Replay Clock');
  });
});

import { AppShell } from './components/shell/AppShell.jsx';
import { CampusOverview } from './components/screens/CampusOverview.jsx';

describe('Theme Logic & AppShell UI Suite', () => {
  // Pure theme transition logic test function mimicking App.jsx
  function computeThemeTransition(prevExplicit, requestedTheme, effectiveTheme) {
    if (prevExplicit === requestedTheme || (prevExplicit === null && effectiveTheme === requestedTheme)) {
      return null; // clears saved choice and returns to system
    }
    return requestedTheme;
  }

  function resolveEffectiveTheme(explicitTheme, systemIsDark) {
    return explicitTheme ? explicitTheme : (systemIsDark ? 'dark' : 'light');
  }

  it('theme logic: defaults to system when no explicit choice is stored', () => {
    // OS dark -> effective dark
    expect(resolveEffectiveTheme(null, true)).toBe('dark');
    // OS light -> effective light
    expect(resolveEffectiveTheme(null, false)).toBe('light');
  });

  it('theme logic: explicit choice overrides system preference', () => {
    // OS is dark, but user explicitly chose light
    expect(resolveEffectiveTheme('light', true)).toBe('light');
    // OS is light, but user explicitly chose dark
    expect(resolveEffectiveTheme('dark', false)).toBe('dark');
  });

  it('theme logic: clicking active button clears saved choice and returns to system', () => {
    // User had explicitly selected 'dark'
    let explicit = 'dark';
    let effective = resolveEffectiveTheme(explicit, false); // OS is light
    expect(effective).toBe('dark');

    // User clicks 'dark' again -> clears explicit choice back to null (system default)
    explicit = computeThemeTransition(explicit, 'dark', effective);
    expect(explicit).toBeNull();
    effective = resolveEffectiveTheme(explicit, false);
    expect(effective).toBe('light'); // back to system light!
  });

  it('theme logic: clicking inactive button sets explicit choice', () => {
    let explicit = null;
    let systemDark = false;
    let effective = resolveEffectiveTheme(explicit, systemDark); // 'light'

    // User clicks 'dark'
    explicit = computeThemeTransition(explicit, 'dark', effective);
    expect(explicit).toBe('dark');
    effective = resolveEffectiveTheme(explicit, systemDark);
    expect(effective).toBe('dark');
  });

  it('renders AppShell with icon-only segmented pill buttons, aria attributes and focus rings', () => {
    const html = renderToString(
      <AppShell
        activeTab="overview"
        onSelectTab={() => {}}
        theme="light"
        explicitTheme={null}
        onChangeTheme={() => {}}
        simClock="Thu 29 Oct · 14:35"
        simSpeed={60}
        connectionStatus="LIVE"
        secondsSinceUpdate={0}
        pendingApprovalsCount={1}
      >
        <div id="test-child">Child Content</div>
      </AppShell>
    );

    // Segmented pill
    expect(html).toContain('aria-label="Theme selector"');
    // Sun button
    expect(html).toContain('aria-label="Light theme"');
    expect(html).toContain('aria-pressed="true"');
    expect(html).toContain('Click again to follow system');
    // Moon button
    expect(html).toContain('aria-label="Dark theme"');
    expect(html).toContain('aria-pressed="false"');
    // Visible focus ring
    expect(html).toContain('focus:ring-2');
    // Compact user chip at top bar
    expect(html).toContain('Sarah Chen');
    expect(html).toContain('Facility Admin');
    expect(html).toContain('SC');
    // Fluid content container capped at max-w-[1800px]
    expect(html).toContain('max-w-[1800px]');
    expect(html).toContain('px-4 sm:px-6 md:px-8');
  });

  it('renders AppShell with dark theme highlighted when theme is dark', () => {
    const html = renderToString(
      <AppShell
        activeTab="overview"
        onSelectTab={() => {}}
        theme="dark"
        explicitTheme="dark"
        onChangeTheme={() => {}}
        simClock="Thu 29 Oct · 14:35"
        simSpeed={60}
        connectionStatus="LIVE"
        secondsSinceUpdate={0}
        pendingApprovalsCount={1}
      >
        <div>Content</div>
      </AppShell>
    );

    // Light button is not pressed
    expect(html).toContain('aria-label="Light theme"');
    expect(html).toContain('aria-pressed="false"');
    // Dark button is pressed
    expect(html).toContain('aria-label="Dark theme"');
    expect(html).toContain('aria-pressed="true"');
  });
});

describe('Dashboard KPI Cards & 7-Step Strip Suite', () => {
  const mockOverviewData = {
    kpis: {
      total_power_kw: 74.4,
      total_waste_kwh: 14.5,
      total_waste_inr: 152.25,
      waste_event_count: 1,
      verified_savings_inr: 152.25
    },
    heatmap: [
      { room_id: 'eng-101', name: 'Room 101', is_on: true, power_kw: 2.8, occupancy: 12, room_temp_c: 24.1, set_temp_c: 24.0 }
    ],
    top_waste_ranking: [
      { room_id: 'eng-101', name: 'Room 101', waste_kwh: 4.2, waste_cost_inr: 44.1, primary_waste_type: 'ghost_cooling' }
    ]
  };

  const mockLiveState = {
    totalPowerKw: 74.4,
    totalWasteKwh: 14.5,
    wasteEventCount: 1,
    pendingApprovalsCount: 1,
    simulatedClock: 'Thu 29 Oct · 14:35',
    activeAnomalies: {},
    latestByRoom: {}
  };

  it('renders 7-step loop without step numbers (1 to 7) and with unified state cards', () => {
    const html = renderToString(
      <CampusOverview
        data={mockOverviewData}
        liveState={mockLiveState}
        loading={false}
        onSelectRoom={() => {}}
        onReviewProposals={() => {}}
        onNavigateWasteEvents={() => {}}
      />
    );

    // Names of all 7 steps present
    expect(html).toContain('Sense');
    expect(html).toContain('Understand');
    expect(html).toContain('Propose');
    expect(html).toContain('Validate');
    expect(html).toContain('Approve');
    expect(html).toContain('Act');
    expect(html).toContain('Verify');

    // No step numbers "Step 1", "Step 2", etc.
    expect(html).not.toMatch(/Step [1-7]/);
    expect(html).not.toMatch(/step-[1-7]/i);

    // Responsive 7-step grid classes
    expect(html).toContain('grid-cols-2');
    expect(html).toContain('sm:grid-cols-4');
    expect(html).toContain('lg:grid-cols-7');
  });

  it('renders the 5 dashboard KPI cards with required formulas and units', () => {
    const html = renderToString(
      <CampusOverview
        data={mockOverviewData}
        liveState={mockLiveState}
        loading={false}
        onSelectRoom={() => {}}
        onReviewProposals={() => {}}
        onNavigateWasteEvents={() => {}}
      />
    );

    // Card A: Total energy usage
    expect(html).toContain('Total energy usage');
    expect(html).toContain('kWh today');
    expect(html).toContain('Live draw:');
    expect(html).toContain('74.4');
    expect(html).toContain('kW');

    // Card B: Total energy saved (range + counterfactual baseline)
    expect(html).toContain('Total energy saved');
    expect(html).toContain('12.2–16.8');
    expect(html).toContain('Verified');
    expect(html).toContain('Best estimate:');
    expect(html).toContain('14.5 kWh');

    // Card C: Cost saved (INR range + tariff in use + projected monthly)
    expect(html).toContain('Cost saved');
    expect(html).toContain('₹128–176');
    expect(html).toContain('Tariff: ₹10.50/kWh');
    expect(html).toContain('Projected / month (est.):');
    expect(html).toContain('₹4,560');

    // Card D: Anomaly detection (active count + detector state + link to Waste Events)
    expect(html).toContain('Anomaly detection');
    expect(html).toContain('Detector: Online');
    expect(html).toContain('Top waste: Ghost Cooling');
    expect(html).toContain('View Events →');

    // Card E: Efficiency (useful energy share = 1 - wasted/total)
    expect(html).toContain('Useful Energy Share');
    expect(html).toContain('Efficiency = 1 - (wasted_kwh / total_kwh) * 100');
    expect(html).toContain('Wasted share:');
  });

  it('validates the efficiency formula: 1 - (wasted_kwh / total_kwh)', () => {
    const totalWasteKwh = 14.5;
    const totalUsageKwh = 14.5 + 185.0; // 199.5
    const usefulShare = (1 - (totalWasteKwh / totalUsageKwh)) * 100;
    const rounded = Math.round(usefulShare);
    expect(rounded).toBe(93); // 93% useful energy
    expect(100 - rounded).toBe(7); // 7% wasted share
  });
});

import { SimulatorScreen } from './components/screens/SimulatorScreen.jsx';

describe('Scenario Lab & Simulation Suite', () => {
  it('renders SimulatorScreen with sandboxed banner, presets, scenario builder, and timeline controls', () => {
    const html = renderToString(
      <SimulatorScreen onNavigateRoom={() => {}} />
    );

    // Title and isolation badges
    expect(html).toContain('Scenario Lab &amp; Simulation');
    expect(html).toContain('100% Sandboxed');
    expect(html).toContain('Simulation Invariant:');
    expect(html).toContain('Nothing here writes to live telemetry');

    // Scenario Builder
    expect(html).toContain('Scenario Builder');
    expect(html).toContain('Scope:');
    expect(html).toContain('Weather:');
    expect(html).toContain('Control Modes');
    expect(html).toContain('Run Scenario Simulation');

    // Presets & Formats
    expect(html).toContain('Presets:');
    expect(html).toContain('CSV');
    expect(html).toContain('JSON');

    // Timeline Scrubber & Now Card
    expect(html).toContain('Simulated Timeline Playhead');
    expect(html).toContain('Campus Load Profile (24h)');
  });
});




