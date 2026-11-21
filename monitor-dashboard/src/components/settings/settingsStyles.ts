/**
 * The class strings and tiny helpers the settings pages share.
 *
 * Kept out of SettingsPrimitives.tsx so that file exports components only —
 * mixing the two breaks fast refresh for every page that imports it.
 */

/**
 * No width of its own: a `w-full` here would beat the `w-32` a caller adds,
 * since the two utilities have equal specificity and the cascade, not the
 * order of the class string, decides. Every field states its own width.
 */
export const inputBase =
    'bg-slate-950 border rounded-lg px-3 py-2 text-sm text-slate-200 font-mono focus:outline-none focus:ring-1 transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
export const inputValid = 'border-slate-800 focus:border-emerald-500 focus:ring-emerald-500';
export const inputInvalid = 'border-rose-700 focus:border-rose-500 focus:ring-rose-500';

export function inputClasses(invalid?: boolean): string {
    return `${inputBase} ${invalid ? inputInvalid : inputValid}`;
}

export const buttonBase =
    'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:opacity-40 disabled:cursor-not-allowed';
export const buttonSecondary = `${buttonBase} px-3.5 py-2 text-xs text-slate-300 bg-slate-800/60 border border-slate-700 hover:bg-slate-700/60 focus-visible:ring-slate-400`;
export const buttonPrimary = `${buttonBase} px-4 py-2 text-sm text-white bg-emerald-600 hover:bg-emerald-500 shadow-lg shadow-emerald-500/20 focus-visible:ring-emerald-400`;
export const buttonDanger = `${buttonBase} px-3.5 py-2 text-sm text-white bg-rose-600/90 hover:bg-rose-500 focus-visible:ring-rose-400`;
export const buttonGhostDanger = `${buttonBase} px-3.5 py-2 text-sm text-rose-300 bg-transparent border border-rose-900/60 hover:bg-rose-950/40 focus-visible:ring-rose-400`;

/** Number inputs hold NaN while empty; render that as a blank field. */
export function numberValue(value: number): number | string {
    return Number.isFinite(value) ? value : '';
}
