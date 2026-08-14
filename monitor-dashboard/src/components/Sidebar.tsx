import { Radar, LayoutDashboard, Terminal, Settings, Activity } from 'lucide-react';
import type { SystemStatus } from '../types';

type View = 'dashboard' | 'settings' | 'logs';

interface SidebarProps {
  currentView: View;
  setCurrentView: (view: View) => void;
  systemStatus: SystemStatus;
}

const NAV_ITEMS: { view: View; label: string; icon: typeof LayoutDashboard }[] = [
  { view: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { view: 'logs', label: 'Live Logs', icon: Terminal },
  { view: 'settings', label: 'Settings', icon: Settings },
];

/** Colour encodes service state, not navigation: nominal, pending, offline. */
function statusClasses(service: string): string {
  if (service === 'Online') return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
  if (service === 'Offline') return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
  return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
}

export default function Sidebar({ currentView, setCurrentView, systemStatus }: SidebarProps) {
  return (
    <aside className="w-64 bg-slate-900/60 backdrop-blur-xl border-r border-slate-800 flex flex-col z-20 shadow-2xl">
      <div className="p-6 flex items-center space-x-3 border-b border-slate-800">
        <div className="p-2 bg-emerald-500/20 rounded-xl border border-emerald-500/30">
          <Radar className="w-6 h-6 text-emerald-400" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-white tracking-tight">Airspace</h1>
          <p className="text-xs text-emerald-500 font-medium">Command Center</p>
        </div>
      </div>

      <nav className="flex-1 px-4 py-6 space-y-2">
        {NAV_ITEMS.map(({ view, label, icon: Icon }) => (
          <button
            key={view}
            onClick={() => setCurrentView(view)}
            aria-current={currentView === view ? 'page' : undefined}
            className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${currentView === view
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
          >
            <Icon className="w-5 h-5" />
            <span className="font-medium">{label}</span>
          </button>
        ))}
      </nav>

      <div className="p-4 border-t border-slate-800">
        <div className={`flex items-center space-x-2 px-3 py-2 rounded-lg border justify-center ${statusClasses(systemStatus.service)}`}>
          <Activity className="w-4 h-4 animate-pulse" />
          <span className="text-xs font-bold uppercase tracking-wider">{systemStatus.service}</span>
        </div>
      </div>
    </aside>
  );
}
