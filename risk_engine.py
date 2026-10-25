"""
DIGITAL SHIELD - RISK ENGINE (Layer 1 logic, no OCR/GUI/Windows deps)
----------------------------------------------------------------------

"""

import re
import hashlib

# ----------------------------------------------------------------------
# Fixed messages (the app imports these names)
# ----------------------------------------------------------------------
GENERIC_EN_WARNING = "Stop! This may be a scam. Do you want help?"
GENERIC_URDU_WARNING = "رک جائیں! یہ چیز مشکوک ہو سکتی ہے۔ کیا آپ مدد چاہتے ہیں؟"
SAFE_EN_MESSAGE = "This screen looks safe."
SAFE_URDU_MESSAGE = "یہ اسکرین محفوظ نظر آتی ہے۔"
UNKNOWN_EN_MESSAGE = "Could not check automatically. If unsure, press 'Explain'."
UNKNOWN_URDU_MESSAGE = (
    "میں خود کار طریقے سے چیک نہیں کر سکا۔ اگر یقین نہیں تو 'وضاحت' پر دبائیں۔"
)

HEADLINES = {
    "email": ("Stop! This email looks FAKE (phishing).",
              "رک جائیں! یہ ای میل جعلی (فشنگ) لگتی ہے۔"),
    "chat": ("Stop! This message looks like a scam.",
             "رک جائیں! یہ پیغام فراڈ لگتا ہے۔"),
    "tech_support": ("Stop! This is a FAKE warning. Do not call or click.",
                     "رک جائیں! یہ جعلی وارننگ ہے۔ نہ کال کریں نہ کلک کریں۔"),
    "gambling": ("This looks like a gambling site.",
                 "یہ جوئے کی ویب سائٹ لگتی ہے۔"),
    "generic": (GENERIC_EN_WARNING, GENERIC_URDU_WARNING),
}

# signal -> (English reason, Urdu reason)
REASONS = {
    "impersonation": ("The web address or sender is pretending to be a real company.",
                      "ویب ایڈریس یا بھیجنے والا کسی اصل کمپنی کا جھوٹا نام استعمال کر رہا ہے۔"),
    "ask_credentials": ("It is asking for your password, OTP, PIN, CNIC or card details.",
                        "یہ آپ سے پاسورڈ، او ٹی پی، پن، شناختی کارڈ یا کارڈ کی تفصیلات مانگ رہا ہے۔"),
    "ask_money": ("It is asking you to send money or pay a fee.",
                  "یہ آپ سے پیسے بھیجنے یا فیس دینے کا کہہ رہا ہے۔"),
    "ask_remote": ("It wants you to install an app that lets a stranger control your computer.",
                   "یہ آپ سے ایسی ایپ انسٹال کروانا چاہتا ہے جس سے اجنبی آپ کا کمپیوٹر چلا سکے۔"),
    "fake_alert": ("It looks like a fake virus warning or fake pop-up.",
                   "یہ جعلی وائرس وارننگ یا جعلی پاپ اپ لگتا ہے۔"),
    "lure": ("It promises a prize, job, loan or free money.",
             "یہ انعام، نوکری، قرض یا مفت رقم کا لالچ دے رہا ہے۔"),
    "investment": ("It promises guaranteed profit.",
                   "یہ یقینی منافع کا وعدہ کر رہا ہے۔"),
    "link": ("It has a suspicious or disguised link.",
             "اس میں ایک مشکوک یا چھپا ہوا لنک ہے۔"),
    "pressure": ("It is trying to scare or rush you.",
                 "یہ آپ کو ڈرا کر یا جلدی کروا کر فیصلہ کروانے کی کوشش کر رہا ہے۔"),
    "soft_ask": ("It asks you to 'verify' or 'update' your account details.",
                 "یہ آپ سے اکاؤنٹ کی تفصیلات 'تصدیق' یا 'اپ ڈیٹ' کرنے کا کہہ رہا ہے۔"),
    "attachment": ("It pushes you to open a risky attachment.",
                   "یہ آپ کو خطرناک فائل کھولنے پر زور دے رہا ہے۔"),
    "greeting": ("It does not use your name (\"Dear customer\").",
                 "اس میں آپ کا نام نہیں ہے (\"محترم صارف\")۔"),
    "gambling": ("This looks like a gambling / betting site.",
                 "یہ جوئے یا شرط لگانے والی ویب سائٹ لگتی ہے۔"),
}
REASON_ORDER = ["impersonation", "ask_credentials", "ask_money", "ask_remote",
                "fake_alert", "lure", "investment", "link", "pressure",
                "soft_ask", "attachment", "greeting", "gambling"]

