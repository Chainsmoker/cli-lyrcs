from __future__ import annotations

from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.box import ROUNDED
from typing import Any

BORDER_STYLES = [
    "red",
    "orange1",
    "yellow1",
    "chartreuse1",
    "green",
    "spring_green1",
    "cyan",
    "deep_sky_blue1",
    "dodger_blue1",
    "blue",
    "purple",
    "magenta",
    "hot_pink",
]


def animated_border_style(frame: int) -> str:
    return BORDER_STYLES[(frame // 2) % len(BORDER_STYLES)]


def build_layout(
    cover: str | Text,
    cava: Text | None,
    lyrics: Any,
    player: str,
    frame: int,
    wave_active: bool,
    ascii_height: int = 18,
) -> Layout:
    """Build a player layout that shows only two rows:

    - Row 1: cover + player
    - Row 2: **lyrics** by default, or **visualizer** when `cava` is provided (instrumental sections).

    `wave_active` controls whether borders animate.
    """
    left_border = animated_border_style(frame) if wave_active else "cyan"
    right_border = animated_border_style(frame + 3) if wave_active else "magenta"

    top_group = Group(
        Align.center(Text(cover, justify="center")),
        Align.center(Text(player)),
    )

    # Second row is conditional: show cava (visualizer) when present, otherwise show lyrics
    if cava is not None:
        second_panel = Panel(
            Align.center(cava, vertical="middle"),
            title="🔊 Visualizer",
            border_style=right_border,
            box=ROUNDED,
        )
    else:
        second_panel = Panel(
            Align.center(lyrics, vertical="middle"),
            title="🎵 Lyrics",
            border_style=right_border,
            box=ROUNDED,
        )

    layout = Layout()
    layout.split_column(
        Layout(
            Panel(
                Align.center(top_group, vertical="middle"),
                title="🎧 Now Playing",
                border_style=left_border,
                box=ROUNDED,
            ),
            size=ascii_height + 8,
        ),
        Layout(second_panel),
    )
    return layout
