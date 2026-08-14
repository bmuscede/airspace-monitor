import type { Config, NumericConfigKey } from '../types';
import { NUMERIC_CONFIG_KEYS } from '../types';

export type ConfigErrors = Partial<Record<keyof Config, string>>;

export const DEFAULT_CONFIG: Config = {
    flightaware_url: '',
    flightaware_api_key: '',
    cache_ttl: 3600,
    home_lat: 0,
    home_lon: 0,
    max_radar_range_nm: 50,
};

export function isNumericConfigKey(key: string): key is NumericConfigKey {
    return (NUMERIC_CONFIG_KEYS as readonly string[]).includes(key);
}

/**
 * Picks the fields we own out of a `/api/config` payload, coercing numerics.
 * Anything missing or unusable falls back to the previous value, so a partial
 * or malformed response can never blank the form.
 */
export function normalizeConfig(payload: unknown, previous: Config): Config {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return previous;
    const raw = payload as Record<string, unknown>;

    const text = (key: 'flightaware_url' | 'flightaware_api_key') =>
        typeof raw[key] === 'string' ? (raw[key] as string) : previous[key];

    const numeric = (key: NumericConfigKey) => {
        const value = Number(raw[key]);
        return Number.isFinite(value) ? value : previous[key];
    };

    return {
        flightaware_url: text('flightaware_url'),
        flightaware_api_key: text('flightaware_api_key'),
        cache_ttl: numeric('cache_ttl'),
        home_lat: numeric('home_lat'),
        home_lon: numeric('home_lon'),
        max_radar_range_nm: numeric('max_radar_range_nm'),
    };
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
    if (!Number.isFinite(config.cache_ttl) || config.cache_ttl < 0) {
        errors.cache_ttl = 'Must be 0 or greater.';
    }

    return errors;
}

/** True when the form differs from the last config loaded from the backend. */
export function isConfigDirty(current: Config, saved: Config): boolean {
    return (Object.keys(current) as (keyof Config)[]).some(key => current[key] !== saved[key]);
}