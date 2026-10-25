"""
DIGITAL SHIELD - GESTURE HELPERS
-----------------------------------
normalize_landmarks()  -> feature vector fed into the trained RandomForest
                           model (ai_help / human_help / neutral).
is_open_palm()          -> a RULE-BASED (not ML) check for "all 5 fingers
                           extended and spread". Used as an immediate,
                           always-available fallback for the "ignore /
                           continue" gesture.

WHY THIS EXISTS: gesture_data.csv only ever had samples for
neutral / ai_help / human_help - never for "ignore" (0 rows). That means
digital_shield_model.pkl's classes_ literally does not include "ignore",
so no amount of holding a flat palm up would ever be predicted as
"ignore" - the model can't predict a class it was never shown. That is
why it looked ignored / like it "wasn't working".

Two ways to fix it, both included:
  1. IMMEDIATE FIX (this file): a flat open palm is detected with simple
     hand-landmark geometry, independent of the trained model. Works the
     first time you run the app, no retraining needed.
  2. PROPER FIX (optional, better long-term): run `python 1_collect_data.py`
     and press '3' ~80-100 times while holding your actual "ignore"
     gesture (varying angle/distance/lighting), then re-run
     `python 2_train_model.py`. Once gesture_data.csv has real "ignore"
     samples, the ML model will also learn your specific gesture, and
     digital_shield_app.py will use the trained model as the primary
     signal for ai_help/human_help/ignore while keeping the geometric
     check as a safety net.
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
