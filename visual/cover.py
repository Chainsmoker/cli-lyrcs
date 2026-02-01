from __future__ import annotations

from pathlib import Path


def render_cover_ascii(path: Path, width: int, height: int) -> str:
    """Render a simple placeholder box using '-' and '|' characters.

    This replaces the previous image->ASCII conversion. The box has the given
    width/height and contains the label 'COVER' centered so you can paste the real
    artwork later when editing.
    """
    w = max(3, int(width))
    h = max(3, int(height))

    top = "-" * w
    bottom = "-" * w

    middle = []
    label = " COVER "
    for i in range(h - 2):
        if i == (h - 2) // 2:
            # center label if it fits
            inner_w = w - 2
            if len(label) <= inner_w:
                pad = inner_w - len(label)
                left = pad // 2
                right = pad - left
                line = "|" + (" " * left) + label + (" " * right) + "|"
            else:
                line = "|" + (" " * inner_w) + "|"
        else:
            line = "|" + (" " * (w - 2)) + "|"
        middle.append(line)

    return "\n".join([top] + middle + [bottom])


def display_cover_image(path: Path, *, pixel_w: int | None = None, pixel_h: int | None = None, x: int = 0, y: int = 0) -> bool:
    """Attempt to display an image using the Kitty graphics protocol.

    Returns True on success, False if Kitty is not detected or display failed.
    """
    import os
    import sys
    import base64
    from io import BytesIO
    try:
        from PIL import Image
    except Exception:
        return False

    # Quick terminal detection: prefer not to rely only on KITTY_WINDOW_ID.
    # If stdout is not a TTY, we can't display graphics; otherwise try sending
    # Kitty graphics escape sequences and catch any errors.
    if not sys.stdout.isatty():
        return False

    try:
        with Image.open(path) as img:
            if pixel_w or pixel_h:
                img = img.resize((pixel_w or img.width, pixel_h or img.height), Image.LANCZOS)

            buf = BytesIO()
            img.save(buf, format="PNG")
            data = base64.b64encode(buf.getvalue()).decode("ascii")

        # send in chunks to avoid overly large writes
        CHUNK_SIZE = 4096
        for i in range(0, len(data), CHUNK_SIZE):
            chunk = data[i : i + CHUNK_SIZE]
            is_last = i + CHUNK_SIZE >= len(data)
            cmd = (
                "\033_G"
                f"a=T,"
                f"f=100,"
                f"x={x},y={y},"
                f"m={'0' if is_last else '1'};"
                f"{chunk}"
                "\033\\"
            )
            sys.stdout.write(cmd)
            sys.stdout.flush()
        return True
    except Exception:
        return False