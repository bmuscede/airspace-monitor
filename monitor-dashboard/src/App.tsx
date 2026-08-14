import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import DashboardView from './views/DashboardView';
import LogsView from './views/LogsView';
import SettingsView from './views/SettingsView';
import { DEFAULT_CONFIG, isNumericConfigKey, normalizeConfig } from './lib/config';
import { useToast } from './lib/toast';
import type { Config, Flight, SystemStatus, LogEntry, WifiNetwork } from './types';

/** Aborted requests are expected on unmount — they are not failures. */
function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}

function toWifiNetworks(data: unknown): WifiNetwork[] | null {
  if (!Array.isArray(data)) return null;
  return data
    .filter((n): n is { ssid: string } => !!n && typeof n === 'object' && typeof (n as { ssid?: unknown }).ssid === 'string')
    .map(n => ({ id: n.ssid, ssid: n.ssid }));
}

export default function AirspaceDashboard() {
  const [currentView, setCurrentView] = useState<'dashboard' | 'settings' | 'logs'>('dashboard');
  const mainRef = useRef<HTMLElement>(null);

  const { showToast } = useToast();

  // Dashboard State
  const [flights, setFlights] = useState<Flight[]>([]);
  const [selectedHex, setSelectedHex] = useState<string | null>(null);

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
  const [config, setConfig] = useState<Config>(DEFAULT_CONFIG);
  const [savedConfig, setSavedConfig] = useState<Config>(DEFAULT_CONFIG);

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
    const controller = new AbortController();

    fetch('/api/config', { signal: controller.signal })
      .then(res => res.json())
      .then(data => {
        const loaded = normalizeConfig(data, DEFAULT_CONFIG);
        setConfig(loaded);
        setSavedConfig(loaded);
      })
      .catch(err => {
        if (!isAbortError(err)) console.error(err);
      });

    fetch('/api/wifi', { signal: controller.signal })
      .then(res => res.json())
      .then(data => {
        const networks = toWifiNetworks(data);
        if (networks) setWifiNetworks(networks);
      })
      .catch(err => {
        if (!isAbortError(err)) console.error(err);
      });

    return () => controller.abort();
  }, []);

  // Polling logic
  useEffect(() => {
    // TODO: See about not hardcoding these intervals.
    const controller = new AbortController();

    const fetchFlights = async () => {
      try {
        const res = await fetch('/api/flights', { signal: controller.signal });
        const data = await res.json();
        // TODO: For now, a jump is acceptable. We can smoothly interpret it over time based on the heading eventually.
        if (!Array.isArray(data)) {
          console.warn('Ignoring malformed /api/flights payload; keeping last known targets.');
          return;
        }
        setFlights(data);
      } catch (err) {
        if (!isAbortError(err)) console.error(err);
      }
    };

    const fetchState = async () => {
      try {
        const res = await fetch('/api/state', { signal: controller.signal });
        const data = await res.json();

        if (!data || typeof data !== 'object' || Array.isArray(data)) {
          console.warn('Ignoring malformed /api/state payload; keeping last known status.');
          return;
        }

        setDisplayMode(data.displayMode || 'E-Ink');
        setSystemStatus(prev => ({
          ...prev,
          dump1090: data.readsbConnected ? 'Connected' : 'Disconnected',
          service: data.systemRunning ? 'Online' : 'Offline'
        }));
      } catch (err) {
        if (!isAbortError(err)) console.error(err);
      }
    };

    const fetchLogs = async () => {
      try {
        const res = await fetch('/api/logs', { signal: controller.signal });
        const data = await res.json();

        if (!Array.isArray(data)) {
          console.warn('Ignoring malformed /api/logs payload; keeping last known entries.');
          return;
        }

        setLogs(data);
      } catch (err) {
        if (!isAbortError(err)) console.error(err);
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
      controller.abort();
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
        showToast('Codebase updated');
      } else {
        setSystemStatus(prev => ({ ...prev, git: 'Error' }));
        showToast('Codebase not updated', 'error');
      }
    } catch (err) {
      console.error(err);
      setSystemStatus(prev => ({ ...prev, git: 'Error' }));
      showToast('Codebase not updated', 'error');
    }
  };

  const handleCsvUpdate = async () => {
    setSystemStatus(prev => ({ ...prev, csv: 'Updating...' }));
    try {
      const res = await fetch('/api/update-db', { method: 'POST' });
      const data = await res.json();
      showToast(
        data.status === 'already_updating'
          ? 'Aircraft DB update already running'
          : 'Aircraft DB update started'
      );

      // TODO: Track CSV update completion properly since the backend doesn't broadcast progress. Mocking sleep for now.
      setTimeout(() => setSystemStatus(prev => ({ ...prev, csv: 'Up to date' })), 5000);
    } catch (err) {
      console.error(err);
      setSystemStatus(prev => ({ ...prev, csv: 'Error' }));
      showToast('Aircraft DB not updated', 'error');
    }
  };

  const handleRestartService = async () => {
    setSystemStatus(prev => ({ ...prev, service: 'Restarting...' }));
    try {
      const res = await fetch('/api/restart-service', { method: 'POST' });
      const data = await res.json();
      if (!res.ok || data.status !== 'success') throw new Error('Service restart rejected.');
      showToast('Services restarting');
    } catch (err) {
      console.error(err);
      showToast('Services not restarted', 'error');
    }
  };

  const handleConfigChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setConfig(prev => {
      const next: Config = { ...prev };
      if (isNumericConfigKey(name)) {
        // An empty field is held as NaN so validation can flag it rather than
        // silently POSTing a zero.
        next[name] = value === '' ? Number.NaN : Number(value);
      } else if (name === 'flightaware_url' || name === 'flightaware_api_key') {
        next[name] = value;
      }
      return next;
    });
  };

  const handleSaveConfig = async () => {
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      const data = await res.json();
      if (!res.ok || data.status === 'error') throw new Error('Config save rejected.');
      setSavedConfig(config);
      showToast('Changes saved');
    } catch (err) {
      console.error(err);
      showToast('Changes not saved', 'error');
    }
  };

  const setRemoteDisplayMode = async (mode: string) => {
    if (mode === displayMode) return;
    try {
      // The backend currently blind-toggles and ignores the body, but the
      // request should still say which mode was asked for.
      const res = await fetch('/api/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      });
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
        const networks = toWifiNetworks(await networksRes.json());
        if (networks) setWifiNetworks(networks);
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
        const networks = toWifiNetworks(await networksRes.json());
        if (networks) setWifiNetworks(networks);
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
          <DashboardView
            flights={flights}
            maxRadarRange={config.max_radar_range_nm}
            selectedHex={selectedHex}
            onSelectTarget={setSelectedHex}
          />
        )}
        {currentView === 'logs' && (
          <LogsView logs={logs} logFilters={logFilters} setLogFilters={setLogFilters} />
        )}
        {currentView === 'settings' && (
          <SettingsView
            config={config}
            savedConfig={savedConfig}
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