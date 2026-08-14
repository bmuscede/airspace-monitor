/**
 * Geometry helpers for the radar scope.
 *
 * These are deliberately pure and free of React so that a future animation
 * loop can call them every frame with interpolated inputs without touching
 * component state.
 */

/** Radius of the outer range ring, in viewBox units. */
export const SCOPE_RADIUS = 100;

/** Half-width of the scope's viewBox — the outer ring plus label margin. */
export const SCOPE_EXTENT = 110;

/** Used whenever the configured radar range is missing or nonsensical. */
export const DEFAULT_MAX_RANGE_NM = 50;

/** Longest velocity leader we will ever draw, in viewBox units. */
const MAX_LEADER_LENGTH = 25;

/**
 * Projects a target onto the scope.
 *
 * Bearing is compass degrees clockwise from north; SVG's y-axis points down,
 * so north lands at (0, -100) and east at (100, 0).
 */
export function projectTarget(distanceNm: number, bearingDeg: number, maxRangeNm: number) {
    const r = (distanceNm / maxRangeNm) * SCOPE_RADIUS;
    const rad = (bearingDeg * Math.PI) / 180;
    return { x: r * Math.sin(rad), y: -r * Math.cos(rad) };
}

/**
 * Coerces a configured radar range into something safe to divide by.
 * Guards against zero, negative, and non-numeric values reaching the scope.
 */
export function resolveMaxRange(value: unknown): number {
    const parsed = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_MAX_RANGE_NM;
    return parsed;
}

/**
 * Length of the velocity leader line, in viewBox units: how far the target
 * travels in 60 seconds, expressed against the current scope.
 */
export function leaderLength(speedKts: number, maxRangeNm: number): number {
    if (!Number.isFinite(speedKts) || speedKts <= 0) return 0;
    const nmPerMinute = speedKts / 60;
    const length = (nmPerMinute / maxRangeNm) * SCOPE_RADIUS;
    return Math.min(length, MAX_LEADER_LENGTH);
}

/** Formats a range ring value, keeping halves (12.5 NM) but not ".0". */
export function formatRange(nm: number): string {
    return Number.isInteger(nm) ? String(nm) : nm.toFixed(1);
}