import { Radar, Plane } from 'lucide-react';
import RadarDisplay from '../components/RadarDisplay';
import type { Flight } from '../types';
import { resolveMaxRange } from '../lib/radar';

interface DashboardViewProps {
  flights: Flight[];
  maxRadarRange: number;
  selectedHex: string | null;
  onSelectTarget: (hex: string | null) => void;
}

export default function DashboardView({
  flights,
  maxRadarRange,
  selectedHex,
  onSelectTarget,
}: DashboardViewProps) {
  const range = resolveMaxRange(maxRadarRange);

  return (
    <div className="h-full flex flex-col space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <header className="mb-2 shrink-0">
        <h2 className="text-2xl font-bold text-white">Live Dashboard</h2>
        <p className="text-slate-400 text-sm">Real-time overhead aircraft telemetry.</p>
      </header>

      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-slate-900/40 border border-slate-800/60 p-6 rounded-2xl shadow-xl backdrop-blur-sm relative overflow-hidden flex flex-col">
          <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-[80px]"></div>
          <div className="flex justify-between items-center mb-8 relative z-10 shrink-0">
            <h3 className="text-lg font-semibold flex items-center text-white">
              <Radar className="w-5 h-5 mr-2 text-emerald-400" />
              Airspace Radar
            </h3>
            <span className="text-xs font-mono bg-slate-800/80 border border-slate-700 text-slate-300 px-3 py-1 rounded-full shadow-inner">
              Range: {range} NM
            </span>
          </div>
          <div className="flex-1 min-h-0 flex items-center justify-center relative z-10 w-full py-4">
            <RadarDisplay
              flights={flights}
              maxRadarRange={range}
              selectedHex={selectedHex}
              onSelect={onSelectTarget}
            />
          </div>
        </div>
      </div>

      <div className="bg-slate-900/40 border border-slate-800/60 p-6 rounded-2xl shadow-xl backdrop-blur-sm relative overflow-hidden flex flex-col">
        <div className="absolute bottom-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-[60px]"></div>
        <h3 className="text-lg font-semibold mb-6 flex items-center text-white relative z-10">
          <Plane className="w-5 h-5 mr-2 text-emerald-400" />
          Active Targets
        </h3>
        <div className="space-y-3 flex-1 overflow-y-auto relative z-10 pr-2 custom-scrollbar">
          {flights.length === 0 ? (
            <div className="text-slate-600 italic text-center py-10">No aircraft in range.</div>
          ) : (
            flights.map(f => {
              const isSelected = f.hex === selectedHex;
              return (
                <button
                  key={f.hex}
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => onSelectTarget(isSelected ? null : f.hex)}
                  className={`w-full text-left p-4 rounded-xl border flex justify-between items-center group transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${isSelected
                    ? 'bg-emerald-500/10 border-emerald-500/40'
                    : 'bg-slate-800/40 hover:bg-slate-800/60 border-slate-700/50'
                    }`}
                >
                  <div>
                    <div className={`font-mono font-bold transition-colors ${isSelected ? 'text-emerald-300' : 'text-white group-hover:text-emerald-400'}`}>
                      {f.flight !== '???' ? f.flight : f.hex.toUpperCase()}
                    </div>
                    <div className="text-xs text-slate-400 flex items-center mt-1">
                      <span className="bg-slate-700/50 px-1.5 py-0.5 rounded mr-2">{f.type}</span>
                      {f.distance.toFixed(1)} NM
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-slate-200">{f.altitude.toLocaleString()} <span className="text-xs text-slate-500">ft</span></div>
                    <div className="text-xs text-slate-400 mt-1">{f.speed} <span className="text-[10px] text-slate-500">kts</span></div>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