ADVICE = {
    "ask_credentials": ("Never tell anyone your password, OTP or PIN.",
                        "اپنا پاسورڈ، او ٹی پی یا پن کسی کو نہ بتائیں۔"),
    "ask_money": ("Do not send money. First call the real company or your family.",
                  "پیسے نہ بھیجیں۔ پہلے اصل ادارے یا گھر والوں سے بات کریں۔"),
    "ask_remote": ("Do not install any app a stranger asks for.",
                   "کسی اجنبی کے کہنے پر کوئی ایپ انسٹال نہ کریں۔"),
    "fake_alert": ("Do not call that number. Close this page.",
                   "اس نمبر پر کال نہ کریں۔ یہ صفحہ بند کر دیں۔"),
    "lure": ("Real prizes and jobs never ask you to pay first.",
             "اصل انعام یا نوکری کے لیے پہلے پیسے نہیں مانگے جاتے۔"),
    "impersonation": ("Do not trust it. Contact the real company using the number on your card or its official website.",
                      "اس پر بھروسہ نہ کریں۔ اصل ادارے سے کارڈ یا سرکاری ویب سائٹ پر دیے گئے نمبر پر رابطہ کریں۔"),
    "gambling": ("Gambling sites can take your money. It is better to close it.",
                 "جوئے کی سائٹس آپ کے پیسے ہتھیا سکتی ہیں۔ بہتر ہے بند کر دیں۔"),
    "links": ("Do not click any link or open any file in this message.",
              "اس پیغام میں کسی لنک پر کلک نہ کریں اور نہ کوئی فائل کھولیں۔"),
    "close": ("Do not type any details. Close this page.",
              "کوئی تفصیل نہ لکھیں۔ یہ صفحہ بند کر دیں۔"),
}
ADVICE_ORDER = ["ask_credentials", "ask_money", "ask_remote", "fake_alert",
                "lure", "impersonation", "gambling"]


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------
def _phrases(words):
    """Compile phrases into one case-insensitive regex that matches whole
    words/phrases only (so 'bet' never matches inside 'better'). Uses
    look-arounds instead of \\b so it also works for Urdu text."""
    alts = sorted((re.escape(w) for w in words), key=len, reverse=True)
    return re.compile(r"(?<!\w)(?:" + "|".join(alts) + r")(?!\w)", re.IGNORECASE)


def _distinct_hits(regex, text):
    """Distinct phrases from `regex` found in text (lower-cased)."""
    return sorted({m.group(0).lower() for m in regex.finditer(text)})


# ----------------------------------------------------------------------
# ASK patterns (hard asks)
# ----------------------------------------------------------------------
_SENSITIVE = (
    r"password|passcode|otp|one[- ]time (?:password|code|pin)|verification code|"
    r"security code|pin(?: number| code)?|cvv|cvc|card number|credit card|"
    r"debit card|bank account(?: number| details)?|account number|"
    r"login details|login credentials|credentials|cnic(?: number)?|"
    r"national id|id card number|atm pin|secret code|card details"
)
_ASK_VERBS = (
    r"enter(?:ing)?|type|typing|send(?:ing)?|share|sharing|provide|providing|"
    r"give|giving|submit(?:ting)?|confirm(?:ing)?|verify(?:ing)?|update|updating|"
    r"reply with|tell us|tell me|forward|read out|re-?enter|supply|disclose|text us"
)
_ASK_EN = re.compile(
    r"(?<!\w)(?:" + _ASK_VERBS + r")(?!\w)[^.\n!?]{0,45}?(?<!\w)(?:" + _SENSITIVE + r")(?!\w)",
    re.IGNORECASE)
_ASK_ROMAN = re.compile(
    r"(?<!\w)(?:otp|pin|password|cnic|cvv|card number|account number)(?!\w)[^.\n!?]{0,30}?"
    r"(?<!\w)(?:batayen|bataen|bataiye|batayein|bhejen|bhejein|bhejiye|bhej do|"
    r"share karen|share karein|share kren|send karen|send karein|likhen)(?!\w)",
    re.IGNORECASE)
_ASK_URDU = re.compile(
    r"(?<!\w)(?:پاسورڈ|پن|او ٹی پی|اوٹی پی|شناختی کارڈ نمبر|کارڈ نمبر|سی وی وی|اکاؤنٹ نمبر)(?!\w)"
    r"[^.\n!?]{0,30}?(?<!\w)(?:بھیجیں|بھیجیے|بھیجئے|بتائیں|بتائیے|شیئر|درج کریں|دیں|فراہم کریں|لکھیں)(?!\w)")

_NEG_BEFORE = re.compile(
    r"(?:do not|don'?t|dont|never|will not|won'?t|must not|should not|shouldn'?t|"
    r"no one should|nobody should)\W*(?:\w+\W+){0,3}$", re.IGNORECASE)
_NEG_INSIDE = re.compile(r"(?<!\w)(?:mat|na|never|not)(?!\w)|نہ|کبھی", re.IGNORECASE)


def _is_negated(text, m):
    before = text[max(0, m.start() - 45):m.start()]
    return bool(_NEG_BEFORE.search(before)) or bool(_NEG_INSIDE.search(m.group(0)))


_BENIGN_ASK = re.compile(r"wi-?fi|wi fi|router|hotspot", re.IGNORECASE)


def _find_asks(text):
    hits = []
    for rx in (_ASK_EN, _ASK_ROMAN, _ASK_URDU):
        for m in rx.finditer(text):
            if _is_negated(text, m):
                continue
            around = text[max(0, m.start() - 25):m.end()]
            if _BENIGN_ASK.search(around):
                continue
            hits.append(m.group(0).strip())
    return hits


