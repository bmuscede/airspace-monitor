import { AlertTriangle, Save, Wrench } from 'lucide-react';
import { buttonPrimary, buttonSecondary } from './settingsStyles';

/**
 * The shared furniture of the four settings pages: panels, label-and-control
 * rows, the save bar, and the notice that marks a control the service has no
 * endpoint for yet. Keeping them here is what stops Backend, Split-Flap,
 * Network and System drifting into four slightly different forms.
 *
 * Components only — the class strings and helpers live in settingsStyles.ts.
 */

interface SettingsHeaderProps {
    title: string;
    description: string;
    children?: React.ReactNode;
}

export function SettingsHeader({ title, description, children }: SettingsHeaderProps) {
    return (
        <header className="flex flex-wrap gap-4 justify-between items-end">
            <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-[0.1em] mb-1">Settings</p>
                <h2 className="text-2xl font-bold text-white">{title}</h2>
                <p className="text-sm text-slate-400 mt-1 max-w-2xl">{description}</p>
            </div>
            {children}
        </header>
    );
}

interface SaveBarProps {
    changeCount: number;
    canSave: boolean;
    saving: boolean;
    /** Why saving is not possible, used as the button's title. */
    blockedReason?: string;
    onSave: () => void;
    onDiscard: () => void;
}

export function SaveBar({ changeCount, canSave, saving, blockedReason, onSave, onDiscard }: SaveBarProps) {
    return (
        <div className="flex items-center gap-3">
            {changeCount > 0 && (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 border border-amber-500/35 text-amber-300">
                    {changeCount} unsaved {changeCount === 1 ? 'change' : 'changes'}
                </span>
            )}
            <button
                type="button"
                onClick={onDiscard}
                disabled={changeCount === 0 || saving}
                className={`${buttonSecondary} text-sm px-4 py-2`}
                title={changeCount === 0 ? 'Nothing to discard.' : 'Put every field back to the saved value.'}
            >
                Discard
            </button>
            <button
                type="button"
                onClick={onSave}
                disabled={!canSave || saving}
                title={blockedReason}
                className={buttonPrimary}
            >
                <Save className="w-4 h-4" />
                <span>{saving ? 'Saving…' : 'Save Changes'}</span>
            </button>
        </div>
    );
}

interface PanelProps {
    title: string;
    /** Small right-aligned note: the config keys behind the panel, or state. */
    meta?: React.ReactNode;
    description?: React.ReactNode;
    tone?: 'default' | 'danger' | 'accent';
    action?: React.ReactNode;
    children: React.ReactNode;
}

const panelTones: Record<'default' | 'danger' | 'accent', string> = {
    default: 'bg-slate-900/40 border-slate-800/60',
    danger: 'bg-rose-950/20 border-rose-900/50',
    accent: 'bg-slate-900/40 border-emerald-500/30',
};

export function Panel({ title, meta, description, tone = 'default', action, children }: PanelProps) {
    return (
        <section className={`border rounded-2xl p-6 backdrop-blur-sm shadow-xl ${panelTones[tone]}`}>
            <div className="flex flex-wrap justify-between items-baseline gap-4 mb-4">
                <div>
                    <h3 className={`text-base font-semibold ${tone === 'danger' ? 'text-rose-100' : 'text-white'}`}>
                        {title}
                    </h3>
                    {description && <p className="text-xs text-slate-400 mt-1.5 max-w-2xl leading-relaxed">{description}</p>}
                </div>
                {meta && <span className="text-xs text-slate-400 flex items-center gap-3 flex-wrap">{meta}</span>}
                {action}
            </div>
            {children}
        </section>
    );
}

interface FieldRowProps {
    label: React.ReactNode;
    help?: React.ReactNode;
    /** First row in a panel: no top divider. */
    first?: boolean;
    align?: 'start' | 'center';
    children: React.ReactNode;
}

export function FieldRow({ label, help, first, align = 'start', children }: FieldRowProps) {
    return (
        <div
            className={`flex flex-wrap gap-6 py-3.5 ${align === 'center' ? 'items-center' : 'items-start'} ${first ? '' : 'border-t border-slate-800/60'}`}
        >
            <div className="w-full sm:w-60 sm:shrink-0 sm:grow-0">
                <span className="block text-sm font-semibold text-slate-200">{label}</span>
                {help && <span className="block text-xs text-slate-400 mt-1 leading-relaxed">{help}</span>}
            </div>
            <div className="flex-1 min-w-0">{children}</div>
        </div>
    );
}

