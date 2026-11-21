import type { FlapCharset, FlapModule, SplitFlapConfig } from '../types';
import { asRecord, readPath } from './config';

/**
 * The split-flap display as a form, and the rules the service already enforces
 * on it.
 *
 * Two shapes need care, both inherited from `splitflap/config.py`:
 *
 *  - a flap is one entry in `splitflap.channels`, either `{"channel": 0,
 *    "charset": "logos"}` or a bare number meaning `default`. The list's order
 *    is the flap order the layout depends on, so it is never sorted;
 *  - a character set's `flaps` is a list where each entry is one flap, so a
 *    multi-character entry is a symbol flap (`ACA`) rather than three letters.
 *    A set given as a string is split with `parse_tokens()`, so `{ACA}` in a
 *    hand-written config file is one flap; this module still writes the list
 *    form back, where no escaping is needed at all.
 *
 * What cannot be written from here: the service's ConfigManager only accepts
 * keys it already defines, so a character set it has never heard of is dropped
 * and reported as `ignored`. Adding and removing sets, the per-set fallback
 * flap, and all of quiet hours are therefore read-only or stubbed in the UI
 * rather than quietly failing on save.
 */

/** "Flap option 1" in the firmware's config.h, as splitflap/config.py has it. */
export const LEGACY_40_FLAPS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,'";

/** The service's firmware addresses Chainlink channels 0-254. */
export const MAX_CHANNEL = 254;

export const DEFAULT_CHARSET_NAME = 'default';

export const DEFAULT_SPLITFLAP: SplitFlapConfig = {
    enabled: false,
    port: '',
    rows: [],
    modules: [],
    charsets: [{ name: DEFAULT_CHARSET_NAME, flaps: Array.from(LEGACY_40_FLAPS), fallback: null }],
    autoRehome: { enabled: true, maxAttempts: 3, windowSeconds: 600, backoffSeconds: 15 },
    calibration: { calibrated: false, calibratedAt: 0 },
};

export const SPLITFLAP_PATHS = {
    enabled: 'splitflap.enabled',
    port: 'splitflap.port',
    rows: 'splitflap.rows',
    channels: 'splitflap.channels',
    autoRehomeEnabled: 'splitflap.auto_rehome.enabled',
    autoRehomeMaxAttempts: 'splitflap.auto_rehome.max_attempts',
    autoRehomeWindowSeconds: 'splitflap.auto_rehome.window_seconds',
    autoRehomeBackoffSeconds: 'splitflap.auto_rehome.backoff_seconds',
    calibrated: 'splitflap.calibration.calibrated',
    calibratedAt: 'splitflap.calibration.calibrated_at',
} as const;

export function charsetPath(name: string): string {
    return `splitflap.charsets.${name}.flaps`;
}

// --- tokens ---------------------------------------------------------------

/**
 * Splits text into flap tokens, the same way `parse_tokens()` does in
 * splitflap/config.py: `{ACA}857` is four flaps, and `{{` is a literal brace.
 * Throws on text the service would also refuse.
 */
export function parseFlapTokens(text: string): string[] {
    const tokens: string[] = [];
    let i = 0;

    while (i < text.length) {
        const char = text[i];
        if (char === '{') {
            if (text.startsWith('{{', i)) {
                tokens.push('{');
                i += 2;
                continue;
            }
            const end = text.indexOf('}', i + 1);
            if (end === -1) throw new Error('There is a "{" with no closing "}".');
            const name = text.slice(i + 1, end);
            if (!name) throw new Error('"{}" is empty — a symbol flap needs a name, like {ACA}.');
            tokens.push(name);
            i = end + 1;
        } else if (char === '}' && text.startsWith('}}', i)) {
            tokens.push('}');
            i += 2;
        } else {
            tokens.push(char);
            i += 1;
        }
    }

    return tokens;
}

/** The inverse of parseFlapTokens: a spool as one editable line of text. */
export function formatFlapTokens(flaps: readonly string[]): string {
    return flaps
        .map(token => {
            if (token === '{') return '{{';
            if (token === '}') return '}}';
            return token.length === 1 ? token : `{${token}}`;
        })
        .join('');
}

/** How one flap reads in a chip or a dropdown. */
export function flapLabel(token: string): string {
    if (token === ' ') return '␣';
    return token.length === 1 ? token : `{${token}}`;
}

// --- reading the config ---------------------------------------------------

