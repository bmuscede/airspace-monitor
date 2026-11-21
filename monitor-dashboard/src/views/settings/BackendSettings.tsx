import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import ConfirmDialog from '../../components/ConfirmDialog';
import {
    FieldError,
    FieldHelp,
    FieldRow,
    FieldWarning,
    Panel,
    SaveBar,
    SegmentedControl,
    PageFootnote,
    SettingsHeader,
} from '../../components/settings/SettingsPrimitives';
import { inputClasses, numberValue } from '../../components/settings/settingsStyles';
import {
    changedConfigKeys,
    configWarnings,
    shortensRetention,
    validateConfig,
} from '../../lib/config';
import { LOG_LEVELS } from '../../types';
import type { Config, LogLevel, NumericConfigKey, TextConfigKey } from '../../types';

interface BackendSettingsProps {
    config: Config;
    savedConfig: Config;
    setConfigField: <K extends keyof Config>(key: K, value: Config[K]) => void;
    onDiscard: () => void;
    onSave: () => void;
    saving: boolean;
    /** Contacts the service is holding, from /api/history/stats. */
    historyContactCount: number | null;
}

/** Seconds as something readable, so 3600 reads as an hour. */
function describeSeconds(value: number): string {
    if (!Number.isFinite(value) || value < 0) return '';
    if (value === 0) return 'no caching';
    if (value < 60) return `${value} s`;
    if (value < 3600) {
        const minutes = value / 60;
        return `${Number.isInteger(minutes) ? minutes : minutes.toFixed(1)} min`;
    }
    const hours = value / 3600;
    return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} h`;
}

export default function BackendSettings({
    config,
    savedConfig,
    setConfigField,
    onDiscard,
    onSave,
    saving,
    historyContactCount,
}: BackendSettingsProps) {
    const [revealed, setRevealed] = useState<Record<string, boolean>>({});
    const [confirmRetention, setConfirmRetention] = useState(false);

    const errors = validateConfig(config);
    const warnings = configWarnings(config);
    const changes = changedConfigKeys(config, savedConfig);
    const hasErrors = Object.keys(errors).length > 0;
    const canSave = changes.length > 0 && !hasErrors;

    const setNumber = (key: NumericConfigKey) => (event: React.ChangeEvent<HTMLInputElement>) => {
        // An empty field is held as NaN so validation can flag it rather than
        // silently POSTing a zero.
        const raw = event.target.value;
        setConfigField(key, raw === '' ? Number.NaN : Number(raw));
    };

    const setText = (key: TextConfigKey) => (event: React.ChangeEvent<HTMLInputElement>) => {
        setConfigField(key, event.target.value);
    };

    const errorProps = (key: keyof Config) => ({
        'aria-invalid': !!errors[key],
        'aria-describedby': errors[key] ? `${key}-error` : undefined,
    });

    const handleSave = () => {
        // Shortening retention deletes rows on the service's next daily sweep,
        // which no other field on this page does.
        if (shortensRetention(config, savedConfig)) {
            setConfirmRetention(true);
            return;
        }
        onSave();
    };

    const keyField = (key: Extract<TextConfigKey, 'flightaware_api_key' | 'openweathermap_api_key'>, label: string) => (
        <div className="flex gap-2">
            <input
                id={key}
                name={key}
                type={revealed[key] ? 'text' : 'password'}
                value={config[key]}
                onChange={setText(key)}
                placeholder="not set"
                aria-label={label}
                autoComplete="off"
                className={`${inputClasses(!!errors[key])} flex-1 min-w-0`}
            />
            <button
                type="button"
                onClick={() => setRevealed(previous => ({ ...previous, [key]: !previous[key] }))}
                aria-label={revealed[key] ? `Hide ${label}` : `Show ${label}`}
                className="px-3 rounded-lg border border-slate-700 bg-slate-800/60 text-slate-300 hover:bg-slate-700/60 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            >
                {revealed[key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
        </div>
    );

    return (
        <div className="space-y-4 pb-10 max-w-5xl">
            <SettingsHeader
                title="Backend"
                description="Where the receiver thinks it is, which services it calls, and how much it keeps."
            >
                <SaveBar
                    changeCount={changes.length}
                    canSave={canSave}
                    saving={saving}
                    blockedReason={
                        hasErrors
                            ? 'Fix the highlighted fields first.'
                            : changes.length === 0
                                ? 'No unsaved changes.'
                                : undefined
                    }
                    onSave={handleSave}
                    onDiscard={onDiscard}
                />
            </SettingsHeader>

            <Panel title="Receiver" meta={<span className="font-mono">radar.*</span>}>
                <FieldRow
                    first
                    label="Home position"
                    help="Every distance and bearing is measured from here. Decimal degrees."
                >
                    <div className="flex flex-wrap gap-3">
                        <label className="flex-1 min-w-36 text-xs text-slate-400">
                            Latitude
                            <input
                                id="home_lat"
                                name="home_lat"
                                type="number"
                                step="any"
                                value={numberValue(config.home_lat)}
                                onChange={setNumber('home_lat')}
                                {...errorProps('home_lat')}
                                className={`${inputClasses(!!errors.home_lat)} w-full mt-1.5`}
                            />
                        </label>
                        <label className="flex-1 min-w-36 text-xs text-slate-400">
                            Longitude
                            <input
                                id="home_lon"
                                name="home_lon"
                                type="number"
                                step="any"
                                value={numberValue(config.home_lon)}
                                onChange={setNumber('home_lon')}
                                {...errorProps('home_lon')}
                                className={`${inputClasses(!!errors.home_lon)} w-full mt-1.5`}
                            />
                        </label>
                    </div>
                    <FieldError id="home_lat-error">{errors.home_lat}</FieldError>
                    <FieldError id="home_lon-error">{errors.home_lon}</FieldError>
                    <FieldHelp>
                        −90 to 90 and −180 to 180. The service accepts whatever is in{' '}
                        <span className="font-mono">config.json</span> without checking, so a position out of
                        range only shows up as a scope with nothing on it.
                    </FieldHelp>
                </FieldRow>

                <FieldRow
                    label="Radar range"
                    help="Outer ring of the scope, and the cut-off for what counts as a contact."
                >
                    <div className="flex items-center gap-2.5">
                        <input
                            id="max_radar_range_nm"
                            name="max_radar_range_nm"
                            type="number"
                            value={numberValue(config.max_radar_range_nm)}
                            onChange={setNumber('max_radar_range_nm')}
                            {...errorProps('max_radar_range_nm')}
                            className={`${inputClasses(!!errors.max_radar_range_nm)} w-32`}
                        />
                        <span className="text-xs text-slate-400 whitespace-nowrap">NM</span>
                    </div>
                    <FieldError id="max_radar_range_nm-error">{errors.max_radar_range_nm}</FieldError>
                </FieldRow>
            </Panel>

            <Panel
                title="FlightAware"
                meta={
                    <span>
                        route lookups · <span className="font-mono">flightaware.*</span>
                    </span>
                }
            >
                <FieldRow first label={<label htmlFor="flightaware_url">API base URL</label>}>
                    <input
                        id="flightaware_url"
                        name="flightaware_url"
                        type="text"
                        value={config.flightaware_url}
                        onChange={setText('flightaware_url')}
                        {...errorProps('flightaware_url')}
                        className={`${inputClasses(!!errors.flightaware_url)} w-full`}
                    />
                    <FieldError id="flightaware_url-error">{errors.flightaware_url}</FieldError>
                </FieldRow>

                <FieldRow
                    label={<label htmlFor="flightaware_api_key">API key</label>}
                    help="Without it, origin and destination stay blank and the display falls back to the callsign alone."
                >
                    {keyField('flightaware_api_key', 'FlightAware API key')}
                    <FieldWarning>{warnings.flightaware_api_key}</FieldWarning>
                    <FieldHelp>
                        <span className="text-amber-300">Worth knowing:</span>{' '}
                        <span className="font-mono">GET /api/config</span> returns this key in plain text, so
                        masking the field hides it from the room, not from the network.
                    </FieldHelp>
                </FieldRow>

                <FieldRow
                    label={<label htmlFor="flightaware_cache_ttl">Cache lifetime</label>}
                    help="How long a looked-up route is reused before asking again."
                >
                    <div className="flex items-center gap-2.5">
                        <input
                            id="flightaware_cache_ttl"
                            name="flightaware_cache_ttl"
                            type="number"
                            value={numberValue(config.flightaware_cache_ttl)}
                            onChange={setNumber('flightaware_cache_ttl')}
                            {...errorProps('flightaware_cache_ttl')}
                            className={`${inputClasses(!!errors.flightaware_cache_ttl)} w-32`}
                        />
                        <span className="text-xs text-slate-400 whitespace-nowrap">
                            seconds{describeSeconds(config.flightaware_cache_ttl) && ` — ${describeSeconds(config.flightaware_cache_ttl)}`}
                        </span>
                    </div>
                    <FieldError id="flightaware_cache_ttl-error">{errors.flightaware_cache_ttl}</FieldError>
                </FieldRow>
            </Panel>

            <Panel
                title="Weather"
                meta={
                    <span>
                        forecast on the idle display · <span className="font-mono">openweathermap.*</span>
                    </span>
                }
            >
                <FieldRow first label={<label htmlFor="openweathermap_url">API base URL</label>}>
                    <input
                        id="openweathermap_url"
                        name="openweathermap_url"
                        type="text"
                        value={config.openweathermap_url}
                        onChange={setText('openweathermap_url')}
                        {...errorProps('openweathermap_url')}
                        className={`${inputClasses(!!errors.openweathermap_url)} w-full`}
                    />
                    <FieldError id="openweathermap_url-error">{errors.openweathermap_url}</FieldError>
                </FieldRow>

                <FieldRow
                    label={<label htmlFor="openweathermap_api_key">API key</label>}
                    help="The four-day forecast on the idle screen needs this. Without it the service asks anyway and gets 401s."
                >
                    {keyField('openweathermap_api_key', 'OpenWeatherMap API key')}
                    <FieldWarning>{warnings.openweathermap_api_key}</FieldWarning>
                </FieldRow>

                <FieldRow
                    label={<label htmlFor="openweathermap_cache_ttl">Cache lifetime</label>}
                    help="The forecast is fetched for the home position; its city name comes back with the response."
                >
                    <div className="flex items-center gap-2.5">
                        <input
                            id="openweathermap_cache_ttl"
                            name="openweathermap_cache_ttl"
                            type="number"
                            value={numberValue(config.openweathermap_cache_ttl)}
                            onChange={setNumber('openweathermap_cache_ttl')}
                            {...errorProps('openweathermap_cache_ttl')}
                            className={`${inputClasses(!!errors.openweathermap_cache_ttl)} w-32`}
                        />
                        <span className="text-xs text-slate-400 whitespace-nowrap">
                            seconds{describeSeconds(config.openweathermap_cache_ttl) && ` — ${describeSeconds(config.openweathermap_cache_ttl)}`}
                        </span>
                    </div>
                    <FieldError id="openweathermap_cache_ttl-error">{errors.openweathermap_cache_ttl}</FieldError>
                </FieldRow>
            </Panel>

            <Panel
                title="Contact history"
                meta={
                    <span>
                        applied live, no restart · <span className="font-mono">history.*</span>
                    </span>
                }
            >
                <FieldRow
                    first
                    label={<label htmlFor="history_contact_gap_seconds">Same-visit gap</label>}
                    help="An aircraft that drops out and comes back within this long counts as one visit rather than two."
                >
                    <div className="flex items-center gap-2.5">
                        <input
                            id="history_contact_gap_seconds"
                            name="history_contact_gap_seconds"
                            type="number"
                            value={numberValue(config.history_contact_gap_seconds)}
                            onChange={setNumber('history_contact_gap_seconds')}
                            {...errorProps('history_contact_gap_seconds')}
                            className={`${inputClasses(!!errors.history_contact_gap_seconds)} w-32`}
                        />
                        <span className="text-xs text-slate-400 whitespace-nowrap">
                            seconds{describeSeconds(config.history_contact_gap_seconds) && ` — ${describeSeconds(config.history_contact_gap_seconds)}`}
                        </span>
                    </div>
                    <FieldError id="history_contact_gap_seconds-error">
                        {errors.history_contact_gap_seconds}
                    </FieldError>
                </FieldRow>

                <FieldRow
                    label={<label htmlFor="history_flush_seconds">Backstop flush</label>}
                    help="How often open visits are written out, so a power cut costs minutes rather than hours."
                >
                    <div className="flex items-center gap-2.5">
                        <input
                            id="history_flush_seconds"
                            name="history_flush_seconds"
                            type="number"
                            value={numberValue(config.history_flush_seconds)}
                            onChange={setNumber('history_flush_seconds')}
                            {...errorProps('history_flush_seconds')}
                            className={`${inputClasses(!!errors.history_flush_seconds)} w-32`}
                        />
                        <span className="text-xs text-slate-400 whitespace-nowrap">
                            seconds{describeSeconds(config.history_flush_seconds) && ` — ${describeSeconds(config.history_flush_seconds)}`}
                        </span>
                    </div>
                    <FieldError id="history_flush_seconds-error">{errors.history_flush_seconds}</FieldError>
                </FieldRow>

                <FieldRow
                    label={<label htmlFor="history_retention_days">Retention</label>}
                    help="Older contacts are swept daily; the per-day counts survive the sweep, the individual rows do not."
                >
                    <div className="flex items-center gap-2.5">
                        <input
                            id="history_retention_days"
                            name="history_retention_days"
                            type="number"
                            value={numberValue(config.history_retention_days)}
                            onChange={setNumber('history_retention_days')}
                            {...errorProps('history_retention_days')}
                            className={`${inputClasses(!!errors.history_retention_days)} w-32`}
                        />
                        <span className="text-xs text-slate-400 whitespace-nowrap">days</span>
                    </div>
                    <FieldError id="history_retention_days-error">{errors.history_retention_days}</FieldError>
                    <FieldHelp>
                        {historyContactCount === null
                            ? 'The number of contacts held could not be read just now.'
                            : `Now holding ${historyContactCount.toLocaleString()} contacts.`}{' '}
                        {/* TODO: This is a stub comment. The size of history.db has no endpoint; the
                            contact count comes from /api/history/stats?range=all. */}
                        Shortening this deletes rows on the next sweep, so saving asks first.
                    </FieldHelp>
                </FieldRow>
            </Panel>

            <Panel
                title="Logging"
                meta={
                    <span>
                        applied live · <span className="font-mono">log_level</span>
                    </span>
                }
            >
                <FieldRow
                    first
                    label="Level"
                    help="Sets what reaches the log file — the Live Logs filters only hide what is already there."
                >
                    <SegmentedControl<LogLevel>
                        label="Log level"
                        options={LOG_LEVELS}
                        value={config.log_level}
                        onChange={level => setConfigField('log_level', level)}
                    />
                    <FieldHelp>DEBUG on a busy sky fills the 16 MB tmpfs log in well under an hour.</FieldHelp>
                    <FieldError>{errors.log_level}</FieldError>
                </FieldRow>
            </Panel>

            <PageFootnote>
                Every field here is a config key the service already defines, and{' '}
                <span className="font-mono">POST /api/config</span> applies{' '}
                <span className="font-mono">log_level</span> and the three{' '}
                <span className="font-mono">history.*</span> values to the live objects rather than waiting for a
                restart. The rest take effect when the service next reads them — the radar position and range on
                the next cycle, the API settings on the next lookup.
            </PageFootnote>

            <ConfirmDialog
                open={confirmRetention}
                destructive
                title="Shorten history retention?"
                description={`Keeping ${Number.isFinite(config.history_retention_days) ? config.history_retention_days : 0} days instead of ${savedConfig.history_retention_days} means the service deletes everything older on its next daily sweep. The per-day counts survive; the individual contacts do not.`}
                confirmLabel="Save and shorten"
                onConfirm={() => {
                    setConfirmRetention(false);
                    onSave();
                }}
                onCancel={() => setConfirmRetention(false)}
            />
        </div>
    );
}
