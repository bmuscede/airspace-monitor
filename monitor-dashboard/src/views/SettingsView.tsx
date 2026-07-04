import { useState } from 'react';
import { Settings, HardDrive, Wifi, Power, GitPullRequest, ChevronRight, Download, RefreshCw, Save, Plus, Trash2 } from 'lucide-react';
import type { SystemStatus, WifiNetwork } from '../types';

interface SettingsViewProps {
  config: any;
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

export default function SettingsView({
  config,
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

  const handleAddNetworkSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSsid.trim()) return;
    onAddWifiNetwork(newSsid.trim(), newPassword);
    setNewSsid('');
    setNewPassword('');
  };

  return (
    <div className="space-y-8 pb-10 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl">
      <header className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-white">System Settings</h2>
          <p className="text-slate-400 text-sm">Configure hardware, backend services, and application preferences.</p>
        </div>
        <button 
          onClick={handleSaveConfig}
          className="flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg transition-colors shadow-lg shadow-emerald-500/20 font-medium"
        >
          <Save className="w-4 h-4" />
          <span>Save Changes</span>
        </button>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Service Config */}
        <div className="bg-slate-900/40 border border-slate-800/60 p-6 rounded-2xl shadow-xl backdrop-blur-sm">
          <h3 className="text-lg font-semibold text-white mb-6 flex items-center">
            <Settings className="w-5 h-5 mr-2 text-blue-400" />
            Backend Configuration
          </h3>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">FlightAware URL</label>
              <input type="text" name="flightaware_url" value={config.flightaware_url} onChange={handleConfigChange} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">API Key</label>
              <input type="password" name="flightaware_api_key" value={config.flightaware_api_key} onChange={handleConfigChange} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">Home Lat</label>
                <input type="number" step="any" name="home_lat" value={config.home_lat} onChange={handleConfigChange} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">Home Lon</label>
                <input type="number" step="any" name="home_lon" value={config.home_lon} onChange={handleConfigChange} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">Radar Range (NM)</label>
                <input type="number" name="max_radar_range_nm" value={config.max_radar_range_nm} onChange={handleConfigChange} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">Cache TTL (s)</label>
                <input type="number" name="cache_ttl" value={config.cache_ttl} onChange={handleConfigChange} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all" />
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {/* Display Configuration */}
          <div className="bg-slate-900/40 border border-slate-800/60 p-6 rounded-2xl shadow-xl backdrop-blur-sm">
            <h3 className="text-lg font-semibold text-white mb-6 flex items-center">
              <HardDrive className="w-5 h-5 mr-2 text-amber-400" />
              Hardware Output
            </h3>
            <div className="flex items-center justify-between bg-slate-950 border border-slate-800 p-2 rounded-xl">
              <button 
                onClick={() => setDisplayMode('E-Ink')}
                className={`flex-1 flex items-center justify-center py-2.5 rounded-lg text-sm font-medium transition-all ${displayMode === 'E-Ink' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/25' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'}`}
              >
                Static E-Ink
              </button>
              <button 
                onClick={() => setDisplayMode('Split-Flap')}
                className={`flex-1 flex items-center justify-center py-2.5 rounded-lg text-sm font-medium transition-all ${displayMode === 'Split-Flap' ? 'bg-amber-600 text-white shadow-lg shadow-amber-500/25' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'}`}
              >
                Split-Flap
              </button>
            </div>
          </div>

          {/* Wi-Fi Configuration */}
          <div className="bg-slate-900/40 border border-slate-800/60 p-6 rounded-2xl shadow-xl backdrop-blur-sm">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
              <Wifi className="w-5 h-5 mr-2 text-cyan-400" />
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
                        <Wifi className="w-4 h-4 text-cyan-400/80" />
                        <span className="text-sm font-medium text-slate-200">{net.ssid}</span>
                      </div>
                      <button 
                        onClick={() => onRemoveWifiNetwork(net.id)}
                        className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 rounded-md transition-colors"
                        title="Remove network"
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
                  value={newSsid} 
                  onChange={e => setNewSsid(e.target.value)} 
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all" 
                />
              </div>
              <div>
                <input 
                  type="password" 
                  placeholder="Password" 
                  value={newPassword} 
                  onChange={e => setNewPassword(e.target.value)} 
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all" 
                />
              </div>
              <button 
                type="submit" 
                disabled={!newSsid.trim()}
                className="w-full flex items-center justify-center space-x-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-white py-2 rounded-lg font-medium text-sm transition-colors shadow-lg shadow-cyan-500/20"
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
          <button onClick={handleGitPull} className="group relative overflow-hidden flex flex-col items-start p-4 bg-slate-900/50 hover:bg-slate-800/80 border border-slate-800 rounded-xl transition-all duration-300">
            <div className="flex items-center justify-between w-full mb-2">
              <GitPullRequest className="w-5 h-5 text-emerald-400 group-hover:scale-110 transition-transform" />
              <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors" />
            </div>
            <span className="font-semibold text-slate-200 group-hover:text-white transition-colors">Update Codebase</span>
            <span className="text-xs text-slate-500 mt-1 font-mono">{systemStatus.git}</span>
          </button>

          <button onClick={handleCsvUpdate} className="group relative overflow-hidden flex flex-col items-start p-4 bg-slate-900/50 hover:bg-slate-800/80 border border-slate-800 rounded-xl transition-all duration-300">
            <div className="flex items-center justify-between w-full mb-2">
              <Download className="w-5 h-5 text-amber-400 group-hover:scale-110 transition-transform" />
              <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors" />
            </div>
            <span className="font-semibold text-slate-200 group-hover:text-white transition-colors">Update Aircraft DB</span>
            <span className="text-xs text-slate-500 mt-1 font-mono">{systemStatus.csv}</span>
          </button>

          <button onClick={handleRestartService} className="group relative overflow-hidden flex flex-col items-start p-4 bg-slate-900/50 hover:bg-rose-900/30 hover:border-rose-800/50 border border-slate-800 rounded-xl transition-all duration-300">
            <div className="flex items-center justify-between w-full mb-2">
              <RefreshCw className={`w-5 h-5 text-rose-400 group-hover:scale-110 transition-transform ${systemStatus.service === 'Restarting...' ? 'animate-spin' : ''}`} />
              <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors" />
            </div>
            <span className="font-semibold text-slate-200 group-hover:text-white transition-colors">Restart Services</span>
            <span className="text-xs text-slate-500 mt-1 font-mono">{systemStatus.service === 'Restarting...' ? 'Rebooting...' : 'Ready'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
