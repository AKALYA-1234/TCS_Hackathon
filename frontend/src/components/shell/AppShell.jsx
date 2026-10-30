import React, { useState } from 'react';
import {
  LayoutDashboard,
  DoorClosed,
  Zap,
  TrendingUp,
  CalendarDays,
  Inbox,
  Bot,
  Gauge,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  Laptop,
  Building,
  MoreHorizontal,
  History as HistoryIcon,
  Camera
} from 'lucide-react';
import { HonestyBadges } from '../ui/BaseComponents';

export const NAV_ITEMS = [
  { id: 'overview', label: 'Campus Overview', icon: LayoutDashboard },
  { id: 'room', label: 'Room Detail', icon: DoorClosed },
  { id: 'history', label: 'AC History', icon: HistoryIcon },
  { id: 'cameras', label: 'Live Cameras & CV', icon: Camera },
  { id: 'waste', label: 'Waste Events', icon: Zap },
  { id: 'forecast', label: 'Forecast', icon: TrendingUp },
  { id: 'optimizer', label: 'Optimizer & Schedules', icon: CalendarDays },
  { id: 'inbox', label: 'Approvals Inbox', icon: Inbox, badge: 3 },
  { id: 'assistant', label: 'Assistant', icon: Bot },
  { id: 'simulator', label: 'Simulator & Evaluation', icon: Gauge }
];

