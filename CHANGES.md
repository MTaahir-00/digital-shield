# v2 - real scam + phishing-email detection, far fewer false alarms

## Why normal sites were flagged
The old engine fired on ONE scary word. "password" on any login page, a bank's own
"do not share your OTP" notice, and a bug where the shortener "t.co" matched inside
"microsof-t.co-m" flagged almost every page. Gmail was also treated as "safe" by title,
so a phishing mail opened inside Gmail slipped through.

## What changed
- `risk_engine.py` rewritten. It now judges COMBINATIONS (ask for password/OTP/CNIC/money
  + pressure/lure/bad link/fake sender) instead of single words.
- Real link analysis: proper hostnames (no substring bugs), raw IPs, shorteners, odd TLDs,
  "@" tricks, misspelled brands (gooogle.com), and brand imitation
  (paypa1-secure.xyz, microsoft.com.verify-login.xyz, nadra-verify.com).
  Official domains list includes Pakistani banks/services (HBL, UBL, Meezan, Alfalah,
  Easypaisa, JazzCash, NADRA, FBR, BISP, PTA) - extend `OFFICIAL` as needed.
- Email awareness (Gmail/Outlook/Yahoo): checks the SENDER ("PayPal" <x@gmail.com>),
  links, urgency, "Dear customer", risky attachments. Inbox list = each row judged alone;
  opened message = judged as a whole. Real company mail from its own domain is left alone.
- WhatsApp/Messenger chat scams: BISP/Ehsaas prizes, "I'm in trouble send money",
  OTP/PIN requests, fake SIM-block notices. Friends asking for wifi password / CNIC copy /
  "send money on easypaisa" are NOT flagged.
- Urdu + Roman-Urdu scam wording. OCR also reads Urdu if Tesseract's Urdu pack
  (`urd`) is installed; otherwise it silently stays English-only.
- Warning now includes plain advice in Urdu + English ("Do not click any link...",
  "Never tell anyone your OTP"), spoken aloud as before. Overlay resizes to fit.
- AI/Claude/ChatGPT windows, code editors and wikis are never flagged. Awareness
  articles about scams are not flagged. Gambling now needs 3+ gambling terms.
- App: ChatGPT prompt now includes what Digital Shield found; capture area clamped to the
  screen; email scans skip the left folder column; overlay window is excluded from scans.

## Test it
`python 3_test_detection.py` -> 59/59 (phishing mails, Gmail/Outlook, WhatsApp, Urdu,
lookalike domains, plus safe cases that must NOT be flagged).
When a scam slips through: add its text as a new case, run, add the phrase, re-run.

## Honest limits
Rule-based + OCR, not ML: it can miss new wording or text OCR cannot read. Gmail shows
the sender address only in the message header - if the address is hidden, the sender
check cannot run (wording/link checks still do). Always keep Explain / Human Help available.

---
# Earlier changes
# What changed, and why

## 1. "How do we know it works on phishing emails / scam sites / popups?"
Layer 1 was, and still is, a **rule-based checker** (keywords + patterns) -
it's not a trained ML model, so there's nothing to "train" in the ML sense.
What you *can* do is grow its coverage and prove it still works. That's
what's new:

- `risk_engine.py` - the detection logic, pulled out of the app into its
  own file with no OCR/GUI/Windows dependencies, so it can be tested on
  its own.
