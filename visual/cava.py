from __future__ import annotations

from typing import Sequence, List
from rich.text import Text

# rainbow gradient colors (left-to-right)
RAINBOW: List[str] = [
    "red",
    "orange1",
    "yellow1",
    "chartreuse1",
    "green",
    "spring_green1",
    "cyan",
    "deep_sky_blue1",
    "blue",
    "purple",
    "magenta",
]


def render_cava_bars(bands: Sequence[float], height: int = 10, width: int = 40) -> Text:
    """Render a vertical CAVA visual using a rainbow gradient.

    `bands` should be normalized to [0..1]. The visual maps columns to the provided bands
    and colors each "█" block using a vertical gradient to give an arcoiris effect.
    """
    if len(bands) == 0:
        return Text("")

    nb = min(len(bands), width)
    step = max(1, len(bands) // nb)
    proc = [max(bands[i : i + step]) for i in range(0, len(bands), step)]
    proc = proc[:width]

    # Build rows from top (0) to bottom (height-1)
    t = Text()
    for row in range(height):
        for x, val in enumerate(proc):
            h = int(val * height)
            present = (height - row) <= h
            if present:
                # pick color based on vertical position to create rainbow gradient
                color_idx = int((row / max(1, height - 1)) * (len(RAINBOW) - 1))
                color = RAINBOW[color_idx]
                t.append("█", style=color)
            else:
                t.append(" ")
        if row < height - 1:
            t.append("\n")
    return t
