"""
input_guard.py
--------------
Runs BEFORE the DNCR engine.
Detects bad input types and redirects gracefully — never errors.

Returns:
    dict with keys:
        - clean_statement: str   (reframed or original)
        - original: str
        - input_type: str        ("clean", "question", "command", "vague", "jargon")
        - redirect_message: str  (empty string if clean)
        - proceed: bool          (False only if too vague to reframe at all)
        - suggestions: list[str] (rewrite suggestions if vague)
"""

import re

# --- Jargon signals: domain-specific abbreviations and clinical/technical terms ---
JARGON_PATTERNS = [
    r'\b[A-Z]{3,}\b',                        # All-caps abbreviations: SGLT2, DKA, PCR
    r'\b\w+[-]\d+\b',                         # Alphanumeric codes: SGLT2, IL-6, COVID-19
    r'\binhibitor[s]?\b',
    r'\breceptor[s]?\b',
    r'\bsynth[a-z]+\b',
    r'\bpharma[a-z]+\b',
    r'\boncolog[a-z]+\b',
    r'\bcarcinoma\b',
    r'\bmetastat[a-z]+\b',
    r'\beuglycemic\b',
    r'\bhyperkalemia\b',
    r'\bgluconeogenesis\b',
]

# --- Vague signals: statements with no clear subject-predicate-object ---
VAGUE_SIGNALS = [
    r'^things? (are|is|were|was)',
    r'^(it|this|that) (is|are|was|were) (bad|good|wrong|fine|okay)',
    r'^(everything|nothing|something) (is|are)',
    r'^\w{1,4}\s+\w{1,4}$',   # Two-word phrases only
]

# --- Command signals ---
COMMAND_STARTERS = [
    'stop', 'start', 'avoid', 'eat', "don't", "do not", 'never',
    'always', 'try', 'use', 'take', 'drink', 'exercise', 'quit', 'get'
]

# --- Implicit beliefs behind common commands ---
COMMAND_BELIEF_MAP = {
    'stop': 'stopping {obj} has positive effects',
    'avoid': 'avoiding {obj} reduces risk',
    'eat': 'consuming {obj} is beneficial',
    "don't": 'avoiding {obj} is recommended',
    "do not": 'avoiding {obj} is recommended',
    'never': '{obj} is always harmful',
    'always': '{obj} is consistently beneficial',
    'quit': 'quitting {obj} improves outcomes',
    'drink': 'consuming {obj} has health effects',
    'exercise': 'exercising has health benefits',
    'take': 'taking {obj} produces effects',
}


def _is_question(text: str) -> bool:
    stripped = text.strip()
    return stripped.endswith('?') or stripped.lower().startswith(
        ('does', 'do ', 'is ', 'are ', 'can ', 'will ', 'what ', 'why ', 'how ', 'when ', 'which ')
    )


def _is_command(text: str) -> bool:
    first_word = text.strip().lower().split()[0] if text.strip() else ''
    return first_word in COMMAND_STARTERS


def _is_vague(text: str) -> bool:
    text_lower = text.strip().lower()
    word_count = len(text_lower.split())
    if word_count <= 2:
        return True
    for pattern in VAGUE_SIGNALS:
        if re.search(pattern, text_lower):
            return True
    return False


def _has_jargon(text: str) -> bool:
    for pattern in JARGON_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def _convert_question_to_claim(text: str) -> str:
    """Best-effort reframe of a question into a testable claim."""
    text = text.strip().rstrip('?')
    lower = text.lower()

    # "Does X cause Y?" → "X causes Y"
    m = re.match(r'does (.+?) cause (.+)', lower)
    if m:
        return f"{m.group(1).capitalize()} causes {m.group(2)}"

    # "Does X improve Y?" → "X improves Y"
    m = re.match(r'does (.+?) (\w+) (.+)', lower)
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)}s {m.group(3)}"

    # "Is X good for Y?" → "X is good for Y"
    m = re.match(r'is (.+?) (good|bad|harmful|beneficial|safe|dangerous)( for .+)?', lower)
    if m:
        suffix = m.group(3) or ''
        return f"{m.group(1).capitalize()} is {m.group(2)}{suffix}"

    # "Can X cause Y?" → "X can cause Y"
    m = re.match(r'can (.+?) cause (.+)', lower)
    if m:
        return f"{m.group(1).capitalize()} can cause {m.group(2)}"

    # Fallback: drop the question word and capitalize
    for starter in ['does ', 'do ', 'is ', 'are ', 'can ', 'will ']:
        if lower.startswith(starter):
            remainder = text[len(starter):]
            return remainder.capitalize()

    return text.capitalize()


def _extract_implicit_belief(text: str) -> str:
    """Extract the belief embedded in a command."""
    words = text.strip().lower().split()
    first_word = words[0] if words else ''
    obj = ' '.join(words[1:]) if len(words) > 1 else 'this'

    template = COMMAND_BELIEF_MAP.get(first_word, '{obj} has effects')
    return template.format(obj=obj).capitalize()


def _generate_suggestions(text: str) -> list:
    """Generate rewrite suggestions for vague input."""
    return [
        "Sugar has no effect on blood glucose",
        "Exercise improves cardiovascular health",
        "Antibiotics cure viral infections",
        f"Try: '{text.strip().capitalize()} causes [specific effect]'"
        if len(text.strip()) > 3 else "Try: 'X causes Y' or 'X improves Z'"
    ]


def guard(raw_input: str) -> dict:
    """
    Main entry point. Takes raw user input, returns structured guard result.
    """
    text = raw_input.strip()

    if not text:
        return {
            "clean_statement": "",
            "original": raw_input,
            "input_type": "empty",
            "redirect_message": "Please enter a statement to evaluate.",
            "proceed": False,
            "suggestions": ["Try: 'Drinking water causes dehydration'", "Try: 'Exercise improves cardiovascular health'"]
        }

    # --- Check: Question ---
    if _is_question(text):
        converted = _convert_question_to_claim(text)
        return {
            "clean_statement": converted,
            "original": raw_input,
            "input_type": "question",
            "redirect_message": (
                f"Your input was a question. I've converted it to the testable claim: "
                f"'{converted}' — reasoning from there."
            ),
            "proceed": True,
            "suggestions": []
        }

    # --- Check: Command ---
    if _is_command(text):
        belief = _extract_implicit_belief(text)
        return {
            "clean_statement": belief,
            "original": raw_input,
            "input_type": "command",
            "redirect_message": (
                f"This was a command, not a claim. The belief behind it appears to be: "
                f"'{belief}' — evaluating that instead."
            ),
            "proceed": True,
            "suggestions": []
        }

    # --- Check: Vague ---
    if _is_vague(text):
        suggestions = _generate_suggestions(text)
        return {
            "clean_statement": "",
            "original": raw_input,
            "input_type": "vague",
            "redirect_message": (
                "This statement is too vague to evaluate. "
                "Try a claim with a clear subject, verb, and object — like 'X causes Y' or 'X has no effect on Z'."
            ),
            "proceed": False,
            "suggestions": suggestions
        }

    # --- Check: Jargon ---
    if _has_jargon(text):
        return {
            "clean_statement": text,
            "original": raw_input,
            "input_type": "jargon",
            "redirect_message": (
                "This statement contains specialized terminology. "
                "I can only partially evaluate it — treat this result as directional, not definitive."
            ),
            "proceed": True,
            "suggestions": []
        }

    # --- Clean input ---
    return {
        "clean_statement": text,
        "original": raw_input,
        "input_type": "clean",
        "redirect_message": "",
        "proceed": True,
        "suggestions": []
    }
