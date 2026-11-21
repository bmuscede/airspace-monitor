import { createContext, useContext } from 'react';
import { describeError } from './api';

export interface ErrorReport {
    /** What the user was trying to do, e.g. "Changes not saved". */
    title: string;
    /** One sentence on what went wrong. */
    message: string;
    /** Raw service output, shown in a monospace block when present. */
    detail?: string;
}

export interface ErrorDialogContextValue {
    /** Queues a modal. Reports raised while one is open are shown in turn. */
    showError: (report: ErrorReport) => void;
}

export const ErrorDialogContext = createContext<ErrorDialogContextValue | null>(null);

export function useErrorDialog(): ErrorDialogContextValue {
    const context = useContext(ErrorDialogContext);
    if (!context) throw new Error('useErrorDialog must be used within an ErrorDialogProvider.');
    return context;
}

/** Turns anything thrown into a report, so no catch block has to format one. */
export function errorReport(title: string, err: unknown): ErrorReport {
    const { message, detail } = describeError(err);
    return { title, message, detail };
}
