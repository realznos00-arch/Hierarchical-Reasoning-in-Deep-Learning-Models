"""
dncr_engine.py
--------------
Pure DNCR rule logic. No LLM. No language. No side effects.

Takes a clean statement string.
Returns a structured dict with one sub-dict per layer: D, N, C, R.

Each layer dict contains:
    - score: float (0.0 to 1.0)
    - verdict: bool
    - rule_fired: str
    - flags: list[str]
    - raw: dict  (layer-specific details for the narrator)
"""

import re


# ---------------------------------------------------------------------------
# Utility: simple NLP helpers (no external libraries)
# ---------------------------------------------------------------------------

NEGATION_WORDS = {'no', 'not', 'never', 'without', "doesn't", "don't", "won't",
                  "isn't", "aren't", "cannot", "can't", 'neither', 'nor', 'nothing'}

ABSOLUTE_WORDS = {'all', 'every', 'always', 'never', 'completely', 'entirely',
                  'only', 'solely', 'exclusively', 'impossible', 'guaranteed'}

HEDGE_WORDS = {'generally', 'usually', 'often', 'may', 'might', 'can', 'could',
               'sometimes', 'tends', 'appears', 'suggests', 'potentially',
               'possibly', 'probably', 'likely', 'typically'}

CAUSAL_WORDS = {'causes', 'cause', 'leads to', 'results in', 'produces',
                'triggers', 'induces', 'creates', 'generates', 'prevents',
                'reduces', 'increases', 'decreases', 'improves', 'worsens',
                'affects', 'impacts', 'influences'}

# Known causal inversions: (subject_signal, effect_signal) pairs that are factually inverted
CAUSAL_INVERSIONS = [
    ('water', 'dehydration'),
    ('hydration', 'dehydration'),
    ('drinking water', 'dehydration'),
    ('exercise', 'heart disease'),         # "causes" heart disease — inversion
    ('sleep', 'fatigue'),                  # sleep causes fatigue — inversion
    ('sunlight', 'vitamin d deficiency'),  # sunlight causes deficiency — inversion
    ('antibiotics', 'viral'),              # antibiotics cure viral — not how it works
    ('sugar', 'hydration'),               # sugar causes hydration — inversion
    ('fasting', 'weight gain'),           # fasting causes weight gain — inversion
]

# Known domain facts: (claim_signal, verdict, explanation_key)
DOMAIN_FACTS = [
    (['water', 'hydrat'], True, 'water_hydrates'),
    (['exercise', 'cardiovascular', 'heart', 'cardio'], True, 'exercise_heart'),
    (['sugar', 'blood glucose', 'glucose'], True, 'sugar_glucose'),
    (['antibiotics', 'bacteria', 'bacterial'], True, 'antibiotics_bacteria'),
    (['antibiotics', 'viral', 'virus'], False, 'antibiotics_viral'),
    (['smoking', 'cancer', 'lung'], True, 'smoking_cancer'),
    (['sleep', 'cognitive', 'memory', 'brain'], True, 'sleep_cognition'),
    (['vitamin c', 'immune', 'immunity'], True, 'vitc_immune'),
    (['radiation', 'cancer', 'dna'], True, 'radiation_dna'),
]


def _tokenize(text: str) -> list:
    return re.findall(r"\b[\w']+\b", text.lower())


def _has_negation(tokens: list) -> bool:
    return any(t in NEGATION_WORDS for t in tokens)


def _is_absolute(tokens: list) -> bool:
    return any(t in ABSOLUTE_WORDS for t in tokens)


def _is_hedged(tokens: list) -> bool:
    return any(t in HEDGE_WORDS for t in tokens)


def _detect_causal_inversion(statement: str) -> tuple:
    """Returns (is_inverted: bool, pair: tuple or None)"""
    lower = statement.lower()
    for subj, effect in CAUSAL_INVERSIONS:
        if subj in lower and effect in lower:
            # Check that a causal word connects them
            for cw in CAUSAL_WORDS:
                if cw in lower:
                    return True, (subj, effect)
    return False, None


def _check_domain_facts(statement: str) -> tuple:
    """Returns (match_found: bool, verdict: bool, fact_key: str)"""
    lower = statement.lower()
    for signals, verdict, key in DOMAIN_FACTS:
        if all(s in lower for s in signals):
            return True, verdict, key
    return False, None, None


def _score_absolute_claim(tokens: list, base_score: float) -> float:
    """Absolute claims get penalized — they're rarely fully true."""
    if _is_absolute(tokens):
        return max(0.05, base_score - 0.35)
    if _is_hedged(tokens):
        return min(1.0, base_score + 0.10)
    return base_score


# ---------------------------------------------------------------------------
# Layer D — Decision Rules (output layer, final verdict)
# ---------------------------------------------------------------------------

