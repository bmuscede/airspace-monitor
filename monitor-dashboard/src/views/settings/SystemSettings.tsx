import { useState } from 'react';
import { Download, GitPullRequest, Power, RefreshCw } from 'lucide-react';
import ConfirmDialog from '../../components/ConfirmDialog';
import {
    FieldHelp,
    FieldRow,
    Panel,
    PageFootnote,
    ReadOnlyGrid,
    SegmentedControl,
    SettingsHeader,
    StubNotice,
} from '../../components/settings/SettingsPrimitives';
import {
    buttonDanger,
    buttonGhostDanger,
    buttonSecondary,
} from '../../components/settings/settingsStyles';
import type { SystemStatus } from '../../types';

const DISPLAY_MODES = ['E-Ink', 'Split-Flap'] as const;
type DisplayMode = (typeof DISPLAY_MODES)[number];

interface SystemSettingsProps {
    systemStatus: SystemStatus;
    displayMode: string;
    onSetDisplayMode: (mode: string) => void;
    switchingMode: boolean;
    onGitPull: () => void;
    onCsvUpdate: () => void;
    onRestart: () => void;
    onShutdown: () => void;
    /** Contacts the history database is holding, from /api/history/stats. */
    historyContactCount: number | null;
}

export default function SystemSettings({
    systemStatus,
    displayMode,
    onSetDisplayMode,
    switchingMode,
    onGitPull,
    onCsvUpdate,
    onRestart,
    onShutdown,
    historyContactCount,
}: SystemSettingsProps) {
    const [confirmRestart, setConfirmRestart] = useState(false);
    const [confirmShutdown, setConfirmShutdown] = useState(false);

    const online = systemStatus.service === 'Online';
    const restarting = systemStatus.service === 'Restarting...';
    const mode: DisplayMode = displayMode === 'Split-Flap' ? 'Split-Flap' : 'E-Ink';

    return (
        <div className="space-y-4 pb-10 max-w-5xl">
            <SettingsHeader
                title="System"
                description="Build, data files, and the actions that take the service away for a moment. Every action here runs immediately — nothing on this page is saved."
            />

            <Panel
                title="This appliance"
                meta={
                    <span className="flex items-center gap-2">
                        <span
                            className={`w-2 h-2 rounded-full ${online ? 'bg-emerald-400' : restarting ? 'bg-amber-400' : 'bg-rose-400'}`}
                        />
                        Service {systemStatus.service.toLowerCase()}
                    </span>
                }
            >
                {/* TODO: This is a stub comment. Commit and branch (git rev-parse), service
                    uptime and start time, the aircraft CSV's row count and date, and the
                    sizes of the log and history database are all new reads the service does
                    not expose. */}
                <ReadOnlyGrid
                    items={[
                        { label: 'Code version', value: null },
                        { label: 'Service uptime', value: null },
                        { label: 'Started', value: null },
                        { label: 'Receiver link', value: systemStatus.dump1090, mono: false },
                        { label: 'Config file', value: 'monitor-service/config.json' },
                        {
                            label: 'History database',
                            value:
                                historyContactCount === null
                                    ? null
                                    : `${historyContactCount.toLocaleString()} contacts`,
                        },
                    ]}
                />

                <div className="mt-4">
                    <StubNotice>
                        Code version, uptime, start time and file sizes are not reported by the service yet. The
                        receiver link and service state come from <span className="font-mono">/api/state</span>, and
                        the contact count from <span className="font-mono">/api/history/stats</span>.
                    </StubNotice>
                </div>

                <div className="mt-2">
                    <FieldRow
                        first
                        align="center"
                        label="Hardware output"
                        help="Which display the service drives. Switches as soon as it is picked."
                    >
                        <div className="flex items-center gap-3 flex-wrap">
                            <SegmentedControl<DisplayMode>
                                label="Hardware output"
                                options={DISPLAY_MODES}
                                value={mode}
                                disabled={switchingMode}
                                onChange={next => onSetDisplayMode(next)}
                                renderLabel={option => (option === 'E-Ink' ? 'Static E-Ink' : 'Split-Flap')}
                            />
                            {switchingMode && <span className="text-xs text-slate-400">Switching…</span>}
                        </div>
                        <FieldHelp>
                            <span className="font-mono">POST /api/mode</span> toggles between the two rather than
                            setting one, so the request says which mode was asked for and the reply is what the
                            service actually switched to.
                        </FieldHelp>
                    </FieldRow>
                </div>
            </Panel>

            <Panel title="Software and data">
                <FieldRow
                    first
                    align="center"
                    label="Update codebase"
                    help={
                        <>
                            Pulls <span className="font-mono">main</span> on the Pi. New code only runs after a
                            restart, which this does not do for you.
                        </>
                    }
                >
                    <div className="flex items-center justify-end gap-4">
                        <span className="text-xs font-mono text-slate-400 whitespace-nowrap">{systemStatus.git}</span>
                        <button
                            type="button"
                            onClick={onGitPull}
                            disabled={systemStatus.git === 'Pulling...'}
                            className={buttonSecondary}
                        >
                            <GitPullRequest className="w-3.5 h-3.5" />
                            Pull latest
                        </button>
                    </div>
                </FieldRow>

                <FieldRow
                    align="center"
                    label="Aircraft database"
                    help={'The registration and type CSV behind every "A21N · C-GJWO".'}
                >
                    <div className="flex items-center justify-end gap-4">
                        <span
                            className={`text-xs font-mono whitespace-nowrap ${systemStatus.csv === 'Updating...' ? 'text-amber-400' : 'text-slate-400'}`}
                        >
                            {systemStatus.csv}
                        </span>
                        <button
                            type="button"
                            onClick={onCsvUpdate}
                            disabled={systemStatus.csv === 'Updating...'}
                            className={buttonSecondary}
                        >
                            <Download className="w-3.5 h-3.5" />
                            Update now
                        </button>
                    </div>
                    {/* TODO: This is a stub comment. The service starts the download as a
                        background task and never reports progress or completion, so the row
                        says "started" and the status clears on a timer in App.tsx. */}
                    <FieldHelp>
                        The service answers as soon as the download starts and never reports progress, so this row
                        can only say that it began. Row count and last-updated date need a new read.
                    </FieldHelp>
                </FieldRow>

                <FieldRow
                    align="center"
                    label="Live log"
                    help="Kept in tmpfs so the SD card survives; cleared on every boot."
                >
                    {/* TODO: This is a stub comment. The log file is on disk but there is no
                        endpoint that serves it, and /api/logs returns only the last 200
                        parsed lines rather than the file. */}
                    <div className="flex items-center justify-end gap-4">
                        <span className="text-xs font-mono text-slate-500">no endpoint</span>
                        <button
                            type="button"
                            disabled
                            title="Downloading the log file needs an endpoint that serves it."
                            className={buttonSecondary}
                        >
                            <Download className="w-3.5 h-3.5" />
                            Download
                        </button>
                    </div>
                    <FieldHelp>
                        Disabled: <span className="font-mono">/api/logs</span> returns the last 200 parsed lines for
                        the Live Logs view, not the file itself.
                    </FieldHelp>
                </FieldRow>
            </Panel>

            <Panel
                title="Power"
                tone="danger"
                description="Both of these interrupt tracking and the hardware display. Both confirm first, naming what stops."
                meta={<Power className="w-4 h-4 text-rose-400" aria-hidden="true" />}
            >
                <FieldRow
                    first
                    align="center"
                    label="Restart services"
                    help="Stops and starts the monitor service. Out for a few seconds; tracking resumes on its own, and open contacts are flushed to history first."
                >
                    <div className="flex items-center justify-end gap-4">
                        <span className="text-xs font-mono text-slate-400 whitespace-nowrap">
                            {restarting ? 'Restarting…' : 'Ready'}
                        </span>
                        <button
                            type="button"
                            onClick={() => setConfirmRestart(true)}
                            disabled={restarting}
                            className={buttonDanger}
                        >
                            <RefreshCw className={`w-4 h-4 ${restarting ? 'animate-spin' : ''}`} />
                            Restart
                        </button>
                    </div>
                </FieldRow>

                <FieldRow
                    align="center"
                    label="Shut down"
                    help="Closes the history database cleanly and stops. Nothing here can bring it back — someone has to power-cycle the Pi."
                >
                    <div className="flex items-center justify-end gap-4">
                        <span className="text-xs font-mono text-slate-400">—</span>
                        <button
                            type="button"
                            onClick={() => setConfirmShutdown(true)}
                            className={buttonGhostDanger}
                        >
                            <Power className="w-4 h-4" />
                            Shut down
                        </button>
                    </div>
                </FieldRow>
            </Panel>

            <PageFootnote>
                Four of these are live endpoints: <span className="font-mono">POST /api/git-pull</span>,{' '}
                <span className="font-mono">POST /api/update-db</span>,{' '}
                <span className="font-mono">POST /api/restart-service</span> and{' '}
                <span className="font-mono">POST /api/shutdown</span> — the last had never had a button, even
                though it is the only clean way to stop. The status words beside each action are the service's own
                strings. What is still missing: commit and branch, uptime, the CSV's row count and date, the log
                and database sizes, and an endpoint that serves the log file.
            </PageFootnote>

            <ConfirmDialog
                open={confirmRestart}
                destructive
                title="Restart Services?"
                description="The monitor service and its hardware output stop for a few seconds while it restarts. Open contacts are flushed to history first, and aircraft tracking resumes automatically."
                confirmLabel="Restart Services"
                onConfirm={() => {
                    setConfirmRestart(false);
                    onRestart();
                }}
                onCancel={() => setConfirmRestart(false)}
            />

            <ConfirmDialog
                open={confirmShutdown}
                destructive
                title="Shut down the monitor service?"
                description="Tracking, the hardware display and this dashboard all stop. The history database is closed cleanly first. Nothing in the browser can start it again — someone has to power-cycle the Pi."
                confirmLabel="Shut down"
                onConfirm={() => {
                    setConfirmShutdown(false);
                    onShutdown();
                }}
                onCancel={() => setConfirmShutdown(false)}
            />
        </div>
    );
}
