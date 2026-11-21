import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertOctagon } from 'lucide-react';
import { ErrorDialogContext } from '../lib/errorDialog';
import type { ErrorReport } from '../lib/errorDialog';

interface ErrorDialogProviderProps {
    children: React.ReactNode;
}

/**
 * Modal errors for anything the user asked for and did not get.
 *
 * Toasts are fine for "it worked" but they expire, and on a wall-mounted
 * appliance nobody is watching the corner of the screen — a failed save has to
 * stop and say so. Reports queue rather than stack: two failures from one
 * action are two modals in turn, not two overlapping dialogs.
 *
 * Polling failures deliberately do not come through here. /api/flights going
 * quiet for one cycle is not news, and a modal every two seconds would bury
 * the page; the sidebar's service pill is the signal for that.
 */
export default function ErrorDialogProvider({ children }: ErrorDialogProviderProps) {
    const [queue, setQueue] = useState<ErrorReport[]>([]);
    const dismissRef = useRef<HTMLButtonElement>(null);

    const showError = useCallback((report: ErrorReport) => {
        setQueue(prev => {
            // The same failure raised twice (a retry, or two views reacting to
            // one dead endpoint) is one thing to tell the user about.
            const duplicate = prev.some(
                existing => existing.title === report.title && existing.message === report.message
            );
            return duplicate ? prev : [...prev, report];
        });
    }, []);

    const dismiss = useCallback(() => setQueue(prev => prev.slice(1)), []);

    const current = queue[0];
    const remaining = queue.length - 1;

    useEffect(() => {
        if (!current) return;
        dismissRef.current?.focus();

        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') dismiss();
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [current, dismiss]);

    return (
        <ErrorDialogContext.Provider value={{ showError }}>
            {children}
            {current && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-6">
                    <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" onClick={dismiss} />
                    <div
                        role="alertdialog"
                        aria-modal="true"
                        aria-labelledby="error-dialog-title"
                        aria-describedby="error-dialog-message"
                        className="relative w-full max-w-lg bg-slate-900 border border-rose-900/50 rounded-2xl p-6 shadow-2xl"
                    >
                        <div className="flex items-center space-x-3 mb-3">
                            <div className="p-2 rounded-xl border bg-rose-500/10 border-rose-500/30">
                                <AlertOctagon className="w-5 h-5 text-rose-400" />
                            </div>
                            <h2 id="error-dialog-title" className="text-lg font-semibold text-white">
                                {current.title}
                            </h2>
                        </div>

                        <p id="error-dialog-message" className="text-sm text-slate-300 leading-relaxed">
                            {current.message}
                        </p>

                        {current.detail && (
                            <pre className="mt-4 max-h-40 overflow-auto custom-scrollbar text-xs font-mono text-rose-200/80 bg-slate-950 border border-slate-800 rounded-lg p-3 whitespace-pre-wrap break-words">
                                {current.detail}
                            </pre>
                        )}

                        <div className="flex justify-between items-center mt-6">
                            <span className="text-xs text-slate-500">
                                {remaining > 0
                                    ? `${remaining} more ${remaining === 1 ? 'problem' : 'problems'} to show`
                                    : ''}
                            </span>
                            <button
                                ref={dismissRef}
                                onClick={dismiss}
                                className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-rose-600 hover:bg-rose-500 transition-colors shadow-lg shadow-rose-500/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                            >
                                {remaining > 0 ? 'Next' : 'Dismiss'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </ErrorDialogContext.Provider>
    );
}