_MONEY_STRONG = [re.compile(p, re.IGNORECASE) for p in [
    r"(?<!\w)(?:send|transfer|deposit|pay)(?!\w)[^.\n!?]{0,50}?(?<!\w)(?:easypaisa|jazzcash|western union|"
    r"moneygram|bitcoin|crypto(?:currency)?|gift cards?|itunes cards?|google play cards?|steam cards?|"
    r"this account|the following account)(?!\w)",
    r"(?<!\w)(?:processing|release|registration|clearance|reactivation|customs|handling|insurance|"
    r"unlock|activation) fees?(?!\w)",
    r"(?<!\w)advance payment(?!\w)",
    r"(?<!\w)(?:pay|send)(?!\w)[^.\n!?]{0,25}?(?<!\w)(?:small|nominal|one[- ]time|refundable|minimal) "
    r"(?:fee|amount|payment|charge)(?!\w)",
    r"(?<!\w)(?:wire transfer|western union|moneygram)(?!\w)",
    r"(?<!\w)(?:paisay|paise|raqam|rupay)(?!\w)[^.\n!?]{0,25}?(?<!\w)(?:bhejen|bhejein|bhejiye|"
    r"jama karayen|transfer karen)(?!\w)",
    r"(?:رقم|پیسے)[^.\n!?]{0,25}?(?:بھیجیں|بھیجیے|ٹرانسفر|جمع کروائیں)",
]]

_REMOTE = re.compile(
    r"(?<!\w)(?:install|download|open|run|launch|allow|give|grant|share|connect|enable)(?!\w)[^.\n!?]{0,40}?"
    r"(?<!\w)(?:anydesk|teamviewer|ultraviewer|ammyy|rustdesk|quick ?support|supremo|"
    r"remote (?:access|desktop|control|support))(?!\w)", re.IGNORECASE)

_SOFT_ASK = _phrases([
    "verify your account", "verify your identity", "confirm your identity",
    "confirm your account", "validate your account", "update your account",
    "update your details", "update your information", "update your billing",
    "reactivate your account", "re-activate your account", "restore access",
    "restore your account", "unlock your account", "click here to verify",
    "click here to confirm", "click here to login", "click here to log in",
    "log in to verify", "log in to confirm", "sign in to verify",
    "sign in to confirm", "verify now", "revalidate",
])

# ----------------------------------------------------------------------
# PRESSURE / LURE / FAKE ALERT / INVESTMENT / GAMBLING / misc phrases
# ----------------------------------------------------------------------
_PRESSURE = [re.compile(p, re.IGNORECASE) for p in [
    r"(?<!\w)account (?:has been|will be|is|was) (?:suspended|closed|blocked|locked|disabled|deactivated|terminated|limited)(?!\w)",
    r"(?<!\w)(?:suspended|blocked|locked) (?:due to|because of) (?:suspicious|unusual|unauthori[sz]ed)",
    r"(?<!\w)(?:final|last) (?:notice|warning)(?!\w)",
    r"(?<!\w)legal action(?!\w)", r"(?<!\w)court notice(?!\w)",
    r"(?<!\w)(?:arrest warrant|you will be arrested)(?!\w)",
    r"(?<!\w)case (?:will be|has been) (?:filed|registered)(?!\w)",
    r"(?<!\w)within (?:\d+|one|two|twenty[- ]four) (?:hours?|hrs?|minutes?)(?:\s*,?\s*(?:or|otherwise|else)|\s*,?\s*your)(?!\w)",
    r"(?<!\w)immediately or(?!\w)",
    r"(?<!\w)unauthori[sz]ed (?:login|access|transaction)(?!\w)",
    r"(?<!\w)suspicious activity(?!\w)",
    r"(?<!\w)unusual (?:sign-?in|activity|login)(?!\w)",
    r"(?<!\w)your sim (?:will be|has been|is going to be) (?:blocked|suspended|deactivated)(?!\w)",
    r"(?<!\w)failure to (?:comply|respond|verify)(?!\w)",
    r"(?<!\w)urgent action required(?!\w)",
    r"(?<!\w)(?:send|transfer|pay)(?!\w)[^.\n!?]{0,60}?(?<!\w)(?:urgent(?:ly)?|immediately|right now|asap)(?!\w)",
    r"(?<!\w)(?:i am|i'm) in (?:trouble|danger|an emergency)(?!\w)",
    r"(?<!\w)this is my new (?:number|phone)(?!\w)",
    r"(?<!\w)lost my phone(?!\w)", r"(?<!\w)phone (?:is )?broken(?!\w)",
    # Roman Urdu / Urdu
    r"(?<!\w)(?:account|sim) (?:band|block)(?!\w)",
    r"(?:اکاؤنٹ|سم) (?:بند|بلاک)", r"قانونی کارروائی", r"گرفتار",
]]

_LURE = _phrases([
    "you have won", "you've won", "you are the winner", "claim your prize",
    "lucky draw", "lottery", "congratulations you", "selected winner",
    "free gift", "you have been selected", "prize money", "unclaimed funds",
    "inheritance", "tax refund", "loan approved", "instant loan",
    "pre-approved loan", "work from home", "daily earning", "no experience required",
    "part-time job", "online job", "crypto giveaway", "double your",
    "bisp", "benazir income support", "ehsaas", "kafaalat", "jeeto pakistan", "8171",
    "parcel is on hold", "package is on hold", "undelivered package", "delivery failed",
    "reschedule your delivery",
    "inaam jeeta", "mubarak ho", "aap ne jeeta",
    "انعام", "لاٹری", "مبارک ہو", "جیت لیا", "بے نظیر انکم سپورٹ", "احساس پروگرام",
])
_LURE_EARN = re.compile(r"(?<!\w)earn(?!\w)[^.\n]{0,30}?(?:daily|per day|weekly|every day)(?!\w)", re.IGNORECASE)

