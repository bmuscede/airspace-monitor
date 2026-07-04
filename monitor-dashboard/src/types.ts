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
