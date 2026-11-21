import type { Config, LogLevel, NumericConfigKey, TextConfigKey } from '../types';
import { NUMERIC_CONFIG_KEYS, TEXT_CONFIG_KEYS, isLogLevel } from '../types';

export type ConfigErrors = Partial<Record<keyof Config, string>>;

export const DEFAULT_CONFIG: Config = {
    home_lat: 0,
    home_lon: 0,
    max_radar_range_nm: 50,
    flightaware_url: '',
    flightaware_api_key: '',
    flightaware_cache_ttl: 3600,
    openweathermap_url: '',
    openweathermap_api_key: '',
    openweathermap_cache_ttl: 3600,
    history_contact_gap_seconds: 300,
    history_flush_seconds: 300,
    history_retention_days: 90,
    log_level: 'INFO',
};

export function isNumericConfigKey(key: string): key is NumericConfigKey {
    return (NUMERIC_CONFIG_KEYS as readonly string[]).includes(key);
}

export function isTextConfigKey(key: string): key is TextConfigKey {
    return (TEXT_CONFIG_KEYS as readonly string[]).includes(key);
}

/**
 * Where each form field lives in the service's config, which is nested and
 * addressed with dots. The form keeps its own flat field names — they are the
 * input names and the validation keys — and this is the only place that knows
 * how they map onto the API.
 *
 * Every path here is a key the service's ConfigManager already defines. It has
 * to be: POST /api/config drops anything Has() does not recognise and lists it
 * back as `ignored`, so a path invented here would silently do nothing.
 */
export const CONFIG_PATHS: Record<keyof Config, string> = {
    home_lat: 'radar.home_lat',
    home_lon: 'radar.home_lon',
    max_radar_range_nm: 'radar.max_range_nm',
    flightaware_url: 'flightaware.url',
    flightaware_api_key: 'flightaware.api_key',
    flightaware_cache_ttl: 'flightaware.cache_ttl',
    openweathermap_url: 'openweathermap.url',
    openweathermap_api_key: 'openweathermap.api_key',
    openweathermap_cache_ttl: 'openweathermap.cache_ttl',
    history_contact_gap_seconds: 'history.contact_gap_seconds',
    history_flush_seconds: 'history.flush_seconds',
    history_retention_days: 'history.retention_days',
    log_level: 'log_level',
};

/** Human label per field, for the unsaved-changes summary and error modals. */
export const CONFIG_LABELS: Record<keyof Config, string> = {
    home_lat: 'Home latitude',
    home_lon: 'Home longitude',
    max_radar_range_nm: 'Radar range',
    flightaware_url: 'FlightAware URL',
    flightaware_api_key: 'FlightAware API key',
    flightaware_cache_ttl: 'FlightAware cache lifetime',
    openweathermap_url: 'Weather URL',
    openweathermap_api_key: 'Weather API key',
    openweathermap_cache_ttl: 'Weather cache lifetime',
    history_contact_gap_seconds: 'Same-visit gap',
    history_flush_seconds: 'Backstop flush',
    history_retention_days: 'Retention',
    log_level: 'Log level',
};

/** Walks a dotted path through a `/api/config` payload. */
export function readPath(payload: Record<string, unknown>, path: string): unknown {
    return path.split('.').reduce<unknown>((value, part) => {
        if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined;
        return (value as Record<string, unknown>)[part];
    }, payload);
}

/** Narrows a payload to a plain object, or null for arrays, scalars and nulls. */
export function asRecord(payload: unknown): Record<string, unknown> | null {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null;
    return payload as Record<string, unknown>;
}

/**
 * Picks the fields we own out of a `/api/config` payload, coercing numerics.
 * Anything missing or unusable falls back to the previous value, so a partial
 * or malformed response can never blank the form.
 */
export function normalizeConfig(payload: unknown, previous: Config): Config {
    const raw = asRecord(payload);
    if (!raw) return previous;

    const text = (key: TextConfigKey) => {
        const value = readPath(raw, CONFIG_PATHS[key]);
        return typeof value === 'string' ? value : previous[key];
    };

    const numeric = (key: NumericConfigKey) => {
        const value = Number(readPath(raw, CONFIG_PATHS[key]));
        return Number.isFinite(value) ? value : previous[key];
    };

    const rawLevel = readPath(raw, CONFIG_PATHS.log_level);
    // Python's logging accepts WARNING and WARN for the same level; the form
    // and the log viewer both speak WARN.
    const level =
        typeof rawLevel === 'string'
            ? rawLevel.trim().toUpperCase().replace('WARNING', 'WARN')
            : '';

    return {
        home_lat: numeric('home_lat'),
        home_lon: numeric('home_lon'),
        max_radar_range_nm: numeric('max_radar_range_nm'),
        flightaware_url: text('flightaware_url'),
        flightaware_api_key: text('flightaware_api_key'),
        flightaware_cache_ttl: numeric('flightaware_cache_ttl'),
        openweathermap_url: text('openweathermap_url'),
        openweathermap_api_key: text('openweathermap_api_key'),
        openweathermap_cache_ttl: numeric('openweathermap_cache_ttl'),
        history_contact_gap_seconds: numeric('history_contact_gap_seconds'),
        history_flush_seconds: numeric('history_flush_seconds'),
        history_retention_days: numeric('history_retention_days'),
        log_level: isLogLevel(level) ? (level as LogLevel) : previous.log_level,
    };
}

