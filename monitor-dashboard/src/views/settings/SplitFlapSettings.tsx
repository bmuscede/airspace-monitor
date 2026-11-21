import { useMemo, useState } from 'react';
import { MoonStar, Plus, Trash2, X } from 'lucide-react';
import ConfirmDialog from '../../components/ConfirmDialog';
import {
    FieldError,
    FieldHelp,
    FieldRow,
    Panel,
    PageFootnote,
    SaveBar,
    SettingsHeader,
    StubNotice,
    Switch,
    WarningNotice,
} from '../../components/settings/SettingsPrimitives';
import {
    buttonDanger,
    buttonGhostDanger,
    buttonPrimary,
    buttonSecondary,
    inputClasses,
    numberValue,
} from '../../components/settings/settingsStyles';
import {
    DEFAULT_CHARSET_NAME,
    addRow,
    charsetUsage,
    flapLabel,
    formatFlapTokens,
    hasSplitFlapErrors,
    parseFlapTokens,
    removeRow,
    rowCharset,
    rowSpans,
    setCharsetFlaps,
    setModule,
    setRowCharset,
    setRowLength,
    splitFlapChanges,
    splitFlapWarnings,
    validateSplitFlap,
} from '../../lib/splitflap';
import type { SplitFlapConfig } from '../../types';

interface SplitFlapSettingsProps {
    splitFlap: SplitFlapConfig;
    savedSplitFlap: SplitFlapConfig;
    onChange: (updater: (previous: SplitFlapConfig) => SplitFlapConfig) => void;
    onDiscard: () => void;
    onSave: () => void;
    saving: boolean;
    /** Clears splitflap.calibration so the service measures offsets again. */
    onForgetCalibration: () => void;
}

const CHIP_LIMIT = 24;

function formatTimestamp(seconds: number): string | null {
    if (!Number.isFinite(seconds) || seconds <= 0) return null;
    return new Date(seconds * 1000).toLocaleString();
}

