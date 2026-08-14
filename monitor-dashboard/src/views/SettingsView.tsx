import { useState } from 'react';
import { Settings, HardDrive, Wifi, Power, GitPullRequest, ChevronRight, Download, RefreshCw, Save, Plus, Trash2 } from 'lucide-react';
import ConfirmDialog from '../components/ConfirmDialog';
import { isConfigDirty, validateConfig } from '../lib/config';
import type { Config, SystemStatus, WifiNetwork } from '../types';

interface SettingsViewProps {
  config: Config;
  savedConfig: Config;
  handleConfigChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleSaveConfig: () => void;
  displayMode: string;
  setDisplayMode: (mode: string) => void;
  systemStatus: SystemStatus;
  handleGitPull: () => void;
  handleCsvUpdate: () => void;
  handleRestartService: () => void;
  wifiNetworks: WifiNetwork[];
  onAddWifiNetwork: (ssid: string, password: string) => void;
  onRemoveWifiNetwork: (id: string) => void;
}

const inputClasses =
  'w-full bg-slate-950 border rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:ring-1 transition-all';
const validInputClasses = 'border-slate-800 focus:border-emerald-500 focus:ring-emerald-500';
const invalidInputClasses = 'border-rose-700 focus:border-rose-500 focus:ring-rose-500';

/** Number inputs hold NaN while empty; render that as a blank field. */
function numberValue(value: number): number | string {
  return Number.isFinite(value) ? value : '';
}