- `3_test_detection.py` - a labeled test suite: real-style phishing
  emails, fake bank/e-commerce lockout pages, tech-support virus popups,
  fake-permission popups, gambling sites, investment scams, and safe
  messages that must NOT be flagged. Run it any time:
  ```
  python 3_test_detection.py
  ```
  When a real scam gets past the app, copy its text into `TEST_CASES` in
  that file as a new case, run the script (it'll fail), add the missing
  phrase/pattern to `CATEGORIES` in `risk_engine.py`, and re-run until it
  passes. Now that scam type is covered for good and you have a
  regression test proving it stays covered.
- Added new categories beyond the original 6: `tech_support_scam` (fake
  virus/"call Microsoft support" popups), `fake_popup` ("click Allow to
  continue", fake session-expiry popups), `investment_scam` ("guaranteed
  returns"), and `phishing_domain` (lookalike brand domains like
  `paypal-secure-login.xyz`).

## 2. On-screen danger display
Added `DangerOverlay` in `digital_shield_app.py` - a borderless,
always-on-top window that pops up centered near the top of the screen
over *whatever the user is doing* (not just inside the main app window,
which could be minimized/behind something). Shows English + Urdu
together, the flagged reason, and the same three response buttons.

## 3. Optimized detection
- Keyword matching now uses **word-boundary regex** instead of plain
  substring matching, so e.g. "Better luck next time" no longer falsely
  matches the gambling category via "bet" (this was a real bug in the
  old code - see the test case for it in `3_test_detection.py`).
- Added a severity score (`low`/`medium`/`high`) instead of a flat
  yes/no, shown in the overlay.
- Added link/domain heuristics: shortened-URL services (bit.ly etc.),
  suspicious TLDs (.xyz, .top, .click...), and brand-lookalike hyphenated
  domains, on top of the existing raw-IP-address check.
- Added a cheap **screen-change check** (`screen_changed` /
  `make_thumb`) that compares a tiny thumbnail of the current screen to
  the last one before running OCR at all. OCR (the expensive part) only
  runs when the screen actually changed, which is why the background
  scan interval could safely drop from 6s to 2s - it's not doing more
  work, just checking more often and mostly skipping the expensive part.

## 4. Urdu + English together
The scan result panel and the new overlay both show an English line and
an Urdu line together now, instead of Urdu-only.

## 5. Automatic detection from launch
This was already wired up in your code (`self.root.after(3000,
self.auto_scan_tick)`), just delayed 3s and quiet unless something is
flagged - if it looked like nothing was happening, check that Tesseract
OCR is actually installed and on PATH, since without it every scan
returns "could not check automatically". The startup delay is now 400ms
and there's an "Auto-Protect: ON" indicator in the header so it's clear
it's running without needing "Check My Screen".

## 6. The open-palm "ignore/continue" gesture
Root cause: `gesture_data.csv` has **zero** `ignore` samples (checked -
206 ai_help, 205 neutral, 205 human_help, 0 ignore), so
`digital_shield_model.pkl` was trained on only 3 classes. A model can
never predict a class it was never shown, no matter how long you hold
the gesture - that's why it looked "ignored" and let you re-scan instead.

Fix: `gesture_utils.py` adds `is_open_palm()`, a rule-based (no training
needed) check using hand-landmark geometry - counts extended fingers and
checks they're spread apart. It's used as a fallback in
`digital_shield_app.py` whenever the trained model doesn't confidently
say `ai_help` or `human_help`. This works immediately, with the model
you already have.

If you still want the ML model to also learn your specific gesture
later (more robust than geometry alone), run `1_collect_data.py`, press
`3` ~80-100 times holding your ignore gesture, then re-run
`2_train_model.py`. Not required anymore, just optional.

## 7. False positives on safe sites (Claude, ChatGPT, etc.) + "gambling" overused
Root cause found in the screenshots: both the on-demand scan and the
background auto-scan were grabbing the **entire desktop** (`ImageGrab.grab()`
with no bounding box), so OCR also picked up text from every *other* window
on screen - taskbar previews, alt-tab thumbnails, and especially any other
browser tab that happened to still be open (e.g. a 1XBET tab left open in
the background kept getting OCR'd and flagged even while the *active* tab
was Claude or ChatGPT). That's why nearly every alert mentioned gambling
regardless of what site was actually being viewed.

Fixes, all in `digital_shield_app.py` / `risk_engine.py`:
- New `capture_active_window()` grabs only the **foreground window's**
  bounding box (via `pygetwindow.getActiveWindow()`), not the whole desktop.
  Used by the background auto-scan, "Check My Screen", and the AI/Human-help
  screenshots. If no usable foreground window is found, the auto-scan just
  waits for the next tick instead of falling back to a full-desktop grab.
- `risk_engine.score_text()` now takes an optional `window_title` and:
  - Requires **more than one** keyword occurrence (or a severity ≥ 2
    finding) before calling anything "risky" - a single stray low-severity
    word (one gambling term, one odd link) is now treated as noise, not a
    verdict.
  - Dampens weak/low-severity matches when the foreground window belongs to
    a well-known safe site (Claude, ChatGPT, Google, Wikipedia, GitHub,
    Microsoft, YouTube, Gmail) - a real high-severity finding (actual
    password/OTP/payment request on the page) still fires regardless.
  - Correctly strips the browser's own name (e.g. "- Google Chrome") from
    the window title first, so "Google Chrome" doesn't itself get
    mistaken for a match against the "google" safe-site hint on every
    single Chrome tab, including genuinely bad ones.
- Added regression tests for all of the above to `3_test_detection.py`
  (a stray gambling mention alongside a safe title -> safe; the real
  gambling site itself, with multiple gambling terms -> still risky).

## 8. WhatsApp "Human Help" wasn't actually sending the screenshot
Root cause: `web.whatsapp.com/send?phone=...&text=...` can only pre-fill
**text** into the chat box - there's no URL parameter for attaching an
image. The old code put the screenshot's local file *path* into that text
(`"...screenshot was saved locally at: screenshots\auto_risk_...png"`),
which is meaningless to whoever receives the WhatsApp message since it's a
path on the user's own PC, not the picture.

Fix: `_trigger_human_help` now copies the actual screenshot image to the
clipboard first (the same `_copy_image_to_clipboard` helper already used
for AI Help), then, once the WhatsApp window is focused, pastes it with
Ctrl+V and types a short caption before sending - so the cybersecurity
contact actually receives the image, not just a local file path.

## Sanity tests included
- `python 3_test_detection.py` - 17/17 passing, covers phishing emails,
  scam sites, popups, gambling, and false-positive guards.
- `python test_gesture_utils.py` - synthetic geometry check that
  `is_open_palm` correctly says yes to an open spread hand and no to a
  fist or a pointing finger.
