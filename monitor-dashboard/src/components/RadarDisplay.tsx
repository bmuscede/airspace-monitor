import type { Flight } from '../types';

interface RadarDisplayProps {
  flights: Flight[];
}

export default function RadarDisplay({ flights }: RadarDisplayProps) {
  return (
    <div className="relative w-full aspect-square max-w-md mx-auto bg-slate-950/50 rounded-full border border-slate-700/50 overflow-hidden shadow-[0_0_40px_rgba(0,0,0,0.5)] backdrop-blur-sm">
      {/* Radar Grid Lines */}
      <div className="absolute inset-0 rounded-full border border-emerald-500/20 m-8"></div>
      <div className="absolute inset-0 rounded-full border border-emerald-500/20 m-16"></div>
      <div className="absolute inset-0 rounded-full border border-emerald-500/20 m-24"></div>
      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-emerald-500/20"></div>
      <div className="absolute top-1/2 left-0 right-0 h-px bg-emerald-500/20"></div>
      
      {/* Radar Sweep Animation */}
      <div 
        className="absolute top-1/2 left-1/2 w-1/2 h-1/2 bg-gradient-to-br from-emerald-400/30 to-transparent origin-top-left"
        style={{ animation: 'spin 4s linear infinite' }}
      ></div>

      <style>{`
        @keyframes spin { 100% { transform: rotate(360deg); } }
        @keyframes ping-fade { 0% { opacity: 1; transform: scale(1); } 100% { opacity: 0; transform: scale(2.5); } }
      `}</style>

      {/* Home Base Marker */}
      <div className="absolute top-1/2 left-1/2 w-3 h-3 bg-white rounded-full -translate-x-1/2 -translate-y-1/2 shadow-[0_0_15px_#fff] z-10 border-2 border-emerald-500"></div>

      {/* Rendering Flights as Blips */}
      {flights.map((flight) => {
        const radius = (flight.distance / 50) * 50; 
        const radians = (flight.bearing - 90) * (Math.PI / 180);
        const x = 50 + radius * Math.cos(radians);
        const y = 50 + radius * Math.sin(radians);

        return (
          <div 
            key={flight.id}
            className="absolute w-3 h-3 bg-emerald-400 rounded-full shadow-[0_0_10px_#34d399] transition-all duration-1000 z-10"
            style={{ left: `${x}%`, top: `${y}%`, transform: 'translate(-50%, -50%)' }}
          >
            <div className="absolute inset-0 bg-emerald-400 rounded-full animate-[ping-fade_2s_infinite]"></div>
            <div className="absolute top-4 left-4 bg-slate-900/90 text-emerald-300 text-[10px] px-2 py-1 rounded-md border border-emerald-500/30 whitespace-nowrap backdrop-blur-md font-mono shadow-xl">
              <span className="font-bold text-white">{flight.id}</span> <br/>
              {flight.alt}ft • {flight.spd}kts
            </div>
          </div>
        );
      })}
    </div>
  );
}
