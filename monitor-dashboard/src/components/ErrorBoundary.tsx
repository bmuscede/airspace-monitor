import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorBoundaryProps {
    children: ReactNode;
}

interface ErrorBoundaryState {
    error: Error | null;
}

/**
 * Catches render-time errors so a single bad payload cannot white-screen the
 * appliance. There is no devtools access on the Pi, so the fallback has to
 * explain itself and offer a way out.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    state: ErrorBoundaryState = { error: null };

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { error };
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error('Dashboard crashed:', error, info.componentStack);
    }

    handleReload = () => {
        window.location.reload();
    };

    render() {
        const { error } = this.state;
        if (!error) return this.props.children;

        return (
            <div className="min-h-screen bg-slate-950 text-slate-200 flex items-center justify-center p-8">
                <div className="max-w-lg w-full bg-slate-900/40 border border-slate-800/60 rounded-2xl p-8 shadow-2xl backdrop-blur-sm">
                    <div className="flex items-center space-x-3 mb-4">
                        <div className="p-2 bg-rose-500/10 rounded-xl border border-rose-500/30">
                            <AlertTriangle className="w-6 h-6 text-rose-400" />
                        </div>
                        <h1 className="text-xl font-bold text-white">The dashboard stopped responding</h1>
                    </div>
                    <p className="text-sm text-slate-400 mb-4">
                        An unexpected error interrupted the interface. The monitor service keeps running
                        independently — reloading the page restores the dashboard.
                    </p>
                    <pre className="text-xs font-mono text-rose-300/80 bg-slate-950 border border-slate-800 rounded-lg p-3 mb-6 overflow-x-auto whitespace-pre-wrap break-words">
                        {error.message || String(error)}
                    </pre>
                    <button
                        onClick={this.handleReload}
                        className="flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg transition-colors shadow-lg shadow-emerald-500/20 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                    >
                        <RefreshCw className="w-4 h-4" />
                        <span>Reload dashboard</span>
                    </button>
                </div>
            </div>
        );
    }
}