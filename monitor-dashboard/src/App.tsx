import { useState, useEffect } from 'react';
import { Radar, RefreshCw, Download, GitPullRequest, Settings, Plane, Activity, CheckCircle2, HardDrive } from 'lucide-react';

interface Flight {
  id: string;
  type: string;
  alt: number;
  spd: number;
  distance: number;
  bearing: number;
}

interface SystemStatus {
  git: string;
  csv: string;
  dump1090: string;
}

const MOCK_FLIGHTS: Flight[] = [
  { id: 'ACA860', type: 'B789', alt: 35000, spd: 490, distance: 15, bearing: 45 },
  { id: 'WJA712', type: 'B38M', alt: 22000, spd: 380, distance: 40, bearing: 120 },
  { id: 'JZA14', type: 'Q400', alt: 8000, spd: 250, distance: 8, bearing: 280 },
];

export default function AirspaceDashboard() {
  const [flights, setFlights] = useState<Flight[]>([]);
  const [displayMode, setDisplayMode] = useState<string>('E-Ink');
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    git: 'Idle',
    csv: 'Up to date',
    dump1090: 'Running',
  });

  useEffect(() => {
    // In production: fetch('/api/flights').then(res => res.json()).then(setFlights)
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

  const handleGitPull = () => {
    setSystemStatus(prev => ({ ...prev, git: 'Pulling...' }));
    setTimeout(() => setSystemStatus(prev => ({ ...prev, git: 'Updated (main)' })), 2000);
  };

  const handleCsvUpdate = () => {
    setSystemStatus(prev => ({ ...prev, csv: 'Downloading...' }));
    setTimeout(() => setSystemStatus(prev => ({ ...prev, csv: 'Up to date' })), 3000);
  };

  const renderRadar = () => {
    return (
      <div className="relative w-full aspect-square max-w-md mx-auto bg-slate-900 rounded-full border-4 border-slate-700 overflow-hidden shadow-2xl">
        {/* Radar Grid Lines */}
        <div className="absolute inset-0 rounded-full border border-emerald-500/30 m-8"></div>
        <div className="absolute inset-0 rounded-full border border-emerald-500/30 m-16"></div>
        <div className="absolute inset-0 rounded-full border border-emerald-500/30 m-24"></div>
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-emerald-500/30"></div>
        <div className="absolute top-1/2 left-0 right-0 h-px bg-emerald-500/30"></div>
        
        {/* Radar Sweep Animation */}
        <div 
          className="absolute top-1/2 left-1/2 w-1/2 h-1/2 bg-gradient-to-br from-emerald-500/40 to-transparent origin-top-left"
          style={{ animation: 'spin 4s linear infinite' }}
        ></div>

        <style>{`
          @keyframes spin { 100% { transform: rotate(360deg); } }
          @keyframes ping-fade { 0% { opacity: 1; transform: scale(1); } 100% { opacity: 0; transform: scale(2.5); } }
        `}</style>

        {/* Home Base Marker */}
        <div className="absolute top-1/2 left-1/2 w-2 h-2 bg-emerald-400 rounded-full -translate-x-1/2 -translate-y-1/2 shadow-[0_0_10px_#34d399]"></div>

        {/* Rendering Flights as Blips */}
        {flights.map((flight) => {
          const radius = (flight.distance / 50) * 50; 
          const radians = (flight.bearing - 90) * (Math.PI / 180);
          const x = 50 + radius * Math.cos(radians);
          const y = 50 + radius * Math.sin(radians);

          return (
            <div 
              key={flight.id}
              className="absolute w-3 h-3 bg-emerald-400 rounded-full shadow-[0_0_8px_#34d399] transition-all duration-1000"
              style={{ left: `${x}%`, top: `${y}%`, transform: 'translate(-50%, -50%)' }}
            >
              <div className="absolute inset-0 bg-emerald-400 rounded-full animate-[ping-fade_2s_infinite]"></div>
              <div className="absolute top-4 left-4 bg-slate-800/80 text-emerald-400 text-xs px-2 py-1 rounded border border-emerald-500/50 whitespace-nowrap backdrop-blur-sm">
                {flight.id} ({flight.alt}ft)
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-6 font-sans selection:bg-emerald-500/30">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Header Section */}
        <header className="flex items-center justify-between bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-lg">
          <div className="flex items-center space-x-3">
            <Radar className="w-8 h-8 text-emerald-500" />
            <div>
              <h1 className="text-xl font-bold text-white">Airspace Command Center</h1>
              <p className="text-sm text-slate-400">Local ADS-B Telemetry & Hardware Node</p>
            </div>
          </div>
          <div className="flex items-center space-x-2 bg-emerald-500/10 text-emerald-400 px-3 py-1.5 rounded-full border border-emerald-500/20">
            <Activity className="w-4 h-4 animate-pulse" />
            <span className="text-sm font-medium">System Online</span>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          <div className="lg:col-span-2 bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-lg">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-semibold flex items-center">
                <Radar className="w-5 h-5 mr-2 text-blue-400" />
                Live Airspace Radar
              </h2>
              <span className="text-xs bg-slate-800 text-slate-400 px-2 py-1 rounded">Range: 50 NM</span>
            </div>
            {renderRadar()}
          </div>

          <div className="space-y-6">
            
            {/* Active Flights List */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg">
              <h2 className="text-md font-semibold mb-4 flex items-center">
                <Plane className="w-5 h-5 mr-2 text-indigo-400" />
                Overhead Targets
              </h2>
              <div className="space-y-3">
                {flights.map(f => (
                  <div key={f.id} className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50 flex justify-between items-center">
                    <div>
                      <div className="font-mono font-bold text-emerald-400">{f.id}</div>
                      <div className="text-xs text-slate-400">{f.type} • {f.distance.toFixed(1)} NM</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm text-slate-300">{f.alt.toLocaleString()} ft</div>
                      <div className="text-xs text-slate-500">{f.spd} kts</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Hardware Settings */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg">
              <h2 className="text-md font-semibold mb-4 flex items-center">
                <Settings className="w-5 h-5 mr-2 text-amber-400" />
                Hardware Configuration
              </h2>
              <div className="flex items-center justify-between bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                <span className="text-sm font-medium">Active Output</span>
                <div className="flex bg-slate-950 rounded-lg p-1 border border-slate-800">
                  <button 
                    onClick={() => setDisplayMode('Split-Flap')}
                    className={`px-3 py-1 text-xs rounded-md transition-colors ${displayMode === 'Split-Flap' ? 'bg-amber-500 text-slate-900 font-bold' : 'text-slate-400 hover:text-slate-200'}`}
                  >
                    Split-Flap
                  </button>
                  <button 
                    onClick={() => setDisplayMode('E-Ink')}
                    className={`px-3 py-1 text-xs rounded-md transition-colors ${displayMode === 'E-Ink' ? 'bg-indigo-500 text-white font-bold' : 'text-slate-400 hover:text-slate-200'}`}
                  >
                    E-Ink
                  </button>
                </div>
              </div>
            </div>

            {/* System Administration */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg">
              <h2 className="text-md font-semibold mb-4 flex items-center">
                <HardDrive className="w-5 h-5 mr-2 text-rose-400" />
                System Administration
              </h2>
              <div className="space-y-3">
                <button 
                  onClick={handleGitPull}
                  className="w-full flex items-center justify-between p-3 bg-slate-800/50 hover:bg-slate-800 transition-colors rounded-lg border border-slate-700/50"
                >
                  <div className="flex items-center">
                    <GitPullRequest className="w-4 h-4 mr-3 text-slate-400" />
                    <span className="text-sm">Update Codebase</span>
                  </div>
                  <span className="text-xs text-emerald-400 font-mono">{systemStatus.git}</span>
                </button>

                <button 
                  onClick={handleCsvUpdate}
                  className="w-full flex items-center justify-between p-3 bg-slate-800/50 hover:bg-slate-800 transition-colors rounded-lg border border-slate-700/50"
                >
                  <div className="flex items-center">
                    <Download className="w-4 h-4 mr-3 text-slate-400" />
                    <span className="text-sm">Update Aircraft DB</span>
                  </div>
                  <span className="text-xs text-amber-400 font-mono">{systemStatus.csv}</span>
                </button>

                <div className="w-full flex items-center justify-between p-3 bg-slate-800/50 rounded-lg border border-slate-700/50">
                  <div className="flex items-center">
                    <RefreshCw className="w-4 h-4 mr-3 text-slate-400 animate-spin-slow" />
                    <span className="text-sm">Decoder Daemon</span>
                  </div>
                  <div className="flex items-center text-xs text-emerald-400 font-mono">
                    <CheckCircle2 className="w-3 h-3 mr-1" />
                    {systemStatus.dump1090}
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}