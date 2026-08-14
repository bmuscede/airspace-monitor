import { useEffect, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';

interface ConfirmDialogProps {
    open: boolean;
    title: string;
    description: string;
    confirmLabel: string;
    cancelLabel?: string;
    destructive?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
}

export default function ConfirmDialog({
    open,
    title,
    description,
    confirmLabel,
    cancelLabel = 'Cancel',
    destructive = false,
    onConfirm,
    onCancel,
}: ConfirmDialogProps) {
    const confirmRef = useRef<HTMLButtonElement>(null);

    useEffect(() => {
        if (!open) return;
        confirmRef.current?.focus();

        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onCancel();
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [open, onCancel]);

    if (!open) return null;

    const confirmClasses = destructive
        ? 'bg-rose-600 hover:bg-rose-500 shadow-rose-500/20 focus-visible:ring-rose-400'
        : 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-500/20 focus-visible:ring-emerald-400';

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
            <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" onClick={onCancel} />
            <div
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="confirm-dialog-title"
                aria-describedby="confirm-dialog-description"
                className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl"
            >
                <div className="flex items-center space-x-3 mb-3">
                    <div
                        className={`p-2 rounded-xl border ${destructive ? 'bg-rose-500/10 border-rose-500/30' : 'bg-emerald-500/10 border-emerald-500/30'}`}
                    >
                        <AlertTriangle className={`w-5 h-5 ${destructive ? 'text-rose-400' : 'text-emerald-400'}`} />
                    </div>
                    <h2 id="confirm-dialog-title" className="text-lg font-semibold text-white">
                        {title}
                    </h2>
                </div>
                <p id="confirm-dialog-description" className="text-sm text-slate-400 mb-6">
                    {description}
                </p>
                <div className="flex justify-end space-x-3">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                    >
                        {cancelLabel}
                    </button>
                    <button
                        ref={confirmRef}
                        onClick={onConfirm}
                        className={`px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors shadow-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${confirmClasses}`}
                    >
                        {confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}