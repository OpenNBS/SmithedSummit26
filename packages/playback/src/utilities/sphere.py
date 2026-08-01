import math
from typing import Iterator, Tuple


def sphere(radius: float, density: float = 1.0) -> Iterator[Tuple[float, float, float]]:
    """Yield evenly distributed points on a sphere's surface.

    ``density`` is points per unit of surface area. The default of 1 yields
    approximately one point per grid unit occupied by the sphere's surface
    (``round(4 * pi * radius² * density)`` points total).
    """
    if radius <= 0 or density <= 0:
        return

    n = max(1, round(4 * math.pi * radius * radius * density))
    # Golden angle: successive points are maximally spaced on each ring
    golden_angle = math.pi * (3 - math.sqrt(5))

    for i in range(n):
        # Equal-area bands from north to south pole
        y = 1 - (2 * i + 1) / n
        r_xy = math.sqrt(max(0.0, 1 - y * y))
        theta = golden_angle * i

        yield (
            math.cos(theta) * r_xy * radius,
            y * radius,
            math.sin(theta) * r_xy * radius,
        )
