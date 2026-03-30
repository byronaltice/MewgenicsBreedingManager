"""Color math utilities for the Breed Priority view.

Pure functions for hex color interpolation, parsing, and blending.
No Qt dependencies.
"""


class ColorUtils:
    """Hex color math — interpolation, parsing, blending."""

    @staticmethod
    def lerp(c1: str, c2: str, t: float) -> str:
        """Linearly interpolate between two hex colors (#rrggbb). t clamped to [0,1]."""
        t = max(0.0, min(1.0, t))
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
        return "#{:02x}{:02x}{:02x}".format(
            int(r1 + (r2 - r1) * t),
            int(g1 + (g2 - g1) * t),
            int(b1 + (b2 - b1) * t),
        )

    @staticmethod
    def lerp_step(c1: str, c2: str, total_steps: int, step: int) -> str:
        """Return interpolated color at *step* within a [1..total_steps] range.

        step=1 returns c1, step=total_steps returns c2.
        """
        if total_steps <= 1:
            return c2
        t = (step - 1) / (total_steps - 1)
        return ColorUtils.lerp(c1, c2, t)

    @staticmethod
    def parse_hex(c: str) -> tuple:
        """Parse a #rrggbb string to (r, g, b) integers."""
        return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)

    @staticmethod
    def blend(c1: str, c2: str, t: float) -> str:
        """Blend c1 toward c2 by factor t (0=c1, 1=c2)."""
        return ColorUtils.lerp(c1, c2, t)

    @staticmethod
    def derive_chip_bg(fg: str, theme_dark: str) -> str:
        """Derive a dark pill/chip background from a foreground color.

        Blends fg into theme_dark at 14% strength, producing a background that
        carries the hue of the foreground without competing with the text.
        """
        return ColorUtils.blend(theme_dark, fg, 0.14)