/**
 * A spool written as one line of text, read the way `SplitFlapCharset` reads
 * it. Text the tokeniser refuses is shown one character at a time so it can be
 * seen and repaired here — the service refuses to start the display on it.
 */
function readFlapsText(text: string): string[] {
    try {
        return parseFlapTokens(text);
    } catch {
        return Array.from(text);
    }
}

function toCharsets(raw: unknown, previous: FlapCharset[]): FlapCharset[] {
    const section = asRecord(raw);
    if (!section) return previous;

    const charsets: FlapCharset[] = [];

    for (const [name, spec] of Object.entries(section)) {
        // The service skips underscore-prefixed names, which is how a config
        // file keeps a commented-out set around.
        if (name.startsWith('_')) continue;

        let flaps: string[] | null = null;
        let fallback: string | null = null;

        if (typeof spec === 'string') {
            flaps = readFlapsText(spec);
        } else if (Array.isArray(spec)) {
            flaps = spec.filter((token): token is string => typeof token === 'string' && token.length > 0);
        } else {
            const entry = asRecord(spec);
            if (!entry) continue;
            if (typeof entry.flaps === 'string') flaps = readFlapsText(entry.flaps);
            else if (Array.isArray(entry.flaps)) {
                flaps = entry.flaps.filter(
                    (token): token is string => typeof token === 'string' && token.length > 0
                );
            }
            if (typeof entry.fallback === 'string') fallback = entry.fallback;
        }

        if (flaps === null) continue;
        charsets.push({ name, flaps, fallback });
    }

    if (!charsets.some(set => set.name === DEFAULT_CHARSET_NAME)) {
        // What the service does when the config describes no default set.
        charsets.unshift({
            name: DEFAULT_CHARSET_NAME,
            flaps: Array.from(LEGACY_40_FLAPS),
            fallback: null,
        });
    }

    return charsets;
}

function toModules(raw: unknown): FlapModule[] {
    if (!Array.isArray(raw)) return [];

    const modules: FlapModule[] = [];
    for (const entry of raw) {
        if (typeof entry === 'number' && Number.isFinite(entry)) {
            modules.push({ channel: entry, charset: DEFAULT_CHARSET_NAME });
            continue;
        }
        const record = asRecord(entry);
        if (!record) continue;
        const channel = Number(record.channel);
        if (!Number.isFinite(channel)) continue;
        const charset = typeof record.charset === 'string' && record.charset ? record.charset : DEFAULT_CHARSET_NAME;
        modules.push({ channel, charset });
    }
    return modules;
}

/**
 * Rows as the page edits them: one entry per row, always summing to the number
 * of flaps. The service treats rows it cannot fit as a single row, so an
 * unusable list is normalised to exactly that instead of being shown as rows
 * the display does not really have.
 */
function toRows(raw: unknown, moduleCount: number): number[] {
    const rows = Array.isArray(raw)
        ? raw.filter(
              (length): length is number =>
                  typeof length === 'number' && Number.isInteger(length) && length > 0
          )
        : [];

    const total = rows.reduce((sum, length) => sum + length, 0);
    if (rows.length > 0 && total === moduleCount) return rows;
    return moduleCount > 0 ? [moduleCount] : [];
}

