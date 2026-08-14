"""Custom Presidio recognizers for structured PII types."""

from presidio_analyzer import (
    EntityRecognizer,
    Pattern,
    PatternRecognizer,
    RecognizerResult,
)
from typing import List, Optional
import phonenumbers
import re


# Phone numbers are handled globally with phonenumbers.
class GlobalPhoneRecognizer(EntityRecognizer):
    ENTITY = "PHONE_NUMBER"

    def __init__(self, default_region: str = "IN"):
        self.default_region = default_region
        super().__init__(
            supported_entities=[self.ENTITY],
            supported_language="en",
            name="GlobalPhoneRecognizer",
        )

    def load(self) -> None:
        # phonenumbers ships its own metadata.
        pass

    def analyze(self, text, entities, nlp_artifacts=None) -> List[RecognizerResult]:
        if self.ENTITY not in entities:
            return []
        results = []
        for match in phonenumbers.PhoneNumberMatcher(text, self.default_region):
            results.append(
                RecognizerResult(
                    entity_type=self.ENTITY,
                    start=match.start,
                    end=match.end,
                    score=0.9,
                )
            )
        return results


PHONE_RECOGNIZER = GlobalPhoneRecognizer(default_region="IN")


# ---------------------------------------------------------------------------
# Email addresses
# ---------------------------------------------------------------------------
EMAIL_PATTERN = Pattern(
    name="email_pattern",
    regex=r"\b[A-Za-z0-9][A-Za-z0-9._%+\-]*@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    score=0.9,
)

EMAIL_RECOGNIZER = PatternRecognizer(
    supported_entity="EMAIL_ADDRESS",
    name="CustomEmailRecognizer",
    patterns=[EMAIL_PATTERN],
)


# ---------------------------------------------------------------------------
# US Social Security Numbers (XXX-XX-XXXX)
# ---------------------------------------------------------------------------
SSN_PATTERN = Pattern(
    name="ssn_pattern",
    regex=r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b",
    score=0.85,
)

SSN_RECOGNIZER = PatternRecognizer(
    supported_entity="US_SSN",
    name="CustomSsnRecognizer",
    patterns=[SSN_PATTERN],
    context=["ssn", "social security"],
)


# ---------------------------------------------------------------------------
# IPv4 addresses
# ---------------------------------------------------------------------------
IP_PATTERN = Pattern(
    name="ipv4_pattern",
    regex=r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
    score=0.7,
)

IP_RECOGNIZER = PatternRecognizer(
    supported_entity="IP_ADDRESS",
    name="CustomIpRecognizer",
    patterns=[IP_PATTERN],
)


# Catch obvious organization names even when spaCy misses them.
ORG_SUFFIX_PATTERN = Pattern(
    name="org_suffix_pattern",
    regex=(
        r"\b[A-Z][A-Za-z&.,\-]*(?:\s+(?:of|and|&)?\s?[A-Z][A-Za-z&.,\-]*){0,6}\s+"
        r"(?:Pvt\.?\s+Ltd\.?|Private\s+Limited|Ltd\.?|Limited|LLP|Trust|"
        r"Corporation|Chartered\s+Accountants?)\b"
    ),
    score=0.6,
)

ORG_SUFFIX_RECOGNIZER = PatternRecognizer(
    supported_entity="ORGANIZATION",
    name="StructuralOrgSuffixRecognizer",
    patterns=[ORG_SUFFIX_PATTERN],
)

# Credit card numbers, Luhn-validated.
CREDIT_CARD_PATTERN = Pattern(
    name="credit_card_pattern",
    regex=r"\b(?:\d[ -]?){13,19}\b",
    score=0.3,
)


def _luhn_checksum(digits: str) -> bool:
    total = 0
    reverse_digits = digits[::-1]
    for i, ch in enumerate(reverse_digits):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


class CreditCardRecognizer(PatternRecognizer):
    def validate_result(self, pattern_text: str) -> Optional[bool]:
        digits = "".join(c for c in pattern_text if c.isdigit())
        if len(digits) < 13 or len(digits) > 19:
            return False
        return _luhn_checksum(digits)


CREDIT_CARD_RECOGNIZER = CreditCardRecognizer(
    supported_entity="CREDIT_CARD",
    name="LuhnValidatedCreditCardRecognizer",
    patterns=[CREDIT_CARD_PATTERN],
)


# Date of birth.
DOB_PATTERNS = [
    Pattern(
        name="dob_numeric",
        regex=r"\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b",
        score=0.15,
    ),
    Pattern(
        name="dob_month_name",
        regex=r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|"
        r"August|September|October|November|December)\s+\d{4}\b|"
        r"\b(?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+\d{1,2},?\s+\d{4}\b",
        score=0.15,
    ),
]

DOB_RECOGNIZER = PatternRecognizer(
    supported_entity="DATE_OF_BIRTH",
    name="DateOfBirthRecognizer",
    patterns=DOB_PATTERNS,
    context=["birth", "dob", "bear"],
)


