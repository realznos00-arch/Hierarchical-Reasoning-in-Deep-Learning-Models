"""
narrator.py
-----------
LLM-only module. Receives structured DNCR output, speaks it in plain English.

The narrator has NO access to rule logic. It only sees scores, flags, verdicts.
Each layer has a distinct personality/voice.

Uses: Groq API + llama-3.3-70b-versatile (successor to decommissioned llama-3.1-70b-versatile)
"""

import os
from groq import Groq


# ---------------------------------------------------------------------------
# Layer personalities — each narrator speaks in a distinct voice
# ---------------------------------------------------------------------------

LAYER_PERSONAS = {
    'D': {
        'name': 'Judge',
        'voice': (
            "You are a judge delivering a ruling. Speak in plain English. "
            "State your verdict directly and name the specific rule that decided it. "
            "No preamble. No hedging. 2 sentences maximum."
        )
    },
    'N': {
        'name': 'Scientist',
        'voice': (
            "You are a research scientist explaining the causal logic behind a finding. "
            "Speak about cause and effect — what mechanistically happened. "
            "Name the specific causal failure or confirmation. 2 sentences maximum."
        )
    },
    'C': {
        'name': 'Mathematician',
        'voice': (
            "You are a mathematician checking whether a claim falls within valid mathematical boundaries. "
            "Speak about constraints — what is and isn't within bounds. "
            "Name the constraint that passed or failed. 2 sentences maximum."
        )
    },
    'R': {
        'name': 'Architect',
        'voice': (
            "You are the architect of a learning system — you see how the model's fundamental structure "
            "shapes what it can and cannot learn. Speak about weight geometry and learning foundations. "
            "Say whether the architecture supports or undermines this claim. 2 sentences maximum."
        )
    }
}


# ---------------------------------------------------------------------------
# Prompt builder per layer
# ---------------------------------------------------------------------------

def _build_prompt(layer_name: str, layer_data: dict, statement: str) -> str:
    score = layer_data['score']
    verdict = layer_data['verdict']
    rule = layer_data['rule_fired']
    rule_desc = layer_data['rule_desc']
    flags = ', '.join(layer_data['flags']) if layer_data['flags'] else 'none'
    verdict_str = 'TRUE' if verdict is True else ('FALSE' if verdict is False else 'UNCERTAIN')

    return (
        f"Statement evaluated: '{statement}'\n"
        f"Layer: {layer_name} — Rule fired: {rule}\n"
        f"Rule description: {rule_desc}\n"
        f"Score: {score:.3f} | Verdict: {verdict_str}\n"
        f"Flags: {flags}\n\n"
        f"Translate this into plain English in your voice. "
        f"Explain WHY this layer reached this verdict — linguistically, not mathematically. "
        f"Do not repeat the numbers. Name the layer ({layer_name}) and the rule ({rule}) naturally in your sentence."
    )


def _build_final_prompt(engine_result: dict) -> str:
    statement = engine_result['statement']
    final_score = engine_result['final_score']
    final_verdict = engine_result['final_verdict']
    broken_at = engine_result['cascade_broken_at']

    verdict_str = 'ALIGNED' if final_verdict else 'NOT ALIGNED'
    broken_str = f"The cascade broke at layer {broken_at}." if broken_at else "The cascade held across all layers."

    return (
        f"Statement: '{statement}'\n"
        f"Final verdict: {verdict_str} (confidence: {final_score:.1%})\n"
        f"{broken_str}\n\n"
        f"Deliver the final verdict in plain English. "
        f"Speak as a senior analyst synthesizing all four layers. "
        f"If the cascade broke, name where and why it mattered. "
        f"Do not list scores. Speak the conclusion directly. 3 sentences maximum."
    )


# ---------------------------------------------------------------------------
# Core narrator call
# ---------------------------------------------------------------------------

def _call_groq(system_prompt: str, user_prompt: str, api_key: str) -> str:
    """Single Groq API call. Returns the narrator's text."""
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=120,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Narrator unavailable: {str(e)}]"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def narrate_layer(layer_name: str, layer_data: dict, statement: str, api_key: str) -> str:
    """
    Narrate a single DNCR layer result in plain English.

    Args:
        layer_name: 'D', 'N', 'C', or 'R'
        layer_data: The dict returned by dncr_engine for that layer
        statement: The evaluated statement
        api_key: Groq API key

    Returns:
        Plain English explanation from the layer's narrator persona
    """
    persona = LAYER_PERSONAS[layer_name]
    system_prompt = persona['voice']
    user_prompt = _build_prompt(layer_name, layer_data, statement)
    return _call_groq(system_prompt, user_prompt, api_key)


def narrate_final(engine_result: dict, api_key: str) -> str:
    """
    Narrate the final verdict across all layers.

    Args:
        engine_result: Full dict from dncr_engine.run()
        api_key: Groq API key

    Returns:
        Plain English final verdict
    """
    system_prompt = (
        "You are a senior analyst synthesizing a multi-layer reasoning result. "
        "Speak plainly and directly. No jargon. No numbers. "
        "Deliver the conclusion as if explaining to a smart non-technical colleague. "
        "3 sentences maximum."
    )
    user_prompt = _build_final_prompt(engine_result)
    return _call_groq(system_prompt, user_prompt, api_key)


def narrate_redirect(guard_result: dict, api_key: str) -> str:
    """
    Narrate the input guard redirect in plain English.

    Args:
        guard_result: Dict from input_guard.guard()
        api_key: Groq API key

    Returns:
        Plain English explanation of what was reframed and why
    """
    input_type = guard_result['input_type']
    original = guard_result['original']
    clean = guard_result.get('clean_statement', '')
    redirect_msg = guard_result['redirect_message']

    system_prompt = (
        "You are a helpful assistant explaining why a user's input needed to be reframed "
        "before it could be reasoned about. Be warm, brief, and clear. "
        "Explain the reframe in one sentence. No preamble."
    )
    user_prompt = (
        f"Original input: '{original}'\n"
        f"Input type detected: {input_type}\n"
        f"Reframed as: '{clean}'\n"
        f"Reason: {redirect_msg}\n\n"
        f"Explain this reframe naturally to the user in one sentence."
    )
    return _call_groq(system_prompt, user_prompt, api_key)