export function AppShell({
  activeTab,
  onSelectTab,
  theme,
  explicitTheme,
  onChangeTheme,
  simClock,
  simSpeed,
  pendingApprovalsCount = 3,
  connectionStatus = 'LIVE',
  secondsSinceUpdate = 0,
  children
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [userRole, setUserRole] = useState('Facility Admin');

  return (
    <div className="flex h-screen w-screen overflow-hidden" style={{ backgroundColor: 'var(--bg-page)' }}>
      {/* 1. Desktop & Tablet Sidebar */}
      <aside
        className={`hidden md:flex flex-col border-r transition-all duration-150 z-20 shrink-0 ${
          collapsed ? 'w-20' : 'w-[244px]'
        }`}
        style={{
          backgroundColor: 'var(--bg-sidebar)',
          borderColor: 'var(--border-separator)'
        }}
      >
        {/* Brand Header */}
        <div className="h-[56px] flex items-center px-5 gap-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center font-bold text-sm select-none"
            style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
          >
            ❄
          </div>
          {!collapsed && (
            <span className="font-bold text-base tracking-tight" style={{ color: 'var(--text-primary)' }}>
              Frostline
            </span>
          )}
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 py-3 px-3 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            const badgeCount = item.id === 'inbox' ? pendingApprovalsCount : item.badge;

            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                title={collapsed ? item.label : undefined}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium text-[13px] transition-all cursor-pointer relative ${
                  isActive ? 'shadow-xs font-semibold' : ''
                }`}
                style={{
                  backgroundColor: isActive ? 'var(--accent-subtle)' : 'transparent',
                  color: isActive ? 'var(--accent)' : 'var(--text-secondary)'
                }}
              >
                <Icon size={18} strokeWidth={isActive ? 2.5 : 2} className="shrink-0" />
                {!collapsed && (
                  <span className="truncate text-left flex-1">{item.label}</span>
                )}
                {badgeCount > 0 && (
                  <span
                    className={`shrink-0 text-xs font-bold px-1.5 py-0.5 rounded-full ${
                      collapsed ? 'absolute top-1 right-2' : ''
                    }`}
                    style={{
                      backgroundColor: 'var(--accent)',
                      color: '#FFFFFF'
                    }}
                  >
                    {badgeCount}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Footer Loop Tagline & Collapse Toggle */}
        <div className="p-3 border-t space-y-2" style={{ borderColor: 'var(--border-subtle)' }}>
          {!collapsed && (
            <p className="text-[11px] px-1 leading-relaxed" style={{ color: 'var(--text-tertiary)' }}>
              Sense, understand, propose, validate, approve, act, verify. Humans stay in the loop.
            </p>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="w-full flex items-center gap-2 py-2 px-3 rounded-lg text-xs font-medium cursor-pointer"
            style={{ color: 'var(--text-secondary)' }}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>

      {/* Main Layout Area */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Top App Bar (Single compact row reclaiming vertical space) */}
        <header
          className="shrink-0 z-10 border-b select-none transition-colors"
          style={{
            backgroundColor: 'var(--bg-frost)',
            backdropFilter: 'var(--bg-frost-blur)',
            WebkitBackdropFilter: 'var(--bg-frost-blur)',
            borderColor: 'var(--border-separator)'
          }}
        >
          {/* Top Bar Row: Height 56px */}
          <div className="h-[56px] px-4 md:px-6 lg:px-8 flex items-center justify-between gap-2.5">
            {/* Left: Building / Campus Selector & Simulated Clock */}
            <div className="flex items-center gap-2 sm:gap-3 shrink-0">
              <button
                className="flex items-center gap-1.5 px-3 h-[36px] rounded-full text-xs font-semibold cursor-pointer shrink-0 border"
                style={{
                  backgroundColor: 'var(--bg-well)',
                  borderColor: 'var(--border-subtle)',
                  color: 'var(--text-primary)'
                }}
              >
                <Building size={14} style={{ color: 'var(--text-primary)' }} />
                <span className="hidden sm:inline">All campus</span>
                <span className="sm:hidden">Campus</span>
                <span className="text-[10px] opacity-60">▾</span>
              </button>

              {/* Simulated Clock, Speed, and Live Connection Status */}
              <div
                className="flex items-center gap-1.5 sm:gap-2 px-3 h-[36px] rounded-full text-xs font-medium shrink-0 border"
                style={{
                  backgroundColor: 'var(--bg-well)',
                  borderColor: 'var(--border-subtle)',
                  color: 'var(--text-secondary)'
                }}
              >
                {/* Status Dot */}
                <span
                  className="w-2 h-2 rounded-full transition-colors shrink-0"
                  style={{
                    backgroundColor:
                      connectionStatus === 'LIVE' ? 'var(--status-healthy)' :
                      connectionStatus === 'RECONNECTING' ? 'var(--status-review)' :
                      connectionStatus === 'STALE' ? 'var(--status-review)' :
                      'var(--status-failed)'
                  }}
                  title={`Connection: ${connectionStatus}`}
                />

                <span className="tabular-nums font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {simClock || 'Thu 29 Oct · 14:35'}
                </span>
                <span className="opacity-70 text-[11px] hidden lg:inline">simulated</span>

                <span
                  className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                  style={{ backgroundColor: 'var(--accent-subtle)', color: 'var(--accent)' }}
                >
                  {simSpeed || 60}x
                </span>

                {/* Connection Status Label */}
                <span
                  className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full hidden sm:inline"
                  style={{
                    backgroundColor:
                      connectionStatus === 'LIVE' ? 'rgba(91, 214, 127, 0.15)' :
                      connectionStatus === 'RECONNECTING' ? 'rgba(255, 184, 77, 0.15)' :
                      connectionStatus === 'STALE' ? 'rgba(255, 184, 77, 0.15)' :
                      'rgba(255, 122, 112, 0.15)',
                    color:
                      connectionStatus === 'LIVE' ? 'var(--status-healthy)' :
                      connectionStatus === 'RECONNECTING' ? 'var(--status-review)' :
                      connectionStatus === 'STALE' ? 'var(--status-review)' :
                      'var(--status-failed)'
                  }}
                >
                  {connectionStatus === 'STALE' ? `Stale (${secondsSinceUpdate}s)` :
                   connectionStatus === 'RECONNECTING' ? 'Reconnecting' :
                   connectionStatus === 'STOPPED' ? 'Sim Stopped' : 'Live'}
                </span>
              </div>
            </div>

            {/* Right: Honesty Badges, Icon-only Theme Toggle, and User Chip */}
            <div className="flex items-center gap-2 sm:gap-3 shrink-0">
              {/* Honesty Badges in Top Bar (Responsive collapse) */}
              <div className="hidden xl:flex items-center gap-2">
                <HonestyBadges />
              </div>

              {/* Theme Toggle: Segmented pill with Two Icon-Only Buttons */}
              <div
                className="flex items-center p-0.5 h-[36px] rounded-full border shrink-0"
                style={{
                  backgroundColor: 'var(--bg-well)',
                  borderColor: 'var(--border-subtle)'
                }}
                role="group"
                aria-label="Theme selector"
              >
                {/* Sun (Light Theme) Button */}
                <button
                  onClick={() => onChangeTheme('light')}
                  aria-label="Light theme"
                  aria-pressed={theme === 'light'}
                  title={theme === 'light' ? 'Light theme active (Click again to follow system)' : 'Light theme'}
                  className={`w-7 h-7 rounded-full flex items-center justify-center transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-500 ${
                    theme === 'light'
                      ? 'bg-white shadow-xs text-amber-500 font-bold'
                      : 'text-stone-400 hover:text-stone-700 dark:hover:text-stone-200'
                  }`}
                >
                  <Sun size={15} strokeWidth={theme === 'light' ? 2.5 : 2} />
                </button>

                {/* Moon (Dark Theme) Button */}
                <button
                  onClick={() => onChangeTheme('dark')}
                  aria-label="Dark theme"
                  aria-pressed={theme === 'dark'}
                  title={theme === 'dark' ? 'Dark theme active (Click again to follow system)' : 'Dark theme'}
                  className={`w-7 h-7 rounded-full flex items-center justify-center transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-500 ${
                    theme === 'dark'
                      ? 'bg-zinc-800 shadow-xs text-indigo-400 font-bold'
                      : 'text-stone-400 hover:text-stone-700 dark:hover:text-stone-200'
                  }`}
                >
                  <Moon size={15} strokeWidth={theme === 'dark' ? 2.5 : 2} />
                </button>
              </div>

              {/* User Chip: Avatar, name, role at far right with dropdown */}
              <div className="relative">
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center gap-2 p-1 sm:pl-1.5 sm:pr-3 h-[36px] rounded-full text-xs font-medium cursor-pointer shrink-0 border transition-all hover:border-stone-400"
                  style={{
                    backgroundColor: 'var(--bg-well)',
                    borderColor: 'var(--border-subtle)'
                  }}
                  aria-label="User account menu"
                  aria-expanded={userMenuOpen}
                >
                  <div
                    className="w-6 h-6 rounded-full flex items-center justify-center font-bold text-[11px] select-none"
                    style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
                  >
                    SC
                  </div>
                  <div className="hidden sm:flex flex-col text-left leading-tight">
                    <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                      Sarah Chen
                    </span>
                    <span className="text-[10px] text-stone-500">
                      {userRole}
                    </span>
                  </div>
                  <span className="text-[10px] opacity-60 hidden sm:inline">▾</span>
                </button>

                {/* Role Switcher & Account Dropdown */}
                {userMenuOpen && (
                  <div
                    className="absolute right-0 mt-2 w-52 rounded-2xl shadow-xl border p-2 z-50 animate-in fade-in duration-100"
                    style={{
                      backgroundColor: 'var(--bg-card)',
                      borderColor: 'var(--border-separator)'
                    }}
                  >
                    <div className="px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                      <p className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>Sarah Chen</p>
                      <p className="text-[10px] text-stone-500">sarah.chen@campus.edu</p>
                    </div>
                    <div className="py-1">
                      <span className="px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-stone-400 block">Switch Role</span>
                      {['Facility Admin', 'Energy Manager', 'Observer'].map((r) => (
                        <button
                          key={r}
                          onClick={() => {
                            setUserRole(r);
                            setUserMenuOpen(false);
                          }}
                          className={`w-full text-left px-3 py-1.5 text-xs rounded-lg transition-colors flex items-center justify-between ${
                            userRole === r ? 'font-bold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400' : 'text-stone-600 dark:text-stone-300 hover:bg-stone-500/10'
                          }`}
                        >
                          <span>{r}</span>
                          {userRole === r && <span>✓</span>}
                        </button>
                      ))}
                    </div>
                    <div className="pt-1 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                      <div className="px-3 py-1 text-[10px] text-stone-400 flex items-center justify-between">
                        <span>Theme Mode</span>
                        <span className="font-bold capitalize">{explicitTheme ? explicitTheme : 'System'}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Content Body Viewport: Fluid width with 24-32px padding (16px on phones), capped at 1800px on ultra-wide */}
        <main
          className="flex-1 overflow-y-auto overflow-x-hidden px-4 sm:px-6 md:px-8 py-6"
          style={{ backgroundColor: 'var(--bg-page)' }}
        >
          <div className="w-full max-w-[1800px] mx-auto transition-all">
            {children}
          </div>
        </main>

        {/* Mobile Bottom Navigation Bar (Phone viewport 390px) */}
        <nav
          className="md:hidden fixed bottom-0 left-0 right-0 h-16 border-t frosted-glass flex items-center justify-around px-2 z-30"
          style={{
            borderColor: 'var(--border-separator)',
            backgroundColor: 'var(--bg-card)',
            boxShadow: '0 -2px 10px rgba(0, 0, 0, 0.08)'
          }}
        >
          {[
            { id: 'overview', label: 'Overview', icon: LayoutDashboard },
            { id: 'waste', label: 'Events', icon: Zap },
            { id: 'inbox', label: 'Approvals', icon: Inbox, badge: pendingApprovalsCount },
            { id: 'assistant', label: 'Assistant', icon: Bot },
          ].map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className="flex flex-col items-center justify-center flex-1 py-1 cursor-pointer relative"
                style={{ color: isActive ? 'var(--accent)' : 'var(--text-secondary)' }}
              >
                <div className="relative">
                  <Icon size={18} strokeWidth={isActive ? 2.5 : 2} />
                  {item.badge > 0 && (
                    <span
                      className="absolute -top-1 -right-2 px-1 text-[9px] font-bold rounded-full"
                      style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
                    >
                      {item.badge}
                    </span>
                  )}
                </div>
                <span className="text-[10px] mt-1 font-medium truncate">{item.label}</span>
              </button>
            );
          })}
          <button
            onClick={() => setMobileMoreOpen(!mobileMoreOpen)}
            className="flex flex-col items-center justify-center flex-1 py-1 cursor-pointer"
            style={{ color: mobileMoreOpen ? 'var(--accent)' : 'var(--text-secondary)' }}
          >
            <MoreHorizontal size={18} />
            <span className="text-[10px] mt-1 font-medium">More</span>
          </button>
        </nav>

        {/* Mobile More Sheet */}
        {mobileMoreOpen && (
          <div
            className="md:hidden fixed inset-0 bg-black/60 z-40 flex flex-col justify-end"
            onClick={() => setMobileMoreOpen(false)}
          >
            <div
              className="p-5 rounded-t-3xl border-t space-y-2 animate-in slide-in-from-bottom"
              style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-separator)' }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-10 h-1 rounded-full mx-auto mb-4" style={{ backgroundColor: 'var(--border-subtle)' }} />
              <h3 className="text-sm font-bold mb-3 px-2" style={{ color: 'var(--text-tertiary)' }}>
                ALL DESTINATIONS
              </h3>
              {NAV_ITEMS.slice(4).map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      onSelectTab(item.id);
                      setMobileMoreOpen(false);
                    }}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl font-medium text-sm cursor-pointer"
                    style={{ backgroundColor: 'var(--bg-well)', color: 'var(--text-primary)' }}
                  >
                    <Icon size={18} style={{ color: 'var(--accent)' }} />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