def _run_D(statement: str, tokens: list, context: dict) -> dict:
    """
    D rules: IF-THEN pattern matching.
    Fires the first matching rule. Falls back to D5 if nothing matches.
    """
    has_neg = _has_negation(tokens)
    is_abs = _is_absolute(tokens)
    is_inv = context.get('causal_inversion', False)
    domain_match = context.get('domain_match', False)
    domain_verdict = context.get('domain_verdict', None)

    flags = []

    # D1: Known causal inversion → false
    if is_inv:
        flags.append('causal_inversion_detected')
        return {
            'score': 0.02,
            'verdict': False,
            'rule_fired': 'D1',
            'rule_desc': 'Known causal inversion — cause and effect are logically reversed',
            'flags': flags,
            'raw': {'negation': has_neg, 'absolute': is_abs, 'domain_match': domain_match}
        }

    # D2: Domain fact match with negation → check if negation flips the verdict
    if domain_match and has_neg:
        # "X does NOT cause Y" where Y is known true → statement is actually correct
        flipped = not domain_verdict
        score = 0.88 if not flipped else 0.12
        flags.append('negated_domain_fact')
        return {
            'score': score,
            'verdict': not flipped,
            'rule_fired': 'D2',
            'rule_desc': 'Negated domain fact — negation inverts a known relationship',
            'flags': flags,
            'raw': {'negation': has_neg, 'absolute': is_abs, 'domain_match': domain_match}
        }

    # D3: Domain fact match without negation
    if domain_match:
        base = 0.91 if domain_verdict else 0.08
        score = _score_absolute_claim(tokens, base)
        if is_abs and domain_verdict:
            flags.append('over_generalizing_true_claim')
        return {
            'score': score,
            'verdict': domain_verdict,
            'rule_fired': 'D3',
            'rule_desc': 'Domain fact confirmed' if domain_verdict else 'Domain fact contradicted',
            'flags': flags,
            'raw': {'negation': has_neg, 'absolute': is_abs, 'domain_match': domain_match}
        }

    # D4: Absolute claim with no domain backing → penalize
    if is_abs:
        flags.append('unverified_absolute_claim')
        return {
            'score': 0.32,
            'verdict': False,
            'rule_fired': 'D4',
            'rule_desc': 'Absolute claim without domain grounding — unverifiable as stated',
            'flags': flags,
            'raw': {'negation': has_neg, 'absolute': is_abs, 'domain_match': domain_match}
        }

    # D5: Fallback — no rule matched
    flags.append('d5_fallback')
    return {
        'score': 0.50,
        'verdict': None,  # uncertain
        'rule_fired': 'D5',
        'rule_desc': 'No matching rule — insufficient information for a verdict',
        'flags': flags,
        'raw': {'negation': has_neg, 'absolute': is_abs, 'domain_match': domain_match}
    }


# ---------------------------------------------------------------------------
# Layer N — Neural-Symbolic (causal logic)
# ---------------------------------------------------------------------------

def _run_N(statement: str, tokens: list, context: dict) -> dict:
    """
    N rules: causal logic gates and data integrity checks.
    Operates on the causal structure of the claim.
    """
    is_inv = context.get('causal_inversion', False)
    has_null = not statement or len(tokens) < 3
    flags = []
    penalty = 0.0

    # N1: Hard gate — causal inversion is a logic failure
    if is_inv:
        flags.append('causal_logic_failure')
        penalty += 0.85
        rule = 'N1'
        rule_desc = 'Causal inversion gate — cause and effect are mechanistically opposed'
    # N2: Data integrity — statement too sparse
    elif has_null:
        flags.append('sparse_statement')
        penalty += 0.40
        rule = 'N2'
        rule_desc = 'Data integrity clamp — statement lacks sufficient structure for causal analysis'
    # N3: Domain penalty — absolute claim in a probabilistic domain
    elif _is_absolute(tokens):
        flags.append('absolute_in_probabilistic_domain')
        penalty += 0.25
        rule = 'N3'
        rule_desc = 'Domain penalty — absolute claim in a naturally probabilistic domain'
    # N4: Domain boost — hedged claim is epistemically sound
    elif _is_hedged(tokens):
        flags.append('hedged_claim_boost')
        penalty -= 0.10
        rule = 'N4'
        rule_desc = 'Domain boost — hedged claim is epistemically appropriate'
    # N5: Null/missing fallback
    else:
        rule = 'N5'
        rule_desc = 'Null fallback — no causal anomaly detected, passing through'

    d_score = context.get('d_score', 0.5)
    n_score = max(0.0, min(1.0, d_score - penalty))

    return {
        'score': round(n_score, 3),
        'verdict': n_score >= 0.5,
        'rule_fired': rule,
        'rule_desc': rule_desc,
        'flags': flags,
        'raw': {'penalty_applied': penalty, 'd_score_input': d_score}
    }


# ---------------------------------------------------------------------------
# Layer C — Constraint-Based (mathematical boundaries)
# ---------------------------------------------------------------------------

