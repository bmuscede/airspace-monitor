import { AlertTriangle, Info, Bug, XCircle } from 'lucide-react';
import { useRef, useEffect } from 'react';
import type { LogEntry } from '../types';

interface LogsViewProps {
  logs: LogEntry[];
  logFilters: { DEBUG: boolean; INFO: boolean; WARN: boolean; ERROR: boolean };
  setLogFilters: React.Dispatch<React.SetStateAction<{ DEBUG: boolean; INFO: boolean; WARN: boolean; ERROR: boolean }>>;
}

export default function LogsView({ logs, logFilters, setLogFilters }: LogsViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, logFilters]);

  const filteredLogs = logs.filter(log => logFilters[log.level]);

  return (
    <div className="h-full flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500">
      <header className="mb-6 flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-white">System Logs</h2>
          <p className="text-slate-400 text-sm">Live console output from the monitor service.</p>
        </div>
        <div className="flex space-x-2 bg-slate-900/50 p-1 rounded-lg border border-slate-800">
          {(['DEBUG', 'INFO', 'WARN', 'ERROR'] as const).map(level => {
            const colors = {
              DEBUG: 'text-slate-400 data-[active=true]:bg-slate-800 data-[active=true]:text-white',
              INFO: 'text-blue-400/50 data-[active=true]:bg-blue-500/20 data-[active=true]:text-blue-400',
              WARN: 'text-amber-400/50 data-[active=true]:bg-amber-500/20 data-[active=true]:text-amber-400',
              ERROR: 'text-rose-400/50 data-[active=true]:bg-rose-500/20 data-[active=true]:text-rose-400',
            };
            return (
              <button
                key={level}
                data-active={logFilters[level]}
                onClick={() => setLogFilters(prev => ({ ...prev, [level]: !prev[level] }))}
                className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${colors[level]}`}
              >
                {level}
              </button>
            );
          })}
        </div>
      </header>

      <div className="flex-1 bg-slate-950 border border-slate-800 rounded-2xl p-4 overflow-hidden shadow-2xl relative min-h-[400px]">
        <div className="absolute top-0 left-0 right-0 h-8 bg-gradient-to-b from-slate-950 to-transparent z-10 pointer-events-none"></div>
        <div ref={containerRef} className="h-full overflow-y-auto font-mono text-sm space-y-2 pr-2 custom-scrollbar pb-10">
          {filteredLogs.length === 0 ? (
            <div className="text-slate-600 italic text-center py-10">No logs matching filters.</div>
          ) : (
            filteredLogs.map(log => {
              const icon = {
                DEBUG: <Bug className="w-4 h-4 text-slate-500 shrink-0" />,
                INFO: <Info className="w-4 h-4 text-blue-400 shrink-0" />,
                WARN: <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />,
                ERROR: <XCircle className="w-4 h-4 text-rose-500 shrink-0" />
              }[log.level];

              const textColor = {
                DEBUG: 'text-slate-400',
                INFO: 'text-slate-200',
                WARN: 'text-amber-200',
                ERROR: 'text-rose-300'
              }[log.level];

              return (
                <div key={log.id} className="flex items-start space-x-3 hover:bg-slate-800/30 p-1.5 rounded transition-colors group">
                  <span className="text-slate-600 text-xs shrink-0 mt-0.5">{log.timestamp}</span>
                  <span className="shrink-0 mt-0.5">{icon}</span>
                  <span className="text-slate-500 text-xs w-16 shrink-0 mt-0.5 uppercase tracking-wider">[{log.source}]</span>
                  <span className={`${textColor} break-words group-hover:text-white transition-colors`}>{log.message}</span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