export function FieldError({ id, children }: { id?: string; children?: React.ReactNode }) {
    if (!children) return null;
    return (
        <p id={id} className="text-xs text-rose-400 mt-1.5">
            {children}
        </p>
    );
}

export function FieldHelp({ children }: { children?: React.ReactNode }) {
    if (!children) return null;
    return <p className="text-xs text-slate-400 mt-2 leading-relaxed">{children}</p>;
}

export function FieldWarning({ children }: { children?: React.ReactNode }) {
    if (!children) return null;
    return <p className="text-xs text-amber-300/90 mt-1.5 leading-relaxed">{children}</p>;
}

export interface ReadOnlyItem {
    label: string;
    /** null renders as "—": the service does not report this value yet. */
    value: React.ReactNode | null;
    mono?: boolean;
}

export function ReadOnlyGrid({ items }: { items: ReadOnlyItem[] }) {
    return (
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3.5">
            {items.map(item => (
                <div
                    key={item.label}
                    className="flex justify-between gap-3 pb-2.5 border-b border-slate-800/60 last:border-b-0"
                >
                    <dt className="text-xs text-slate-400">{item.label}</dt>
                    <dd
                        className={`text-sm text-right ${item.mono === false ? '' : 'font-mono'} ${item.value === null ? 'text-slate-600' : 'text-slate-200'}`}
                        title={item.value === null ? 'The service does not report this yet.' : undefined}
                    >
                        {item.value === null ? '—' : item.value}
                    </dd>
                </div>
            ))}
        </dl>
    );
}

interface SwitchProps {
    checked: boolean;
    onChange: (checked: boolean) => void;
    label: string;
    disabled?: boolean;
    title?: string;
}

export function Switch({ checked, onChange, label, disabled, title }: SwitchProps) {
    return (
        <button
            type="button"
            role="switch"
            aria-checked={checked}
            aria-label={label}
            title={title}
            disabled={disabled}
            onClick={() => onChange(!checked)}
            className={`relative w-11 h-6 rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:opacity-40 disabled:cursor-not-allowed ${checked ? 'bg-emerald-600' : 'bg-slate-700'}`}
        >
            <span
                className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${checked ? 'left-[22px]' : 'left-0.5'}`}
            />
        </button>
    );
}

interface SegmentedControlProps<T extends string> {
    options: readonly T[];
    value: T;
    onChange: (value: T) => void;
    label: string;
    disabled?: boolean;
    renderLabel?: (option: T) => string;
}

export function SegmentedControl<T extends string>({
    options,
    value,
    onChange,
    label,
    disabled,
    renderLabel,
}: SegmentedControlProps<T>) {
    return (
        <div
            role="group"
            aria-label={label}
            className="inline-flex gap-1 p-1 bg-slate-950/60 border border-slate-800 rounded-xl"
        >
            {options.map(option => (
                <button
                    key={option}
                    type="button"
                    aria-pressed={value === option}
                    disabled={disabled}
                    onClick={() => onChange(option)}
                    className={`px-4 py-1.5 rounded-lg text-xs font-bold tracking-wide transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed ${value === option ? 'bg-emerald-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}
                >
                    {renderLabel ? renderLabel(option) : option}
                </button>
            ))}
        </div>
    );
}

/**
 * Marks a control the service cannot serve yet. Every one of these sits beside
 * a disabled input, so the page never offers an action that would silently do
 * nothing.
 */
export function StubNotice({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex items-start gap-2.5 px-3.5 py-3 rounded-xl border border-amber-500/30 bg-amber-500/5">
            <Wrench className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" aria-hidden="true" />
            <p className="text-xs text-amber-200/90 leading-relaxed">{children}</p>
        </div>
    );
}

export function WarningNotice({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex items-start gap-2.5 px-3.5 py-3 rounded-xl border border-rose-900/50 bg-rose-950/25">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" aria-hidden="true" />
            <p className="text-xs text-rose-100/90 leading-relaxed">{children}</p>
        </div>
    );
}

/** The closing paragraph each page ends on, explaining what is not wired up. */
export function PageFootnote({ children }: { children: React.ReactNode }) {
    return <p className="text-xs text-slate-500 leading-relaxed max-w-3xl">{children}</p>;
}
