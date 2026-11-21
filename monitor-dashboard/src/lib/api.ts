/**
 * The dashboard's whole conversation with the service.
 *
 * Everything the appliance can go wrong at — the Pi dropping off the network,
 * nginx answering instead of the service, FastAPI returning a validation
 * error, an endpoint that answers 200 with {"status": "error"} — arrives here
 * as one ApiError carrying a sentence for the user and the raw detail for the
 * modal. Callers never see a raw Response, so no call site can forget to check
 * `res.ok` again.
 */

const DETAIL_LIMIT = 600;

export class ApiError extends Error {
    /** HTTP status, when the request reached the service at all. */
    readonly status?: number;
    /** Raw response body or exception text, for the error modal's detail block. */
    readonly detail?: string;

    constructor(message: string, options: { status?: number; detail?: string; cause?: unknown } = {}) {
        super(message);
        this.name = 'ApiError';
        this.status = options.status;
        this.detail = options.detail?.slice(0, DETAIL_LIMIT) || undefined;
        if (options.cause !== undefined) this.cause = options.cause;
    }
}

/** Aborted requests are expected on unmount — they are not failures. */
export function isAbortError(err: unknown): boolean {
    return err instanceof DOMException && err.name === 'AbortError';
}

/** A sentence and optional detail for any thrown value, for the error modal. */
export function describeError(err: unknown): { message: string; detail?: string } {
    if (err instanceof ApiError) return { message: err.message, detail: err.detail };
    if (err instanceof Error) return { message: err.message };
    return { message: String(err) };
}

async function readBody(res: Response): Promise<string> {
    try {
        return (await res.text()).trim();
    } catch {
        return '';
    }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response;
    try {
        res = await fetch(path, init);
    } catch (err) {
        if (isAbortError(err)) throw err;
        throw new ApiError(
            'The monitor service did not respond. It may be restarting, or this browser has lost the network.',
            { detail: err instanceof Error ? err.message : String(err), cause: err }
        );
    }

    const body = await readBody(res);

    if (!res.ok) {
        throw new ApiError(`The monitor service rejected the request (HTTP ${res.status}).`, {
            status: res.status,
            detail: body || res.statusText,
        });
    }

    // 204 and an empty 200 are both legitimate "nothing to say".
    if (!body) return undefined as T;

    try {
        return JSON.parse(body) as T;
    } catch (err) {
        throw new ApiError('The monitor service returned a reply the dashboard could not read.', {
            status: res.status,
            detail: body,
            cause: err,
        });
    }
}

export function getJson<T>(path: string, init?: RequestInit): Promise<T> {
    return request<T>(path, init);
}

export function postJson<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
    return request<T>(path, {
        method: 'POST',
        ...(body === undefined
            ? {}
            : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
        ...init,
    });
}

export function deleteJson<T>(path: string, init?: RequestInit): Promise<T> {
    return request<T>(path, { method: 'DELETE', ...init });
}

/**
 * Several endpoints answer 200 with a status word instead of an HTTP error —
 * `{"status": "error"}` from /api/config and /api/wifi, for one. A reply whose
 * status is not in `accepted` is a failure however healthy the HTTP looked.
 */
export function statusOf(payload: unknown): string | undefined {
    if (!payload || typeof payload !== 'object') return undefined;
    const status = (payload as { status?: unknown }).status;
    return typeof status === 'string' ? status : undefined;
}

export function assertStatus(payload: unknown, accepted: readonly string[], message: string): void {
    const status = statusOf(payload);
    if (status !== undefined && accepted.includes(status)) return;
    throw new ApiError(message, {
        detail: status ? `The service replied status "${status}".` : JSON.stringify(payload),
    });
}
