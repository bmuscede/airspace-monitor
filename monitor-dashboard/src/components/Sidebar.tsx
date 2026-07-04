import { Radar, LayoutDashboard, Terminal, Settings, Activity } from 'lucide-react';
import type { SystemStatus } from '../types';

interface SidebarProps {
  currentView: 'dashboard' | 'settings' | 'logs';
  setCurrentView: (view: 'dashboard' | 'settings' | 'logs') => void;
  systemStatus: SystemStatus;
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
        <button 
          onClick={() => setCurrentView('dashboard')}
          className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-300 ${currentView === 'dashboard' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}
        >
          <LayoutDashboard className="w-5 h-5" />
          <span className="font-medium">Dashboard</span>
        </button>
        <button 
          onClick={() => setCurrentView('logs')}
          className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-300 ${currentView === 'logs' ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.1)]' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}
        >
          <Terminal className="w-5 h-5" />
          <span className="font-medium">Live Logs</span>
        </button>
        <button 
          onClick={() => setCurrentView('settings')}
          className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-300 ${currentView === 'settings' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20 shadow-[0_0_15px_rgba(245,158,11,0.1)]' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}
        >
          <Settings className="w-5 h-5" />
          <span className="font-medium">Settings</span>
        </button>
      </nav>

      <div className="p-4 border-t border-slate-800">
        <div className="flex items-center space-x-2 bg-emerald-500/10 text-emerald-400 px-3 py-2 rounded-lg border border-emerald-500/20 justify-center">
          <Activity className="w-4 h-4 animate-pulse" />
          <span className="text-xs font-bold uppercase tracking-wider">{systemStatus.service}</span>
        </div>
      </div>
    </aside>
  );
}