def _run_C(statement: str, tokens: list, context: dict) -> dict:
    """
    C rules: hard mathematical boundaries.
    C1: non-negativity. C2: simplex (output in [0,1]).
    """
    n_score = context.get('n_score', 0.5)
    flags = []

    # C1: Non-negativity — score must be >= 0
    if n_score < 0:
        flags.append('c1_non_negativity_violation')
        c_score = 0.0
        simplex_pass = False
        rule = 'C1'
        rule_desc = 'Non-negativity violated — score fell below zero boundary'
    # C2: Simplex constraint — output must be in [0, 1]
    elif not (0.0 <= n_score <= 1.0):
        flags.append('c2_simplex_violation')
        c_score = max(0.0, min(1.0, n_score))
        simplex_pass = False
        rule = 'C2'
        rule_desc = 'Simplex boundary clamped — score forced into valid [0,1] range'
    else:
        # Score is valid — apply consistency check across domain signals
        cross_domain_penalty = 0.0
        inversion = context.get('causal_inversion', False)
        if inversion:
            cross_domain_penalty = 0.10
            flags.append('cross_domain_inconsistency')
        c_score = max(0.0, n_score - cross_domain_penalty)
        simplex_pass = True
        rule = 'C2'
        rule_desc = 'Simplex constraint satisfied — output within valid mathematical boundary'

    return {
        'score': round(c_score, 3),
        'verdict': simplex_pass and c_score >= 0.5,
        'rule_fired': rule,
        'rule_desc': rule_desc,
        'flags': flags,
        'raw': {'simplex_pass': simplex_pass, 'n_score_input': n_score}
    }


# ---------------------------------------------------------------------------
# Layer R — Regularized (weight geometry, training foundation)
# ---------------------------------------------------------------------------

def _run_R(statement: str, tokens: list, context: dict) -> dict:
    """
    R rules: weight geometry and regularization shape.
    R1: L1/L2 alpha. R2: dropout rate.
    Only changes with full retrain — so R reflects structural confidence.
    """
    c_score = context.get('c_score', 0.5)
    flags = []

    # R1: L1/L2 regularization signal — if cascaded score is very low, geometry is suspect
    if c_score < 0.15:
        alpha_signal = 'high_regularization_needed'
        flags.append('r1_high_regularization_signal')
        r_penalty = 0.05
        rule = 'R1'
        rule_desc = 'L1/L2 signal — cascaded score suggests model weight geometry has not learned this pattern correctly'
    elif c_score < 0.40:
        alpha_signal = 'moderate_regularization'
        flags.append('r1_moderate_regularization')
        r_penalty = 0.02
        rule = 'R1'
        rule_desc = 'L1/L2 signal — moderate weight geometry uncertainty detected'
    else:
        alpha_signal = 'nominal'
        r_penalty = 0.0
        rule = 'R2'
        rule_desc = 'Dropout rate nominal — weight geometry consistent with input confidence'

    r_score = max(0.0, min(1.0, c_score - r_penalty))

    return {
        'score': round(r_score, 3),
        'verdict': r_score >= 0.5,
        'rule_fired': rule,
        'rule_desc': rule_desc,
        'flags': flags,
        'raw': {
            'alpha_signal': alpha_signal,
            'c_score_input': c_score,
            'penalty_applied': r_penalty,
            'retrain_required': r_score < 0.5
        }
    }


# ---------------------------------------------------------------------------
# Main engine entry point
# ---------------------------------------------------------------------------

def run(statement: str) -> dict:
    """
    Run the full DNCR stack on a clean statement.

    Args:
        statement: A clean, pre-validated string from input_guard.

    Returns:
        dict with keys: D, N, C, R, final_verdict, final_score, cascade_broken_at
    """
    tokens = _tokenize(statement)

    # Pre-compute shared context
    is_inv, inv_pair = _detect_causal_inversion(statement)
    domain_match, domain_verdict, domain_key = _check_domain_facts(statement)

    context = {
        'causal_inversion': is_inv,
        'inversion_pair': inv_pair,
        'domain_match': domain_match,
        'domain_verdict': domain_verdict,
        'domain_key': domain_key,
    }

    # Run layers in sequence, passing scores forward
    D = _run_D(statement, tokens, context)
    context['d_score'] = D['score']

    N = _run_N(statement, tokens, context)
    context['n_score'] = N['score']

    C = _run_C(statement, tokens, context)
    context['c_score'] = C['score']

    R = _run_R(statement, tokens, context)

    # Determine where cascade broke (if anywhere)
    cascade_broken_at = None
    for layer_name, layer_data in [('D', D), ('N', N), ('C', C), ('R', R)]:
        if layer_data['verdict'] is False:
            cascade_broken_at = layer_name
            break

    final_score = R['score']
    final_verdict = final_score >= 0.5 and cascade_broken_at is None

    return {
        'statement': statement,
        'D': D,
        'N': N,
        'C': C,
        'R': R,
        'final_verdict': final_verdict,
        'final_score': round(final_score, 3),
        'cascade_broken_at': cascade_broken_at,
        'context': context,
    }
