# PII Redaction Tool

## Approach

I went with a hybrid approach rather than picking one tool and hoping it covers everything: Presidio + spaCy's NER model (`en_core_web_lg`) does the heavy lifting for the unstructured stuff — names, organizations, locations — where you genuinely need a model that understands context. Everything that actually has a verifiable format gets its own dedicated recognizer instead of being left to the NER model's guesswork: emails and SSNs are regex, phone numbers go through Google's `phonenumbers` library so they validate against real per-country numbering rules instead of a fixed digit pattern, and credit cards get Luhn-checksum validated on top of the shape match — so a random 16-digit invoice number doesn't get treated the same as a real card number.

The one deliberate design choice I'd point to as the most important: organization detection doesn't rely on spaCy alone. Early testing showed the NER model missing suffix-obvious company names outright — `Link Intime India Private Limited` got zero predictions when it appeared in a "(Formerly X)" aside, despite having about as clear a legal-entity suffix as English allows. So there's a second, independent structural recognizer that catches anything with a `Ltd`/`Limited`/`LLP`/`Trust`/etc. suffix, regardless of whether the NER model noticed it. Two paths to the same entity type, so a weakness in one doesn't silently become a gap in the redaction.

Every redaction is replaced with a Faker-generated fake value, seeded and canonicalized so the same real entity always gets the same fake name throughout the document — "BSE Ltd" and "BSE Limited" both collapse to one canonical form before generating, so you don't end up with three different fake names for the same real company scattered across 100 pages.

## Judgment calls I made explicitly, rather than letting the tool decide silently

**Public and statutory bodies don't get redacted.** SEBI, BSE, NSE, RBI, RoC — these are regulators and exchanges, not anyone's personal information, and redacting them every time they're mentioned in a 100+ page filing would make the document unreadable for zero privacy benefit. This is the same kind of call the assignment's own "Order/Ticket number" example is gesturing at: there's no universally correct answer, so the right move is to make the call and say so, not to pretend the tool is neutral.

**Bare city, state, or country names count as address PII**, even without a street or PIN code attached. I went back and forth on this — a standalone "Pune" or "Maharashtra" is pretty generic — but I'd rather the tool over-redact a place name than have someone assume a specific mention of "Mumbai" in a context that actually does identify someone slipped through. It costs some precision on the LOCATION category, and I think that's the right trade to make.

**Plot numbers, flat numbers, and PIN codes aren't targeted yet.** They're pure digits or bookkeeping fragments — nothing about them has the kind of shape an NER model or a name/email/phone recognizer can key off of. This is a real gap, not something I'm going to pretend is covered. If I were extending this next, a dedicated PIN-code regex recognizer is the cheapest, highest-value addition — same pattern as the SSN/IP recognizers already in place, just a few lines.

**SSNs, credit cards, and IP addresses don't appear anywhere in this document at all** — it's a corporate IPO prospectus, and there's no reason it would contain any of them. I evaluated those three categories as "not applicable" rather than reporting a hollow 100% (nothing to false-positive on) or a hollow 0% (nothing real to catch) — either number would be technically true and completely uninformative.

## Where the evaluation numbers land

I built a gold-standard evaluation set by hand, sampled directly from this document — around 120 real text elements covering every required PII type the document actually contains, plus explicit negative-control examples (real non-birth dates, real public-entity mentions) to check the tool isn't over-triggering. Full methodology and the per-category breakdown are in the evaluation report; the short version is **86% precision, 79% recall, 82.6% F1 overall**, with email and phone detection landing at a clean 100/100 — which makes sense, since those are the two categories where "correct" has an unambiguous, checkable definition and I leaned on that instead of asking a language model to guess.

## What's actually going wrong, and why

I'd rather point at the real failure patterns than leave them for a reviewer to find. Two things explain almost everything:

**Context-free table cells confuse the NER model.** A full sentence gives spaCy plenty to work with; a bare table cell containing just `"Kushal Subbayya Hegde"` with no surrounding sentence sometimes gets classified as an organization instead of a person — there's nothing in a 3-word capitalized string alone to tell a name from a company. The same root cause runs the other way too: address and building fragments like `"Pushpakamal Apartment"` or `"Deccan Gymkhana"` get picked up as PERSON or ORGANIZATION instead of LOCATION, and the literal word `"Email"` sitting alone in a cell has, more than once, been classified as somebody's name. None of this is random noise — it's a consistent, explainable pattern tied to how much context the model has to work with, and it's the main thing dragging PERSON and LOCATION precision/recall down from where EMAIL and PHONE sit.

**Slash-separated contact lists are a genuinely unusual format the model wasn't built for.** This document lists multiple contacts as `"Eric Bacha/ Sachin Gawade/ Pravin Teli/ Siddharth Jadhav/ Tushar Gavankar"` — no commas, just slashes. spaCy reliably drops or merges roughly one name out of every five in that format. It's not a bug I'd expect a general-purpose NER model to handle out of the box, and the honest fix is a small dedicated pattern for this specific list convention rather than hoping the general model improves on it.

Both of these are documented with real examples in the evaluation report, not just asserted here.

## Extending this to a new PII type

Write a `Pattern` (or subclass `EntityRecognizer` if it needs real logic, the way phone numbers and credit cards do), register it in `get_custom_recognizers()`, and add the entity name to `SUPPORTED_ENTITIES`. That's it — detection, redaction, and evaluation all read from those two registration points, so nothing else in the pipeline needs to know a new type exists.