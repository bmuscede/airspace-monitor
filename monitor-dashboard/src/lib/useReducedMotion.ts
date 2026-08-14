import { useEffect, useState } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

/**
 * Tracks the OS-level reduced-motion preference.
 *
 * CSS handles this for stylesheet animations; this hook exists for animations
 * expressed in markup (SMIL), which a media query cannot reach.
 */
export function usePrefersReducedMotion(): boolean {
    const [prefersReduced, setPrefersReduced] = useState(
        () => typeof window !== 'undefined' && window.matchMedia(QUERY).matches
    );

    useEffect(() => {
        const media = window.matchMedia(QUERY);
        const onChange = () => setPrefersReduced(media.matches);
        media.addEventListener('change', onChange);
        return () => media.removeEventListener('change', onChange);
    }, []);

    return prefersReduced;
}