export const CONFIG_KEYS = Object.keys(CONFIG_PATHS) as (keyof Config)[];

/** The fields that differ from the last config the service gave us. */
export function changedConfigKeys(current: Config, saved: Config): (keyof Config)[] {
    return CONFIG_KEYS.filter(key => !Object.is(current[key], saved[key]));
}

/** True when the form differs from the last config loaded from the backend. */
export function isConfigDirty(current: Config, saved: Config): boolean {
    return changedConfigKeys(current, saved).length > 0;
}

/**
 * The changed fields as a POST body for `/api/config`: one dotted key per
 * field, so the service sets exactly these and leaves the rest of each object
 * alone. Only what changed is sent, so an untouched API key is never echoed
 * back over the wire.
 */
export function toConfigPayload(current: Config, saved?: Config): Record<string, unknown> {
    const keys = saved ? changedConfigKeys(current, saved) : CONFIG_KEYS;
    return Object.fromEntries(keys.map(key => [CONFIG_PATHS[key], current[key]]));
}

function urlError(value: string): string | undefined {
    if (!value.trim()) return undefined;
    try {
        const parsed = new URL(value);
        if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
            return 'Must be an http:// or https:// address.';
        }
    } catch {
        return 'Must be a full URL, including https://.';
    }
    return undefined;
}

function wholeNumberError(value: number, min: number, unit: string): string | undefined {
    if (!Number.isFinite(value)) return 'Required.';
    if (!Number.isInteger(value)) return `Must be a whole number of ${unit}.`;
    if (value < min) return `Must be ${min} or greater.`;
    return undefined;
}

/** Returns a message per invalid field. An empty object means the form is savable. */
export function validateConfig(config: Config): ConfigErrors {
    const errors: ConfigErrors = {};

    if (!Number.isFinite(config.home_lat) || config.home_lat < -90 || config.home_lat > 90) {
        errors.home_lat = 'Must be between -90 and 90.';
    }
    if (!Number.isFinite(config.home_lon) || config.home_lon < -180 || config.home_lon > 180) {
        errors.home_lon = 'Must be between -180 and 180.';
    }
    if (
        !Number.isFinite(config.max_radar_range_nm) ||
        config.max_radar_range_nm < 1 ||
        config.max_radar_range_nm > 250
    ) {
        errors.max_radar_range_nm = 'Must be between 1 and 250 NM.';
    }

    const flightawareUrl = urlError(config.flightaware_url);
    if (flightawareUrl) errors.flightaware_url = flightawareUrl;

    const weatherUrl = urlError(config.openweathermap_url);
    if (weatherUrl) errors.openweathermap_url = weatherUrl;

    const flightawareCache = wholeNumberError(config.flightaware_cache_ttl, 0, 'seconds');
    if (flightawareCache) errors.flightaware_cache_ttl = flightawareCache;

    const weatherCache = wholeNumberError(config.openweathermap_cache_ttl, 0, 'seconds');
    if (weatherCache) errors.openweathermap_cache_ttl = weatherCache;

    const gap = wholeNumberError(config.history_contact_gap_seconds, 1, 'seconds');
    if (gap) errors.history_contact_gap_seconds = gap;

    const flush = wholeNumberError(config.history_flush_seconds, 1, 'seconds');
    if (flush) errors.history_flush_seconds = flush;

    const retention = wholeNumberError(config.history_retention_days, 1, 'days');
    if (retention) errors.history_retention_days = retention;

    if (!isLogLevel(config.log_level)) errors.log_level = 'Pick a level.';

    return errors;
}

/**
 * Things worth saying but not worth blocking a save over. An empty weather key
 * is the shipped state of the appliance — refusing to save the rest of the
 * page until someone finds one would be the wrong trade.
 */
export function configWarnings(config: Config): Partial<Record<keyof Config, string>> {
    const warnings: Partial<Record<keyof Config, string>> = {};

    if (!config.flightaware_api_key.trim()) {
        warnings.flightaware_api_key =
            'Not set. Origin and destination stay blank, and the display falls back to the callsign alone.';
    }
    if (!config.openweathermap_api_key.trim()) {
        warnings.openweathermap_api_key = 'Not set. The idle screen draws its forecast section empty.';
    }

    return warnings;
}

/** Whether saving will shorten retention, which deletes rows on the next sweep. */
export function shortensRetention(current: Config, saved: Config): boolean {
    return (
        Number.isFinite(current.history_retention_days) &&
        current.history_retention_days < saved.history_retention_days
    );
}
