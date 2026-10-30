import React, { useState, useEffect } from 'react';
import { Cloud, Sun, Wind, Droplets, RefreshCw, AlertCircle, Thermometer, ChevronRight } from 'lucide-react';

export function LiveWeatherStrip({ simClock }) {
  const [weatherData, setWeatherData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedSource, setSelectedSource] = useState('auto'); // 'auto', 'live', 'replay'
  const [showLiveModal, setShowLiveModal] = useState(false);

  const fetchWeather = async (sourceOverride) => {
    setLoading(true);
    setError(null);
    try {
      const src = sourceOverride || selectedSource;
      const url = src === 'auto' ? '/api/ac/weather' : `/api/ac/weather?source=${src}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setWeatherData(json);
    } catch (err) {
      console.error('Failed to load weather telemetry:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWeather(selectedSource);
    // Refresh weather telemetry every 5 minutes
    const interval = setInterval(() => fetchWeather(selectedSource), 300000);
    return () => clearInterval(interval);
  }, [selectedSource]);

  const curr = weatherData?.current;
  const isLive = weatherData?.is_live;
  const sourceLabel = weatherData?.source || 'Loading...';
  const statusBadge = weatherData?.status || 'connecting';

  // 24-hour strip items
  const forecastStrip = weatherData?.forecast_24h?.slice(0, 12) || [];

  return (
    <div
      className="p-4 rounded-[5px] border shadow-xs transition-all relative overflow-hidden"
      style={{
        backgroundColor: 'var(--bg-card)',
        borderColor: 'var(--border-subtle)'
      }}
    >
      {/* Top Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b" style={{ borderColor: 'var(--border-separator)' }}>
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0"
            style={{
              backgroundColor: isLive ? 'rgba(59, 130, 246, 0.15)' : 'rgba(245, 158, 11, 0.15)',
              color: isLive ? '#3b82f6' : '#f59e0b'
            }}
          >
            {isLive ? <Sun className="w-4 h-4 text-amber-500 animate-spin-slow" /> : <Cloud className="w-4 h-4 text-blue-500" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
                Campus Ambient Weather
              </span>
              <span
                className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase"
                style={{
                  backgroundColor: isLive ? 'rgba(16, 185, 129, 0.15)' : 'rgba(99, 102, 241, 0.15)',
                  color: isLive ? 'var(--status-healthy)' : 'var(--status-info)',
                  border: isLive ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(99, 102, 241, 0.3)'
                }}
              >
                {isLive ? 'Live (Open-Meteo)' : 'Simulated weather for replay time'}
              </span>
              {statusBadge === 'cached' && (
                <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-stone-500/15 text-stone-500">
                  Cached
                </span>
              )}
              {statusBadge === 'fallback' && (
                <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 text-amber-600">
                  Fallback active
                </span>
              )}
            </div>
            <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>
              Latitude 11.0168°N, Longitude 76.9558°E (Sathyamangalam / Coimbatore Campus) · IST (UTC+5:30)
            </p>
          </div>
        </div>

        {/* Source Switcher & Live Toggle */}
        <div className="flex items-center gap-2 self-start sm:self-center">
          <div className="flex items-center rounded-xl border p-0.5" style={{ borderColor: 'var(--border-separator)' }}>
            <button
              onClick={() => setSelectedSource('auto')}
              className={`px-2 py-0.5 text-[11px] font-semibold rounded-lg transition-all ${
                selectedSource === 'auto'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-stone-500 hover:text-stone-800 dark:hover:text-stone-200'
              }`}
            >
              Auto
            </button>
            <button
              onClick={() => setSelectedSource('live')}
              className={`px-2 py-0.5 text-[11px] font-semibold rounded-lg transition-all ${
                selectedSource === 'live'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-stone-500 hover:text-stone-800 dark:hover:text-stone-200'
              }`}
            >
              Live API
            </button>
            <button
              onClick={() => setSelectedSource('replay')}
              className={`px-2 py-0.5 text-[11px] font-semibold rounded-lg transition-all ${
                selectedSource === 'replay'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-stone-500 hover:text-stone-800 dark:hover:text-stone-200'
              }`}
            >
              Replay Clock
            </button>
          </div>

          <button
            onClick={() => fetchWeather()}
            disabled={loading}
            className="p-1.5 rounded-xl border transition-all text-stone-500 hover:bg-stone-500/10"
            style={{ borderColor: 'var(--border-separator)' }}
            title="Refresh weather conditions"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Middle Row: Current Metrics & Thermal Impact */}
      {curr && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 pt-3 pb-3">
          <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[10px] uppercase font-bold text-stone-500 flex items-center gap-1">
              <Thermometer className="w-3 h-3 text-rose-500" /> Outdoor Temp
            </span>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                {curr.outdoor_temp_c}
              </span>
              <span className="text-xs text-stone-500">°C</span>
            </div>
            <span className="text-[10px] text-stone-500">
              Apparent: {curr.apparent_temp_c ?? curr.outdoor_temp_c}°C
            </span>
          </div>

          <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[10px] uppercase font-bold text-stone-500 flex items-center gap-1">
              <Droplets className="w-3 h-3 text-blue-500" /> Humidity
            </span>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                {curr.relative_humidity}
              </span>
              <span className="text-xs text-stone-500">%</span>
            </div>
            <span className="text-[10px] text-stone-500">
              Dew point: {curr.dew_point_c ?? 'N/A'}°C
            </span>
          </div>

          <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[10px] uppercase font-bold text-stone-500 flex items-center gap-1">
              <Sun className="w-3 h-3 text-amber-500" /> Solar Irradiance
            </span>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                {curr.solar_irradiance_wm2}
              </span>
              <span className="text-xs text-stone-500">W/m²</span>
            </div>
            <span className="text-[10px] text-stone-500">
              Solar envelope peak
            </span>
          </div>

          <div className="p-2.5 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
            <span className="text-[10px] uppercase font-bold text-stone-500 flex items-center gap-1">
              <Wind className="w-3 h-3 text-emerald-500" /> Wind Speed
            </span>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                {curr.wind_speed_kmh ?? 5.0}
              </span>
              <span className="text-xs text-stone-500">km/h</span>
            </div>
            <span className="text-[10px] text-stone-500">
              Precip: {curr.precipitation_mm ?? 0} mm
            </span>
          </div>

          <div className="col-span-2 p-2.5 rounded-xl border bg-indigo-50/50 dark:bg-indigo-950/20 border-indigo-500/20 flex flex-col justify-between">
            <div>
              <span className="text-[10px] uppercase font-bold text-indigo-700 dark:text-indigo-300">
                Optimizer Pre-cool Lead Time
              </span>
              <p className="text-xs text-indigo-900 dark:text-indigo-200 mt-0.5">
                Thermal load delta: {(curr.outdoor_temp_c - 24.0).toFixed(1)}°C. Pre-cooling scheduled {Math.round(Math.min(60, Math.max(15, 10 + Math.max(0, curr.outdoor_temp_c - 25.0) * 2.5)))} mins before classes.
              </p>
            </div>
            <div className="flex items-center justify-between text-[10px] text-stone-500 pt-1 border-t border-indigo-500/20">
              <span>Source: {sourceLabel}</span>
              <span>Updated: {weatherData.fetched_at?.slice(11, 16)} UTC</span>
            </div>
          </div>
        </div>
      )}

      {/* 24-Hour Forecast Horizontal Strip */}
      {forecastStrip.length > 0 && (
        <div className="pt-2 border-t" style={{ borderColor: 'var(--border-separator)' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-bold text-stone-500">
              Next 12 Hours Forecast Strip ({isLive ? 'Open-Meteo Hourly' : 'Diurnal Simulation Model'})
            </span>
            <span className="text-[10px] text-stone-400">
              Values in °C &amp; % RH
            </span>
          </div>

          <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-12 gap-1.5 overflow-x-auto pb-1">
            {forecastStrip.map((pt, idx) => {
              const hourLabel = pt.timestamp.includes('T') ? pt.timestamp.split('T')[1].slice(0, 5) : `${idx}:00`;
              return (
                <div
                  key={pt.timestamp + idx}
                  className="p-2 rounded-xl text-center border transition-all"
                  style={{
                    backgroundColor: 'var(--bg-well)',
                    borderColor: 'var(--border-subtle)'
                  }}
                >
                  <span className="text-[10px] font-mono text-stone-500 block">
                    {hourLabel}
                  </span>
                  <div className="my-1">
                    <span className="text-xs font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                      {pt.outdoor_temp_c}°
                    </span>
                  </div>
                  <span className="text-[9px] text-stone-400 block font-mono">
                    {pt.relative_humidity}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
