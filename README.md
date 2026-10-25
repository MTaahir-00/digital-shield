# Digital Shield

**An accessible digital safety assistant for elderly and low-literacy users in Pakistan.**
It watches the screen for scams and phishing, warns the user in **Urdu + English with a spoken voice**,
and lets them get help with a simple **hand gesture** - no typing, no reading, no menus.

*Built for the Genesis hackathon (CSS Launch).*

## The problem
Online scams (fake bank / NADRA / BISP messages, phishing emails, fake "virus" pop-ups, prize and
"relative in trouble" WhatsApp messages) target people who struggle to read English or judge what is
safe. Existing tools assume the user can read a warning and use a settings menu.

## What it does
| Feature | How |
|---|---|
| **Auto-Protect** | Every ~2 s it reads the active window with OCR and checks it for scam behaviour. Shows a red warning in Urdu + English and **speaks it aloud**, with plain advice ("Never tell anyone your OTP"). |
| **Phishing emails inside Gmail / Outlook** | Checks the *sender* (e.g. "PayPal" sent from a gmail.com address), links, urgency, "Dear customer", risky attachments. Inbox list = each row judged alone; opened mail = judged as a whole. |
| **Scam websites & pop-ups** | Lookalike domains (`paypa1-secure.xyz`, `microsoft.com.verify-login.xyz`, `nadra-verify.com`), raw-IP / shortened / hidden links, fake virus & tech-support pop-ups, remote-access scams, fake investment and gambling sites. |
| **WhatsApp / chat scams** | BISP-Ehsaas prize scams, OTP/PIN requests, "I'm in trouble, send money". Friends asking for a wifi password or CNIC copy are *not* flagged. |
| **Gesture control (webcam)** | Held for ~2.5 s: **Explain** -> screenshot is sent to ChatGPT with a simple-Urdu prompt; **Human Help** -> screenshot + alert sent over WhatsApp to a trusted contact; **open palm** -> dismiss / continue. |
| **Few false alarms** | Judges *combinations* (ask + pressure + bad link...), not single words. Official domains (HBL, Meezan, NADRA, Google...) and AI/code/wiki windows are not flagged. |

## How it works
```
webcam -> MediaPipe hand landmarks -> RandomForest gesture model (+ open-palm geometry rule)
screen -> active-window screenshot -> OCR (Tesseract, English + Urdu) -> risk_engine.py -> warning overlay (UR + EN + voice)
```
`risk_engine.py` is a rule-based, context-aware detector (no cloud, pure Python) with a 59-case test suite.

## Setup (Windows)
1. Install **Python 3.12** and **Tesseract OCR** (UB Mannheim build; tick the Urdu language data; add to PATH).
2. `py -3.12 -m pip install -r requirements.txt`
3. Log in to **WhatsApp Web** and **ChatGPT** in your default browser (needed for the Human Help / Explain gestures).
4. `py -3.12 digital_shield_app.py`
5. In the app: enter the help contact's WhatsApp number (with `+92...`) -> **Save Settings** -> **Start Monitoring**.

## Try it safely
Open the harmless pages in `demo_test_pages/` in Chrome - four fake scams and one safe page.
Do not visit real scam sites to test.

## Tests
```
py -3.12 3_test_detection.py      # 59 detection cases (scams must flag, safe pages must not)
py -3.12 test_gesture_utils.py    # open-palm geometry check
```

## Train your own gestures (optional)
`1_collect_data.py` records samples (0 neutral, 1 ai_help, 2 human_help, 3 ignore) -> `2_train_model.py` trains `digital_shield_model.pkl`.

## Privacy
Detection runs on the user's own computer. Nothing is sent anywhere unless the user chooses *Explain* (ChatGPT) or
*Human Help* (WhatsApp). Screenshots are saved only in a local `screenshots/` folder (git-ignored).

## Limitations (honest)
Rule-based + OCR, not ML: it can miss brand-new scam wording or text OCR can't read. Gmail shows the sender address
only in an opened message's header. WhatsApp/ChatGPT automation depends on being logged in and the browser window.
Designed as a prototype safety aid, not a guarantee.

## Team
[Team name] - [member names] - [IBA ERP IDs are entered in the submission form]
