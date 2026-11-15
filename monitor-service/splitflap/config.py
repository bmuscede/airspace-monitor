"""
config.py - the display as the config file describes it.

One SplitFlapConfig describes a physical display: which Chainlink channel each flap is wired
to, which flaps are on its spool, how the channels are grouped into rows, and how patient to
be with a module that cannot find home. Both the service and the calibration tool build theirs
with SplitFlapConfig.from_service_section(), so there is one description of the display rather
than two that can disagree.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

from utils.logs import GetLogger

log = GetLogger("SplitFlap.Config")

# The flaps on a stock build: "Flap option 1" in the firmware's config.h. Used for the default
# charset when the config file doesn't describe one.
LEGACY_40_FLAPS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,'"

# Tells "no fallback flap" apart from "work the fallback out yourself".
_DEFAULT = object()

__all__ = [
    "LEGACY_40_FLAPS",
    "SplitFlapCharset",
    "SplitFlapConfig",
    "SplitFlapPosition",
    "parse_tokens",
    "token_label",
]


class SplitFlapCharset:
    """
    The flap characters and order in one kind of module.

    Index 0 is the home flap (the one the module shows after calibration + homing).
    A flap is a single character or icon. Icons have multiple characters.

    A spool is described either as one line of text, which is split with parse_tokens() so
    that "{ACA}" is one logo flap and not five flaps, or as a sequence in which every entry
    is already exactly one flap ([" ", "A", "ACA"]). The text form is what a config file
    written by hand uses; the dashboard writes the sequence form.
    """

    def __init__(self, name: str, flaps: Union[str, Sequence[str]], aliases: Optional[Dict[str, str]] = None,
                 fallback=_DEFAULT):
        # A flap list can either be a string or a sequence of strings.
        # If a sequence of strings, multicharacters represent symbols.
        if isinstance(flaps, str):
            try:
                flap_list = parse_tokens(flaps)
            except ValueError as e:
                # Which set in the file is wrong matters more than where in its text.
                raise ValueError(f"charset {name!r}: {e}") from None
        else:
            flap_list = list(flaps)

        # If we don't have a flap list, return an error.
        if not flap_list:
            raise ValueError(f"charset {name!r} has no flaps")

        # Each token must be a non empty string.
        for token in flap_list:
            if not isinstance(token, str) or not token:
                raise ValueError(f"charset {name!r}: every flap must be a non-empty string (got {token!r})")

        # Handle the flap list items.
        self.name = name
        self.flaps: Tuple[str, ...] = tuple(flap_list)
        self._index: Dict[str, int] = {}
        
        for i, token in enumerate(self.flaps):
            self._index.setdefault(token, i)

        # Aliases resolve one symbol for another.
        # For instance AC Rouge can be resolved to AC.
        self.aliases: Dict[str, str] = dict(aliases or {})
        for alias, target in self.aliases.items():
            if target not in self._index:
                raise ValueError(f"charset {name!r}: alias {alias!r} points at {target!r}, which isn't one of its flaps")

        # Fallback allows us to go to a particular character if 
        if fallback is _DEFAULT:
            fallback = " " if " " in self._index else None
        elif fallback is not None and self.lookup(fallback) is None:
            raise ValueError(f"charset {name!r}: fallback {fallback!r} isn't one of its flaps")
        self.fallback: Optional[str] = fallback

    def __len__(self) -> int:
        return len(self.flaps)

    def __repr__(self) -> str:
        return f"SplitFlapCharset({self.name!r}, {len(self.flaps)} flaps)"

    def lookup(self, token: str) -> Optional[int]:
        """
        Flap index for a token (exact, then alias, then upper-case), or None.
        """
        for candidate in (token, token.upper()):
            if candidate in self._index:
                return self._index[candidate]
            target = self.aliases.get(candidate)
            if target is not None:
                return self._index[target]
        return None

    def resolve(self, token: str) -> Optional[int]:
        """
        Like lookup(), but falls back to the fallback flap if it doesn't exist. 
        If none, don't use this module.
        """
        index = self.lookup(token)
        if index is None and self.fallback is not None:
            index = self.lookup(self.fallback)
        return index

    def token(self, index: int) -> Optional[str]:
        return self.flaps[index] if 0 <= index < len(self.flaps) else None

@dataclass(frozen=True)
class SplitFlapPosition:
    """
    SplitFlapPosition represents the position for a module.

    Holds information about the position (0-indexed from left to right)
    and character set of the flap characters.
    """
    channel: int               # The channel on the board.
    charset: SplitFlapCharset  # The character set for this module.

@dataclass
class SplitFlapConfig:
    """
    SplitFlapConfig represents the configuration for a SplitFlap display.

    Automatically parses configuration settings from a configuration file. Required
    to handle connecting to the SplitFlap display.
    """

    positions: List[SplitFlapPosition]              # Display positions, left to right as seen from the front.
    rows: List[int] = field(default_factory=list)   # Flaps per row, top to bottom. Empty is one row.
    port: Optional[str] = None                      # If None, auto-detect.
    auto_rehome: bool = True                        # Automatically rehomes if there's a problem.
    max_rehome_attempts: int = 3                    # Per module will rehome a certain number of times.
    rehome_window_s: float = 600.0                  # When to try rehoming if there's a problem.
    rehome_backoff_s: float = 15.0                  # Minimum time between attempts on one module

    def __post_init__(self):
        # Get the number of channels and the values.
        channels = [p.channel for p in self.positions]
        if len(set(channels)) != len(channels):
            raise ValueError(f"each channel can only be used by one position (got {channels})")

        # Ensure the channels are in range.
        for ch in channels:
            if not 0 <= ch < 255:
                raise ValueError(f"channel {ch} is out of range")

        # Ensure the character set lengths are valid.
        lengths = sorted({len(p.charset) for p in self.positions})
        if len(lengths) > 1:
            log.warning("Charsets have different lengths %s, but the firmware uses one NUM_FLAPS for every "
                        "module. Every charset should have exactly NUM_FLAPS flaps.", lengths)

    def row_spans(self) -> List[Tuple[int, int]]:
        """
        Returns the position of the first flap and length for each row from top to bottom.

        The driver only knows one long line of positions; this is what divides it into the rows
        that are physically stacked on the frame. 
        """
        spans: List[Tuple[int, int]] = []
        start = 0
        try:
            for length in self.rows:
                if isinstance(length, bool) or not isinstance(length, int):
                    # JSON hands us whole numbers; anything else is a typo, and quietly
                    # rounding 2.5 down would leave flaps out of every row below it.
                    raise ValueError(f"row lengths have to be whole numbers (got {length!r})")
                if length <= 0 or start + length > len(self.positions):
                    raise ValueError(f"a row of {length} doesn't fit in the "
                                     f"{len(self.positions) - start} channel(s) left")
                spans.append((start, length))
                start += length
        except (TypeError, ValueError) as e:
            log.warning("rows %s is unusable (%s); treating all %d channels as one row.",
                        self.rows, e, len(self.positions))
            return [(0, len(self.positions))]
        return spans or [(0, len(self.positions))]

    @classmethod
    def from_dict(cls, data: dict) -> "SplitFlapConfig":
        charsets: Dict[str, SplitFlapCharset] = {}
        for name, spec in (data.get("charsets") or {}).items():
            if name.startswith("_"):
                continue
            if isinstance(spec, (str, list)):
                spec = {"flaps": spec}
            kwargs = {}
            if "fallback" in spec:
                kwargs["fallback"] = spec["fallback"]
            charsets[name] = SplitFlapCharset(name, spec["flaps"], spec.get("aliases"), **kwargs)
        if "default" not in charsets:
            charsets["default"] = SplitFlapCharset("default", LEGACY_40_FLAPS)

        raw_positions = data.get("positions")
        if not isinstance(raw_positions, list):
            raise ValueError("the config needs a 'positions' list (one entry per display position, left to right)")
        positions = []
        for i, entry in enumerate(raw_positions):
            if isinstance(entry, int):
                entry = {"channel": entry}
            charset_name = entry.get("charset", "default")
            if charset_name not in charsets:
                raise ValueError(f"position {i}: unknown charset {charset_name!r}")
            positions.append(SplitFlapPosition(int(entry["channel"]), charsets[charset_name]))

        rehome = data.get("auto_rehome", {})
        if isinstance(rehome, bool):
            rehome = {"enabled": rehome}
        return cls(
            positions=positions,
            rows=list(data.get("rows") or []),
            port=data.get("port"),
            auto_rehome=bool(rehome.get("enabled", True)),
            max_rehome_attempts=int(rehome.get("max_attempts", 3)),
            rehome_window_s=float(rehome.get("window_s", 600.0)),
            rehome_backoff_s=float(rehome.get("backoff_s", 15.0)),
        )

    @classmethod
    def from_service_section(cls, section: dict) -> "SplitFlapConfig":
        """
        Builds a config out of the "splitflap" section of the service's config.json.

        The file speaks in channels ("which Chainlink channel is this flap wired to") and says
        its timings in seconds, because that is what someone editing it by hand wants to read;
        the names in this module are the ones the driver wants.
        """
        rehome = section.get("auto_rehome") or {}
        return cls.from_dict({
            "positions": section.get("channels") or [],
            "rows": section.get("rows") or [],
            "port": section.get("port") or None,
            "charsets": section.get("charsets") or {},
            "auto_rehome": {
                "enabled": rehome.get("enabled", True),
                "max_attempts": rehome.get("max_attempts", 3),
                "window_s": rehome.get("window_seconds", 600.0),
                "backoff_s": rehome.get("backoff_seconds", 15.0),
            },
        })

def parse_tokens(text: str) -> List[str]:
    """
    Split text into flap tokens.
    Example: "{ACA}857" -> ["ACA", "8", "5", "7"]
    
    Use "{{" / "}}" for braces.
    """
    tokens: List[str] = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == "{":
            if text.startswith("{{", i):
                tokens.append("{")
                i += 2
                continue
            end = text.find("}", i + 1)
            if end == -1:
                raise ValueError(f"unclosed '{{' in {text!r}")
            name = text[i + 1:end]
            if not name:
                raise ValueError(f"empty '{{}}' in {text!r}")
            tokens.append(name)
            i = end + 1
        elif c == "}" and text.startswith("}}", i):
            tokens.append("}")
            i += 2
        else:
            tokens.append(c)
            i += 1
    return tokens

def token_label(token: Optional[str]) -> str:
    """
    Helper function to print a human readable version of the token
    currently being printed.
    """
    if token is None:
        return "?"
    if token == " ":
        return "(blank)"
    return token if len(token) == 1 else "{" + token + "}"
