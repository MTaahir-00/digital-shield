"""
DIGITAL SHIELD - STEP 2: TRAIN MODEL
--------------------------------------
Run: python 2_train_model.py
Reads gesture_data.csv, trains a RandomForest classifier, saves
digital_shield_model.pkl. Prints cross-validated accuracy + confusion
matrix.
"""

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import pickle

DATA_FILE = 'gesture_data.csv'
MODEL_FILE = 'digital_shield_model.pkl'

data = pd.read_csv(DATA_FILE)
print(f"Loaded {len(data)} samples total.")
print(data['label'].value_counts())
print()

X = data.drop('label', axis=1)
y = data['label']

min_class_count = data['label'].value_counts().min()
if min_class_count < 5:
    print(f"NOTE: smallest class has only {min_class_count} sample(s) — "
          f"need 5+ per class for cross-validation. Collect more data first.")
else:
    cv_model = RandomForestClassifier(n_estimators=200, random_state=42)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(cv_model, X, y, cv=skf)
    print("Cross-validation accuracy:", ", ".join(f"{s*100:.1f}%" for s in cv_scores))
    print(f"Average: {cv_scores.mean()*100:.1f}%")
    print()

try:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)
except ValueError:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)

model = RandomForestClassifier(n_estimators=200, random_state=42)
model.fit(X_train, y_train)
predictions = model.predict(X_test)
print(f"Held-out test accuracy: {accuracy_score(y_test, predictions)*100:.1f}%")
print(classification_report(y_test, predictions))

labels_sorted = sorted(y.unique())
cm = confusion_matrix(y_test, predictions, labels=labels_sorted)
print("Confusion matrix (rows=actual, cols=predicted):", labels_sorted)
print(cm)

final_model = RandomForestClassifier(n_estimators=200, random_state=42)
final_model.fit(X, y)
with open(MODEL_FILE, 'wb') as f:
    pickle.dump(final_model, f)
print(f"Saved {MODEL_FILE}. Run digital_shield_app.py next.")
