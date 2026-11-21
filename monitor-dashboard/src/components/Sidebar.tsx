import { useState } from 'react';
import {
    Activity,
    ChevronDown,
    Clock,
    LayoutDashboard,
    Radar,
    Settings,
    Terminal,
} from 'lucide-react';
import { DEFAULT_SETTINGS_VIEW, SETTINGS_VIEWS, isSettingsView } from '../types';
import type { SettingsView, SystemStatus, View } from '../types';

interface SidebarProps {
    currentView: View;
    setCurrentView: (view: View) => void;
    systemStatus: SystemStatus;
}

interface Destination {
    view: View;
    label: string;
    icon: typeof LayoutDashboard;
    /** Set when the view does not exist yet: the item shows, disabled. */
    unavailable?: string;
}

const DESTINATIONS: Destination[] = [
    { view: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    {
        view: 'history',
        label: 'History',
        icon: Clock,
        // TODO: This is a stub comment. /api/history/contacts and
        // /api/history/stats are both live, but the History view itself is not
        // built yet, so the destination stays disabled rather than navigating
        // to an empty pane.
        unavailable: 'The History view is not built yet.',
    },
    { view: 'logs', label: 'Live Logs', icon: Terminal },
];

const SETTINGS_LABELS: Record<SettingsView, string> = {
    'settings.backend': 'Backend',
    'settings.splitflap': 'Split-Flap',
    'settings.network': 'Network',
    'settings.system': 'System',
};

const itemBase =
    'w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900';
const itemActive =
    'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]';
const itemIdle = 'border border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/50';
const itemDisabled = 'border border-transparent text-slate-600 cursor-not-allowed';

/** Colour encodes service state, not navigation: nominal, pending, offline. */
function statusClasses(service: string): string {
    if (service === 'Online') return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    if (service === 'Offline') return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
    return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
}

/**
 * The navigation drawer: four destinations, with Settings holding its four
 * sections behind a chevron.
 *
 * The group is open whenever a settings section is the current view, and the
 * chevron collapses it again without navigating away — which is the only way
 * to fold the group while looking at one of its pages.
 */
export default function Sidebar({ currentView, setCurrentView, systemStatus }: SidebarProps) {
    const onSettings = isSettingsView(currentView);

    // null follows the current view, so arriving at a settings page reveals
    // which section is showing without an effect to force it open. The chevron
    // sets it explicitly, which is the only way to fold the group while
    // looking at one of its pages.
    const [openOverride, setOpenOverride] = useState<boolean | null>(null);
    const settingsOpen = openOverride ?? onSettings;

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

            <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto custom-scrollbar">
                {DESTINATIONS.map(({ view, label, icon: Icon, unavailable }) => (
                    <button
                        key={view}
                        type="button"
                        onClick={() => setCurrentView(view)}
                        disabled={!!unavailable}
                        title={unavailable}
                        aria-current={currentView === view ? 'page' : undefined}
                        className={`${itemBase} ${unavailable ? itemDisabled : currentView === view ? itemActive : itemIdle}`}
                    >
                        <Icon className="w-5 h-5 shrink-0" />
                        <span className="font-medium">{label}</span>
                        {unavailable && (
                            <span className="ml-auto text-[10px] uppercase tracking-wider text-slate-600">Soon</span>
                        )}
                    </button>
                ))}

                <div
                    className={`flex items-center rounded-xl ${onSettings ? itemActive : 'border border-transparent'}`}
                >
                    <button
                        type="button"
                        onClick={() => {
                            setOpenOverride(true);
                            if (!onSettings) setCurrentView(DEFAULT_SETTINGS_VIEW);
                        }}
                        aria-current={onSettings ? 'page' : undefined}
                        className={`flex-1 flex items-center gap-3 pl-4 pr-2 py-3 rounded-l-xl transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-inset ${onSettings ? 'text-emerald-400' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                        <Settings className="w-5 h-5 shrink-0" />
                        <span className="font-medium">Settings</span>
                    </button>
                    <button
                        type="button"
                        onClick={() => setOpenOverride(!settingsOpen)}
                        aria-expanded={settingsOpen}
                        aria-controls="settings-sections"
                        aria-label={settingsOpen ? 'Collapse settings sections' : 'Expand settings sections'}
                        className={`px-2.5 py-3 rounded-r-xl transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-inset ${onSettings ? 'text-emerald-400' : 'text-slate-500 hover:text-slate-300'}`}
                    >
                        <ChevronDown
                            className={`w-4 h-4 transition-transform duration-200 ${settingsOpen ? '' : '-rotate-90'}`}
                        />
                    </button>
                </div>

                {settingsOpen && (
                    <div
                        id="settings-sections"
                        className="ml-7 pl-2.5 border-l border-slate-800 flex flex-col gap-0.5"
                    >
                        {SETTINGS_VIEWS.map(view => (
                            <button
                                key={view}
                                type="button"
                                onClick={() => setCurrentView(view)}
                                aria-current={currentView === view ? 'page' : undefined}
                                className={`text-left px-3 py-1.5 rounded-lg text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${currentView === view
                                    ? 'text-emerald-400 font-semibold bg-emerald-500/[0.08]'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                                    }`}
                            >
                                {SETTINGS_LABELS[view]}
                            </button>
                        ))}
                    </div>
                )}
            </nav>

            <div className="p-4 border-t border-slate-800">
                <div
                    className={`flex items-center space-x-2 px-3 py-2 rounded-lg border justify-center ${statusClasses(systemStatus.service)}`}
                >
                    <Activity className="w-4 h-4 animate-pulse" />
                    <span className="text-xs font-bold uppercase tracking-wider">{systemStatus.service}</span>
                </div>
            </div>
        </aside>
    );
}