_FAKE_STRONG = _phrases([
    "call microsoft support", "call apple support", "do not restart your computer",
    "your computer has been locked", "call this number immediately",
    "system has been compromised",
])
_FAKE_ALERT = _phrases([
    "your computer is infected", "your pc is infected", "your device has been infected",
    "your windows is infected", "virus detected", "viruses detected",
    "windows defender alert", "security alert your computer", "call now to fix",
    "contact microsoft support", "trojan detected", "spyware detected", "critical alert",
    "click allow to continue", "verify you are human", "your session will expire",
    "do not close this tab", "enable notifications to continue",
    "close this window at your own risk", "press ok to remove virus",
    "download now to fix",
])

_INVEST = _phrases([
    "guaranteed returns", "double your money", "risk free profit", "risk-free profit",
    "forex trading bot", "crypto investment plan", "guaranteed profit",
    "invest now and earn", "daily profit", "100% profit", "trading signals guaranteed",
])

_GAMBLING = _phrases([
    "bet now", "place your bet", "sportsbook", "sports betting", "online betting",
    "betting site", "betting app", "bookmaker", "casino", "jackpot", "free spins",
    "deposit bonus", "welcome bonus", "claim your bonus", "odds boost", "live betting",
    "register and bet", "roulette", "blackjack", "online slots", "slot machine",
    "teen patti", "wager", "1xbet", "bet365", "betway", "melbet", "parimatch",
    "22bet", "mostbet",
])

_GREETING = _phrases([
    "dear customer", "dear user", "dear client", "dear member", "dear account holder",
    "dear valued customer", "valued customer", "dear sir/madam", "dear sir or madam",
    "dear beneficiary", "dear winner", "dear friend", "dear email owner",
])

_ATTACH_STRONG = re.compile(r"(?<!\w)[\w\- ]{1,40}\.(?:exe|scr|bat|cmd|vbs|js|jar|iso|apk)(?!\w)", re.IGNORECASE)
_ATTACH_MEDIUM = re.compile(r"(?<!\w)[\w\- ]{1,40}\.(?:html?|zip|rar|7z)(?!\w)", re.IGNORECASE)
_ATTACH_WORDS = re.compile(r"(?<!\w)(?:attach(?:ed|ment)|download|open|enable macros|enable content|enable editing)(?!\w)", re.IGNORECASE)

_EDU = _phrases([
    "how to spot", "how to avoid", "how to protect yourself", "tips to avoid",
    "scam awareness", "phishing awareness", "cyber security tips", "cybersecurity tips",
    "report a scam", "stay safe online", "examples of phishing", "common scams",
])

# ----------------------------------------------------------------------
# Domains / brands
# ----------------------------------------------------------------------
SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "rebrand.ly", "shorturl.at",
    "tiny.cc", "rb.gy", "buff.ly", "ow.ly", "goo.gl", "s.id", "shorte.st",
}
SUSPICIOUS_TLDS = {
    "xyz", "top", "click", "work", "support", "fit", "country", "gq", "men", "ml",
    "cf", "tk", "ga", "icu", "vip", "buzz", "rest", "cyou", "monster", "sbs", "cam",
    "loan", "zip", "mov",
}
_KNOWN_TLDS = (
    "com|net|org|info|biz|pk|co|io|me|xyz|top|click|work|support|fit|country|gq|men|ml|cf|tk|ga|"
    "online|site|shop|club|live|icu|vip|link|app|dev|buzz|rest|cyou|monster|sbs|cam|loan|zip|mov|"
    "gov|edu|uk|us|in|ae|cc|ws|to|ly|gl|id"
)
_URL_RE = re.compile(
    r"(?:(?:https?://|www\.)[^\s<>\"')\]]+)|"
    r"(?:(?<![\w@.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:" + _KNOWN_TLDS + r")(?![\w-])(?:/[^\s<>\"')\]]*)?)",
    re.IGNORECASE)
_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
_IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")

_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "edu", "ac", "gob"}

