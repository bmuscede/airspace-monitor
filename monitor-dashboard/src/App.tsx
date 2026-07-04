import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import DashboardView from './views/DashboardView';
import LogsView from './views/LogsView';
import SettingsView from './views/SettingsView';
import type { Flight, SystemStatus, LogEntry, WifiNetwork } from './types';

const MOCK_FLIGHTS: Flight[] = [
  { id: 'ACA860', type: 'B789', alt: 35000, spd: 490, distance: 15, bearing: 45 },
  { id: 'WJA712', type: 'B38M', alt: 22000, spd: 380, distance: 40, bearing: 120 },
  { id: 'JZA14', type: 'Q400', alt: 8000, spd: 250, distance: 8, bearing: 280 },
];

const MOCK_LOGS: LogEntry[] = [
  { id: 1, timestamp: '12:00:01', level: 'INFO', message: 'Service started successfully.', source: 'system' },
  { id: 2, timestamp: '12:00:05', level: 'DEBUG', message: 'Initialized E-Ink display driver.', source: 'hardware' },
  { id: 3, timestamp: '12:01:12', level: 'INFO', message: 'Connected to readsb on port 30005.', source: 'decoder' },
  { id: 4, timestamp: '12:02:44', level: 'WARN', message: 'FlightAware API response delayed (450ms).', source: 'api' },
  { id: 5, timestamp: '12:05:00', level: 'ERROR', message: 'Failed to connect to I2C expander at 0x20.', source: 'hardware' },
  { id: 6, timestamp: '12:06:30', level: 'INFO', message: 'New target acquired: ACA860.', source: 'radar' },
  { id: 7, timestamp: '12:08:15', level: 'DEBUG', message: 'Flushing flight cache (TTL expired).', source: 'cache' },
];

const MOCK_WIFI_NETWORKS: WifiNetwork[] = [
  { id: '1', ssid: 'Home_Network_5G' },
  { id: '2', ssid: 'Airspace_IoT_Node' },
];

export default function AirspaceDashboard() {
  const [currentView, setCurrentView] = useState<'dashboard' | 'settings' | 'logs'>('dashboard');
  const mainRef = useRef<HTMLElement>(null);
  
  // Dashboard State
  const [flights, setFlights] = useState<Flight[]>([]);
  
  // Settings State
  const [displayMode, setDisplayMode] = useState<string>('E-Ink');
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    git: 'Idle',
    csv: 'Up to date',
    dump1090: 'Running',
    service: 'Online',
  });
  
  // Wi-Fi State
  const [wifiNetworks, setWifiNetworks] = useState<WifiNetwork[]>(MOCK_WIFI_NETWORKS);

  // Mock Config State
  const [config, setConfig] = useState({
    flightaware_url: 'https://aeroapi.flightaware.com/aeroapi',
    flightaware_api_key: 'fa_mock_key_12345',
    cache_ttl: 3600,
    home_lat: 45.4215,
    home_lon: -75.6972,
    max_radar_range_nm: 50,
  });

  // Logs State
  const [logs, setLogs] = useState<LogEntry[]>(MOCK_LOGS);
  const [logFilters, setLogFilters] = useState({
    DEBUG: true,
    INFO: true,
    WARN: true,
    ERROR: true
  });

  useEffect(() => {
    // Reset main scroll position when switching views
    if (mainRef.current) {
      mainRef.current.scrollTop = 0;
    }
  }, [currentView]);

  useEffect(() => {
    // Simulate flight movement
    setFlights(MOCK_FLIGHTS);
    const interval = setInterval(() => {
      setFlights(prev => prev.map(f => ({
        ...f,
        distance: Math.max(1, f.distance - 0.5),
        bearing: (f.bearing + 1) % 360
      })));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  // Actions
  const handleGitPull = () => {
    setSystemStatus(prev => ({ ...prev, git: 'Pulling...' }));
    setTimeout(() => setSystemStatus(prev => ({ ...prev, git: 'Updated (main)' })), 2000);
  };

  const handleCsvUpdate = () => {
    setSystemStatus(prev => ({ ...prev, csv: 'Downloading...' }));
    setTimeout(() => setSystemStatus(prev => ({ ...prev, csv: 'Up to date' })), 3000);
  };

  const handleRestartService = () => {
    setSystemStatus(prev => ({ ...prev, service: 'Restarting...' }));
    setTimeout(() => setSystemStatus(prev => ({ ...prev, service: 'Online' })), 3500);
  };

  const handleConfigChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setConfig(prev => ({ ...prev, [name]: value }));
  };

  const handleSaveConfig = () => {
    const newLog: LogEntry = {
      id: logs.length + 1,
      timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
      level: 'INFO',
      message: 'Configuration saved successfully.',
      source: 'system'
    };
    setLogs(prev => [...prev, newLog]);
  };

  const handleAddWifiNetwork = (ssid: string, _password: string) => {
    const newNetwork: WifiNetwork = {
      id: Date.now().toString(),
      ssid
    };
    setWifiNetworks(prev => [...prev, newNetwork]);
    const newLog: LogEntry = {
      id: logs.length + 1,
      timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
      level: 'INFO',
      message: `Added Wi-Fi network '${ssid}' to wpa_supplicant.`,
      source: 'network'
    };
    setLogs(prev => [...prev, newLog]);
  };

  const handleRemoveWifiNetwork = (id: string) => {
    const target = wifiNetworks.find(n => n.id === id);
    setWifiNetworks(prev => prev.filter(n => n.id !== id));
    if (target) {
      const newLog: LogEntry = {
        id: logs.length + 1,
        timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
        level: 'INFO',
        message: `Removed Wi-Fi network '${target.ssid}' from wpa_supplicant.`,
        source: 'network'
      };
      setLogs(prev => [...prev, newLog]);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-200 font-sans selection:bg-emerald-500/30 overflow-hidden relative selection:text-white">
      {/* Dynamic Background */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-emerald-600/10 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none"></div>

      <Sidebar 
        currentView={currentView} 
        setCurrentView={setCurrentView} 
        systemStatus={systemStatus} 
      />

      <main ref={mainRef} className="flex-1 p-8 overflow-y-auto relative z-10 custom-scrollbar">
        {currentView === 'dashboard' && (
          <DashboardView flights={flights} maxRadarRange={config.max_radar_range_nm} />
        )}
        {currentView === 'logs' && (
          <LogsView logs={logs} logFilters={logFilters} setLogFilters={setLogFilters} />
        )}
        {currentView === 'settings' && (
          <SettingsView 
            config={config} 
            handleConfigChange={handleConfigChange} 
            handleSaveConfig={handleSaveConfig} 
            displayMode={displayMode} 
            setDisplayMode={setDisplayMode} 
            systemStatus={systemStatus} 
            handleGitPull={handleGitPull} 
            handleCsvUpdate={handleCsvUpdate} 
            handleRestartService={handleRestartService} 
            wifiNetworks={wifiNetworks}
            onAddWifiNetwork={handleAddWifiNetwork}
            onRemoveWifiNetwork={handleRemoveWifiNetwork}
          />
        )}
      </main>
    </div>
  );
}