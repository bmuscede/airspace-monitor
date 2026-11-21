import { useCallback, useEffect, useRef, useState } from 'react';
import Sidebar from './components/Sidebar';
import ConfigGate from './components/settings/ConfigGate';
import DashboardView from './views/DashboardView';
import LogsView from './views/LogsView';
import BackendSettings from './views/settings/BackendSettings';
import SplitFlapSettings from './views/settings/SplitFlapSettings';
import NetworkSettings from './views/settings/NetworkSettings';
import SystemSettings from './views/settings/SystemSettings';
import { ApiError, assertStatus, deleteJson, getJson, isAbortError, postJson } from './lib/api';
import { SPLITFLAP_PATHS } from './lib/splitflap';
import { errorReport, useErrorDialog } from './lib/errorDialog';
import { useSettings } from './lib/useSettings';
import { useToast } from './lib/toast';
import type { Flight, LogEntry, SystemStatus, View, WifiNetwork } from './types';

/** How long the aircraft-DB row keeps saying "Updating…" (see handleCsvUpdate). */
const CSV_UPDATE_HOLD_MS = 5000;

function toWifiNetworks(data: unknown): WifiNetwork[] | null {
  if (!Array.isArray(data)) return null;
  return data
    .filter((n): n is { ssid: string } => !!n && typeof n === 'object' && typeof (n as { ssid?: unknown }).ssid === 'string')
    .map(n => ({ id: n.ssid, ssid: n.ssid }));
}

/** Reads the saved networks, or throws something the error modal can show. */
async function fetchWifiNetworks(signal?: AbortSignal): Promise<WifiNetwork[]> {
  const data = await getJson<unknown>('/api/wifi', { signal });
  const networks = toWifiNetworks(data);
  if (!networks) {
    throw new ApiError('The service returned a Wi-Fi list the dashboard could not read.', {
      detail: JSON.stringify(data),
    });
  }
  return networks;
}