# brand -> official second-level domain names (SLDs). nadra/fbr/bisp/pta must
# be on .gov.pk. Extend this list with banks/services your users rely on.
OFFICIAL = {
    "paypal": {"slds": {"paypal", "paypalobjects"}},
    "google": {"slds": {"google", "gmail", "googlemail", "youtube", "gstatic", "googleusercontent", "goo"}},
    "microsoft": {"slds": {"microsoft", "live", "outlook", "office", "office365", "microsoftonline",
                           "hotmail", "msn", "skype", "xbox", "windows", "bing", "azure",
                           "sharepoint", "onedrive"}},
    "apple": {"slds": {"apple", "icloud"}},
    "amazon": {"slds": {"amazon", "amzn", "aws"}},
    "facebook": {"slds": {"facebook", "fb", "facebookmail", "meta", "messenger", "instagram", "whatsapp"}},
    "instagram": {"slds": {"instagram"}},
    "whatsapp": {"slds": {"whatsapp"}},
    "netflix": {"slds": {"netflix"}},
    "dhl": {"slds": {"dhl"}},
    "fedex": {"slds": {"fedex"}},
    "tcs": {"slds": {"tcs"}},
    "daraz": {"slds": {"daraz"}},
    "careem": {"slds": {"careem"}},
    "easypaisa": {"slds": {"easypaisa", "telenor"}},
    "jazzcash": {"slds": {"jazzcash", "jazz"}},
    "hbl": {"slds": {"hbl"}},
    "ubl": {"slds": {"ubl", "ubldigital"}},
    "meezan": {"slds": {"meezanbank"}},
    "alfalah": {"slds": {"bankalfalah"}},
    "mcb": {"slds": {"mcb"}},
    "abl": {"slds": {"abl"}},
    "nadra": {"slds": {"nadra"}, "tlds": {"gov.pk"}},
    "fbr": {"slds": {"fbr"}, "tlds": {"gov.pk"}},
    "bisp": {"slds": {"bisp"}, "tlds": {"gov.pk"}},
    "pta": {"slds": {"pta"}, "tlds": {"gov.pk"}},
}
BRAND_TOKENS = sorted(OFFICIAL.keys(), key=len, reverse=True)
_BRAND_SUFFIXES = {
    "secure", "login", "verify", "verification", "support", "service", "services",
    "account", "accounts", "update", "alert", "alerts", "online", "help", "care",
    "security", "billing", "web", "portal", "wallet", "pay", "payment", "payments",
    "official", "team", "center", "centre", "customer", "bank", "app", "id",
    "signin", "reward", "rewards", "prize", "claim", "refund", "offer", "offers",
    "helpdesk", "assist", "recovery", "unlock",
}
_BRAND_PREFIXES = {"my", "secure", "login", "verify", "online", "mobile", "e", "official", "www"}
_LEET = str.maketrans({"0": "o", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})

FREEMAIL_SLDS = {"gmail", "googlemail", "yahoo", "outlook", "hotmail", "live", "aol",
                 "icloud", "proton", "protonmail", "yandex", "zoho", "msn", "mail", "gmx"}
_OFFICIAL_WORDS = re.compile(
    r"(?<!\w)(?:bank|support|security|helpdesk|help desk|customer care|customer service|"
    r"billing|verification|service desk)(?!\w)", re.IGNORECASE)


def _reg_domain(host):
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if len(parts[-1]) == 2 and parts[-2] in _SECOND_LEVEL and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _sld_tld(reg):
    sld, _, tld = reg.partition(".")
    return sld, tld


def _is_official(brand, reg):
    info = OFFICIAL[brand]
    sld, tld = _sld_tld(reg)
    if sld not in info["slds"]:
        return False
    if info.get("tlds"):
        return tld in info["tlds"]
    return tld.split(".")[-1] not in SUSPICIOUS_TLDS


def _official_any(reg):
    return any(_is_official(b, reg) for b in OFFICIAL)


def _leet_variants(token):
    base = token.lower().translate(_LEET)
    return {base.replace("1", "l"), base.replace("1", "i")}


def _brand_in_token(token):
    for n in _leet_variants(token):
        for b in BRAND_TOKENS:
            if n == b:
                return b
            if n.startswith(b) and n[len(b):] in _BRAND_SUFFIXES:
                return b
            if n.endswith(b) and n[:-len(b)] in _BRAND_PREFIXES:
                return b
    return None


