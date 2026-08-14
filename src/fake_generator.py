"""Generate stable fake replacements for detected PII."""

import hashlib
import json
import re
from pathlib import Path
from faker import Faker


CORPORATE_SUFFIXES = [
    "private limited",
    "pvt. ltd.",
    "pvt ltd",
    "ltd.",
    "ltd",
    "limited",
    "llp",
    "inc.",
    "inc",
    "corp.",
    "corp",
]

NAME_TITLES = {"mr.", "mr", "mrs.", "mrs", "ms.", "ms", "dr.", "dr", "shri", "smt.", "smt"}


def _canonicalize(text: str, entity_type: str) -> str:
    """Normalize surface variations to one canonical key."""
    t = " ".join(text.strip().lower().split())

    if entity_type == "ORGANIZATION":
        for suffix in CORPORATE_SUFFIXES:
            if t == suffix or t.endswith(" " + suffix):
                t = t[: -len(suffix)].strip()
        t = t.rstrip(",. ")

    elif entity_type == "PERSON":
        tokens = [tok for tok in t.split() if tok not in NAME_TITLES]
        t = " ".join(tokens)

    return t


class FakeValueGenerator:
    def __init__(self, seed: int = 42):
        self.mapping: dict[tuple[str, str], str] = {}
        self._base_seed = seed

    def _seeded_faker(self, canonical: str, entity_type: str) -> Faker:
        key = f"{self._base_seed}:{entity_type}:{canonical}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        numeric_seed = int(digest, 16) % (2**32)
        fkr = Faker()
        fkr.seed_instance(numeric_seed)
        return fkr

    def _generate(self, fkr: Faker, original: str, entity_type: str) -> str:
        if entity_type == "PERSON":
            return fkr.name()
        elif entity_type == "ORGANIZATION":
            return fkr.company()
        elif entity_type == "LOCATION":
            return fkr.city()
        elif entity_type == "EMAIL_ADDRESS":
            first = fkr.first_name().lower()
            last = fkr.last_name().lower()
            return f"{first}.{last}@example.com"
        elif entity_type == "PHONE_NUMBER":
            return self._fake_india_phone(fkr, original)
        elif entity_type == "US_SSN":
            return fkr.ssn()
        elif entity_type == "CREDIT_CARD":
            return fkr.credit_card_number()
        elif entity_type == "IP_ADDRESS":
            return fkr.ipv4_public()
        elif entity_type == "DATE_OF_BIRTH":
            dob = fkr.date_of_birth(minimum_age=25, maximum_age=70)
            return dob.strftime("%d/%m/%Y")
        else:
            return "[REDACTED]"

    def _fake_india_phone(self, fkr: Faker, original: str) -> str:
        digits = str(fkr.random_number(digits=10, fix_len=True))
        if original.strip().startswith(("+91", "0091")):
            return f"+91 {digits[:5]} {digits[5:]}"
        return digits

    def get_fake(self, original: str, entity_type: str) -> str:
        canonical = _canonicalize(original, entity_type)
        key = (entity_type, canonical)
        if key in self.mapping:
            return self.mapping[key]

        fkr = self._seeded_faker(canonical, entity_type)
        fake_value = self._generate(fkr, original, entity_type)
        self.mapping[key] = fake_value
        return fake_value

    def save_mapping(self, path: str) -> None:
        serializable = {f"{etype}||{orig}": fake for (etype, orig), fake in self.mapping.items()}
        Path(path).write_text(json.dumps(serializable, indent=2, ensure_ascii=False))

    def load_mapping(self, path: str) -> None:
        raw = json.loads(Path(path).read_text())
        self.mapping = {}
        for combined_key, fake in raw.items():
            etype, orig = combined_key.split("||", 1)
            self.mapping[(etype, orig)] = fake


if __name__ == "__main__":
    gen = FakeValueGenerator()
    # Check that canonicalization keeps these consistent.
    print(gen.get_fake("BSE Ltd", "ORGANIZATION"))
    print(gen.get_fake("BSE Limited", "ORGANIZATION"))
    print(gen.get_fake("BSE", "ORGANIZATION"))
    print(gen.get_fake("Mr. Kushal Hegde", "PERSON"))
    print(gen.get_fake("Kushal Hegde", "PERSON"))