import { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2, X, XCircle } from 'lucide-react';
import { ToastContext } from '../lib/toast';
import type { Toast, ToastVariant } from '../lib/toast';

const DISMISS_AFTER_MS = 4000;

interface ToastProviderProps {
    children: React.ReactNode;
}

export default function ToastProvider({ children }: ToastProviderProps) {
    const [toasts, setToasts] = useState<Toast[]>([]);
    const nextId = useRef(0);
    const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

    const dismiss = useCallback((id: number) => {
        setToasts(prev => prev.filter(toast => toast.id !== id));
    }, []);

    const showToast = useCallback(
        (message: string, variant: ToastVariant = 'success') => {
            const id = nextId.current++;
            setToasts(prev => [...prev, { id, message, variant }]);
            timers.current.push(setTimeout(() => dismiss(id), DISMISS_AFTER_MS));
        },
        [dismiss]
    );

    useEffect(() => {
        const pending = timers.current;
        return () => pending.forEach(clearTimeout);
    }, []);

    return (
        <ToastContext.Provider value={{ showToast }}>
            {children}
            <div
                className="fixed bottom-6 right-6 z-50 flex flex-col items-end space-y-2 pointer-events-none"
                role="status"
                aria-live="polite"
            >
                {toasts.map(toast => {
                    const isError = toast.variant === 'error';
                    return (
                        <div
                            key={toast.id}
                            className={`pointer-events-auto flex items-center space-x-3 pl-4 pr-3 py-3 rounded-xl border shadow-2xl backdrop-blur-md text-sm animate-in fade-in slide-in-from-bottom-2 duration-200 ${isError
                                    ? 'bg-rose-950/80 border-rose-800/60 text-rose-100'
                                    : 'bg-slate-900/90 border-emerald-600/40 text-slate-100'
                                }`}
                        >
                            {isError ? (
                                <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                            ) : (
                                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                            )}
                            <span className="font-medium">{toast.message}</span>
                            <button
                                onClick={() => dismiss(toast.id)}
                                aria-label="Dismiss notification"
                                className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                            >
                                <X className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    );
                })}
            </div>
        </ToastContext.Provider>
    );
}