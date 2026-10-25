"""Quick sanity check for gesture_utils.is_open_palm() using synthetic
landmark coordinates (no camera / mediapipe runtime needed to test the
math itself). Run: python test_gesture_utils.py
"""

from gesture_utils import is_open_palm


class P:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class Hand:
    def __init__(self, points):
        self.landmark = points


def make(points_dict):
    pts = [P(0, 0) for _ in range(21)]
    for i, (x, y) in points_dict.items():
        pts[i] = P(x, y)
    return Hand(pts)


# Open, spread palm: wrist at bottom, fingers fanned out upward/outward.
open_palm = make({
    0: (0.50, 0.90),   # wrist
    9: (0.50, 0.55),   # middle MCP (palm ref)
    2: (0.35, 0.70), 3: (0.30, 0.60), 4: (0.25, 0.50),     # thumb
    5: (0.42, 0.60), 6: (0.40, 0.45), 7: (0.39, 0.32), 8: (0.38, 0.20),   # index
    9: (0.50, 0.60), 10: (0.50, 0.42), 11: (0.50, 0.28), 12: (0.50, 0.15),  # middle
    13: (0.58, 0.60), 14: (0.60, 0.45), 15: (0.61, 0.32), 16: (0.62, 0.20),  # ring
    17: (0.66, 0.65), 18: (0.68, 0.52), 19: (0.69, 0.42), 20: (0.70, 0.32),  # pinky
})

# Closed fist: all tips curled back near the palm/PIP joints.
fist = make({
    0: (0.50, 0.90),
    9: (0.50, 0.55),
    2: (0.35, 0.72), 3: (0.34, 0.70), 4: (0.40, 0.68),
    5: (0.42, 0.60), 6: (0.40, 0.55), 7: (0.41, 0.58), 8: (0.42, 0.60),
    9: (0.50, 0.60), 10: (0.50, 0.50), 11: (0.50, 0.54), 12: (0.50, 0.58),
    13: (0.58, 0.60), 14: (0.60, 0.50), 15: (0.60, 0.54), 16: (0.60, 0.58),
    17: (0.66, 0.65), 18: (0.68, 0.55), 19: (0.68, 0.58), 20: (0.68, 0.60),
})

# One finger pointing up (index only extended) - should NOT count as open palm.
pointing = make({
    0: (0.50, 0.90),
    9: (0.50, 0.55),
    2: (0.35, 0.72), 3: (0.34, 0.70), 4: (0.40, 0.68),
    5: (0.42, 0.60), 6: (0.40, 0.45), 7: (0.39, 0.30), 8: (0.38, 0.15),
    9: (0.50, 0.60), 10: (0.50, 0.50), 11: (0.50, 0.54), 12: (0.50, 0.58),
    13: (0.58, 0.60), 14: (0.60, 0.50), 15: (0.60, 0.54), 16: (0.60, 0.58),
    17: (0.66, 0.65), 18: (0.68, 0.55), 19: (0.68, 0.58), 20: (0.68, 0.60),
})

cases = [("open_palm", open_palm, True), ("fist", fist, False), ("pointing", pointing, False)]
passed = 0
for name, hand, expected in cases:
    got = is_open_palm(hand)
    ok = got == expected
    passed += ok
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: expected={expected}, got={got}")
print(f"{passed}/{len(cases)} passed")
