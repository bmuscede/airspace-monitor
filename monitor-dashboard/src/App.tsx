import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import DashboardView from './views/DashboardView';
import LogsView from './views/LogsView';
import SettingsView from './views/SettingsView';
import type { Flight, SystemStatus, LogEntry, WifiNetwork } from './types';

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
    dump1090: 'Checking...',
    service: 'Checking...',
  });
  
  // Wi-Fi State
  const [wifiNetworks, setWifiNetworks] = useState<WifiNetwork[]>([]);

  // Config State
  const [config, setConfig] = useState({
    flightaware_url: '',
    flightaware_api_key: '',
    cache_ttl: 3600,
    home_lat: 0.0,
    home_lon: 0.0,
    max_radar_range_nm: 50,
  });

  // Logs State
  const [logs, setLogs] = useState<LogEntry[]>([]);
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

  // Initial Load
  useEffect(() => {
    fetch('/api/config')
      .then(res => res.json())
      .then(data => {
        if (data && typeof data === 'object') {
          setConfig(prev => ({ ...prev, ...data }));
        }
      })
      .catch(console.error);

    fetch('/api/wifi')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setWifiNetworks(data.map((n: any) => ({ id: n.ssid, ssid: n.ssid })));
        }
      })
      .catch(console.error);
  }, []);

  // Polling logic
  useEffect(() => {
    // TODO: See about not hardcoding these intervals.

    const fetchFlights = async () => {
      try {
        const res = await fetch('/api/flights');
        const data = await res.json();
        // TODO: For now, a jump is acceptable. We can smoothly interpret it over time based on the heading eventually.
        setFlights(data);
      } catch (err) {
        console.error(err);
      }
    };

    const fetchState = async () => {
      try {
        const res = await fetch('/api/state');
        const data = await res.json();
        
        setDisplayMode(data.displayMode || 'E-Ink');
        setSystemStatus(prev => ({
          ...prev,
          dump1090: data.readsbConnected ? 'Connected' : 'Disconnected',
          service: data.systemRunning ? 'Online' : 'Offline'
        }));
      } catch (err) {
        console.error(err);
      }
    };

    const fetchLogs = async () => {
      try {
        const res = await fetch('/api/logs');
        const data = await res.json();
        setLogs(data);
      } catch (err) {
        console.error(err);
      }
    };

    // Initial fetch
    fetchFlights();
    fetchState();
    fetchLogs();

    // Set up polling intervals
    const flightInterval = setInterval(() => {
      fetchFlights();
      fetchState();
    }, 2000);

    const logInterval = setInterval(fetchLogs, 3000);

    return () => {
      clearInterval(flightInterval);
      clearInterval(logInterval);
    };
  }, []);

  // Actions
  const handleGitPull = async () => {
    setSystemStatus(prev => ({ ...prev, git: 'Pulling...' }));
    try {
      const res = await fetch('/api/git-pull', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        setSystemStatus(prev => ({ ...prev, git: 'Updated (main)' }));
      } else {
        setSystemStatus(prev => ({ ...prev, git: 'Error' }));
      }
    } catch (err) {
      setSystemStatus(prev => ({ ...prev, git: 'Error' }));
    }
  };

  const handleCsvUpdate = async () => {
    setSystemStatus(prev => ({ ...prev, csv: 'Updating...' }));
    try {
      await fetch('/api/update-db', { method: 'POST' });
      // TODO: Track CSV update completion properly since the backend doesn't broadcast progress. Mocking sleep for now.
      setTimeout(() => setSystemStatus(prev => ({ ...prev, csv: 'Up to date' })), 5000);
    } catch (err) {
      setSystemStatus(prev => ({ ...prev, csv: 'Error' }));
    }
  };

  const handleRestartService = async () => {
    setSystemStatus(prev => ({ ...prev, service: 'Restarting...' }));
    try {
      await fetch('/api/restart-service', { method: 'POST' });
    } catch (err) {
      console.error(err);
    }
  };

  const handleConfigChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setConfig(prev => ({ ...prev, [name]: value }));
  };

  const handleSaveConfig = async () => {
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
    } catch (err) {
      console.error(err);
    }
  };

  const setRemoteDisplayMode = async (mode: string) => {
    if (mode === displayMode) return;
    try {
      const res = await fetch('/api/mode', { method: 'POST' });
      const data = await res.json();
      setDisplayMode(data.mode);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddWifiNetwork = async (ssid: string, password: string) => {
    try {
      const res = await fetch('/api/wifi', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ssid, password })
      });
      if (res.ok) {
        const networksRes = await fetch('/api/wifi');
        const data = await networksRes.json();
        if (Array.isArray(data)) {
          setWifiNetworks(data.map((n: any) => ({ id: n.ssid, ssid: n.ssid })));
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleRemoveWifiNetwork = async (id: string) => {
    const target = wifiNetworks.find(n => n.id === id);
    if (!target) return;
    
    try {
      const res = await fetch(`/api/wifi/${target.ssid}`, { method: 'DELETE' });
      if (res.ok) {
        const networksRes = await fetch('/api/wifi');
        const data = await networksRes.json();
        if (Array.isArray(data)) {
          setWifiNetworks(data.map((n: any) => ({ id: n.ssid, ssid: n.ssid })));
        }
      }
    } catch (err) {
      console.error(err);
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
            setDisplayMode={setRemoteDisplayMode} 
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