"""Deterministic evidence rules shared by local policy and vision services."""
import re

BRANDS = {
    'GIGABYTE': ['gigabyte', 'aorus'], 'ASUS': ['asus', 'asustek', 'rog', 'tuf'],
    'MSI': ['msi', 'micro-star'], 'EVGA': ['evga'], 'Zotac': ['zotac'],
    'PNY': ['pny'], 'Palit': ['palit'], 'Sapphire': ['sapphire'],
    'PowerColor': ['powercolor'], 'XFX': ['xfx'], 'Corsair': ['corsair'],
    'Apple': ['apple', 'macbook'], 'Dell': ['dell', 'alienware'],
    'Acer': ['acer', 'predator'], 'Lenovo': ['lenovo', 'thinkpad'],
    'HP': ['hp', 'hewlett-packard', 'omen'], 'Intel': ['intel', 'xeon'],
    'NVIDIA': ['nvidia', 'geforce'], 'AMD': ['amd', 'radeon'],
}
CHIP_BRANDS = {'NVIDIA', 'AMD', 'Intel'}

def mentioned_brands(text):
    return {brand for brand, aliases in BRANDS.items() if any(
        re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', text, re.I) for alias in aliases)}

def canonical_manufacturer(text):
    exact = text.strip().casefold()
    for brand, aliases in BRANDS.items():
        if exact in {brand.casefold(), *[a.casefold() for a in aliases]}:
            return brand
    return text.strip()

def detect_manufacturer(text):
    brands = mentioned_brands(text)
    board_brands = brands - CHIP_BRANDS
    if board_brands:
        return next(iter(board_brands)) if len(board_brands) == 1 else None
    if brands:
        return next(iter(brands)) if len(brands) == 1 else None
    # A family name may identify the chip designer only when no board brand was named.
    if re.search(r'\brtx\b', text, re.I):
        return 'NVIDIA'
    return None

def normalize_identifier(value):
    return re.sub(r'[^A-Z0-9]', '', (value or '').upper())

def canonical_model(value):
    # Strip only standalone maker/marketing prefixes, never model or variant tokens.
    text = (value or '').upper().strip()
    text = re.sub(r'^(?:(?:NVIDIA|AMD|INTEL|GEFORCE)\s+)+', '', text)
    return normalize_identifier(text)

_DAMAGE = r'(?:physical damage|damage|burn(?:t|ed|ing|s)?(?: marks?)?|scorch(?:ed|ing|es)?|crack(?:ed|s|ing)?|liquid(?: damage| residue| exposure| ingress)?|water(?: damage| exposure)?|corrosion|corroded|bent pins?|melt(?:ed|ing|s)?|tamper(?:ed|ing)?|missing serial(?: label)?|broken seal|scuff(?:ed|s|ing)?|missing (?:component|capacitor)|broken (?:component|capacitor|connector))'

def damage_evidence(text):
    """Return asserted damage and uncertainty; negation is scoped to a damage phrase."""
    value = text.lower()
    # These engineering activities/subsystems are not themselves physical damage.
    value = re.sub(r'\bburn[ -]?in\b(?:\s+(?:test|testing|passed|completed|successful))*', '', value)
    value = re.sub(r'\b(?:liquid|water)[ -]cool(?:ing|ed)\b', '', value)
    value = re.sub(rf'\b{_DAMAGE}[ -]free\b', '', value)
    prefix = r'\b(?:no|not|without|neither|free (?:of|from))\s+(?:any\s+)?(?:visible\s+)?(?:(?:evidence|signs?|indication)\s+of\s+)?(?:any\s+)?'
    value = re.sub(prefix + _DAMAGE + rf'(?:\s*(?:,\s*(?:or\s+|and\s+)?|\s+(?:or|and|nor)\s+){_DAMAGE})*', '', value)
    value = re.sub(rf'\b{_DAMAGE}\s+(?:(?:is|are|was|were)\s+)?(?:absent|not (?:present|observed|visible|seen|detected|found))\b', '', value)
    value = re.sub(r'\bno (?:display|signal|power|video output|boot)\b', '', value)
    # A negation separated from its target by unknown words is ambiguous, not asserted CID.
    uncertain = bool(re.search(r'\b(?:possible|possibly|suspect(?:ed)?|may|might|could|uncertain|cannot rule out|can.t rule out)\b', value))
    asserted = bool(re.search(rf'\b{_DAMAGE}\b', value))
    if asserted and re.search(r'\b(?:no|not|without)\b[^.;!?\n]{0,45}' + _DAMAGE, value):
        uncertain = True
    return {'damage_asserted': asserted, 'ambiguous': uncertain}

AUTHORIZATION_FALLBACK = ('I cannot authorize a return, refund, or replacement. Submit your evidence '
    'in the intake form for technician review and obtain official authorization directly from the manufacturer.')

def informational_reply(reply):
    """Block asserted personal outcomes and commitments, including ordinary paraphrases."""
    clauses = re.split(r'[.!?\n;]+|\b(?:but|however|nevertheless)\b', reply, flags=re.I)
    for clause in clauses:
        text = clause.lower().replace('’', "'")
        personal = re.search(r'\b(?:your|you|we|i|this|the claim|the return|all claims)\b', text)
        outcome = re.search(r'\b(?:approv\w*|accept\w*|authoriz\w*|guarantee\w*|grant\w*|refund\w*|replace\w*|reimburse\w*)\b', text)
        if not outcome:
            continue
        before = text[:outcome.start()]
        after = text[outcome.end():]
        negated = bool(re.search(r"\b(?:cannot|can't|won't|will not|must not|do not|does not|not|never|unable to)\b(?!\s+only\b)[^,;]{0,65}$", before))
        conditional = bool(re.search(r'\b(?:may|might|could|if|whether|can be|manufacturer can|manufacturer will)\b', before))
        commitment = bool(re.search(r"\b(?:we|i|you)\s+(?:will|shall|guarantee|promise|are going to)|\byou(?:'ll|’ll)\b", text))
        # An unqualified status statement is disallowed even without a personal pronoun.
        status = bool(re.search(r'\b(?:is|are|was|has been|have been|now|hereby|already|successfully)\s+(?:now\s+|officially\s+|fully\s+)?(?:approved|accepted|authorized|granted|guaranteed)\b|^\s*(?:approved|refund granted|claim accepted)\s*$', text))
        personal_outcome = bool(re.search(r'\byour\b[^.;]{0,70}\b(?:claim|return|warranty|refund|replacement)\b[^.;]{0,65}\b(?:approv\w*|accept\w*|authoriz\w*|grant\w*|guarantee\w*|processed|issued|confirmed|released)\b', text))
        performative = bool(re.search(r'\b(?:we|i)\s+(?:(?:hereby|officially)\s+)?(?:approve|authorize|accept|grant|guarantee|promise|refund|replace)\b', text))
        entitlement = bool(re.search(r"\byou(?: are|'re)\s+(?:entitled|guaranteed|approved)\b", text))
        if (status or commitment or personal_outcome or performative or entitlement) and not negated and not conditional:
            return AUTHORIZATION_FALLBACK, True
    return reply, False
