"""
DIGITAL SHIELD - STEP 3: TEST THE TEXT DETECTION
---------------------------------------------------
Run: python 3_test_detection.py

This is how you know Layer 1 (screen/OCR risk detection) actually works.
It is a RULE-BASED, CONTEXT-AWARE checker (scam behaviours + domains + email
senders), not a trained ML model
- so "training" it means adding a real phrase/pattern to risk_engine.py
whenever a scam gets past it, or a safe message gets wrongly flagged.

WORKFLOW WHEN YOU FIND A SCAM THE APP MISSED:
  1. Copy the exact wording (or the OCR text from activity_history.log /
     a screenshot in screenshots/) into TEST_CASES below as a new
     ("risky", "<the text>", "why it's dangerous") entry.
  2. Run this script - it will fail and tell you.
  3. Add the missing phrase(s) to CATEGORIES in risk_engine.py.
  4. Re-run this script until it passes. Now that scam type is covered
     for good, and you have a regression test proving it stays covered.

Do the same for anything SAFE that gets wrongly flagged (false positive) -
add it as a ("safe", "<text>", ...) case.
"""

from risk_engine import score_text

# label, sample OCR-like text, short description
TEST_CASES = [
    # ---- phishing emails ----
    ("risky", "Dear customer, your account will be suspended in 24 hours. "
              "Verify your account now by entering your password and OTP.",
     "classic bank phishing email"),
    ("risky", "PayPal: We detected unusual activity. Confirm your identity "
              "and login details immediately or your account will be locked.",
     "PayPal-style phishing"),
    ("risky", "Congratulations you have won $1,000,000 in the international "
              "lottery! Claim your prize now by sending a small processing fee.",
     "lottery / advance-fee scam"),
    ("risky", "Your parcel is on hold. Pay a small release fee via gift card "
              "to receive your package today.",
     "delivery / gift-card scam"),

    # ---- scam / fake websites ----
    ("risky", "FINAL NOTICE!!!! Your Amazon account has been locked due to "
              "suspicious activity. Click here to verify your account.",
     "fake e-commerce lockout page"),
    ("risky", "Visit http://192.168.55.201/login-secure to update your bank "
              "account number and password.",
     "raw-IP phishing link"),
    ("risky", "Get your free bet now! Deposit bonus, free spins, jackpot "
              "waiting. Register and bet at melbet today.",
     "gambling / betting site"),
    ("risky", "secure-paypal-login.xyz - enter your card number and cvv to "
              "restore access",
     "lookalike brand domain + suspicious TLD"),
    ("risky", "Guaranteed returns! Double your money in 7 days with our "
              "crypto investment plan. Invest now and earn daily profit.",
     "investment scam site"),

    # ---- pop-ups ----
    ("risky", "WARNING! Your computer is infected with 3 viruses. Call "
              "Microsoft support now at this number. Do not restart your computer.",
     "fake tech-support virus popup"),
    ("risky", "Click Allow to continue. Verify you are human. Your session "
              "will expire in 60 seconds, do not close this tab.",
     "fake browser permission / consent popup"),
    ("risky", "System has been compromised! Press OK to remove virus and "
              "call this number immediately.",
     "fake system alert popup"),

    # ---- safe text (must NOT be flagged) ----
    ("safe", "Welcome back! Here is your weekly newsletter with recipes and "
             "gardening tips.",
     "harmless newsletter"),
    ("safe", "Your order #4821 has shipped and will arrive Thursday. Track "
             "it on our website.",
     "normal shipping notice, no fee/urgency language"),
    ("safe", "Team meeting moved to 3pm tomorrow, see the calendar invite.",
     "normal work message"),
    ("safe", "Better luck next time! The weather today is warm with a "
             "gentle breeze.",
     "contains 'bet' inside 'Better' - must not trigger gambling category"),
    ("safe", "Please update your profile picture and bio on your account "
             "settings page whenever you have time.",
     "benign 'account'/'update' wording with no urgency or credential ask"),

    # ---- false positives caused by scanning the WHOLE desktop instead of
    # just the active window (a stray background tab's text - e.g. a
    # gambling site left open elsewhere - was leaking into the OCR of an
    # unrelated, currently-focused safe page) ----
    ("safe", "Claude by Anthropic - chat with Claude. Ask anything. "
             "1XBET Pakistan Betting company",
     "safe Claude tab with a stray gambling tab title leaking in - must not flag",
     "Your first chat with Claude - Google Chrome"),
    ("safe", "ChatGPT can make mistakes. Check important info. Available "
             "time slots for support call.",
     "safe ChatGPT tab, one incidental low-severity word only - must not flag",
     "ChatGPT - Google Chrome"),
    ("risky", "1XBET REGISTRATION Place your bet now on Cricket, Football, "
              "Casino, Live Betting, Jackpot",
     "the actual gambling site itself, multiple real gambling terms - must still flag",
     "1XBET Pakistan \u2013 Betting company - Google Chrome"),
    ("risky", "Please enter your password to verify your "
              "paypal-secure-login.xyz account",
     "real phishing even on a window title containing a safe-site hint - must still flag",
     "PayPal Account Verification - Google Chrome"),

    # =====================================================================
    # v2: PHISHING EMAILS INSIDE REAL WEBMAIL (Gmail / Outlook)
    # =====================================================================
    ("risky", "Urgent: Verify your PayPal account\nPayPal Support <support@paypa1-secure.xyz> to me\n"
              "Dear customer, we noticed unusual activity. Your account will be suspended within 24 hours "
              "unless you confirm your password. http://paypa1-secure.xyz/login\nReply Forward",
     "Gmail: opened phishing mail, fake PayPal sender + lookalike link",
     "Urgent: Verify your PayPal account - user@gmail.com - Gmail - Google Chrome"),
    ("risky", "Your statement\nMeezan Bank <alerts.meezan@gmail.com> to me\nPlease review the attached statement.\nReply Forward",
     "Gmail: bank name sent from a free gmail address (no scary words at all)",
     "Your statement - user@gmail.com - Gmail - Google Chrome"),
    ("risky", "Password expires today\nMicrosoft Security <security@microsoft.com.verify-login.xyz> to me\n"
              "Your password expires today. Click https://microsoft.com.verify-login.xyz/reset\nReply Forward",
     "Gmail: microsoft.com.<evil>.xyz subdomain trick",
     "Password expires today - user@gmail.com - Gmail - Google Chrome"),
    ("risky", "DHL Express <info@dhl-parcel-track.top> to me\nYour parcel is on hold. Pay a small release fee to "
              "receive your package.\nReply Reply all Forward",
     "Outlook: fake courier + release fee",
     "Package on hold - Mail - Outlook - Google Chrome"),
    ("risky", "Reply Forward\nBISP Ehsaas Kafaalat: you have been selected for Rs 25,000. "
              "Send your CNIC number to claim.",
     "email: BISP / Ehsaas lure asking for CNIC",
     "Ehsaas payment - user@gmail.com - Gmail - Google Chrome"),
    ("risky", "Inbox\nPrimary\nMeezan Bank Alert: your account has been suspended, enter your password to restore access\n"
              "Daraz your order shipped",
     "Gmail INBOX LIST: one phishing row among normal ones",
     "Inbox (3) - user@gmail.com - Gmail - Google Chrome"),
    ("risky", "Invoice\nAccounts <billing@company-docs.top> to me\nDear user, open the attached invoice.html to see "
              "your invoice. Your account will be closed immediately or legal action follows.\nReply Forward",
     "email: html attachment lure + threat",
     "Invoice - user@gmail.com - Gmail - Google Chrome"),

    # ---- webmail messages that are SAFE (must not be flagged) ----
    ("safe", "Security alert\nGoogle <no-reply@accounts.google.com> to me\nA new sign-in on Windows. We noticed a new "
             "sign-in to your Google Account. If this was you, you don't need to do anything. If not, we'll help "
             "you secure your account. https://accounts.google.com/AccountChooser\nReply Forward",
     "Gmail: real Google security alert from the official domain",
     "Security alert - user@gmail.com - Gmail - Google Chrome"),
    ("safe", "Your OTP is 482913. Do not share this OTP with anyone. HBL will never ask for your PIN or password.",
     "bank's own OTP notice that WARNS not to share (negation)",
     "Your HBL OTP - user@gmail.com - Gmail - Google Chrome"),
    ("safe", "Daraz <no-reply@daraz.pk> to me\nDear customer, your order has shipped. Track your parcel here "
             "https://www.daraz.pk/track. Thank you for shopping!\nReply Forward",
     "Gmail: normal Daraz shipping email using 'Dear customer'",
     "Your order has shipped - user@gmail.com - Gmail - Google Chrome"),
    ("safe", "Inbox\nPrimary\nSocial\nPromotions\nDaraz Your order has shipped\nLinkedIn 5 new jobs for you\n"
             "Netflix New arrivals this week\nHBL Your monthly statement is ready\n"
             "Bank Alfalah Verify your account details securely",
     "Gmail INBOX LIST of ordinary mail",
     "Inbox (2) - user@gmail.com - Gmail - Google Chrome"),
    ("safe", "Gmail Sign in Enter your password Forgot password? Next Create account",
     "Gmail SIGN-IN page (asks for password legitimately)",
     "Gmail - Google Chrome"),
    ("safe", "Microsoft account team <account-security-noreply@accountprotection.microsoft.com> to me\n"
             "Security info was added to your account. If this wasn't you, review recent activity "
             "https://account.microsoft.com/security\nReply Forward",
     "Outlook: real Microsoft account email",
     "Security info added - Mail - Outlook - Google Chrome"),
    ("safe", "Ali Khan <ali.khan@gmail.com> to me\nSalam! Are you coming to the family dinner on Friday? "
             "Please bring your laptop.\nReply Forward",
     "Gmail: ordinary mail from a friend",
     "Family dinner - user@gmail.com - Gmail - Google Chrome"),
    ("safe", "Ali Khan <ali.khan@gmail.com> to me\nCan you send me the wifi password? Thanks!\nReply Forward",
     "friend asking for the WIFI password is not a credential scam",
     "Wifi - user@gmail.com - Gmail - Google Chrome"),

    # =====================================================================
    # v2: WHATSAPP / CHAT SCAMS
    # =====================================================================
    ("risky", "Unknown +92 300 1234567\nAssalam o alaikum, I am from BISP office. You have won Rs 50,000 prize money "
              "under Ehsaas program.\nPlease send your CNIC number and OTP code to receive payment.",
     "WhatsApp: fake BISP prize asking for CNIC + OTP",
     "WhatsApp - Google Chrome"),
    ("risky", "Beta I am in trouble, my phone is broken. Please send money to this Easypaisa account urgently",
     "WhatsApp: 'relative in trouble' money scam",
     "WhatsApp - Google Chrome"),
    ("safe", "Mama\nDinner is at 8 tonight\nAbu\nOk I will bring the cake\nAli\nCan someone pick me up at 6?",
     "WhatsApp: normal family chat",
     "WhatsApp - Google Chrome"),
    ("safe", "Bhai send money on easypaisa for tonight's dinner, I will return it tomorrow",
     "WhatsApp: friends splitting a bill",
     "WhatsApp - Google Chrome"),
    ("safe", "Eid Mubarak ho sab ko! Allah aap sab ko khushiyan de",
     "WhatsApp: 'mubarak ho' greeting is not a prize scam",
     "WhatsApp - Google Chrome"),

    # =====================================================================
    # v2: URDU / ROMAN URDU
    # =====================================================================
    ("risky", "Aap ka account band ho jaye ga. Foran apna PIN aur OTP share karen",
     "Roman Urdu: account threat + asks for PIN/OTP", None),
    ("risky", "آپ کا اکاؤنٹ بند ہو جائے گا۔ فوری اپنا پاسورڈ بھیجیں",
     "Urdu script: account threat + asks for password", None),
    ("safe", "آج موسم بہت اچھا ہے اور بازار میں رش ہے",
     "ordinary Urdu sentence", None),

    # =====================================================================
    # v2: WEBSITES, POP-UPS, LOOKALIKE DOMAINS
    # =====================================================================
    ("risky", "Your computer is infected. Call support now and install AnyDesk so our technician can fix it.",
     "tech-support scam that asks for remote access", None),
    ("risky", "Welcome to Meezan Bank. Enter your password and OTP to log in. http://meezanbank-secure-login.top/login",
     "fake Meezan Bank login page (lookalike domain)",
     "Meezan Bank Login - Google Chrome"),
    ("safe", "Welcome to Meezan Bank. Enter your password and OTP to log in. https://www.meezanbank.com/login",
     "the REAL Meezan Bank login page (official domain)",
     "Meezan Bank Login - Google Chrome"),
    ("safe", "Welcome to HBL Internet Banking. Enter your password and OTP to log in. https://www.hblibank.com.pk/home",
     "the real HBL internet banking page",
     "HBL Internet Banking - Google Chrome"),
    ("risky", "Enter your password at www.gooogle.com/login to continue",
     "misspelled Google domain asking for a password", None),
    ("risky", "Click http://www.google.com@evil-site.xyz/login to verify your account and enter your password",
     "'@' trick hides the real destination", None),
    ("risky", "NADRA notice: your CNIC will be blocked. Verify at nadra-verify.com and enter your CNIC number now",
     "fake NADRA site", None),
    ("safe", "Visit https://www.nadra.gov.pk for CNIC services and locate your nearest NADRA center",
     "the real NADRA site", None),
    ("safe", "Pay Rs. 1,999 cash on delivery. Limited time offer! Free gift card with purchase. Hurry!!!!",
     "normal shop page with marketing hype", "Daraz.pk - Google Chrome"),
    ("safe", "Verify you are human by completing the action below. Checking if the site connection is secure",
     "Cloudflare 'verify you are human' check (single phrase)", "Just a moment... - Google Chrome"),
    ("safe", "How to avoid phishing scams: never share your password or OTP. Scammers say your account will be "
             "suspended within 24 hours or you must pay a fee.",
     "news / awareness article ABOUT scams", "Dawn News - Google Chrome"),
    ("safe", "Windows help https://support.microsoft.com/en-us/windows get started. Visit www.microsoft.com. "
             "Enter your password to sign in.",
     "normal Microsoft page ('t.co' used to match inside microsof-t.co-m)", None),
    ("safe", "Visit www.example.com for details. See styles.menu and notes.support files, laptop.top shelf",
     "'.menu' '.support' '.top' text fragments are not links", None),

    # ---- windows that DISCUSS scams must never be flagged ----
    ("safe", "SCAM_WORDS = password otp lottery you have won call microsoft support do not restart your computer",
     "source code in an editor", "risk_engine.py - Visual Studio Code"),
    ("safe", "This looks like a phishing scam. The link paypal-secure-login.xyz is fake. Do not enter your password.",
     "AI chat explaining a scam (after AI Help)", "ChatGPT - Google Chrome"),
]


def run():
    passed = 0
    failed = []
    for case in TEST_CASES:
        expected, text, description = case[0], case[1], case[2]
        window_title = case[3] if len(case) > 3 else None
        result = score_text(text, window_title=window_title)
        ok = result["status"] == expected
        mark = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed.append((description, expected, result["status"], result.get("reason_en", "")))
        print(f"[{mark}] {description}  (expected={expected}, got={result['status']}, "
              f"severity={result.get('severity')}, matched={result.get('matched')})")

    print()
    print(f"{passed}/{len(TEST_CASES)} test cases passed.")
    if failed:
        print("\nFAILURES - fix these before trusting the detector on new scam types:")
        for description, expected, got, reason in failed:
            print(f"  - {description}: expected '{expected}', got '{got}' ({reason})")
    else:
        print("All good. Add new real-world scam text you encounter as a new "
              "test case above to keep growing coverage.")


if __name__ == "__main__":
    run()