def _lev1(a, b):
    """True if a and b differ by exactly one insert/delete/substitute."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(long_)):
        if long_[:i] + long_[i + 1:] == short:
            return True
    return False


_TYPO_TARGETS = sorted({s for info in OFFICIAL.values() for s in info["slds"] if len(s) >= 6})


def _extract_hosts(text):
    """Returns list of (host, at_sign_trick)."""
    scrubbed = _EMAIL_RE.sub(" ", text)
    out, seen = [], set()
    for m in _URL_RE.finditer(scrubbed):
        s = m.group(0).strip(".,;:)]}'\"")
        s = re.sub(r"^https?://", "", s, flags=re.IGNORECASE)
        authority = re.split(r"[/?#]", s, maxsplit=1)[0]
        at = "@" in authority
        host = authority.rsplit("@", 1)[-1].split(":")[0].lower().strip(".")
        if not host or "." not in host or not re.fullmatch(r"[a-z0-9.-]+", host):
            continue
        if host.startswith("www."):
            host = host[4:]
        if (host, at) not in seen:
            seen.add((host, at))
            out.append((host, at))
    return out


def _host_findings(host, at_trick=False):
    """-> list of (signal, evidence)."""
    findings = []
    reg = _reg_domain(host)
    sld, tld = _sld_tld(reg)
    last_tld = host.rsplit(".", 1)[-1]

    if _IP_RE.match(host):
        findings.append(("link", f"raw IP address link ({host})"))
        return findings
    if host in SHORTENERS or reg in SHORTENERS:
        findings.append(("link", f"shortened link ({host})"))
    if "xn--" in host:
        findings.append(("link", f"disguised (punycode) address ({host})"))
    if at_trick:
        findings.append(("link", "link hides its real destination after an '@'"))

    # brand look-alike: a brand name sits in the address but the real
    # registered domain is not that brand's.
    labels = host.split(".")[:-1]
    brand_hit = None
    for label in labels:
        for token in re.split(r"[-_]", label):
            b = _brand_in_token(token)
            if b and not _is_official(b, reg):
                brand_hit = b
                break
        if brand_hit:
            break
    if brand_hit:
        findings.append(("impersonation", f"{host} imitates {brand_hit}"))
    else:
        if last_tld in SUSPICIOUS_TLDS:
            findings.append(("link", f"unusual web address ending (.{last_tld})"))
        if not _official_any(reg):
            for target in _TYPO_TARGETS:
                if _lev1(sld, target):
                    findings.append(("link", f"{host} looks like a misspelling of {target}"))
                    break
    if host.count("-") >= 4 or len(host.split(".")) >= 6:
        findings.append(("link", f"very long, odd web address ({host})"))
    return findings


def _sender_findings(text):
    """Email sender checks. -> (impersonation_evidence_list, official_sender_ok)"""
    imp, official_ok = [], False
    for line in text.splitlines():
        for m in _EMAIL_RE.finditer(line):
            domain = m.group(2).lower().strip(".")
            reg = _reg_domain(domain)
            sld, _ = _sld_tld(reg)
            prefix = line[:m.start()].replace("<", " ").replace("(", " ")
            name = prefix[-45:].lower()

            for f_sig, f_ev in _host_findings(domain):
                if f_sig == "impersonation":
                    imp.append(f"sender address {domain}: {f_ev}")

            brand_in_name = None
            for b in BRAND_TOKENS:
                if re.search(r"(?<!\w)" + re.escape(b) + r"(?!\w)", name):
                    brand_in_name = b
                    break
            if brand_in_name and not _is_official(brand_in_name, reg):
                imp.append(f"sender says '{brand_in_name}' but address is {domain}")
            elif sld in FREEMAIL_SLDS and _OFFICIAL_WORDS.search(name):
                imp.append(f"official-sounding sender uses a free mail address ({domain})")

            if sld not in FREEMAIL_SLDS and _official_any(reg):
                official_ok = True
    return imp, official_ok


# ----------------------------------------------------------------------
# Context detection (window title + text)
# ----------------------------------------------------------------------
_BROWSER_SUFFIXES = [
    "google chrome", "mozilla firefox", "microsoft edge", "brave",
    "opera", "safari", "internet explorer",
]
EMAIL_HINTS = ["gmail", "outlook", "yahoo mail", "protonmail", "proton mail",
               "zoho mail", "thunderbird", "hotmail", "inbox"]
CHAT_HINTS = ["whatsapp", "messenger", "telegram", "facebook", "instagram", "discord"]
TRUSTED_HINTS = [
    # AI assistants (they explain scams, so their text must never be flagged)
    "chatgpt", "claude", "anthropic", "gemini", "copilot", "perplexity", "deepseek",
    # reference
    "wikipedia", "github", "stack overflow", "stackoverflow", "w3schools", "geeksforgeeks",
    # developer tools / editors (source code is full of scam keywords)
    "visual studio code", "pycharm", "sublime text", "notepad++", "notepad",
    "command prompt", "powershell", "windows terminal", "jupyter",
]
_FOLDER_PREFIXES = ("inbox", "starred", "sent", "drafts", "spam", "trash", "all mail",
                    "promotions", "social", "updates", "forums", "important", "scheduled",
                    "snoozed", "search results", "bin", "junk", "archive", "mail")
_GENERIC_TITLES = {"gmail", "outlook", "yahoo mail", "mail", "proton mail", "protonmail",
                   "zoho mail", "hotmail"}
_LOGIN_PAGE_RE = _phrases(["forgot password", "forgot email", "use another account",
                           "create account", "stay signed in", "keep me signed in",
                           "remember me", "sign in with"])
_OPEN_MARKER_RE = _phrases(["to me", "reply all", "forward", "show details",
                            "show trimmed content"])
_EMAIL_UI_WORDS = ("inbox", "compose", "sent", "drafts", "spam", "starred", "trash")


def _strip_browser_suffix(title_lower):
    for suffix in _BROWSER_SUFFIXES:
        marker = " - " + suffix
        if title_lower.endswith(marker):
            return title_lower[: -len(marker)]
    return title_lower


def _clean_title(title):
    t = _strip_browser_suffix((title or "").lower().strip())
    return re.sub(r"^\(\d+\)\s*", "", t)


def detect_context(window_title, text=""):
    """-> 'email' | 'chat' | 'trusted' | 'browser'"""
    t = _clean_title(window_title)
    lower = (text or "").lower()
    if t.endswith("google search"):
        return "browser"              # searching ABOUT gmail is not webmail
    if any(h in t for h in EMAIL_HINTS):
        if _LOGIN_PAGE_RE.search(lower) and len(lower) < 1200:
            return "browser"          # the sign-in page itself, not a message
        return "email"
    if any(h in t for h in CHAT_HINTS):
        return "chat"
    if any(h in t for h in TRUSTED_HINTS):
        return "trusted"
    words = sum(1 for w in _EMAIL_UI_WORDS if re.search(r"(?<!\w)" + w + r"(?!\w)", lower))
    if words >= 4:
        return "email"
    return "browser"


def _is_open_message(window_title, lower_text):
    if _OPEN_MARKER_RE.search(lower_text):
        return True
    t = _clean_title(window_title)
    if not t or t in _GENERIC_TITLES or t.startswith(_FOLDER_PREFIXES):
        return False
    return True


# ----------------------------------------------------------------------
# Core analysis of ONE chunk of text
# ----------------------------------------------------------------------
def _analyze(text, ctx):
    """-> dict(risky, scam_type, severity, signals{name:[evidence]})"""
    lower = text.lower()
    sig = {}

    def add(name, evidence):
        if evidence:
            sig.setdefault(name, [])
            for e in (evidence if isinstance(evidence, list) else [evidence]):
                if e not in sig[name]:
                    sig[name].append(e)

    add("ask_credentials", _find_asks(text))
    money = []
    for rx in _MONEY_STRONG:
        for m in rx.finditer(text):
            if not _is_negated(text, m):
                money.append(m.group(0).strip())
    add("ask_money", money)
    add("ask_remote", [m.group(0) for m in _REMOTE.finditer(text) if not _is_negated(text, m)])
    add("soft_ask", _distinct_hits(_SOFT_ASK, lower))

    pressure = []
    for rx in _PRESSURE:
        m = rx.search(text)
        if m:
            pressure.append(m.group(0).lower())
    add("pressure", pressure)

    lure = _distinct_hits(_LURE, lower)
    for m in _LURE_EARN.finditer(lower):
        lure.append(m.group(0))
    add("lure", lure)
    add("investment", _distinct_hits(_INVEST, lower))
    add("gambling", _distinct_hits(_GAMBLING, lower))
    add("greeting", _distinct_hits(_GREETING, lower))

    fake = _distinct_hits(_FAKE_ALERT, lower)
    strong_fake = _distinct_hits(_FAKE_STRONG, lower)
    add("fake_alert", sorted(set(fake) | set(strong_fake)))

    attach = []
    if _ATTACH_WORDS.search(lower):
        attach += [m.group(0).strip() for m in _ATTACH_STRONG.finditer(text)]
        attach += [m.group(0).strip() for m in _ATTACH_MEDIUM.finditer(text)]
    add("attachment", attach)

    # links + impersonation (web addresses)
    for host, at in _extract_hosts(text):
        for name, ev in _host_findings(host, at):
            add(name, ev)

    # email-only sender checks
    official_sender = False
    if ctx == "email":
        imp, official_sender = _sender_findings(text)
        add("impersonation", imp)

    return _decide(sig, ctx, official_sender, strong_fake)


_CRITICAL_ASK = re.compile(
    r"otp|pin|password|passcode|cvv|cvc|card|security code|verification code|credentials|login|"
    r"پاسورڈ|پن|او ٹی پی|اوٹی پی|سی وی وی", re.IGNORECASE)


def _critical_ask(evidence):
    return any(_CRITICAL_ASK.search(e) for e in evidence)


def _decide(sig, ctx, official_sender, strong_fake):
    n = lambda k: len(sig.get(k, []))
    hard = n("ask_credentials") > 0 or n("ask_money") > 0 or n("ask_remote") > 0
    strong_companion = (n("pressure") + n("lure") + n("link") + n("impersonation")
                        + n("fake_alert") + n("attachment")) > 0
    scam_type, risky = None, False

    if n("fake_alert") >= 2 or strong_fake:
        risky, scam_type = True, "tech_support"
    elif n("impersonation"):
        risky, scam_type = True, "phishing"
    elif hard and (strong_companion or n("soft_ask") or n("greeting")):
        risky, scam_type = True, "phishing"
    elif hard and ctx == "email":
        risky, scam_type = True, "phishing"
    elif ctx == "chat" and (n("ask_remote") or _critical_ask(sig.get("ask_credentials", []))):
        risky, scam_type = True, "phishing"
    elif n("lure") and (hard or n("pressure") or n("link") or n("soft_ask") or n("attachment")):
        risky, scam_type = True, "lure"
    elif n("lure") >= 2 and ctx in ("email", "chat"):
        risky, scam_type = True, "lure"
    elif n("lure") and ctx in ("email", "chat") and n("greeting"):
        risky, scam_type = True, "lure"
    elif n("pressure") >= 2 and (n("soft_ask") or n("link")):
        risky, scam_type = True, "phishing"
    elif ctx == "email" and n("pressure") >= 1 and n("soft_ask") and (n("link") or n("greeting")):
        risky, scam_type = True, "phishing"
    elif ctx == "email" and n("soft_ask") and n("link"):
        risky, scam_type = True, "phishing"
    elif n("investment") >= 2 or (n("investment") and (hard or n("pressure"))):
        risky, scam_type = True, "investment"
    elif ctx == "email" and n("attachment") and (n("pressure") or n("greeting") or n("soft_ask")):
        risky, scam_type = True, "phishing"
    elif n("gambling") >= 3:
        risky, scam_type = True, "gambling"

    # A real company's own email (official sender domain, no hard ask, no odd
    # link) is not a scam just because it uses words like "verify".
    if risky and ctx == "email" and official_sender and not hard and not n("link") \
            and not n("impersonation") and scam_type in ("phishing", "lure"):
        risky, scam_type = False, None

    severity = "none"
    if risky:
        if scam_type == "gambling":
            severity = "low"
        elif scam_type == "tech_support" or n("impersonation") or \
                (hard and (n("pressure") + n("link") + n("lure") + n("soft_ask")) >= 2):
            severity = "high"
        else:
            severity = "medium"
    return {"risky": risky, "scam_type": scam_type, "severity": severity, "signals": sig}


def _rank(v):
    return (v["risky"], {"none": 0, "low": 1, "medium": 2, "high": 3}[v["severity"]],
            sum(len(x) for x in v["signals"].values()))


def _windows(lines, size):
    lines = lines[:300]
    if len(lines) <= size:
        return ["\n".join(lines)]
    return ["\n".join(lines[i:i + size]) for i in range(len(lines) - size + 1)]


# ----------------------------------------------------------------------
# Compose the user-facing message
# ----------------------------------------------------------------------
def _compose(v, ctx):
    sig, scam_type = v["signals"], v["scam_type"]
    key = "generic"
    if scam_type == "gambling":
        key = "gambling"
    elif scam_type == "tech_support":
        key = "tech_support"
    elif ctx == "email":
        key = "email"
    elif ctx == "chat":
        key = "chat"
    en_parts, ur_parts = [HEADLINES[key][0]], [HEADLINES[key][1]]

    shown = [k for k in REASON_ORDER if k in sig and (k != "gambling" or scam_type == "gambling")]
    for k in shown[:2]:
        en_parts.append(REASONS[k][0])
        ur_parts.append(REASONS[k][1])

    adv_en, adv_ur = [], []
    for k in ADVICE_ORDER:
        if k in sig and (k != "gambling" or scam_type == "gambling"):
            adv_en.append(ADVICE[k][0])
            adv_ur.append(ADVICE[k][1])
    if ctx in ("email", "chat"):
        adv_en.append(ADVICE["links"][0])
        adv_ur.append(ADVICE["links"][1])
    elif not adv_en or scam_type in ("phishing", "lure"):
        adv_en.append(ADVICE["close"][0])
        adv_ur.append(ADVICE["close"][1])
    adv_en, adv_ur = adv_en[:2], adv_ur[:2]
    return (" ".join(en_parts + adv_en), " ".join(ur_parts + adv_ur),
            " ".join(adv_en), " ".join(adv_ur))


def _result_safe(reason, text_hash, ctx):
    return {
        "status": "safe", "severity": "none", "matched": [], "scam_type": None,
        "context": ctx, "en_text": SAFE_EN_MESSAGE, "ur_text": SAFE_URDU_MESSAGE,
        "advice_en": "", "advice_ur": "", "reason_en": reason, "text_hash": text_hash,
    }


# ----------------------------------------------------------------------
# Public API (same name/signature the app already uses)
# ----------------------------------------------------------------------
def score_text(text, window_title=None):
    """Pure text -> risk verdict. Returns a dict with:
      status      "risky" | "safe"
      severity    "high" | "medium" | "low" | "none"
      matched     list of signal names that fired
      scam_type   "phishing" | "lure" | "tech_support" | "investment" |
                  "gambling" | None
      context     "email" | "chat" | "trusted" | "browser"
      en_text / ur_text   full message (headline + reasons + advice)
      advice_en / advice_ur   just the "what to do" part
      reason_en   short machine-readable reason (for logs)
      text_hash   md5 of the normalized text (de-duplicates alerts)
    """
    text = text or ""
    normalized = re.sub(r"\s+", " ", text).strip()
    text_hash = hashlib.md5(normalized.encode("utf-8", "ignore")).hexdigest()
    ctx = detect_context(window_title, text)

    if ctx == "trusted":
        return _result_safe("recognized AI / reference / developer window - not scanned", text_hash, ctx)
    if not normalized:
        return _result_safe("no text found on screen", text_hash, ctx)

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    lower = text.lower()

    if ctx == "email" and _is_open_message(window_title, lower):
        verdict = _analyze(text, ctx)
    elif ctx in ("email", "chat"):
        size = 3 if ctx == "email" else 4
        verdict = max((_analyze(w, ctx) for w in _windows(lines, size)), key=_rank)
    else:
        verdict = _analyze(text, ctx)
        if verdict["risky"] and _EDU.search(lower) and verdict["scam_type"] != "tech_support":
            return _result_safe("page looks like scam-awareness / educational content", text_hash, ctx)

    if not verdict["risky"]:
        sigs = ", ".join(verdict["signals"]) or "none"
        return _result_safe(f"no scam pattern found (weak signals: {sigs})", text_hash, ctx)

    en, ur, adv_en, adv_ur = _compose(verdict, ctx)
    matched = [k for k in REASON_ORDER if k in verdict["signals"]]
    evidence = "; ".join(
        f"{k}={verdict['signals'][k][0]}" for k in matched[:3])
    return {
        "status": "risky", "severity": verdict["severity"], "matched": matched,
        "scam_type": verdict["scam_type"], "context": ctx,
        "en_text": en, "ur_text": ur, "advice_en": adv_en, "advice_ur": adv_ur,
        "reason_en": f"{verdict['scam_type']} [{ctx}]: {', '.join(matched)} | {evidence}",
        "text_hash": text_hash,
    }
