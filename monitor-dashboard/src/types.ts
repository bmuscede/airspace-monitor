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

export interface Config {
  flightaware_url: string;
  flightaware_api_key: string;
  cache_ttl: number;
  home_lat: number;
  home_lon: number;
  max_radar_range_nm: number;
}

export const NUMERIC_CONFIG_KEYS = [
  'cache_ttl',
  'home_lat',
  'home_lon',
  'max_radar_range_nm',
] as const;

export type NumericConfigKey = (typeof NUMERIC_CONFIG_KEYS)[number];

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
