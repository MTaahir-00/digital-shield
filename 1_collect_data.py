"""
DIGITAL SHIELD - STEP 1: DATA COLLECTION
------------------------------------------
Records hand-gesture samples for the 4 Digital Shield states.
Run: python 1_collect_data.py
Press 0/1/2/3 while holding each gesture steady. Press 'q' to quit.

  0 = neutral    (relaxed hand, everyday movement, near-miss poses)
  1 = ai_help     (deliberate gesture -> "Explain this to me")
  2 = human_help  (deliberate gesture -> contact human/cybersecurity help)
  3 = ignore      (deliberate gesture -> dismiss a warning / continue)

NOTE: your existing gesture_data.csv already has neutral/ai_help/human_help
samples from before, that data is still valid and does not need to be
re-recorded. You only need to run this again to add 'ignore' samples
(60-100+), then re-run 2_train_model.py. New rows are appended, so just
run this script and press '3' a bunch of times while holding the ignore
gesture; existing rows are left alone.

NOTE 2: gesture_data.csv had ZERO 'ignore' rows, so digital_shield_model.pkl
was trained without that class and can never predict it, no matter how
long you hold the gesture - that's the bug where the palm gesture seemed
to be "ignored". gesture_utils.is_open_palm() now covers this immediately
with a rule-based (non-ML) check, so the app works without retraining.
Recording real samples here and retraining is still worth doing later -
it teaches the model your exact gesture/speed and makes recognition more
robust than geometry alone, but it's optional now, not required.

Record 60-100+ samples per gesture, varying angle/distance/lighting.
For 'neutral', also include near-miss poses (resting fist on chin etc)
to reduce false triggers, same lesson learned in the original project.
"""

import cv2
import mediapipe as mp
import csv
import os

GESTURE_LABELS = {
    ord('0'): 'neutral',
    ord('1'): 'ai_help',
    ord('2'): 'human_help',
    ord('3'): 'ignore',
}

DATA_FILE = 'gesture_data.csv'

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False, max_num_hands=1,
    min_detection_confidence=0.7, min_tracking_confidence=0.7
)


def normalize_landmarks(hand_landmarks):
    """Translation + scale invariant hand-shape fingerprint (63 numbers).
    Identical logic to the original emergency-alert project — must stay
    identical between collection and inference."""
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


file_exists = os.path.isfile(DATA_FILE)
csv_file = open(DATA_FILE, mode='a', newline='')
csv_writer = csv.writer(csv_file)
if not file_exists:
    csv_writer.writerow(['label'] + [f'f{i}' for i in range(63)])

cap = cv2.VideoCapture(0)
sample_counts = {label: 0 for label in GESTURE_LABELS.values()}
print("Webcam started.")
key_instructions = " | ".join(f"{chr(k)} = {label}" for k, label in GESTURE_LABELS.items())
print(f"Press {key_instructions} | q = quit")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        continue
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)
    current_landmarks = None

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            current_landmarks = hand_landmarks

    y_offset = 30
    for label, count in sample_counts.items():
        cv2.putText(frame, f'{label}: {count}', (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        y_offset += 30
    cv2.putText(frame, key_instructions + ' | q = quit', (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.imshow('Digital Shield - Data Collection', frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    if key in GESTURE_LABELS and current_landmarks is not None:
        label = GESTURE_LABELS[key]
        features = normalize_landmarks(current_landmarks)
        csv_writer.writerow([label] + features)
        sample_counts[label] += 1
        print(f"Saved sample for '{label}' (total: {sample_counts[label]})")

cap.release()
cv2.destroyAllWindows()
csv_file.close()
print("Data collection finished. Saved to", DATA_FILE)
