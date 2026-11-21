import { useState } from 'react';
import { Plus, RefreshCw, Trash2, Wifi } from 'lucide-react';
import ConfirmDialog from '../../components/ConfirmDialog';
import {
    FieldHelp,
    FieldRow,
    Panel,
    PageFootnote,
    ReadOnlyGrid,
    SettingsHeader,
    StubNotice,
    WarningNotice,
} from '../../components/settings/SettingsPrimitives';
import { buttonPrimary, buttonSecondary, inputClasses } from '../../components/settings/settingsStyles';
import type { WifiNetwork } from '../../types';

interface NetworkSettingsProps {
    networks: WifiNetwork[];
    loading: boolean;
    /** The last /api/wifi read failed, so the list below may be stale or empty. */
    failed: boolean;
    busy: boolean;
    onReload: () => void;
    onAdd: (ssid: string, password: string) => Promise<boolean>;
    onRemove: (ssid: string) => Promise<boolean>;
}

export default function NetworkSettings({
    networks,
    loading,
    failed,
    busy,
    onReload,
    onAdd,
    onRemove,
}: NetworkSettingsProps) {
    const [ssid, setSsid] = useState('');
    const [password, setPassword] = useState('');
    const [pendingRemoval, setPendingRemoval] = useState<WifiNetwork | null>(null);

    const handleAdd = async (event: React.FormEvent) => {
        event.preventDefault();
        const trimmed = ssid.trim();
        if (!trimmed) return;
        const added = await onAdd(trimmed, password);
        if (added) {
            setSsid('');
            setPassword('');
        }
    };

    return (
        <div className="space-y-4 pb-10 max-w-5xl">
            <SettingsHeader
                title="Network"
                description="How the appliance gets online, and how you reach it. Changes here apply immediately — there is nothing to save."
            />

            <Panel title="Connection" meta={<span className="font-mono">wlan0</span>}>
                {/* TODO: This is a stub comment. The associated SSID, signal, IP address,
                    hostname and link uptime need a new read on the service side (iwgetid,
                    iwconfig, hostname -I); /api/state carries none of it. */}
                <ReadOnlyGrid
                    items={[
                        { label: 'Network', value: null },
                        { label: 'Signal', value: null },
                        { label: 'IP address', value: null },
                        { label: 'Hostname', value: null },
                        { label: 'Dashboard', value: window.location.origin, mono: true },
                        { label: 'Uptime on this link', value: null },
                    ]}
                />
                <div className="mt-4">
                    <StubNotice>
                        Which network the Pi is actually on, its signal and its address are not reported by the
                        service yet — they need a read of <span className="font-mono">iwgetid</span>,{' '}
                        <span className="font-mono">iwconfig</span> and <span className="font-mono">hostname -I</span>.
                        The dashboard address above is simply the one this browser is using.
                    </StubNotice>
                </div>
            </Panel>

            <Panel
                title="Saved networks"
                meta={<span className="font-mono">/etc/wpa_supplicant/wpa_supplicant.conf</span>}
            >
                <FieldRow
                    first
                    label="Known networks"
                    help="In the order the file lists them. The Pi picks whichever it can see."
                >
                    {failed && (
                        <div className="mb-3">
                            <WarningNotice>
                                The list of saved networks could not be read. What is shown may be out of date.{' '}
                                <button
                                    type="button"
                                    onClick={onReload}
                                    className="underline text-rose-200 hover:text-white focus:outline-none focus-visible:ring-1 focus-visible:ring-rose-400 rounded"
                                >
                                    Try again
                                </button>
                                .
                            </WarningNotice>
                        </div>
                    )}

                    <div className="flex flex-col gap-2">
                        {loading && networks.length === 0 ? (
                            <p className="text-xs text-slate-500 italic px-3 py-3 bg-slate-950/50 border border-slate-800/80 rounded-lg">
                                Reading wpa_supplicant…
                            </p>
                        ) : networks.length === 0 ? (
                            <p className="text-xs text-slate-500 italic px-3 py-3 bg-slate-950/50 border border-slate-800/80 rounded-lg">
                                No Wi-Fi networks configured.
                            </p>
                        ) : (
                            networks.map(network => (
                                <div
                                    key={network.id}
                                    className="flex items-center gap-3 px-3 py-2.5 bg-slate-950/50 border border-slate-800 rounded-lg hover:border-slate-700 transition-colors"
                                >
                                    <Wifi className="w-4 h-4 text-slate-400 shrink-0" />
                                    <span className="flex-1 text-sm font-mono text-slate-200">{network.ssid}</span>
                                    {/* TODO: This is a stub comment. "connected" and "not in range"
                                        need a scan (wpa_cli scan_results) plus the association read
                                        above, so no network can be labelled either way yet. */}
                                    <span
                                        className="text-[11px] text-slate-600"
                                        title="Whether this network is in range is not reported yet."
                                    >
                                        state unknown
                                    </span>
                                    <button
                                        type="button"
                                        onClick={() => setPendingRemoval(network)}
                                        disabled={busy}
                                        aria-label={`Forget ${network.ssid}`}
                                        title="Forget network"
                                        className="p-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-rose-400 hover:border-rose-900 transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            ))
                        )}
                    </div>

                    <div className="mt-3">
                        <button type="button" onClick={onReload} disabled={loading} className={buttonSecondary}>
                            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                            Refresh list
                        </button>
                    </div>
                </FieldRow>

                <FieldRow
                    label="Forgetting a network"
                    help={
                        <>
                            Removal rewrites the file and runs <span className="font-mono">wpa_cli reconfigure</span>,
                            which drops the link for a second or two.
                        </>
                    }
                >
                    <WarningNotice>
                        If you forget the network this page arrived over, the dashboard goes with it — the request
                        that removes it is travelling over that link. The service does not report which network it
                        is associated with, so every removal confirms with that consequence spelled out.
                    </WarningNotice>
                </FieldRow>
            </Panel>

            <Panel title="Add a network" meta={<span>WPA-PSK only</span>}>
                <form onSubmit={handleAdd}>
                    <FieldRow
                        first
                        label={<label htmlFor="wifi_ssid">Network name</label>}
                        help="Case-sensitive, exactly as the router broadcasts it."
                    >
                        <input
                            id="wifi_ssid"
                            type="text"
                            placeholder="SSID"
                            aria-label="Network SSID"
                            value={ssid}
                            onChange={event => setSsid(event.target.value)}
                            className={`${inputClasses()} w-full`}
                        />
                    </FieldRow>

                    <FieldRow
                        label={<label htmlFor="wifi_password">Password</label>}
                        help={
                            <>
                                Written into <span className="font-mono">wpa_supplicant.conf</span> as{' '}
                                <span className="font-mono">psk="…"</span> — in the clear, as root. Anyone who can
                                read that file can read the password.
                            </>
                        }
                    >
                        <input
                            id="wifi_password"
                            type="password"
                            placeholder="Password"
                            aria-label="Network password"
                            autoComplete="off"
                            value={password}
                            onChange={event => setPassword(event.target.value)}
                            className={`${inputClasses()} w-full`}
                        />
                    </FieldRow>

                    <FieldRow
                        label="Apply"
                        align="center"
                        help={
                            <>
                                Appends the block and runs{' '}
                                <span className="font-mono">wpa_cli -i wlan0 reconfigure</span>, so the chip
                                rescans at once.
                            </>
                        }
                    >
                        <div className="flex items-center gap-3 flex-wrap">
                            <button
                                type="submit"
                                disabled={!ssid.trim() || busy}
                                title={!ssid.trim() ? 'Disabled until the name has content.' : undefined}
                                className={buttonPrimary}
                            >
                                <Plus className="w-4 h-4" />
                                <span>{busy ? 'Working…' : 'Add network'}</span>
                            </button>
                            {!ssid.trim() && (
                                <span className="text-xs text-slate-400">Disabled until the name has content.</span>
                            )}
                        </div>
                        <FieldHelp>
                            A failure here raises a modal rather than passing in silence: the service answers both
                            add and remove with a status word, and a rejected write looks exactly like a successful
                            one over HTTP.
                        </FieldHelp>
                    </FieldRow>
                </form>
            </Panel>

            <PageFootnote>
                The list, add and remove are live today — <span className="font-mono">GET/POST /api/wifi</span> and{' '}
                <span className="font-mono">DELETE /api/wifi/{'{ssid}'}</span>, parsing and rewriting{' '}
                <span className="font-mono">wpa_supplicant.conf</span> and reconfiguring{' '}
                <span className="font-mono">wlan0</span> each time. The Connection panel and the per-network
                in-range state are the parts still waiting on the service.
            </PageFootnote>

            <ConfirmDialog
                open={pendingRemoval !== null}
                destructive
                title={`Forget ${pendingRemoval?.ssid ?? 'this network'}?`}
                description="The service rewrites wpa_supplicant.conf and reconfigures wlan0, which drops the link for a second or two. If this is the network the dashboard is reached over, it will not come back on its own."
                confirmLabel="Forget network"
                onConfirm={() => {
                    const target = pendingRemoval;
                    setPendingRemoval(null);
                    if (target) void onRemove(target.ssid);
                }}
                onCancel={() => setPendingRemoval(null)}
            />
        </div>
    );
}
