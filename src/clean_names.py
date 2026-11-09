"""Step 3b, layer 1: rule-based cleaning of free-text drug names.

Examples
    'TYLENOL EXTRA STRENGTH 500MG TABLETS'  -> 'tylenol'
    'HUMIRA (ADALIMUMAB) 40 MG/0.4 ML'      -> 'humira'  (plus candidate 'adalimumab')
    'LISINOPRIL.'                           -> 'lisinopril'
    'ACETAMINOPHEN\\HYDROCODONE BITARTRATE'  -> 'acetaminophen / hydrocodone bitartrate'
"""
import re

UNITS = r"(?:mg|mcg|µg|ug|g|kg|ml|l|iu|units?|u|meq|mmol|%|mg/ml|mcg/ml|mg/kg|mg/m2|mcg/hr|mg/hr)"
DOSE_RE = re.compile(rf"\b\d+(?:[.,]\d+)?\s*{UNITS}(?:\s*/\s*\d*(?:[.,]\d+)?\s*{UNITS})?\b", re.I)
NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")
PAREN_RE = re.compile(r"[\(\[]([^\)\]]*)[\)\]]")

# Words describing form, strength, packaging, or the report itself - not the drug.
NOISE_WORDS = {
    "tablet", "tablets", "tab", "tabs", "capsule", "capsules", "cap", "caps", "caplet", "caplets",
    "injection", "injectable", "inj", "solution", "soln", "suspension", "susp", "syrup", "cream",
    "ointment", "gel", "lotion", "patch", "patches", "spray", "drops", "powder", "film", "coated",
    "film-coated", "chewable", "dispersible", "effervescent", "oral", "po", "iv", "im", "sc",
    "subcutaneous", "intravenous", "topical", "ophthalmic", "nasal", "inhaler", "inhalation",
    "extended", "release", "delayed", "er", "xr", "sr", "cr", "dr", "xl", "la", "od", "ec",
    "prefilled", "pre-filled", "syringe", "pen", "autoinjector", "vial", "vials", "ampoule",
    "strength", "extra", "maximum", "regular", "generic", "brand", "product", "products",
    "unknown", "manufacturer", "mfr", "unk", "nos", "daily", "once", "twice", "dose", "doses",
}

UNINFORMATIVE = {
    "", "unknown", "unk", "unknown drug", "unspecified", "not reported", "not specified", "other",
    "others", "none", "n/a", "na", "-", "?", "other medications", "other medication",
    "concomitant drugs", "concomitant drug",
}


def _strip(text: str) -> str:
    text = text.lower().replace("\\", " / ")
    text = DOSE_RE.sub(" ", text)
    text = NUMBER_RE.sub(" ", text)
    text = re.sub(r"[^a-z0-9/\-\s]", " ", text)  # drop punctuation like . , ; : * ' "
    words = [w for w in text.split() if w not in NOISE_WORDS]
    text = " ".join(words)
    text = re.sub(r"\s*/\s*", " / ", text)
    text = re.sub(r"(^\s*/\s*|\s*/\s*$)", "", text)
    text = re.sub(r"\s*-\s*$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_name(raw: str | None) -> str | None:
    """Main cleaned form used as the lookup key. None means 'uninformative'."""
    if raw is None:
        return None
    raw = str(raw).strip()
    if raw.lower().strip(" .") in UNINFORMATIVE:
        return None
    outside = PAREN_RE.sub(" ", raw)
    cleaned = _strip(outside) or _strip(raw)
    return cleaned if cleaned and cleaned not in UNINFORMATIVE else None


def candidate_names(raw: str | None) -> list[str]:
    """All lookup candidates, best first: the cleaned name, then any name in parentheses
    (FAERS reporters often write 'BRAND (GENERIC)')."""
    if raw is None:
        return []
    out = []
    main = clean_name(raw)
    if main:
        out.append(main)
    for inner in PAREN_RE.findall(str(raw)):
        c = _strip(inner)
        if c and c not in UNINFORMATIVE and c not in out and len(c) > 2:
            out.append(c)
    return out