export default function SplitFlapSettings({
    splitFlap,
    savedSplitFlap,
    onChange,
    onDiscard,
    onSave,
    saving,
    onForgetCalibration,
}: SplitFlapSettingsProps) {
    const [selectedSet, setSelectedSet] = useState(DEFAULT_CHARSET_NAME);
    const [bulkText, setBulkText] = useState('');
    const [confirmClear, setConfirmClear] = useState(false);
    const [confirmForget, setConfirmForget] = useState(false);

    const errors = validateSplitFlap(splitFlap);
    const warnings = splitFlapWarnings(splitFlap);
    const changes = splitFlapChanges(splitFlap, savedSplitFlap);
    const blocked = hasSplitFlapErrors(errors);
    const canSave = changes.length > 0 && !blocked;

    const spans = rowSpans(splitFlap);
    const usage = charsetUsage(splitFlap);
    const names = splitFlap.charsets.map(set => set.name);
    const active = splitFlap.charsets.find(set => set.name === selectedSet) ?? splitFlap.charsets[0];

    const parsed = useMemo(() => {
        if (!bulkText) return { tokens: [] as string[], error: null as string | null };
        try {
            return { tokens: parseFlapTokens(bulkText), error: null };
        } catch (err) {
            return { tokens: [], error: err instanceof Error ? err.message : String(err) };
        }
    }, [bulkText]);

    const appendFlaps = () => {
        if (!active || parsed.error || parsed.tokens.length === 0) return;
        onChange(previous => setCharsetFlaps(previous, active.name, [...active.flaps, ...parsed.tokens]));
        setBulkText('');
    };

    const removeFlap = (index: number) => {
        if (!active) return;
        onChange(previous =>
            setCharsetFlaps(
                previous,
                active.name,
                active.flaps.filter((_, i) => i !== index)
            )
        );
    };

    const calibratedAt = formatTimestamp(splitFlap.calibration.calibratedAt);

    return (
        <div className="space-y-4 pb-10 max-w-5xl">
            <SettingsHeader
                title="Split-Flap Display"
                description="Modules, layout, character sets — and when the flaps are allowed to move."
            >
                <SaveBar
                    changeCount={changes.length}
                    canSave={canSave}
                    saving={saving}
                    blockedReason={
                        blocked
                            ? 'Fix the highlighted fields first.'
                            : changes.length === 0
                                ? 'No unsaved changes.'
                                : undefined
                    }
                    onSave={onSave}
                    onDiscard={onDiscard}
                />
            </SettingsHeader>

            {errors.general.length > 0 && (
                <WarningNotice>
                    {errors.general.map(message => (
                        <span key={message} className="block">
                            {message}
                        </span>
                    ))}
                </WarningNotice>
            )}

            {warnings.map(message => (
                <StubNotice key={message}>{message}</StubNotice>
            ))}

            <Panel
                title="On the flaps now"
                meta={
                    <>
                        <span>{splitFlap.enabled ? 'Enabled in config' : 'Disabled in config'}</span>
                        <span className="font-mono">{splitFlap.port.trim() || 'auto-detect'}</span>
                        <span>{splitFlap.modules.length} modules</span>
                    </>
                }
            >
                {/* TODO: This is a stub comment. Nothing reports what the driver last
                    wrote, the firmware version, the resolved serial port or the
                    connection state — /api/state carries none of it. This panel shows
                    the configured shape until a live read exists. */}
                <StubNotice>
                    The flaps the display is actually showing, its firmware version, the port it settled on and
                    when it last wrote are not reported by the service yet. What is above is the configured
                    shape, not live hardware.
                </StubNotice>
            </Panel>

            <Panel title="Hardware">
                <FieldRow
                    first
                    align="center"
                    label="Display enabled"
                    help="Off leaves the modules alone and writes nothing."
                >
                    <div className="flex justify-end">
                        <Switch
                            label="Display enabled"
                            checked={splitFlap.enabled}
                            onChange={enabled => onChange(previous => ({ ...previous, enabled }))}
                        />
                    </div>
                </FieldRow>

                <FieldRow
                    label={<label htmlFor="splitflap_port">Serial port</label>}
                    help="Blank means auto-detect, which is the default."
                >
                    <input
                        id="splitflap_port"
                        type="text"
                        value={splitFlap.port}
                        placeholder="Auto-detect"
                        onChange={event => {
                            const port = event.target.value;
                            onChange(previous => ({ ...previous, port }));
                        }}
                        className={`${inputClasses()} w-full`}
                    />
                    {/* TODO: This is a stub comment. The design offers a list of detected
                        ports; enumerating them needs an endpoint, so this stays free text. */}
                    <FieldHelp>
                        Typed rather than picked from a list: the service has no endpoint that enumerates serial
                        ports. A path like <span className="font-mono">/dev/ttyUSB0</span> pins it; blank lets the
                        service find the board.
                    </FieldHelp>
                </FieldRow>

                <FieldRow label="Test the display" help="Would run immediately; nothing is saved.">
                    {/* TODO: This is a stub comment. Re-home, cycle and show-text exist as
                        splitflap.calibrate subcommands but have no POST endpoint, and the
                        service holds the serial port while it runs. */}
                    <div className="flex flex-wrap gap-2">
                        <button type="button" className={buttonSecondary} disabled title="No endpoint for this yet.">
                            Re-home all
                        </button>
                        <button type="button" className={buttonSecondary} disabled title="No endpoint for this yet.">
                            Cycle every flap
                        </button>
                        <button type="button" className={buttonSecondary} disabled title="No endpoint for this yet.">
                            Show text…
                        </button>
                    </div>
                    <FieldHelp>
                        Disabled: these are <span className="font-mono">splitflap.calibrate</span> subcommands
                        today, and running one needs the service to hand over the serial port.
                    </FieldHelp>
                </FieldRow>
            </Panel>

            <Panel
                title="Rows and character sets"
                meta={
                    <span>
                        {splitFlap.modules.length} flaps across {splitFlap.rows.length || 0}{' '}
                        {splitFlap.rows.length === 1 ? 'row' : 'rows'}
                    </span>
                }
            >
                <FieldRow
                    first
                    label="Rows"
                    help={
                        <>
                            Top to bottom, as they are stacked on the frame. Each flap carries the set its spool is
                            loaded with, and under it the Chainlink channel it is wired to. Channels auto-assign as
                            flaps are added; a channel can only belong to one flap.
                        </>
                    }
                >
                    <div className="flex flex-col gap-2.5">
                        {spans.map((span, rowIndex) => {
                            const wholeRow = rowCharset(splitFlap, rowIndex);
                            return (
                                <div
                                    key={rowIndex}
                                    className="border border-slate-800 bg-slate-950/45 rounded-xl p-3"
                                >
                                    <div className="flex items-center gap-2.5 flex-wrap mb-3">
                                        <span className="text-sm font-semibold text-white">Row {rowIndex + 1}</span>
                                        <input
                                            type="number"
                                            min={1}
                                            value={numberValue(splitFlap.rows[rowIndex] ?? span.length)}
                                            aria-label={`Modules in row ${rowIndex + 1}`}
                                            aria-invalid={!!errors.rows[rowIndex]}
                                            onChange={event => {
                                                const length = Number(event.target.value);
                                                if (!Number.isFinite(length)) return;
                                                onChange(previous => setRowLength(previous, rowIndex, length));
                                            }}
                                            className={`${inputClasses(!!errors.rows[rowIndex])} w-16 text-center`}
                                        />
                                        <span className="text-xs text-slate-400">modules</span>
                                        <span className="flex-1" />
                                        <label className="text-xs text-slate-400 flex items-center gap-2">
                                            Whole row
                                            <select
                                                aria-label={`Character set for every module in row ${rowIndex + 1}`}
                                                value={wholeRow ?? ''}
                                                onChange={event => {
                                                    const charset = event.target.value;
                                                    if (!charset) return;
                                                    onChange(previous => setRowCharset(previous, rowIndex, charset));
                                                }}
                                                className={`${inputClasses()} w-32`}
                                            >
                                                {wholeRow === null && <option value="">Mixed</option>}
                                                {names.map(name => (
                                                    <option key={name} value={name}>
                                                        {name}
                                                    </option>
                                                ))}
                                            </select>
                                        </label>
                                        <button
                                            type="button"
                                            onClick={() => onChange(previous => removeRow(previous, rowIndex))}
                                            disabled={splitFlap.rows.length <= 1}
                                            aria-label={`Remove row ${rowIndex + 1}`}
                                            title={
                                                splitFlap.rows.length <= 1
                                                    ? 'The display needs at least one row.'
                                                    : 'Remove row — its flaps join the row above.'
                                            }
                                            className="p-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-rose-400 hover:border-rose-900 transition-colors disabled:opacity-35 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </div>

                                    <FieldError>{errors.rows[rowIndex]}</FieldError>

                                    <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-8 gap-1.5">
                                        {Array.from({ length: span.length }, (_, offset) => {
                                            const index = span.start + offset;
                                            const module = splitFlap.modules[index];
                                            if (!module) return null;
                                            const moduleError = errors.modules[index];
                                            return (
                                                <div key={index} className="flex flex-col gap-1">
                                                    <span className="text-[10px] text-slate-400 text-center font-mono">
                                                        Flap {index + 1}
                                                    </span>
                                                    <select
                                                        aria-label={`Character set for flap ${index + 1}`}
                                                        value={module.charset}
                                                        onChange={event => {
                                                            const charset = event.target.value;
                                                            onChange(previous => setModule(previous, index, { charset }));
                                                        }}
                                                        className={`w-full bg-slate-950 border rounded-md px-1 py-1.5 text-[11px] font-mono text-center text-slate-200 focus:outline-none focus:ring-1 focus:ring-emerald-500 ${module.charset === DEFAULT_CHARSET_NAME ? 'border-slate-800' : 'border-emerald-500/50 text-emerald-300'}`}
                                                    >
                                                        {!names.includes(module.charset) && (
                                                            <option value={module.charset}>{module.charset}</option>
                                                        )}
                                                        {names.map(name => (
                                                            <option key={name} value={name}>
                                                                {name}
                                                            </option>
                                                        ))}
                                                    </select>
                                                    <input
                                                        type="number"
                                                        value={numberValue(module.channel)}
                                                        aria-label={`Channel for flap ${index + 1}`}
                                                        aria-invalid={!!moduleError}
                                                        title={moduleError}
                                                        onChange={event => {
                                                            const raw = event.target.value;
                                                            const channel = raw === '' ? Number.NaN : Number(raw);
                                                            onChange(previous => setModule(previous, index, { channel }));
                                                        }}
                                                        className={`w-full bg-slate-950 border rounded-md px-1 py-1 text-[11px] font-mono text-center focus:outline-none focus:ring-1 ${moduleError ? 'border-rose-700 text-rose-300 focus:ring-rose-500' : 'border-slate-800 text-slate-300 focus:ring-emerald-500'}`}
                                                    />
                                                </div>
                                            );
                                        })}
                                    </div>
                                    <p className="flex justify-end gap-1.5 mt-1.5 text-[10px] text-slate-500 font-mono">
                                        <span>character set</span>
                                        <span className="text-slate-600">·</span>
                                        <span>channel</span>
                                    </p>
                                </div>
                            );
                        })}

                        {Object.entries(errors.modules).map(([index, message]) => (
                            <FieldError key={index}>{`Flap ${Number(index) + 1}: ${message}`}</FieldError>
                        ))}

                        <div className="flex items-center gap-3 flex-wrap">
                            <button
                                type="button"
                                onClick={() => onChange(addRow)}
                                className={`${buttonSecondary} border-dashed`}
                            >
                                <Plus className="w-3.5 h-3.5" />
                                Add row
                            </button>
                            <span className="text-xs text-slate-400">
                                A new row starts on <span className="font-mono">default</span> throughout, taking the
                                next free channels. Removing a row hands its flaps back to the row above.
                            </span>
                        </div>
                    </div>
                </FieldRow>

                <FieldRow
                    label="Sets"
                    help={
                        <>
                            <span className="font-mono">default</span> is required. Every set has to hold the same
                            number of flaps — the firmware has one <span className="font-mono">NUM_FLAPS</span> for
                            all modules.
                        </>
                    }
                >
                    <div className="flex flex-col gap-2">
                        {splitFlap.charsets.map(set => {
                            const editing = active?.name === set.name;
                            return (
                                <div
                                    key={set.name}
                                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border ${editing ? 'border-emerald-500/40 bg-emerald-500/[0.07]' : 'border-slate-800 bg-slate-950/50'}`}
                                >
                                    <span
                                        className={`flex-1 text-sm font-mono font-semibold ${editing ? 'text-emerald-300' : 'text-white'}`}
                                    >
                                        {set.name}
                                    </span>
                                    <span className="text-xs text-slate-400">{set.flaps.length} flaps</span>
                                    <span className="text-xs text-slate-400">used by {usage[set.name] ?? 0}</span>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setSelectedSet(set.name);
                                            setBulkText('');
                                        }}
                                        className={`${buttonSecondary} px-2.5 py-1`}
                                    >
                                        {editing ? 'Editing' : 'Edit'}
                                    </button>
                                    {/* TODO: This is a stub comment. Removing a set means deleting a
                                        config key, which POST /api/config cannot express — it only sets
                                        keys the service already defines, and ignores nulls. */}
                                    <button
                                        type="button"
                                        disabled
                                        aria-label={`Remove ${set.name} set`}
                                        title={
                                            set.name === DEFAULT_CHARSET_NAME
                                                ? 'The default set is required.'
                                                : 'Removing a set needs an endpoint that can delete a config key.'
                                        }
                                        className="p-1.5 rounded-lg border border-slate-700 text-slate-400 opacity-35 cursor-not-allowed"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            );
                        })}

                        {Object.entries(errors.charsets).map(([name, message]) => (
                            <FieldError key={name}>{`${name}: ${message}`}</FieldError>
                        ))}

                        {/* TODO: This is a stub comment. A new set cannot be saved: the service
                            drops config keys it does not already define and lists them back as
                            ignored, so adding one would look like it worked and do nothing. */}
                        <button
                            type="button"
                            disabled
                            title="A set the service has never seen cannot be saved yet."
                            className={`${buttonSecondary} border-dashed self-start`}
                        >
                            <Plus className="w-3.5 h-3.5" />
                            Add character set
                        </button>
                        <StubNotice>
                            Sets can be edited but not added or removed. Writing a set the service has never seen
                            needs an endpoint that can create and delete config keys — today{' '}
                            <span className="font-mono">POST /api/config</span> only sets keys it already defines.
                        </StubNotice>
                    </div>
                </FieldRow>

                {active && (
                    <FieldRow
                        label={
                            <>
                                Flaps in <span className="font-mono text-emerald-300">{active.name}</span>
                            </>
                        }
                        help="In spool order. Index 0 is the home flap — the one a module shows after homing."
                    >
                        <div className="flex flex-wrap gap-1.5 p-3 bg-slate-950/60 border border-slate-800 rounded-xl">
                            {active.flaps.length === 0 && (
                                <span className="text-xs text-slate-500">
                                    This set has no flaps, so it cannot be saved.
                                </span>
                            )}
                            {active.flaps.slice(0, CHIP_LIMIT).map((token, index) => (
                                <span
                                    key={`${token}-${index}`}
                                    className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs font-mono ${token.length > 1 ? 'border-emerald-500/45 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-950/60 text-slate-300'}`}
                                >
                                    {flapLabel(token)}
                                    {index === 0 ? (
                                        <span className="text-[10px] text-slate-400">home</span>
                                    ) : (
                                        <button
                                            type="button"
                                            onClick={() => removeFlap(index)}
                                            aria-label={`Remove flap ${flapLabel(token)}`}
                                            className="text-slate-500 hover:text-rose-400 transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-rose-400 rounded"
                                        >
                                            <X className="w-3 h-3" />
                                        </button>
                                    )}
                                </span>
                            ))}
                            {active.flaps.length > CHIP_LIMIT && (
                                <span className="inline-flex items-center px-2 py-1 rounded-md border border-dashed border-slate-700 text-xs text-slate-400 font-mono">
                                    + {active.flaps.length - CHIP_LIMIT} more
                                </span>
                            )}
                        </div>

                        <div className="mt-3">
                            <label htmlFor="flap-bulk" className="text-xs text-slate-400">
                                Type the whole spool in one go
                            </label>
                            <textarea
                                id="flap-bulk"
                                rows={3}
                                value={bulkText}
                                onChange={event => setBulkText(event.target.value)}
                                placeholder={formatFlapTokens(active.flaps.slice(0, 8))}
                                className={`${inputClasses(!!parsed.error)} w-full mt-1.5 leading-relaxed`}
                            />
                            <div className="flex flex-wrap items-center gap-3 mt-2.5">
                                <button
                                    type="button"
                                    onClick={appendFlaps}
                                    disabled={!!parsed.error || parsed.tokens.length === 0}
                                    title={parsed.error ?? (parsed.tokens.length === 0 ? 'Nothing to add.' : undefined)}
                                    className={`${buttonPrimary} px-3.5 py-2 text-xs`}
                                >
                                    Add
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setConfirmClear(true)}
                                    disabled={active.flaps.length === 0}
                                    className={`${buttonGhostDanger} px-3 py-1.5 text-xs`}
                                >
                                    Clear all
                                </button>
                                {parsed.error ? (
                                    <span className="text-xs text-rose-400">{parsed.error}</span>
                                ) : (
                                    bulkText && (
                                        <span className="text-xs font-mono text-emerald-300">
                                            parses to {parsed.tokens.length}{' '}
                                            {parsed.tokens.length === 1 ? 'flap' : 'flaps'}
                                        </span>
                                    )
                                )}
                            </div>
                            <FieldHelp>
                                Anything inside braces is one symbol flap — <span className="font-mono">{'{ACA}'}</span>{' '}
                                — and everything outside is read one character at a time, so{' '}
                                <span className="font-mono">{'{ACA}AB'}</span> is three flaps. Spaces count; write{' '}
                                <span className="font-mono">{'{{'}</span> for a literal brace.{' '}
                                <strong className="text-slate-300">Add</strong> appends to the end of the spool
                                order, so pasting replaces nothing. Reordering is done by clearing and retyping the
                                spool — dragging flaps is not implemented.
                            </FieldHelp>
                        </div>
                    </FieldRow>
                )}

                {active && (
                    <FieldRow
                        label="Fallback flap"
                        help={
                            <>
                                Shown when text asks{' '}
                                <span className="font-mono text-emerald-300">{active.name}</span> for something it
                                does not carry.
                            </>
                        }
                    >
                        {/* TODO: This is a stub comment. splitflap.charsets.<name>.fallback is
                            not a key the service's config defines, so it cannot be written yet;
                            the service derives the fallback itself (a space when the set has one). */}
                        <select
                            disabled
                            aria-label="Fallback flap"
                            value=""
                            title="The service has no fallback key to write to yet."
                            className={`${inputClasses()} w-full max-w-60`}
                        >
                            <option value="">
                                {active.fallback === null
                                    ? 'Chosen by the service — a space when the set has one'
                                    : flapLabel(active.fallback)}
                            </option>
                        </select>
                        <FieldHelp>
                            Disabled: the service works the fallback out itself and has no config key for it.
                        </FieldHelp>
                    </FieldRow>
                )}

                <FieldHelp>
                    Flap order is what text is laid out across — flap 1 is the leftmost of the top row — while the
                    channel is how that flap is wired. A wrong channel is the one mistake on this page that fails
                    silently, by addressing a module that looks fine, so duplicates and out-of-range values are
                    refused here rather than written.
                </FieldHelp>
            </Panel>

            <Panel
                title="Quiet hours"
                tone="accent"
                description="The modules are audible from the next room. Inside the window the service would keep tracking and the dashboard would keep updating — only the flaps hold still."
                action={
                    <MoonStar className="w-5 h-5 text-emerald-400/70" aria-hidden="true" />
                }
            >
                {/* TODO: This is a stub comment. None of the six splitflap.quiet_hours.*
                    keys exist in the service's config, and the hardware cycle does not
                    honour a window yet, so the whole panel is disabled rather than
                    offering settings that would be dropped as ignored on save. */}
                <StubNotice>
                    Not available yet. Quiet hours need six new{' '}
                    <span className="font-mono">splitflap.quiet_hours.*</span> config keys and a hardware cycle
                    that honours the window — the service has neither, and saving them now would be dropped as
                    ignored. The window, days, freeze-or-blank choice and the close-aircraft override are drawn in
                    the design and left out here on purpose.
                </StubNotice>
            </Panel>

            <Panel title="Reliability">
                <FieldRow
                    first
                    align="center"
                    label="Auto re-home"
                    help="Recover a module that has lost its home sensor."
                >
                    <div className="flex justify-end">
                        <Switch
                            label="Auto re-home enabled"
                            checked={splitFlap.autoRehome.enabled}
                            onChange={enabled =>
                                onChange(previous => ({
                                    ...previous,
                                    autoRehome: { ...previous.autoRehome, enabled },
                                }))
                            }
                        />
                    </div>
                </FieldRow>

                <FieldRow
                    label="Limits"
                    help="Per module: at most this many attempts in the window, at least the backoff apart."
                >
                    <div className="flex flex-wrap gap-3">
                        {(
                            [
                                ['maxAttempts', 'Attempts', 1] as const,
                                ['windowSeconds', 'Window (s)', 1] as const,
                                ['backoffSeconds', 'Backoff (s)', 0] as const,
                            ]
                        ).map(([key, label, min]) => (
                            <label key={key} className="flex-1 min-w-28 text-xs text-slate-400">
                                {label}
                                <input
                                    type="number"
                                    min={min}
                                    value={numberValue(splitFlap.autoRehome[key])}
                                    aria-label={label}
                                    aria-invalid={!!errors.autoRehome[key]}
                                    disabled={!splitFlap.autoRehome.enabled}
                                    onChange={event => {
                                        const raw = event.target.value;
                                        const value = raw === '' ? Number.NaN : Number(raw);
                                        onChange(previous => ({
                                            ...previous,
                                            autoRehome: { ...previous.autoRehome, [key]: value },
                                        }));
                                    }}
                                    className={`${inputClasses(!!errors.autoRehome[key])} mt-1.5 text-center`}
                                />
                                <FieldError>{errors.autoRehome[key]}</FieldError>
                            </label>
                        ))}
                    </div>
                </FieldRow>

                <FieldRow label="Module health" help="Which modules homed, re-homed or gave up.">
                    {/* TODO: This is a stub comment. The driver tracks per-module rehome
                        state but nothing exposes it; /api/state carries no module array. */}
                    <StubNotice>
                        Per-module health is not reported yet. The driver knows which modules re-homed and which
                        gave up, but no endpoint returns it.
                    </StubNotice>
                </FieldRow>
            </Panel>

            <Panel title="Calibration">
                <FieldRow
                    first
                    align="center"
                    label="Home offsets"
                    help="Measured once per build; this is what stops the service redoing it on every boot."
                >
                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <span className="text-sm font-mono text-emerald-300">
                            {splitFlap.calibration.calibrated
                                ? calibratedAt
                                    ? `measured ${calibratedAt}`
                                    : 'measured, date not recorded'
                                : 'not calibrated'}
                        </span>
                        <span className="flex gap-2">
                            {/* TODO: This is a stub comment. Re-running calibration is
                                `python -m splitflap.calibrate` with the service stopped; wiring
                                it to a button means the service has to hand the serial port
                                over and take it back, and there is no endpoint for either. */}
                            <button
                                type="button"
                                disabled
                                title="Calibration has to run with the service stopped; there is no endpoint for it yet."
                                className={buttonDanger}
                            >
                                Re-run calibration
                            </button>
                            <button
                                type="button"
                                onClick={() => setConfirmForget(true)}
                                disabled={!splitFlap.calibration.calibrated}
                                title={
                                    splitFlap.calibration.calibrated
                                        ? 'Clear the saved calibration so the service measures again.'
                                        : 'Nothing is calibrated.'
                                }
                                className={buttonGhostDanger}
                            >
                                Forget
                            </button>
                        </span>
                    </div>
                    <FieldHelp>
                        Forgetting writes <span className="font-mono">splitflap.calibration.calibrated</span>{' '}
                        straight away — it is not part of the save above — and the service measures offsets again
                        on its next start.
                    </FieldHelp>
                </FieldRow>
            </Panel>

            <PageFootnote>
                <span className="font-mono">rows</span>, <span className="font-mono">channels</span>,{' '}
                <span className="font-mono">charsets</span>, <span className="font-mono">auto_rehome.*</span>,{' '}
                <span className="font-mono">port</span>, <span className="font-mono">enabled</span> and{' '}
                <span className="font-mono">calibration.*</span> all exist under{' '}
                <span className="font-mono">splitflap</span> in the service config, and this page writes them with
                dotted keys. A flap is saved as{' '}
                <span className="font-mono">{'{"channel": 0, "charset": "logos"}'}</span> in list order, and a
                set's flaps as a list, so a symbol flap stays one flap. Everything disabled above is marked where
                it sits: the live display read, the three test actions, quiet hours, module health, adding or
                removing a set, the per-set fallback, and re-running calibration.
            </PageFootnote>

            <ConfirmDialog
                open={confirmClear}
                destructive
                title={`Clear every flap in ${active?.name ?? 'this set'}?`}
                description="A set with no flaps cannot be saved, so the page will refuse to save until flaps are typed back in. Nothing is written to the service until you save."
                confirmLabel="Clear flaps"
                onConfirm={() => {
                    setConfirmClear(false);
                    if (active) onChange(previous => setCharsetFlaps(previous, active.name, []));
                }}
                onCancel={() => setConfirmClear(false)}
            />

            <ConfirmDialog
                open={confirmForget}
                destructive
                title="Forget the saved calibration?"
                description="The service measures home offsets again the next time it starts the display, which takes the flaps through a full homing pass. The offsets themselves live in the controller's flash; this only clears the note that says they were measured."
                confirmLabel="Forget calibration"
                onConfirm={() => {
                    setConfirmForget(false);
                    onForgetCalibration();
                }}
                onCancel={() => setConfirmForget(false)}
            />
        </div>
    );
}
