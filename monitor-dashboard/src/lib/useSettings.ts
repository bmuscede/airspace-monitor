import { useCallback, useEffect, useRef, useState } from 'react';
import { assertStatus, getJson, isAbortError, postJson } from './api';
import { DEFAULT_CONFIG, normalizeConfig, toConfigPayload } from './config';
import { DEFAULT_SPLITFLAP, normalizeSplitFlap, toSplitFlapPayload } from './splitflap';
import { errorReport, useErrorDialog } from './errorDialog';
import { useToast } from './toast';
import type { Config, SplitFlapConfig } from '../types';

/**
 * Owns everything that lives in `config.json`.
 *
 * One GET /api/config feeds both settings forms — the Backend page and the
 * Split-Flap page — and each saves only the dotted keys it changed, so the two
 * can hold unsaved edits at the same time without overwriting each other.
 *
 * The service answers a save with `{"status": ..., "ignored": [...]}`, and
 * `ignored` is the interesting half: a key it does not define is dropped
 * silently as far as HTTP is concerned. Treating that as a failure is what
 * keeps a control from looking like it saved when nothing happened.
 */

interface SaveResponse {
    status?: string;
    ignored?: unknown;
}

function ignoredKeys(payload: unknown): string[] {
    const ignored = (payload as SaveResponse | null)?.ignored;
    if (!Array.isArray(ignored)) return [];
    return ignored.filter((key): key is string => typeof key === 'string');
}

export interface SettingsController {
    loading: boolean;
    /** True once the service has answered at least once. */
    loaded: boolean;
    /** True when the last load failed: the pages show a retry instead of a form. */
    loadFailed: boolean;
    reload: () => void;

    config: Config;
    savedConfig: Config;
    setConfigField: <K extends keyof Config>(key: K, value: Config[K]) => void;
    discardConfig: () => void;
    saveConfig: () => void;
    savingConfig: boolean;

    splitFlap: SplitFlapConfig;
    savedSplitFlap: SplitFlapConfig;
    updateSplitFlap: (updater: (previous: SplitFlapConfig) => SplitFlapConfig) => void;
    discardSplitFlap: () => void;
    saveSplitFlap: () => void;
    savingSplitFlap: boolean;

    /**
     * Writes dotted config keys straight away, for the controls that are not
     * part of a form (forgetting calibration, for one). Resolves true when the
     * service confirmed it.
     */
    writeKeys: (payload: Record<string, unknown>, labels: { success: string; failure: string }) => Promise<boolean>;
}

