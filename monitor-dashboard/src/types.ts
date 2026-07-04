export interface Flight {
  id: string;
  type: string;
  alt: number;
  spd: number;
  distance: number;
  bearing: number;
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