function numberOr(value: unknown, fallback: number): number {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

/** Picks the `splitflap` section out of a `/api/config` payload. */
export function normalizeSplitFlap(payload: unknown, previous: SplitFlapConfig): SplitFlapConfig {
    const raw = asRecord(payload);
    if (!raw) return previous;

    const section = asRecord(readPath(raw, 'splitflap'));
    if (!section) return previous;

    const rehome = asRecord(section.auto_rehome) ?? {};
    const calibration = asRecord(section.calibration) ?? {};
    const modules = toModules(section.channels);

    return {
        enabled: typeof section.enabled === 'boolean' ? section.enabled : previous.enabled,
        port: typeof section.port === 'string' ? section.port : previous.port,
        modules,
        rows: toRows(section.rows, modules.length),
        charsets: toCharsets(section.charsets, previous.charsets),
        autoRehome: {
            enabled: typeof rehome.enabled === 'boolean' ? rehome.enabled : previous.autoRehome.enabled,
            maxAttempts: numberOr(rehome.max_attempts, previous.autoRehome.maxAttempts),
            windowSeconds: numberOr(rehome.window_seconds, previous.autoRehome.windowSeconds),
            backoffSeconds: numberOr(rehome.backoff_seconds, previous.autoRehome.backoffSeconds),
        },
        calibration: {
            calibrated:
                typeof calibration.calibrated === 'boolean'
                    ? calibration.calibrated
                    : previous.calibration.calibrated,
            calibratedAt: numberOr(calibration.calibrated_at, previous.calibration.calibratedAt),
        },
    };
}

// --- editing --------------------------------------------------------------

export interface RowSpan {
    start: number;
    length: number;
}

/** Where each row starts in the flap list, top to bottom. */
export function rowSpans(config: SplitFlapConfig): RowSpan[] {
    const spans: RowSpan[] = [];
    let start = 0;
    for (const length of config.rows) {
        spans.push({ start, length });
        start += length;
    }
    // A flap list longer than the rows describe would otherwise disappear from
    // the page, which is how a wrong channel gets saved without being seen.
    if (start < config.modules.length) {
        spans.push({ start, length: config.modules.length - start });
    }
    return spans;
}

/** The lowest channel nothing is wired to yet. */
export function nextFreeChannel(modules: readonly FlapModule[]): number {
    const used = new Set(modules.map(module => module.channel));
    let channel = 0;
    while (used.has(channel) && channel <= MAX_CHANNEL) channel += 1;
    return channel;
}

function newModule(modules: readonly FlapModule[]): FlapModule {
    return { channel: nextFreeChannel(modules), charset: DEFAULT_CHARSET_NAME };
}

/** Grows or shrinks one row, adding flaps on the next free channels. */
export function setRowLength(config: SplitFlapConfig, rowIndex: number, length: number): SplitFlapConfig {
    if (!Number.isInteger(length) || length < 1 || rowIndex < 0 || rowIndex >= config.rows.length) {
        return config;
    }

    const spans = rowSpans(config);
    const span = spans[rowIndex];
    if (!span) return config;

    const modules = [...config.modules];
    const difference = length - span.length;

    if (difference > 0) {
        const added: FlapModule[] = [];
        for (let i = 0; i < difference; i += 1) {
            added.push(newModule([...modules, ...added]));
        }
        modules.splice(span.start + span.length, 0, ...added);
    } else if (difference < 0) {
        modules.splice(span.start + length, -difference);
    }

    const rows = [...config.rows];
    rows[rowIndex] = length;

    return { ...config, rows, modules };
}

/** A new row of the same width as the last one, on the next free channels. */
export function addRow(config: SplitFlapConfig): SplitFlapConfig {
    const length = config.rows.length > 0 ? config.rows[config.rows.length - 1] : 8;
    const modules = [...config.modules];
    for (let i = 0; i < length; i += 1) {
        modules.push(newModule(modules));
    }
    return { ...config, rows: [...config.rows, length], modules };
}

/** Removing a row hands its flaps back to the neighbouring row. */
export function removeRow(config: SplitFlapConfig, rowIndex: number): SplitFlapConfig {
    if (config.rows.length <= 1 || rowIndex < 0 || rowIndex >= config.rows.length) return config;

    const rows = [...config.rows];
    const [length] = rows.splice(rowIndex, 1);
    const absorber = rowIndex > 0 ? rowIndex - 1 : 0;
    rows[absorber] += length;

    return { ...config, rows };
}

export function setModule(
    config: SplitFlapConfig,
    index: number,
    patch: Partial<FlapModule>
): SplitFlapConfig {
    if (index < 0 || index >= config.modules.length) return config;
    const modules = config.modules.map((module, i) => (i === index ? { ...module, ...patch } : module));
    return { ...config, modules };
}

/** Sets one character set across every flap in a row. */
export function setRowCharset(config: SplitFlapConfig, rowIndex: number, charset: string): SplitFlapConfig {
    const span = rowSpans(config)[rowIndex];
    if (!span) return config;
    const modules = config.modules.map((module, i) =>
        i >= span.start && i < span.start + span.length ? { ...module, charset } : module
    );
    return { ...config, modules };
}

export function setCharsetFlaps(
    config: SplitFlapConfig,
    name: string,
    flaps: string[]
): SplitFlapConfig {
    const charsets = config.charsets.map(set => (set.name === name ? { ...set, flaps } : set));
    return { ...config, charsets };
}

/** The character set every row uses, or null when a row is mixed. */
export function rowCharset(config: SplitFlapConfig, rowIndex: number): string | null {
    const span = rowSpans(config)[rowIndex];
    if (!span || span.length === 0) return null;
    const slice = config.modules.slice(span.start, span.start + span.length);
    const first = slice[0]?.charset;
    return slice.every(module => module.charset === first) ? first ?? null : null;
}

/** How many flaps each character set is loaded on. */
export function charsetUsage(config: SplitFlapConfig): Record<string, number> {
    const usage: Record<string, number> = {};
    for (const set of config.charsets) usage[set.name] = 0;
    for (const module of config.modules) {
        usage[module.charset] = (usage[module.charset] ?? 0) + 1;
    }
    return usage;
}

// --- validation -----------------------------------------------------------

export interface SplitFlapErrors {
    rows: Record<number, string>;
    modules: Record<number, string>;
    charsets: Record<string, string>;
    autoRehome: Partial<Record<'maxAttempts' | 'windowSeconds' | 'backoffSeconds', string>>;
    general: string[];
}

export function emptySplitFlapErrors(): SplitFlapErrors {
    return { rows: {}, modules: {}, charsets: {}, autoRehome: {}, general: [] };
}

export function hasSplitFlapErrors(errors: SplitFlapErrors): boolean {
    return (
        errors.general.length > 0 ||
        Object.keys(errors.rows).length > 0 ||
        Object.keys(errors.modules).length > 0 ||
        Object.keys(errors.charsets).length > 0 ||
        Object.keys(errors.autoRehome).length > 0
    );
}

/**
 * Everything the service would refuse, or accept and then get wrong. A wrong
 * channel is the one mistake on this page that fails silently — it addresses a
 * module that looks fine — so duplicates and out-of-range values are caught
 * here rather than written.
 */
export function validateSplitFlap(config: SplitFlapConfig): SplitFlapErrors {
    const errors = emptySplitFlapErrors();
    const names = new Set(config.charsets.map(set => set.name));
    const seen = new Map<number, number>();

    config.modules.forEach((module, index) => {
        if (!Number.isInteger(module.channel) || module.channel < 0 || module.channel > MAX_CHANNEL) {
            errors.modules[index] = `Channel must be a whole number between 0 and ${MAX_CHANNEL}.`;
        } else {
            const owner = seen.get(module.channel);
            if (owner !== undefined) {
                errors.modules[index] = `Channel ${module.channel} is already wired to flap ${owner + 1}.`;
            } else {
                seen.set(module.channel, index);
            }
        }

        if (!names.has(module.charset)) {
            errors.modules[index] = `There is no character set named "${module.charset}".`;
        }
    });

    config.rows.forEach((length, index) => {
        if (!Number.isInteger(length) || length < 1) {
            errors.rows[index] = 'A row needs at least one flap.';
        }
    });

    const rowTotal = config.rows.reduce((sum, length) => sum + length, 0);
    if (config.modules.length > 0 && rowTotal !== config.modules.length) {
        errors.general.push(
            `The rows describe ${rowTotal} flaps but the display has ${config.modules.length}.`
        );
    }

    for (const set of config.charsets) {
        if (set.flaps.length === 0) {
            errors.charsets[set.name] = 'A set with no flaps cannot be saved.';
        }
    }

    if (config.enabled && config.modules.length === 0) {
        errors.general.push('The display is switched on but no flaps are configured.');
    }

    const { autoRehome } = config;
    if (!Number.isInteger(autoRehome.maxAttempts) || autoRehome.maxAttempts < 1) {
        errors.autoRehome.maxAttempts = 'At least 1.';
    }
    if (!Number.isFinite(autoRehome.windowSeconds) || autoRehome.windowSeconds < 1) {
        errors.autoRehome.windowSeconds = 'At least 1 second.';
    }
    if (!Number.isFinite(autoRehome.backoffSeconds) || autoRehome.backoffSeconds < 0) {
        errors.autoRehome.backoffSeconds = '0 or more seconds.';
    }

    return errors;
}

/** Accepted by the service, but worth saying out loud. */
export function splitFlapWarnings(config: SplitFlapConfig): string[] {
    const warnings: string[] = [];

    const lengths = [...new Set(config.charsets.map(set => set.flaps.length))].sort((a, b) => a - b);
    if (lengths.length > 1) {
        warnings.push(
            `Character sets hold different numbers of flaps (${lengths.join(', ')}). The firmware uses ` +
                'one NUM_FLAPS for every module, so text sent to the odd set out can land on the wrong flap.'
        );
    }

    if (config.modules.length > 0 && !config.enabled) {
        warnings.push('The display is switched off, so nothing here is written to the modules.');
    }

    return warnings;
}

// --- saving ---------------------------------------------------------------

function modulesPayload(config: SplitFlapConfig): Record<string, unknown>[] {
    return config.modules.map(module => ({ channel: module.channel, charset: module.charset }));
}

function sameFlaps(a: readonly string[], b: readonly string[]): boolean {
    return a.length === b.length && a.every((token, i) => token === b[i]);
}

/**
 * The dotted config keys that differ from what the service last gave us. The
 * page counts these for its unsaved-changes badge and sends exactly these.
 */
export function splitFlapChanges(current: SplitFlapConfig, saved: SplitFlapConfig): string[] {
    const changes: string[] = [];

    if (current.enabled !== saved.enabled) changes.push(SPLITFLAP_PATHS.enabled);
    if (current.port !== saved.port) changes.push(SPLITFLAP_PATHS.port);
    if (JSON.stringify(current.rows) !== JSON.stringify(saved.rows)) changes.push(SPLITFLAP_PATHS.rows);
    if (JSON.stringify(modulesPayload(current)) !== JSON.stringify(modulesPayload(saved))) {
        changes.push(SPLITFLAP_PATHS.channels);
    }
    if (current.autoRehome.enabled !== saved.autoRehome.enabled) {
        changes.push(SPLITFLAP_PATHS.autoRehomeEnabled);
    }
    if (!Object.is(current.autoRehome.maxAttempts, saved.autoRehome.maxAttempts)) {
        changes.push(SPLITFLAP_PATHS.autoRehomeMaxAttempts);
    }
    if (!Object.is(current.autoRehome.windowSeconds, saved.autoRehome.windowSeconds)) {
        changes.push(SPLITFLAP_PATHS.autoRehomeWindowSeconds);
    }
    if (!Object.is(current.autoRehome.backoffSeconds, saved.autoRehome.backoffSeconds)) {
        changes.push(SPLITFLAP_PATHS.autoRehomeBackoffSeconds);
    }

    for (const set of current.charsets) {
        const previous = saved.charsets.find(candidate => candidate.name === set.name);
        // A set the service has never seen cannot be written: POST /api/config
        // would list it as ignored. The UI disables adding sets for exactly
        // this reason, so this only guards against a stale form.
        if (!previous) continue;
        if (!sameFlaps(set.flaps, previous.flaps)) changes.push(charsetPath(set.name));
    }

    return changes;
}

export function isSplitFlapDirty(current: SplitFlapConfig, saved: SplitFlapConfig): boolean {
    return splitFlapChanges(current, saved).length > 0;
}

/** The changed keys as a POST body for `/api/config`. */
export function toSplitFlapPayload(
    current: SplitFlapConfig,
    saved: SplitFlapConfig
): Record<string, unknown> {
    const payload: Record<string, unknown> = {};

    for (const key of splitFlapChanges(current, saved)) {
        switch (key) {
            case SPLITFLAP_PATHS.enabled:
                payload[key] = current.enabled;
                break;
            case SPLITFLAP_PATHS.port:
                payload[key] = current.port.trim();
                break;
            case SPLITFLAP_PATHS.rows:
                payload[key] = current.rows;
                break;
            case SPLITFLAP_PATHS.channels:
                payload[key] = modulesPayload(current);
                break;
            case SPLITFLAP_PATHS.autoRehomeEnabled:
                payload[key] = current.autoRehome.enabled;
                break;
            case SPLITFLAP_PATHS.autoRehomeMaxAttempts:
                payload[key] = current.autoRehome.maxAttempts;
                break;
            case SPLITFLAP_PATHS.autoRehomeWindowSeconds:
                payload[key] = current.autoRehome.windowSeconds;
                break;
            case SPLITFLAP_PATHS.autoRehomeBackoffSeconds:
                payload[key] = current.autoRehome.backoffSeconds;
                break;
            default: {
                const set = current.charsets.find(candidate => charsetPath(candidate.name) === key);
                // Sent as a list so each entry is one flap, with no braces to
                // escape: a flap really named "{" or "}" needs doubling in the
                // text form, and nothing here has to know that.
                if (set) payload[key] = set.flaps;
                break;
            }
        }
    }

    return payload;
}