# Public bodies are not PII.
PUBLIC_ENTITY_ALLOWLIST = {
    "sebi",
    "securities and exchange board of india",
    "bse",
    "bse limited",
    "bse ltd",
    "bombay stock exchange",
    "nse",
    "nse limited",
    "national stock exchange",
    "national stock exchange of india",
    "rbi",
    "reserve bank of india",
    "roc",
    "registrar of companies",
    "companies act",
    "companies act, 2013",
    "sebi icdr regulations",
    "depositories act",
    "cdsl",
    "central depository services",
    "central depository services (india) limited",
    "nsdl",
    "national securities depository",
    "national securities depository limited",
    "income tax act",
    "income tax department",
    "ministry of corporate affairs",
    "mca",
    "exchange board of india",  # truncated NER span of "Securities and..."
    "board of india",            # further-truncated variant, seen in practice
}


def is_public_entity(text: str) -> bool:
    """Return True for known public/statutory bodies."""
    normalized = " ".join(text.lower().strip().split())
    if normalized in PUBLIC_ENTITY_ALLOWLIST:
        return True
    return any(
        normalized == entry or normalized.startswith(entry + " ")
        for entry in PUBLIC_ENTITY_ALLOWLIST
    )


# Structural filter for organization false positives.

LEGAL_ENTITY_SUFFIXES = [
    "ltd", "ltd.", "limited", "llp", "pvt", "pvt.", "private limited",
    "inc", "inc.", "corp", "corp.", "corporation", "co.", "& co",
    "& co.", "bank", "trust", "group", "industries", "enterprises",
    "consultants", "advisors", "associates", "partners", "capital",
    "securities", "chartered accountants", "chartered accountant",
]

# Common legal terms that are not company names.
GENERIC_LEGAL_TERMS = {
    "syndicate", "offer", "underwriters", "underwriter", "ebit",
    "ebitda", "aif", "upi mechanism", "retail individual investors",
    "non-institutional portion", "statutory auditors", "committee",
    "board", "company", "the company", "issuer", "promoter",
    "promoters", "registrar", "lead manager", "book running lead manager",
    "escrow account", "public offer", "anchor investor", "qib",
    "qualified institutional buyers", "nbfc-si", "nbfc",
    "bid/ offer period", "bid/offer period", "non-institutional investors",
    "national daily newspaper", "service tax appellate tribunal",
}


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _has_legal_suffix(text: str) -> bool:
    t = _normalize(text)
    return any(t == s or t.endswith(" " + s) for s in LEGAL_ENTITY_SUFFIXES)


# Words that usually point to addresses or layout text.
FRAGMENT_WORDS = {
    "wing", "floor", "branch", "block", "tower", "building", "road",
    "street", "period", "phase", "portion", "section", "annexure",
    "schedule", "appendix", "exhibit", "chapter", "part",
}

# Words that make a capitalized phrase look like a business.
BUSINESS_SIGNAL_WORDS = {
    "bank", "trust", "group", "industries", "enterprises", "consultants",
    "advisors", "associates", "partners", "capital", "securities",
    "chartered", "ventures", "holdings", "motors", "corporation",
    "company", "park", "centre", "center", "complex", "house", "society",
}


def is_likely_organization(text: str) -> bool:
    """Return True when a span looks like a real company name."""
    t = text.strip()

    alpha_only = re.sub(r"[^A-Za-z]", "", t)
    if len(alpha_only) < 3:
        return False  # too short or symbols only

    if re.match(r"^(the|a|an)\s+", t, re.IGNORECASE):
        return False  # defined-term style phrase

    if _normalize(t) in GENERIC_LEGAL_TERMS:
        return False

    letters_only = re.sub(r"[^A-Za-z]", "", t)
    if t.isupper() and len(letters_only) <= 8:
        return False  # bare acronym

    if _has_legal_suffix(t):
        for suffix in LEGAL_ENTITY_SUFFIXES:
            norm = _normalize(t)
            if norm == suffix:
                return False  # just the suffix
            if norm.endswith(" " + suffix):
                prefix = norm[: -(len(suffix) + 1)].strip()
                if len(prefix) >= 3:
                    return True
        return False

    words = t.split()
    if len(words) >= 2:
        normalized_words = {w.lower().strip(".,") for w in words}
        if normalized_words & FRAGMENT_WORDS:
            return False  # address or layout fragment
        if not (normalized_words & BUSINESS_SIGNAL_WORDS):
            return False  # not business-like enough
        return True

    return False

def clean_span_text(text: str) -> tuple[str, int, int]:
    """Trim stray punctuation from a detected span."""
    original_len = len(text)
    stripped_leading = text.lstrip(" \t&/,;:.-")
    left_trim = original_len - len(stripped_leading)
    fully_stripped = stripped_leading.rstrip(" \t&/,;:.-")
    right_trim = len(stripped_leading) - len(fully_stripped)
    return fully_stripped, left_trim, right_trim

def get_custom_recognizers() -> List:
    """Return all custom recognizers for the analyzer."""
    return [
        PHONE_RECOGNIZER,
        EMAIL_RECOGNIZER,
        SSN_RECOGNIZER,
        IP_RECOGNIZER,
        CREDIT_CARD_RECOGNIZER,
        DOB_RECOGNIZER,
        ORG_SUFFIX_RECOGNIZER,
    ]