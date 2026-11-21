import { AlertTriangle, RefreshCw } from 'lucide-react';
import { buttonPrimary } from './settingsStyles';

interface ConfigGateProps {
    loaded: boolean;
    loading: boolean;
    failed: boolean;
    onRetry: () => void;
    children: React.ReactNode;
}

/**
 * Holds the two config-backed settings pages back until the service has
 * answered once.
 *
 * Rendering a form full of client-side defaults against a service that never
 * replied is the worst option here: it looks like the appliance's settings and
 * would be saved as if it were. Later reloads are allowed to happen underneath
 * the form, so a refresh never pulls the page out from under someone typing.
 */
export default function ConfigGate({ loaded, loading, failed, onRetry, children }: ConfigGateProps) {
    if (loaded) return <>{children}</>;

    if (failed) {
        return (
            <div className="max-w-xl bg-slate-900/40 border border-rose-900/50 rounded-2xl p-6 shadow-xl backdrop-blur-sm">
                <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-rose-500/10 rounded-xl border border-rose-500/30">
                        <AlertTriangle className="w-5 h-5 text-rose-400" />
                    </div>
                    <h2 className="text-lg font-semibold text-white">Settings could not be read</h2>
                </div>
                <p className="text-sm text-slate-400 mb-5 leading-relaxed">
                    The dashboard could not fetch <span className="font-mono">/api/config</span>. The monitor
                    service may be restarting, or this browser has lost the network. Nothing on this page can be
                    edited until it answers.
                </p>
                <button type="button" onClick={onRetry} disabled={loading} className={buttonPrimary}>
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    <span>{loading ? 'Trying again…' : 'Try again'}</span>
                </button>
            </div>
        );
    }

    return (
        <div className="max-w-xl bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 shadow-xl backdrop-blur-sm">
            <p className="text-sm text-slate-400">Reading the configuration from the monitor service…</p>
        </div>
    );
}