export default function AirspaceDashboard() {
  const [currentView, setCurrentView] = useState<View>('dashboard');
  const mainRef = useRef<HTMLElement>(null);

  const { showToast } = useToast();
  const { showError } = useErrorDialog();

  // Everything that lives in config.json, shared by the Backend and
  // Split-Flap pages.
  const settings = useSettings();

  // Dashboard State
  const [flights, setFlights] = useState<Flight[]>([]);
  const [selectedHex, setSelectedHex] = useState<string | null>(null);

  // Hardware + service State
  const [displayMode, setDisplayMode] = useState<string>('E-Ink');
  const [switchingMode, setSwitchingMode] = useState(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    git: 'Idle',
    csv: 'Up to date',
    dump1090: 'Checking...',
    service: 'Checking...',
  });

  // Wi-Fi State
  const [wifiNetworks, setWifiNetworks] = useState<WifiNetwork[]>([]);
  const [wifiLoading, setWifiLoading] = useState(true);
  const [wifiFailed, setWifiFailed] = useState(false);
  const [wifiBusy, setWifiBusy] = useState(false);

  // History State — only the count, for the retention and System panels.
  const [historyContactCount, setHistoryContactCount] = useState<number | null>(null);

  // Logs State
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logFilters, setLogFilters] = useState({
    DEBUG: true,
    INFO: true,
    WARN: true,
    ERROR: true
  });

  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  useEffect(() => {
    // Reset main scroll position when switching views
    if (mainRef.current) {
      mainRef.current.scrollTop = 0;
    }
  }, [currentView]);

  /** Re-reads the saved networks for a refresh, or after an add or remove. */
  const loadWifi = useCallback(async () => {
    setWifiLoading(true);
    try {
      setWifiNetworks(await fetchWifiNetworks());
      setWifiFailed(false);
    } catch (err) {
      if (isAbortError(err)) return;
      setWifiFailed(true);
      showError(errorReport('Wi-Fi networks could not be read', err));
    } finally {
      setWifiLoading(false);
    }
  }, [showError]);

  // Initial Load. The failure is reported inline on the Network page rather
  // than as a modal: this runs at startup, on whatever view was opened, so a
  // modal here would be about a page nobody has asked for yet.
  useEffect(() => {
    const controller = new AbortController();

    const read = async () => {
      try {
        setWifiNetworks(await fetchWifiNetworks(controller.signal));
        setWifiFailed(false);
      } catch (err) {
        if (isAbortError(err)) return;
        console.error(err);
        setWifiFailed(true);
      } finally {
        if (!controller.signal.aborted) setWifiLoading(false);
      }
    };

    void read();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    // Ambient information rather than an action: a failure leaves the panels
    // showing "—" instead of raising anything.
    getJson<{ contact_count?: unknown }>('/api/history/stats?range=all', { signal: controller.signal })
      .then(data => {
        const count = Number(data?.contact_count);
        setHistoryContactCount(Number.isFinite(count) ? count : null);
      })
      .catch(err => {
        if (isAbortError(err)) return;
        console.error(err);
        setHistoryContactCount(null);
      });

    return () => controller.abort();
  }, []);

  // Polling logic
  useEffect(() => {
    // TODO: See about not hardcoding these intervals.
    const controller = new AbortController();

    const fetchFlights = async () => {
      try {
        const data = await getJson<unknown>('/api/flights', { signal: controller.signal });
        // TODO: For now, a jump is acceptable. We can smoothly interpret it over time based on the heading eventually.
        if (!Array.isArray(data)) {
          console.warn('Ignoring malformed /api/flights payload; keeping last known targets.');
          return;
        }
        setFlights(data);
      } catch (err) {
        // Polling failures stay in the console: the sidebar pill is the signal
        // for a service that has gone quiet, and a modal every two seconds
        // would bury the page.
        if (!isAbortError(err)) console.error(err);
      }
    };

    const fetchState = async () => {
      try {
        const data = await getJson<Record<string, unknown>>('/api/state', { signal: controller.signal });

        if (!data || typeof data !== 'object' || Array.isArray(data)) {
          console.warn('Ignoring malformed /api/state payload; keeping last known status.');
          return;
        }

        setDisplayMode(typeof data.displayMode === 'string' && data.displayMode ? data.displayMode : 'E-Ink');
        setSystemStatus(prev => ({
          ...prev,
          dump1090: data.readsbConnected ? 'Connected' : 'Disconnected',
          service: data.systemRunning ? 'Online' : 'Offline'
        }));
      } catch (err) {
        if (isAbortError(err)) return;
        console.error(err);
        // A service that cannot be reached is offline as far as anyone looking
        // at this screen is concerned; leaving the pill on its last good value
        // is the one lie the shell can tell. Only written when it changes, so
        // an unreachable service does not re-render every two seconds.
        setSystemStatus(prev =>
          prev.service === 'Offline' && prev.dump1090 === 'Unknown'
            ? prev
            : { ...prev, service: 'Offline', dump1090: 'Unknown' }
        );
      }
    };

    const fetchLogs = async () => {
      try {
        const data = await getJson<unknown>('/api/logs', { signal: controller.signal });

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
      const data = await postJson<{ status?: string; output?: string }>('/api/git-pull');
      if (data?.status !== 'success') {
        // git itself failed, and its stderr is the only useful thing to show.
        throw new ApiError('The service could not pull the latest code.', { detail: data?.output });
      }
      setSystemStatus(prev => ({ ...prev, git: 'Updated (main)' }));
      showToast('Codebase updated');
    } catch (err) {
      setSystemStatus(prev => ({ ...prev, git: 'Error' }));
      showError(errorReport('Codebase not updated', err));
    }
  };

  const handleCsvUpdate = async () => {
    setSystemStatus(prev => ({ ...prev, csv: 'Updating...' }));
    try {
      const data = await postJson<{ status?: string }>('/api/update-db');
      assertStatus(data, ['started', 'already_updating'], 'The service did not start the database update.');
      showToast(
        data?.status === 'already_updating'
          ? 'Aircraft DB update already running'
          : 'Aircraft DB update started'
      );

      // TODO: Track CSV update completion properly since the backend doesn't broadcast progress. Mocking sleep for now.
      timers.current.push(
        setTimeout(() => setSystemStatus(prev => ({ ...prev, csv: 'Up to date' })), CSV_UPDATE_HOLD_MS)
      );
    } catch (err) {
      setSystemStatus(prev => ({ ...prev, csv: 'Error' }));
      showError(errorReport('Aircraft DB not updated', err));
    }
  };

  const handleRestartService = async () => {
    setSystemStatus(prev => ({ ...prev, service: 'Restarting...' }));
    try {
      const data = await postJson<{ status?: string }>('/api/restart-service');
      assertStatus(data, ['success'], 'The service refused to restart.');
      showToast('Services restarting');
    } catch (err) {
      showError(errorReport('Services not restarted', err));
    }
  };

  const handleShutdown = async () => {
    try {
      const data = await postJson<{ status?: string }>('/api/shutdown');
      assertStatus(data, ['shutting_down'], 'The service did not confirm the shutdown.');
      // The call blocks until open contacts are flushed, so by the time this
      // resolves the hardware loop really has stopped. Polling will confirm it.
      setSystemStatus(prev => ({ ...prev, service: 'Offline' }));
      showToast('Monitor service shutting down');
    } catch (err) {
      showError(errorReport('Service not shut down', err));
    }
  };

  const setRemoteDisplayMode = async (mode: string) => {
    if (mode === displayMode) return;
    setSwitchingMode(true);
    try {
      // The backend currently blind-toggles and ignores the body, but the
      // request should still say which mode was asked for.
      const data = await postJson<{ mode?: unknown }>('/api/mode', { mode });
      if (typeof data?.mode !== 'string') {
        throw new ApiError('The service did not say which display it switched to.', {
          detail: JSON.stringify(data),
        });
      }
      setDisplayMode(data.mode);
      showToast(`Hardware output set to ${data.mode}`);
    } catch (err) {
      showError(errorReport('Hardware output not changed', err));
    } finally {
      setSwitchingMode(false);
    }
  };

  const handleAddWifiNetwork = async (ssid: string, password: string): Promise<boolean> => {
    setWifiBusy(true);
    try {
      const data = await postJson<{ status?: string }>('/api/wifi', { ssid, password });
      assertStatus(data, ['added'], `The service could not add ${ssid}.`);
      showToast(`${ssid} added`);
      await loadWifi();
      return true;
    } catch (err) {
      showError(errorReport('Network not added', err));
      return false;
    } finally {
      setWifiBusy(false);
    }
  };

  const handleRemoveWifiNetwork = async (ssid: string): Promise<boolean> => {
    setWifiBusy(true);
    try {
      const data = await deleteJson<{ status?: string }>(`/api/wifi/${encodeURIComponent(ssid)}`);
      assertStatus(data, ['removed'], `The service could not remove ${ssid}.`);
      showToast(`${ssid} forgotten`);
      await loadWifi();
      return true;
    } catch (err) {
      showError(errorReport('Network not removed', err));
      return false;
    } finally {
      setWifiBusy(false);
    }
  };

  const handleForgetCalibration = () => {
    void settings.writeKeys(
      { [SPLITFLAP_PATHS.calibrated]: false, [SPLITFLAP_PATHS.calibratedAt]: 0 },
      { success: 'Calibration forgotten', failure: 'Calibration not forgotten' }
    );
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
            /* The saved value, not the form's: an unsaved edit on the Backend
               page must not redraw the scope. */
            maxRadarRange={settings.savedConfig.max_radar_range_nm}
            selectedHex={selectedHex}
            onSelectTarget={setSelectedHex}
          />
        )}
        {currentView === 'logs' && (
          <LogsView logs={logs} logFilters={logFilters} setLogFilters={setLogFilters} />
        )}
        {currentView === 'history' && (
          /* TODO: This is a stub comment. The History view is not built yet; the
             drawer keeps its destination disabled, so this is only a backstop. */
          <div className="max-w-xl bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white mb-2">History is not built yet</h2>
            <p className="text-sm text-slate-400">
              The service already serves <span className="font-mono">/api/history/contacts</span> and{' '}
              <span className="font-mono">/api/history/stats</span>, but this view has not been implemented.
            </p>
          </div>
        )}
        {currentView === 'settings.backend' && (
          <ConfigGate
            loaded={settings.loaded}
            loading={settings.loading}
            failed={settings.loadFailed}
            onRetry={settings.reload}
          >
            <BackendSettings
              config={settings.config}
              savedConfig={settings.savedConfig}
              setConfigField={settings.setConfigField}
              onDiscard={settings.discardConfig}
              onSave={settings.saveConfig}
              saving={settings.savingConfig}
              historyContactCount={historyContactCount}
            />
          </ConfigGate>
        )}
        {currentView === 'settings.splitflap' && (
          <ConfigGate
            loaded={settings.loaded}
            loading={settings.loading}
            failed={settings.loadFailed}
            onRetry={settings.reload}
          >
            <SplitFlapSettings
              splitFlap={settings.splitFlap}
              savedSplitFlap={settings.savedSplitFlap}
              onChange={settings.updateSplitFlap}
              onDiscard={settings.discardSplitFlap}
              onSave={settings.saveSplitFlap}
              saving={settings.savingSplitFlap}
              onForgetCalibration={handleForgetCalibration}
            />
          </ConfigGate>
        )}
        {currentView === 'settings.network' && (
          <NetworkSettings
            networks={wifiNetworks}
            loading={wifiLoading}
            failed={wifiFailed}
            busy={wifiBusy}
            onReload={() => void loadWifi()}
            onAdd={handleAddWifiNetwork}
            onRemove={handleRemoveWifiNetwork}
          />
        )}
        {currentView === 'settings.system' && (
          <SystemSettings
            systemStatus={systemStatus}
            displayMode={displayMode}
            onSetDisplayMode={mode => void setRemoteDisplayMode(mode)}
            switchingMode={switchingMode}
            onGitPull={() => void handleGitPull()}
            onCsvUpdate={() => void handleCsvUpdate()}
            onRestart={() => void handleRestartService()}
            onShutdown={() => void handleShutdown()}
            historyContactCount={historyContactCount}
          />
        )}
      </main>
    </div>
  );
}