export default function SettingsView({
  config,
  savedConfig,
  handleConfigChange,
  handleSaveConfig,
  displayMode,
  setDisplayMode,
  systemStatus,
  handleGitPull,
  handleCsvUpdate,
  handleRestartService,
  wifiNetworks,
  onAddWifiNetwork,
  onRemoveWifiNetwork
}: SettingsViewProps) {
  const [newSsid, setNewSsid] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmRestart, setConfirmRestart] = useState(false);

  const errors = validateConfig(config);
  const hasErrors = Object.keys(errors).length > 0;
  const isDirty = isConfigDirty(config, savedConfig);
  const canSave = isDirty && !hasErrors;

  const handleAddNetworkSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSsid.trim()) return;
    onAddWifiNetwork(newSsid.trim(), newPassword);
    setNewSsid('');
    setNewPassword('');
  };

  const fieldClasses = (field: keyof Config) =>
    `${inputClasses} ${errors[field] ? invalidInputClasses : validInputClasses}`;

  const fieldError = (field: keyof Config) =>
    errors[field] ? (
      <p id={`${field}-error`} className="text-xs text-rose-400 mt-1.5">{errors[field]}</p>
    ) : null;

  return (
    <div className="space-y-8 pb-10 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl">
      <header className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-white">System Settings</h2>
          <p className="text-slate-400 text-sm">Configure hardware, backend services, and application preferences.</p>
        </div>
        <button
          onClick={handleSaveConfig}
          disabled={!canSave}
          title={hasErrors ? 'Fix the highlighted fields first.' : isDirty ? undefined : 'No unsaved changes.'}
          className="flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-emerald-600 text-white px-4 py-2 rounded-lg transition-colors shadow-lg shadow-emerald-500/20 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
        >
          <Save className="w-4 h-4" />
          <span>Save Changes</span>
        </button>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Service Config */}
        <div className="bg-slate-900/40 border border-slate-800/60 p-6 rounded-2xl shadow-xl backdrop-blur-sm">
          <h3 className="text-lg font-semibold text-white mb-6 flex items-center">
            <Settings className="w-5 h-5 mr-2 text-emerald-400" />
            Backend Configuration
          </h3>
          <div className="space-y-4">
            <div>
              <label htmlFor="flightaware_url" className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">FlightAware URL</label>
              <input id="flightaware_url" type="text" name="flightaware_url" value={config.flightaware_url} onChange={handleConfigChange} className={fieldClasses('flightaware_url')} />
            </div>
            <div>
              <label htmlFor="flightaware_api_key" className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">API Key</label>
              <input id="flightaware_api_key" type="password" name="flightaware_api_key" value={config.flightaware_api_key} onChange={handleConfigChange} className={fieldClasses('flightaware_api_key')} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="home_lat" className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">Home Lat</label>
                <input
                  id="home_lat"
                  type="number"
                  step="any"
                  name="home_lat"
                  value={numberValue(config.home_lat)}
                  onChange={handleConfigChange}
                  aria-invalid={!!errors.home_lat}
                  aria-describedby={errors.home_lat ? 'home_lat-error' : undefined}
                  className={fieldClasses('home_lat')}
                />
                {fieldError('home_lat')}
              </div>
              <div>
                <label htmlFor="home_lon" className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">Home Lon</label>
                <input
                  id="home_lon"
                  type="number"
                  step="any"
                  name="home_lon"
                  value={numberValue(config.home_lon)}
                  onChange={handleConfigChange}
                  aria-invalid={!!errors.home_lon}
                  aria-describedby={errors.home_lon ? 'home_lon-error' : undefined}
                  className={fieldClasses('home_lon')}
                />
                {fieldError('home_lon')}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="max_radar_range_nm" className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">Radar Range (NM)</label>
                <input
                  id="max_radar_range_nm"
                  type="number"
                  name="max_radar_range_nm"
                  value={numberValue(config.max_radar_range_nm)}
                  onChange={handleConfigChange}
                  aria-invalid={!!errors.max_radar_range_nm}
                  aria-describedby={errors.max_radar_range_nm ? 'max_radar_range_nm-error' : undefined}
                  className={fieldClasses('max_radar_range_nm')}
                />
                {fieldError('max_radar_range_nm')}
              </div>
              <div>
                <label htmlFor="cache_ttl" className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">Cache TTL (s)</label>
                <input
                  id="cache_ttl"
                  type="number"
                  name="cache_ttl"
                  value={numberValue(config.cache_ttl)}
                  onChange={handleConfigChange}
                  aria-invalid={!!errors.cache_ttl}
                  aria-describedby={errors.cache_ttl ? 'cache_ttl-error' : undefined}
                  className={fieldClasses('cache_ttl')}
                />
                {fieldError('cache_ttl')}
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {/* Display Configuration */}
          <div className="bg-slate-900/40 border border-slate-800/60 p-6 rounded-2xl shadow-xl backdrop-blur-sm">
            <h3 className="text-lg font-semibold text-white mb-6 flex items-center">
              <HardDrive className="w-5 h-5 mr-2 text-slate-400" />
              Hardware Output
            </h3>
            <div className="flex items-center justify-between bg-slate-950 border border-slate-800 p-2 rounded-xl">
              {(['E-Ink', 'Split-Flap'] as const).map(mode => (
                <button
                  key={mode}
                  onClick={() => setDisplayMode(mode)}
                  aria-pressed={displayMode === mode}
                  className={`flex-1 flex items-center justify-center py-2.5 rounded-lg text-sm font-medium transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 ${displayMode === mode
                    ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/25'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                    }`}
                >
                  {mode === 'E-Ink' ? 'Static E-Ink' : 'Split-Flap'}
                </button>
              ))}
            </div>
          </div>

          {/* Wi-Fi Configuration */}
          <div className="bg-slate-900/40 border border-slate-800/60 p-6 rounded-2xl shadow-xl backdrop-blur-sm">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
              <Wifi className="w-5 h-5 mr-2 text-slate-400" />
              Network Configuration
            </h3>

            {/* Saved Networks List */}
            <div className="space-y-2 mb-6">
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide">Saved Networks (wpa_supplicant)</label>
              {wifiNetworks.length === 0 ? (
                <div className="text-slate-500 text-xs italic p-3 bg-slate-950/50 rounded-lg border border-slate-800/80">No Wi-Fi networks configured.</div>
              ) : (
                <div className="space-y-2 max-h-40 overflow-y-auto pr-1 custom-scrollbar">
                  {wifiNetworks.map(net => (
                    <div key={net.id} className="flex items-center justify-between p-2.5 bg-slate-950 border border-slate-800 rounded-lg group hover:border-slate-700 transition-colors">
                      <div className="flex items-center space-x-2.5">
                        <Wifi className="w-4 h-4 text-slate-400" />
                        <span className="text-sm font-medium text-slate-200">{net.ssid}</span>
                      </div>
                      <button
                        onClick={() => onRemoveWifiNetwork(net.id)}
                        className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
                        title="Remove network"
                        aria-label={`Remove ${net.ssid}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Add Network Form */}
            <form onSubmit={handleAddNetworkSubmit} className="space-y-3 pt-3 border-t border-slate-800">
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide">Add Wi-Fi Network</label>
              <div>
                <input
                  type="text"
                  placeholder="Network SSID"
                  aria-label="Network SSID"
                  value={newSsid}
                  onChange={e => setNewSsid(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all"
                />
              </div>
              <div>
                <input
                  type="password"
                  placeholder="Password"
                  aria-label="Network password"
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all"
                />
              </div>
              <button
                type="submit"
                disabled={!newSsid.trim()}
                className="w-full flex items-center justify-center space-x-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white py-2 rounded-lg font-medium text-sm transition-colors shadow-lg shadow-emerald-500/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
              >
                <Plus className="w-4 h-4" />
                <span>Add Network</span>
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* System Admin */}
      <div className="bg-rose-950/20 border border-rose-900/30 p-6 rounded-2xl shadow-xl backdrop-blur-sm mt-6">
        <h3 className="text-lg font-semibold text-rose-100 mb-6 flex items-center">
          <Power className="w-5 h-5 mr-2 text-rose-400" />
          System Administration
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button onClick={handleGitPull} className="group relative overflow-hidden flex flex-col items-start p-4 bg-slate-900/50 hover:bg-slate-800/80 border border-slate-800 rounded-xl transition-all duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950">
            <div className="flex items-center justify-between w-full mb-2">
              <GitPullRequest className="w-5 h-5 text-emerald-400 group-hover:scale-110 transition-transform" />
              <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors" />
            </div>
            <span className="font-semibold text-slate-200 group-hover:text-white transition-colors">Update Codebase</span>
            <span className="text-xs text-slate-500 mt-1 font-mono">{systemStatus.git}</span>
          </button>

          <button onClick={handleCsvUpdate} className="group relative overflow-hidden flex flex-col items-start p-4 bg-slate-900/50 hover:bg-slate-800/80 border border-slate-800 rounded-xl transition-all duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950">
            <div className="flex items-center justify-between w-full mb-2">
              <Download className={`w-5 h-5 group-hover:scale-110 transition-transform ${systemStatus.csv === 'Updating...' ? 'text-amber-400' : 'text-emerald-400'}`} />
              <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors" />
            </div>
            <span className="font-semibold text-slate-200 group-hover:text-white transition-colors">Update Aircraft DB</span>
            <span className="text-xs text-slate-500 mt-1 font-mono">{systemStatus.csv}</span>
          </button>

          <button onClick={() => setConfirmRestart(true)} className="group relative overflow-hidden flex flex-col items-start p-4 bg-slate-900/50 hover:bg-rose-900/30 hover:border-rose-800/50 border border-slate-800 rounded-xl transition-all duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950">
            <div className="flex items-center justify-between w-full mb-2">
              <RefreshCw className={`w-5 h-5 text-rose-400 group-hover:scale-110 transition-transform ${systemStatus.service === 'Restarting...' ? 'animate-spin' : ''}`} />
              <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors" />
            </div>
            <span className="font-semibold text-slate-200 group-hover:text-white transition-colors">Restart Services</span>
            <span className="text-xs text-slate-500 mt-1 font-mono">{systemStatus.service === 'Restarting...' ? 'Rebooting...' : 'Ready'}</span>
          </button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmRestart}
        destructive
        title="Restart Services?"
        description="The monitor service and its hardware output stop for a few seconds while it restarts. Aircraft tracking resumes automatically."
        confirmLabel="Restart Services"
        onConfirm={() => {
          setConfirmRestart(false);
          handleRestartService();
        }}
        onCancel={() => setConfirmRestart(false)}
      />
    </div>
  );
}
