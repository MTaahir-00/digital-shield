"""
DIGITAL SHIELD - GESTURE HELPERS
-----------------------------------

"""

FINGER_TIPS = [8, 12, 16, 20]     # index, middle, ring, pinky tips
FINGER_PIPS = [6, 10, 14, 18]     # matching PIP joints
WRIST = 0
PALM_REF = 9                       # middle-finger MCP, used for scale
THUMB_TIP = 4
THUMB_MCP = 2
PINKY_MCP = 17


def _dist(a, b):
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5


def normalize_landmarks(hand_landmarks):
    """Translation + scale invariant hand-shape fingerprint (63 numbers) fed
    to the trained classifier. Must stay identical between data collection,
    training, and inference."""
    coords = [[lm.x, lm.y, lm.z] for lm in hand_landmarks.landmark]
    wrist = coords[0]
    relative = [[p[0] - wrist[0], p[1] - wrist[1], p[2] - wrist[2]] for p in coords]
    ref_x, ref_y, ref_z = relative[9]
    scale = (ref_x ** 2 + ref_y ** 2 + ref_z ** 2) ** 0.5
    if scale == 0:
        scale = 1e-6
    normalized = []
    for p in relative:
        normalized.extend([p[0] / scale, p[1] / scale, p[2] / scale])
    return normalized


def is_open_palm(hand_landmarks, min_fingers_extended=4, spread_ratio=0.4):
    """True if this looks like a flat, open, spread-out palm (the
    universal 'stop / continue / it's fine' gesture), regardless of what
    the trained model thinks. Pure geometry - works with zero training
    data.

    - "extended": each fingertip is meaningfully farther from the wrist
      than its PIP joint (finger is straight, not curled into a fist).
    - "spread": fingertips are reasonably far apart from each other
      relative to palm size (rules out e.g. all fingers extended but
      pressed together, or a pointing gesture with 1 finger up).
    """
    lm = hand_landmarks.landmark
    wrist = lm[WRIST]
    palm_size = _dist(lm[WRIST], lm[PALM_REF]) or 1e-6

    extended = 0
    for tip_idx, pip_idx in zip(FINGER_TIPS, FINGER_PIPS):
        if _dist(lm[tip_idx], wrist) > _dist(lm[pip_idx], wrist) * 1.15:
            extended += 1

    thumb_extended = _dist(lm[THUMB_TIP], lm[PINKY_MCP]) > _dist(lm[THUMB_MCP], lm[PINKY_MCP])
    if thumb_extended:
        extended += 1

    if extended < min_fingers_extended:
        return False

    tips = [lm[i] for i in FINGER_TIPS]
    gaps = [_dist(tips[i], tips[i + 1]) for i in range(len(tips) - 1)]
    avg_gap = sum(gaps) / len(gaps)
    return (avg_gap / palm_size) > spread_ratio
