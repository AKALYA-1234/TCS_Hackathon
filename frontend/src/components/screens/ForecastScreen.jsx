import React, { useState } from 'react';
import { ChevronRight, ChevronDown, TrendingUp, Sun, Users, Clock, Zap } from 'lucide-react';
import { Button } from '../ui/BaseComponents';

export function ForecastScreen() {
  const [period, setPeriod] = useState('Weekly');
  const [activeDriver, setActiveDriver] = useState('weather');
  const [expandedRooms, setExpandedRooms] = useState({ 'Lab 204': true });

  const toggleRoomExpand = (room) => {
    setExpandedRooms(prev => ({ ...prev, [room]: !prev[room] }));
  };

  const forecastData = [
    { room: 'A - 101', units: '3 units', forecast: '612 kWh', interval: '566–661', rangePos: 75, cost: '₹5,722', vsLast: '-1.8%', vsLastClass: 'text-emerald-500' },
    { room: 'A - 102', units: '2 units', forecast: '548 kWh', interval: '507–592', rangePos: 70, cost: '₹5,124', vsLast: '+0.4%', vsLastClass: 'text-amber-500' },
    { room: 'A - 201', units: '2 units', forecast: '404 kWh', interval: '374–436', rangePos: 55, cost: '₹3,777', vsLast: '-2.6%', vsLastClass: 'text-emerald-500' },
    {
      room: 'Lab 204',
      units: '2 units',
      forecast: '391 kWh',
      interval: '362–422',
      rangePos: 52,
      cost: '₹3,656',
      vsLast: '-3.3%',
      vsLastClass: 'text-emerald-500',
      subUnits: [
        { name: 'AC-204-N', forecast: '206 kWh', interval: '191–222', cost: '₹1,926' },
        { name: 'AC-204-S', forecast: '185 kWh', interval: '171–200', cost: '₹1,730' }
      ]
    },
    { room: 'Lab 205', units: '2 units', forecast: '366 kWh', interval: '339–395', rangePos: 48, cost: '₹3,422', vsLast: '+1.2%', vsLastClass: 'text-amber-500' },
    { room: 'Board Room', units: '1 unit', forecast: '322 kWh', interval: '298–348', rangePos: 42, cost: '₹3,011', vsLast: '-0.9%', vsLastClass: 'text-emerald-500' },
    { room: '10 other rooms', units: '', forecast: '4,368 kWh', interval: '4,259–4,477', rangePos: 65, cost: '₹40,841', vsLast: '-2.4%', vsLastClass: 'text-emerald-500' }
  ];

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* 1. Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
            Forecast
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
            Week of Monday 26 October to Sunday 1 November, with 80% intervals.
          </p>
        </div>

        {/* Period Switcher (Weekly / Monthly) */}
        <div
          className="inline-flex p-1 rounded-xl self-start sm:self-auto"
          style={{ backgroundColor: 'var(--bg-well)', border: '1px solid var(--border-subtle)' }}
        >
          {['Weekly', 'Monthly'].map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className="px-3.5 py-1.5 text-xs font-semibold rounded-lg cursor-pointer transition-all"
              style={{
                backgroundColor: period === p ? 'var(--bg-card)' : 'transparent',
                color: period === p ? 'var(--text-primary)' : 'var(--text-secondary)',
                boxShadow: period === p ? 'var(--shadow-card)' : 'none'
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* 2. KPI Cards (3 columns) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div
          className="p-5 rounded-2xl border space-y-1"
          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
        >
          <div className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Energy</div>
          <div className="text-3xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
            7,011 <span className="text-base font-normal" style={{ color: 'var(--text-tertiary)' }}>kWh</span>
          </div>
          <div className="text-xs tabular-nums" style={{ color: 'var(--text-tertiary)' }}>
            80% range 6,760–7,290 kWh
          </div>
        </div>

        <div
          className="p-5 rounded-2xl border space-y-1"
          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
        >
          <div className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Cost</div>
          <div className="text-3xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
            ₹65.6k
          </div>
          <div className="text-xs tabular-nums" style={{ color: 'var(--text-tertiary)' }}>
            80% range ₹63.2k–₹68.2k
          </div>
        </div>

        <div
          className="p-5 rounded-2xl border space-y-1"
          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
        >
          <div className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Against last week</div>
          <div className="text-3xl font-bold tabular-nums" style={{ color: 'var(--status-healthy)' }}>
            −2.1%
          </div>
          <div className="text-xs tabular-nums" style={{ color: 'var(--text-tertiary)' }}>
            Last week 7,160 kWh
          </div>
        </div>
      </div>

      {/* 3. Daily Energy Chart with 80% Whiskers */}
      <div
        className="p-6 rounded-2xl border space-y-4"
        style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
              Daily energy, kWh
            </h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
              Solid is measured, hatched is forecast, whiskers are the 80% interval.
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-xs" style={{ backgroundColor: 'var(--accent)' }} />
              <span style={{ color: 'var(--text-secondary)' }}>Measured</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-xs border" style={{ borderColor: 'var(--accent)', background: 'repeating-linear-gradient(45deg, transparent, transparent 2px, var(--accent) 2px, var(--accent) 4px)' }} />
              <span style={{ color: 'var(--text-secondary)' }}>Forecast</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-sm leading-none">I</span>
              <span style={{ color: 'var(--text-secondary)' }}>80% interval</span>
            </div>
          </div>
        </div>

        {/* SVG Bar Chart with Whiskers */}
        <div className="h-64 w-full pt-4">
          <svg className="w-full h-full" viewBox="0 0 700 220">
            {/* Horizontal Grid lines */}
            <line x1="40" y1="30" x2="680" y2="30" stroke="var(--border-subtle)" strokeWidth="1" strokeDasharray="3 3" />
            <line x1="40" y1="80" x2="680" y2="80" stroke="var(--border-subtle)" strokeWidth="1" strokeDasharray="3 3" />
            <line x1="40" y1="130" x2="680" y2="130" stroke="var(--border-subtle)" strokeWidth="1" strokeDasharray="3 3" />
            <line x1="40" y1="180" x2="680" y2="180" stroke="var(--border-subtle)" strokeWidth="1" />

            {/* Pattern def for hatched bars */}
            <defs>
              <pattern id="forecastHatch" width="6" height="6" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
                <line x1="0" y1="0" x2="0" y2="6" stroke="var(--accent)" strokeWidth="1.5" />
              </pattern>
            </defs>

            {/* Bars: Mon, Tue, Wed (Solid Measured), Thu (Split), Fri, Sat, Sun (Hatched Forecast) */}
            {/* Mon */}
            <rect x="75" y="55" width="48" height="125" rx="6" fill="var(--accent)" />
            {/* Tue */}
            <rect x="160" y="50" width="48" height="130" rx="6" fill="var(--accent)" />
            {/* Wed */}
            <rect x="245" y="52" width="48" height="128" rx="6" fill="var(--accent)" />

            {/* Thu (Measured partial + Forecast hatched) */}
            <rect x="330" y="48" width="48" height="132" rx="6" fill="url(#forecastHatch)" stroke="var(--accent)" strokeWidth="1" />
            <rect x="330" y="105" width="48" height="75" rx="6" fill="var(--accent)" />
            {/* Thu Whisker */}
            <line x1="354" y1="38" x2="354" y2="60" stroke="var(--text-primary)" strokeWidth="1.5" />
            <line x1="346" y1="38" x2="362" y2="38" stroke="var(--text-primary)" strokeWidth="1.5" />
            <line x1="346" y1="60" x2="362" y2="60" stroke="var(--text-primary)" strokeWidth="1.5" />

            {/* Fri (Hatched) */}
            <rect x="415" y="58" width="48" height="122" rx="6" fill="url(#forecastHatch)" stroke="var(--accent)" strokeWidth="1" />
            {/* Fri Whisker */}
            <line x1="439" y1="46" x2="439" y2="72" stroke="var(--text-primary)" strokeWidth="1.5" />
            <line x1="431" y1="46" x2="447" y2="46" stroke="var(--text-primary)" strokeWidth="1.5" />
            <line x1="431" y1="72" x2="447" y2="72" stroke="var(--text-primary)" strokeWidth="1.5" />

            {/* Sat (Hatched) */}
            <rect x="500" y="105" width="48" height="75" rx="6" fill="url(#forecastHatch)" stroke="var(--accent)" strokeWidth="1" />
            {/* Sat Whisker */}
            <line x1="524" y1="94" x2="524" y2="116" stroke="var(--text-primary)" strokeWidth="1.5" />
            <line x1="516" y1="94" x2="532" y2="94" stroke="var(--text-primary)" strokeWidth="1.5" />
            <line x1="516" y1="116" x2="532" y2="116" stroke="var(--text-primary)" strokeWidth="1.5" />

            {/* Sun (Hatched) */}
            <rect x="585" y="125" width="48" height="55" rx="6" fill="url(#forecastHatch)" stroke="var(--accent)" strokeWidth="1" />
            {/* Sun Whisker */}
            <line x1="609" y1="114" x2="609" y2="134" stroke="var(--text-primary)" strokeWidth="1.5" />
            <line x1="601" y1="114" x2="617" y2="114" stroke="var(--text-primary)" strokeWidth="1.5" />
            <line x1="601" y1="134" x2="617" y2="134" stroke="var(--text-primary)" strokeWidth="1.5" />

            {/* X Labels */}
            <text x="99" y="200" fill="var(--text-tertiary)" fontSize="10" textAnchor="middle">Mon 26</text>
            <text x="184" y="200" fill="var(--text-tertiary)" fontSize="10" textAnchor="middle">Tue 27</text>
            <text x="269" y="200" fill="var(--text-tertiary)" fontSize="10" textAnchor="middle">Wed 28</text>
            <text x="354" y="200" fill="var(--accent)" fontSize="10" fontWeight="bold" textAnchor="middle">Thu 29</text>
            <text x="439" y="200" fill="var(--text-tertiary)" fontSize="10" textAnchor="middle">Fri 30</text>
            <text x="524" y="200" fill="var(--text-tertiary)" fontSize="10" textAnchor="middle">Sat 31</text>
            <text x="609" y="200" fill="var(--text-tertiary)" fontSize="10" textAnchor="middle">Sun 1</text>
          </svg>
        </div>
      </div>

      {/* 4. What moves the forecast (Driver toggles) */}
      <div
        className="p-6 rounded-2xl border space-y-4"
        style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
      >
        <div>
          <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
            What moves the forecast
          </h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Pick a driver to see its effect compared with the previous period.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {[
            { id: 'weather', label: 'Weather', val: '−1.2%', icon: Sun },
            { id: 'headcount', label: 'Headcount', val: '−0.6%', icon: Users },
            { id: 'timetable', label: 'Timetable', val: '−0.7%', icon: Clock },
            { id: 'peakhours', label: 'Peak hours', val: '+0.4% cost', icon: Zap }
          ].map((d) => (
            <button
              key={d.id}
              onClick={() => setActiveDriver(d.id)}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold cursor-pointer border transition-all"
              style={{
                backgroundColor: activeDriver === d.id ? 'var(--bg-well)' : 'var(--bg-card)',
                borderColor: activeDriver === d.id ? 'var(--accent)' : 'var(--border-subtle)',
                color: 'var(--text-primary)'
              }}
            >
              <d.icon size={14} style={{ color: 'var(--accent)' }} />
              <span>{d.label}</span>
              <span className="font-bold tabular-nums" style={{ color: d.val.startsWith('+') ? 'var(--status-review)' : 'var(--status-healthy)' }}>
                {d.val}
              </span>
            </button>
          ))}
        </div>

        {/* Driver Description Pill */}
        <div
          className="p-3.5 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
          style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}
        >
          <div className="font-bold" style={{ color: 'var(--text-primary)' }}>
            Highs of 33–35 °C, about 2 °C below last week.
          </div>
          <div style={{ color: 'var(--text-tertiary)' }}>
            Forecast uses the 7-day weather outlook, refreshed hourly in the simulation.
          </div>
        </div>
      </div>

      {/* 5. Hierarchical Table by Room and Unit */}
      <div
        className="rounded-2xl border overflow-hidden"
        style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
      >
        <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>
            By room and unit
          </div>
          <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            Intervals do not add up across rooms
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
                <th className="py-3 px-4 font-medium">Room or unit</th>
                <th className="py-3 px-4 font-medium">Forecast</th>
                <th className="py-3 px-4 font-medium">80% interval</th>
                <th className="py-3 px-4 font-medium">Range</th>
                <th className="py-3 px-4 font-medium">Cost</th>
                <th className="py-3 px-4 font-medium">vs last week</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
              {forecastData.map((row) => {
                const isExpanded = expandedRooms[row.room];
                return (
                  <React.Fragment key={row.room}>
                    <tr
                      onClick={() => row.subUnits && toggleRoomExpand(row.room)}
                      className={`transition-colors ${row.subUnits ? 'cursor-pointer hover:bg-slate-500/5' : ''}`}
                    >
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          {row.subUnits ? (
                            isExpanded ? <ChevronDown size={14} style={{ color: 'var(--text-tertiary)' }} /> : <ChevronRight size={14} style={{ color: 'var(--text-tertiary)' }} />
                          ) : (
                            <span className="w-3.5" />
                          )}
                          <span className="font-bold" style={{ color: 'var(--text-primary)' }}>
                            {row.room}
                          </span>
                          {row.units && (
                            <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                              {row.units}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                        {row.forecast}
                      </td>
                      <td className="py-3.5 px-4 tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                        {row.interval}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="w-24 h-1 rounded-full bg-slate-200 dark:bg-white/10 relative">
                          <div
                            className="w-2 h-2 rounded-full absolute -top-0.5"
                            style={{
                              left: `${row.rangePos}%`,
                              backgroundColor: 'var(--accent)'
                            }}
                          />
                        </div>
                      </td>
                      <td className="py-3.5 px-4 tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                        {row.cost}
                      </td>
                      <td className="py-3.5 px-4 font-semibold tabular-nums" style={{ color: row.vsLast.startsWith('-') ? 'var(--status-healthy)' : 'var(--status-review)' }}>
                        {row.vsLast}
                      </td>
                    </tr>

                    {/* Nested Sub-units if expanded */}
                    {row.subUnits && isExpanded && row.subUnits.map((sub) => (
                      <tr key={sub.name} style={{ backgroundColor: 'var(--bg-well)' }}>
                        <td className="py-2.5 px-4 pl-10 font-medium" style={{ color: 'var(--text-secondary)' }}>
                          {sub.name}
                        </td>
                        <td className="py-2.5 px-4 tabular-nums" style={{ color: 'var(--text-primary)' }}>
                          {sub.forecast}
                        </td>
                        <td className="py-2.5 px-4 tabular-nums" style={{ color: 'var(--text-tertiary)' }}>
                          {sub.interval}
                        </td>
                        <td className="py-2.5 px-4">
                          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: 'var(--accent)' }} />
                        </td>
                        <td className="py-2.5 px-4 tabular-nums" style={{ color: 'var(--text-tertiary)' }}>
                          {sub.cost}
                        </td>
                        <td className="py-2.5 px-4"></td>
                      </tr>
                    ))}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
