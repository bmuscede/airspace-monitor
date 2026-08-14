import { useState } from 'react';
import type { Flight } from '../types';
import {
  SCOPE_EXTENT,
  SCOPE_RADIUS,
  formatRange,
  leaderLength,
  projectTarget,
  resolveMaxRange,
} from '../lib/radar';
import { usePrefersReducedMotion } from '../lib/useReducedMotion';

interface RadarDisplayProps {
  flights: Flight[];
  maxRadarRange: number;
  selectedHex: string | null;
  onSelect: (hex: string | null) => void;
}

const RING_FRACTIONS = [0.25, 0.5, 0.75, 1];

/** Aircraft glyph, pointing along its own forward direction (up / north). */
const GLYPH = 'M 0 -2.6 L 2 2.4 L 0 1.1 L -2 2.4 Z';

const LABEL_FONT_SIZE = 5;
/** Monospace advance width at LABEL_FONT_SIZE, used to size label backdrops. */
const LABEL_CHAR_WIDTH = LABEL_FONT_SIZE * 0.62;

function callsignOf(flight: Flight): string {
  return flight.flight && flight.flight !== '???' ? flight.flight : flight.hex.toUpperCase();
}

export default function RadarDisplay({
  flights,
  maxRadarRange,
  selectedHex,
  onSelect,
}: RadarDisplayProps) {
  const [hoveredHex, setHoveredHex] = useState<string | null>(null);

  const maxRange = resolveMaxRange(maxRadarRange);
  const targets = flights.filter(f => Number.isFinite(f.distance) && f.distance <= maxRange);

  const prefersReducedMotion = usePrefersReducedMotion();

  const count = targets.length;
  const ariaLabel = `Airspace radar, ${count === 0 ? 'no aircraft' : count === 1 ? '1 aircraft' : `${count} aircraft`} within ${formatRange(maxRange)} nautical miles`;

  return (
    <div className="relative h-full aspect-square max-h-full max-w-full mx-auto">
      <svg
        role="img"
        aria-label={ariaLabel}
        viewBox={`${-SCOPE_EXTENT} ${-SCOPE_EXTENT} ${SCOPE_EXTENT * 2} ${SCOPE_EXTENT * 2}`}
        className="h-full w-full"
        onClick={() => onSelect(null)}
      >
        <defs>
          {/* Fades the sweep away from its leading edge (due north) back to its tail. */}
          <linearGradient
            id="radar-sweep-gradient"
            gradientUnits="userSpaceOnUse"
            x1="0"
            y1={-SCOPE_RADIUS}
            x2={-SCOPE_RADIUS * 0.707}
            y2={-SCOPE_RADIUS * 0.707}
          >
            <stop offset="0%" stopColor="#34d399" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#34d399" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Scope face. Also the click target that clears the current selection. */}
        <circle r={SCOPE_RADIUS} fill="#020617" fillOpacity="0.5" stroke="#334155" strokeWidth="1" />

        {/* Range rings */}
        {RING_FRACTIONS.map(fraction => (
          <circle
            key={fraction}
            r={SCOPE_RADIUS * fraction}
            fill="none"
            stroke="#10b981"
            strokeOpacity="0.2"
            vectorEffect="non-scaling-stroke"
          />
        ))}

        {/* Cardinal axes */}
        <line
          x1="0"
          y1={-SCOPE_RADIUS}
          x2="0"
          y2={SCOPE_RADIUS}
          stroke="#10b981"
          strokeOpacity="0.2"
          vectorEffect="non-scaling-stroke"
        />
        <line
          x1={-SCOPE_RADIUS}
          y1="0"
          x2={SCOPE_RADIUS}
          y2="0"
          stroke="#10b981"
          strokeOpacity="0.2"
          vectorEffect="non-scaling-stroke"
        />

        {/* Range ring labels, offset clear of the vertical axis */}
        {RING_FRACTIONS.map(fraction => (
          <text
            key={fraction}
            x="4"
            y={-SCOPE_RADIUS * fraction - 2}
            textAnchor="start"
            fontSize={LABEL_FONT_SIZE}
            fill="#64748b"
            className="font-mono select-none"
          >
            {formatRange(maxRange * fraction)}
          </text>
        ))}

        {/* Compass rose */}
        {[
          { label: 'N', x: 0, y: -(SCOPE_RADIUS + 6) },
          { label: 'E', x: SCOPE_RADIUS + 6, y: 0 },
          { label: 'S', x: 0, y: SCOPE_RADIUS + 6 },
          { label: 'W', x: -(SCOPE_RADIUS + 6), y: 0 },
        ].map(({ label, x, y }) => (
          <text
            key={label}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="7"
            fill="#94a3b8"
            className="font-mono select-none"
          >
            {label}
          </text>
        ))}

        {/*
          Sweep. The rotation centre is given explicitly rather than through
          CSS: with a viewBox whose origin is not 0 0, `transform-box: view-box`
          resolves `transform-origin` against the user-space origin rather than
          the viewBox corner, so the CSS form rotates about the wrong point.
        */}
        <path
          d={`M 0 0 L ${-SCOPE_RADIUS * 0.707} ${-SCOPE_RADIUS * 0.707} A ${SCOPE_RADIUS} ${SCOPE_RADIUS} 0 0 1 0 ${-SCOPE_RADIUS} Z`}
          fill="url(#radar-sweep-gradient)"
        >
          {!prefersReducedMotion && (
            <animateTransform
              attributeName="transform"
              attributeType="XML"
              type="rotate"
              from="0 0 0"
              to="360 0 0"
              dur="4s"
              repeatCount="indefinite"
            />
          )}
        </path>

        {/* Home marker */}
        <circle r="5" fill="none" stroke="#10b981" strokeOpacity="0.6" vectorEffect="non-scaling-stroke" />
        <circle r="2" fill="#ffffff" />

        {/* Targets */}
        {targets.map(flight => {
          const { x, y } = projectTarget(flight.distance, flight.bearing, maxRange);
          const heading = Number.isFinite(flight.heading) ? flight.heading : 0;
          const leader = leaderLength(flight.speed, maxRange);
          const isSelected = flight.hex === selectedHex;
          const isActive = isSelected || flight.hex === hoveredHex;
          const callsign = callsignOf(flight);

          const lines = [callsign, `${flight.altitude}ft • ${flight.speed}kts`];
          const labelWidth =
            Math.max(...lines.map(line => line.length)) * LABEL_CHAR_WIDTH + 4;
          const flip = x > 40;
          const labelX = flip ? -7 : 7;
          const labelRectX = flip ? labelX - labelWidth : labelX;

          return (
            <g
              key={flight.hex}
              transform={`translate(${x} ${y})`}
              className="cursor-pointer"
              onClick={event => {
                event.stopPropagation();
                onSelect(isSelected ? null : flight.hex);
              }}
              onMouseEnter={() => setHoveredHex(flight.hex)}
              onMouseLeave={() => setHoveredHex(current => (current === flight.hex ? null : current))}
            >
              <title>{callsign}</title>

              {/* Generous, invisible hit area — the glyph itself is tiny. */}
              <circle r="8" fill="transparent" />

              {isSelected && (
                <circle
                  r="7"
                  fill="none"
                  stroke="#34d399"
                  strokeOpacity="0.9"
                  vectorEffect="non-scaling-stroke"
                />
              )}

              <g transform={`rotate(${heading})`}>
                {leader > 0 && (
                  <line
                    x1="0"
                    y1="0"
                    x2="0"
                    y2={-leader}
                    stroke="#34d399"
                    strokeOpacity={isActive ? 0.9 : 0.5}
                    vectorEffect="non-scaling-stroke"
                  />
                )}
                <path d={GLYPH} fill={isActive ? '#ffffff' : '#34d399'} />
              </g>

              {isActive && (
                <g pointerEvents="none">
                  <rect
                    x={labelRectX}
                    y="-10"
                    width={labelWidth}
                    height="15"
                    rx="2"
                    fill="#020617"
                    fillOpacity="0.9"
                    stroke="#10b981"
                    strokeOpacity="0.3"
                    vectorEffect="non-scaling-stroke"
                  />
                  <text
                    x={labelRectX + 2}
                    y="-4.5"
                    fontSize={LABEL_FONT_SIZE}
                    textAnchor="start"
                    fill="#ffffff"
                    className="font-mono font-bold select-none"
                  >
                    {lines[0]}
                  </text>
                  <text
                    x={labelRectX + 2}
                    y="1.5"
                    fontSize={LABEL_FONT_SIZE}
                    textAnchor="start"
                    fill="#6ee7b7"
                    className="font-mono select-none"
                  >
                    {lines[1]}
                  </text>
                </g>
              )}
            </g>
          );
        })}
      </svg>

      {targets.length === 0 && (
        <div className="absolute left-1/2 top-[58%] -translate-x-1/2 -translate-y-1/2 pointer-events-none text-center">
          <p className="text-slate-600 italic text-sm">No aircraft in range.</p>
        </div>
      )}
    </div>
  );
}
