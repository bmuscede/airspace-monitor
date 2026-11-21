export interface Flight {
  hex: string;
  flight: string;
  altitude: number;
  speed: number;
  heading: number;
  lat: number;
  lon: number;
  distance: number;
  bearing: number;
  origin: string;
  destination: string;
  type: string;
  reg: string;
}

/**
 * Every destination in the drawer. `currentView` is still React state rather
 * than a route, so these strings are the whole navigation model: the settings
 * sections are spelled out here so the drawer can keep its sub-nav open and
 * the shell can tell a settings page from a top-level one.
 */
export type View =
  | 'dashboard'
  | 'history'
  | 'logs'
  | 'settings.backend'
  | 'settings.splitflap'
  | 'settings.network'
  | 'settings.system';

export const SETTINGS_VIEWS = [
  'settings.backend',
  'settings.splitflap',
  'settings.network',
  'settings.system',
] as const;

export type SettingsView = (typeof SETTINGS_VIEWS)[number];

/** The settings section the drawer lands on when Settings itself is clicked. */
export const DEFAULT_SETTINGS_VIEW: SettingsView = 'settings.backend';

export function isSettingsView(view: View): view is SettingsView {
  return (SETTINGS_VIEWS as readonly string[]).includes(view);
}

export type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

export const LOG_LEVELS: readonly LogLevel[] = ['DEBUG', 'INFO', 'WARN', 'ERROR'];

export function isLogLevel(value: unknown): value is LogLevel {
  return typeof value === 'string' && (LOG_LEVELS as readonly string[]).includes(value);
}

/**
 * The Backend page as a flat form. Field names are the validation keys and the
 * input names; `CONFIG_PATHS` in lib/config.ts is the only place that knows
 * where each one lives in the service's nested config.
 */
export interface Config {
  home_lat: number;
  home_lon: number;
  max_radar_range_nm: number;
  flightaware_url: string;
  flightaware_api_key: string;
  flightaware_cache_ttl: number;
  openweathermap_url: string;
  openweathermap_api_key: string;
  openweathermap_cache_ttl: number;
  history_contact_gap_seconds: number;
  history_flush_seconds: number;
  history_retention_days: number;
  log_level: LogLevel;
}

export const NUMERIC_CONFIG_KEYS = [
  'home_lat',
  'home_lon',
  'max_radar_range_nm',
  'flightaware_cache_ttl',
  'openweathermap_cache_ttl',
  'history_contact_gap_seconds',
  'history_flush_seconds',
  'history_retention_days',
] as const;

export type NumericConfigKey = (typeof NUMERIC_CONFIG_KEYS)[number];

export const TEXT_CONFIG_KEYS = [
  'flightaware_url',
  'flightaware_api_key',
  'openweathermap_url',
  'openweathermap_api_key',
] as const;

export type TextConfigKey = (typeof TEXT_CONFIG_KEYS)[number];

/** One flap: the character set on its spool, and the channel it is wired to. */
export interface FlapModule {
  channel: number;
  charset: string;
}

/**
 * One character set. `flaps` is in spool order — index 0 is the home flap —
 * and each entry is one flap, so a multi-character entry is a symbol flap
 * (`ACA`), not three letters.
 */
export interface FlapCharset {
  name: string;
  flaps: string[];
  /** The flap shown for text this set does not carry. Read-only for now. */
  fallback: string | null;
}

export interface AutoRehomeConfig {
  enabled: boolean;
  maxAttempts: number;
  windowSeconds: number;
  backoffSeconds: number;
}

export interface CalibrationState {
  calibrated: boolean;
  calibratedAt: number;
}

/** The Split-Flap page as a form. Mirrors the `splitflap` config section. */
export interface SplitFlapConfig {
  enabled: boolean;
  /** Empty means auto-detect, which is the service's default. */
  port: string;
  /** Flaps per row, top to bottom. Always sums to `modules.length`. */
  rows: number[];
  /** Flap order: row 1 left to right, then row 2, and so on. */
  modules: FlapModule[];
  charsets: FlapCharset[];
  autoRehome: AutoRehomeConfig;
  calibration: CalibrationState;
}

export interface SystemStatus {
  git: string;
  csv: string;
  dump1090: string;
  service: string;
}

export interface LogEntry {
  id: number;
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';
  message: string;
  source: string;
}

export interface WifiNetwork {
  id: string;
  ssid: string;
}