export function useSettings(): SettingsController {
    const { showToast } = useToast();
    const { showError } = useErrorDialog();

    const [loading, setLoading] = useState(true);
    const [loaded, setLoaded] = useState(false);
    const [loadFailed, setLoadFailed] = useState(false);

    const [config, setConfig] = useState<Config>(DEFAULT_CONFIG);
    const [savedConfig, setSavedConfig] = useState<Config>(DEFAULT_CONFIG);
    const [savingConfig, setSavingConfig] = useState(false);

    const [splitFlap, setSplitFlap] = useState<SplitFlapConfig>(DEFAULT_SPLITFLAP);
    const [savedSplitFlap, setSavedSplitFlap] = useState<SplitFlapConfig>(DEFAULT_SPLITFLAP);
    const [savingSplitFlap, setSavingSplitFlap] = useState(false);

    // Bumped to re-run the load effect; the effect owns its AbortController so
    // a reload while one is in flight cannot land out of order.
    const [loadToken, setLoadToken] = useState(0);
    const mounted = useRef(true);

    useEffect(() => {
        mounted.current = true;
        return () => {
            mounted.current = false;
        };
    }, []);

    useEffect(() => {
        const controller = new AbortController();

        const load = async () => {
            setLoading(true);
            try {
                const payload = await getJson<unknown>('/api/config', { signal: controller.signal });
                const nextConfig = normalizeConfig(payload, DEFAULT_CONFIG);
                const nextSplitFlap = normalizeSplitFlap(payload, DEFAULT_SPLITFLAP);

                setConfig(nextConfig);
                setSavedConfig(nextConfig);
                setSplitFlap(nextSplitFlap);
                setSavedSplitFlap(nextSplitFlap);
                setLoadFailed(false);
                setLoaded(true);
            } catch (err) {
                if (isAbortError(err)) return;
                setLoadFailed(true);
                // The first load runs at startup, on whatever view the user
                // opened: a modal there would be about a page they are not
                // looking at, so the settings pages show the failure inline and
                // only an explicit retry escalates to a modal.
                if (loadToken > 0) showError(errorReport('Settings could not be loaded', err));
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        };

        load();
        return () => controller.abort();
    }, [loadToken, showError]);

    const reload = useCallback(() => setLoadToken(token => token + 1), []);

    const setConfigField = useCallback(<K extends keyof Config>(key: K, value: Config[K]) => {
        setConfig(previous => ({ ...previous, [key]: value }));
    }, []);

    const discardConfig = useCallback(() => setConfig(savedConfig), [savedConfig]);

    const updateSplitFlap = useCallback(
        (updater: (previous: SplitFlapConfig) => SplitFlapConfig) => setSplitFlap(updater),
        []
    );

    const discardSplitFlap = useCallback(() => setSplitFlap(savedSplitFlap), [savedSplitFlap]);

    /** Posts a dotted-key payload and turns every failure mode into a report. */
    const post = useCallback(
        async (payload: Record<string, unknown>, failure: string): Promise<boolean> => {
            try {
                const reply = await postJson<unknown>('/api/config', payload);
                assertStatus(reply, ['saved', 'no changes'], 'The service did not save the changes.');

                const ignored = ignoredKeys(reply);
                if (ignored.length > 0) {
                    showError({
                        title: failure,
                        message:
                            'The monitor service does not recognise some of these settings, so it ignored them. ' +
                            'The dashboard has reloaded what the service actually holds.',
                        detail: `Ignored keys:\n${ignored.join('\n')}`,
                    });
                    // What the service kept is now unknowable from here, so go
                    // back to it as the source of truth.
                    reload();
                    return false;
                }

                return true;
            } catch (err) {
                if (isAbortError(err)) return false;
                showError(errorReport(failure, err));
                return false;
            }
        },
        [reload, showError]
    );

    const saveConfig = useCallback(async () => {
        const payload = toConfigPayload(config, savedConfig);
        if (Object.keys(payload).length === 0) return;

        setSavingConfig(true);
        const ok = await post(payload, 'Changes not saved');
        if (!mounted.current) return;
        setSavingConfig(false);

        if (ok) {
            setSavedConfig(config);
            showToast('Changes saved');
        }
    }, [config, savedConfig, post, showToast]);

    const saveSplitFlap = useCallback(async () => {
        const payload = toSplitFlapPayload(splitFlap, savedSplitFlap);
        if (Object.keys(payload).length === 0) return;

        setSavingSplitFlap(true);
        const ok = await post(payload, 'Display settings not saved');
        if (!mounted.current) return;
        setSavingSplitFlap(false);

        if (ok) {
            setSavedSplitFlap(splitFlap);
            showToast('Display settings saved');
        }
    }, [splitFlap, savedSplitFlap, post, showToast]);

    const writeKeys = useCallback(
        async (payload: Record<string, unknown>, labels: { success: string; failure: string }) => {
            const ok = await post(payload, labels.failure);
            if (ok) {
                showToast(labels.success);
                reload();
            }
            return ok;
        },
        [post, reload, showToast]
    );

    return {
        loading,
        loaded,
        loadFailed,
        reload,
        config,
        savedConfig,
        setConfigField,
        discardConfig,
        saveConfig: () => void saveConfig(),
        savingConfig,
        splitFlap,
        savedSplitFlap,
        updateSplitFlap,
        discardSplitFlap,
        saveSplitFlap: () => void saveSplitFlap(),
        savingSplitFlap,
        writeKeys,
    };
}
