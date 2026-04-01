"""
app.py
------
Streamlit UI for the Ruled-DL Reasoner.

Flow: input_guard → dncr_engine → narrator (per layer + final)
LLM (narrator) is external to the reasoning protocol — it only speaks results.
"""

import streamlit as st
import time

import input_guard
import dncr_engine
import narrator

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Ruled-DL Reasoner",
    page_icon="🧠",
    layout="wide"
)

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    .layer-card {
        border-radius: 10px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
    }
    .layer-D { border-left: 5px solid #E74C3C; background: #1a0a0a; }
    .layer-N { border-left: 5px solid #3498DB; background: #0a0f1a; }
    .layer-C { border-left: 5px solid #2ECC71; background: #0a1a0f; }
    .layer-R { border-left: 5px solid #9B59B6; background: #120a1a; }

    .verdict-true  { color: #2ECC71; font-weight: bold; font-size: 1.1rem; }
    .verdict-false { color: #E74C3C; font-weight: bold; font-size: 1.1rem; }
    .verdict-uncertain { color: #F39C12; font-weight: bold; font-size: 1.1rem; }

    .narrator-text {
        font-style: italic;
        color: #BDC3C7;
        font-size: 0.95rem;
        margin-top: 0.5rem;
        padding-top: 0.5rem;
        border-top: 1px solid #2c2c2c;
    }

    .score-bar-container {
        height: 8px;
        background: #2c2c2c;
        border-radius: 4px;
        margin: 0.4rem 0;
    }

    .redirect-box {
        background: #1a1500;
        border-left: 4px solid #F39C12;
        padding: 1rem 1.2rem;
        border-radius: 6px;
        margin-bottom: 1.2rem;
    }

    .final-verdict-box {
        padding: 1.5rem 2rem;
        border-radius: 10px;
        margin-top: 1.5rem;
        text-align: center;
    }

    .final-aligned { background: #0a2a0f; border: 2px solid #2ECC71; }
    .final-not-aligned { background: #2a0a0a; border: 2px solid #E74C3C; }
    .final-uncertain { background: #2a1f00; border: 2px solid #F39C12; }

    .layer-header {
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
    }

    .persona-badge {
        display: inline-block;
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 20px;
        margin-left: 8px;
        vertical-align: middle;
        background: #2c2c2c;
        color: #aaa;
    }

    .flag-chip {
        display: inline-block;
        font-size: 0.68rem;
        padding: 2px 7px;
        border-radius: 10px;
        background: #2c2c2c;
        color: #888;
        margin: 2px 2px 0 0;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LAYER_CONFIG = {
    'D': {'label': 'D — Decision Rules',    'role': 'Output / Verdict',    'persona': 'Judge',        'color': '#E74C3C'},
    'N': {'label': 'N — Neural-Symbolic',   'role': 'Causal Logic',        'persona': 'Scientist',    'color': '#3498DB'},
    'C': {'label': 'C — Constraint-Based',  'role': 'Math Boundaries',     'persona': 'Mathematician','color': '#2ECC71'},
    'R': {'label': 'R — Regularized',       'role': 'Weight Geometry',     'persona': 'Architect',    'color': '#9B59B6'},
}

INPUT_TYPE_LABELS = {
    'clean':    ('✅', 'Clean input'),
    'question': ('❓', 'Question → converted to claim'),
    'command':  ('⚡', 'Command → implicit belief extracted'),
    'jargon':   ('⚠️', 'Specialized terminology → partial evaluation'),
    'vague':    ('🔴', 'Too vague to evaluate'),
    'empty':    ('🔴', 'Empty input'),
}


def render_score_bar(score: float, color: str):
    pct = int(score * 100)
    st.markdown(f"""
    <div class="score-bar-container">
        <div style="height:8px;width:{pct}%;background:{color};border-radius:4px;transition:width 0.4s;"></div>
    </div>
    <div style="font-size:0.75rem;color:#888;margin-bottom:0.3rem;">{score:.1%} confidence</div>
    """, unsafe_allow_html=True)


def render_verdict_badge(verdict):
    if verdict is True:
        return '<span class="verdict-true">✅ ALIGNED</span>'
    elif verdict is False:
        return '<span class="verdict-false">❌ NOT ALIGNED</span>'
    else:
        return '<span class="verdict-uncertain">⚠️ UNCERTAIN</span>'


def render_flags(flags: list):
    if not flags:
        return ''
    chips = ''.join(f'<span class="flag-chip">{f}</span>' for f in flags)
    return f'<div style="margin-top:0.4rem;">{chips}</div>'


def render_layer_card(layer_name: str, layer_data: dict, narration: str):
    cfg = LAYER_CONFIG[layer_name]
    color = cfg['color']
    css_class = f"layer-{layer_name}"
    verdict_html = render_verdict_badge(layer_data['verdict'])
    flags_html = render_flags(layer_data['flags'])

    st.markdown(f"""
    <div class="layer-card {css_class}">
        <div class="layer-header" style="color:{color};">
            {cfg['label']}
            <span class="persona-badge">🎭 {cfg['persona']}</span>
        </div>
        <div style="font-size:0.8rem;color:#666;margin-bottom:0.6rem;">{cfg['role']} · Rule: {layer_data['rule_fired']}</div>
        {verdict_html}
        {flags_html}
    </div>
    """, unsafe_allow_html=True)

    render_score_bar(layer_data['score'], color)

    # Rule description
    st.markdown(f"""
    <div style="font-size:0.8rem;color:#7f8c8d;margin-bottom:0.4rem;">
        📐 <em>{layer_data['rule_desc']}</em>
    </div>
    """, unsafe_allow_html=True)

    # Narrator text
    if narration:
        st.markdown(f"""
        <div class="narrator-text">
            💬 {narration}
        </div>
        """, unsafe_allow_html=True)


def render_redirect_box(guard_result: dict, narration: str):
    icon, label = INPUT_TYPE_LABELS.get(guard_result['input_type'], ('ℹ️', 'Reframed'))
    clean = guard_result.get('clean_statement', '')
    suggestions = guard_result.get('suggestions', [])

    st.markdown(f"""
    <div class="redirect-box">
        <div style="font-weight:700;color:#F39C12;margin-bottom:0.4rem;">{icon} {label}</div>
        <div style="color:#aaa;font-size:0.9rem;">{guard_result['redirect_message']}</div>
        {f'<div style="margin-top:0.5rem;color:#2ECC71;font-size:0.9rem;">→ Evaluating: <strong>{clean}</strong></div>' if clean else ''}
        {f'<div style="margin-top:0.5rem;color:#888;font-size:0.8rem;">💬 {narration}</div>' if narration else ''}
    </div>
    """, unsafe_allow_html=True)

    if suggestions:
        st.markdown("**Try one of these instead:**")
        for s in suggestions:
            if st.button(s, key=f"suggest_{s[:20]}"):
                st.session_state['prefill'] = s
                st.rerun()


def render_final_verdict(engine_result: dict, final_narration: str):
    verdict = engine_result['final_verdict']
    score = engine_result['final_score']
    broken = engine_result['cascade_broken_at']

    if verdict:
        css = 'final-aligned'
        icon = '✅'
        label = 'ALIGNED'
        color = '#2ECC71'
    elif verdict is False:
        css = 'final-not-aligned'
        icon = '❌'
        label = 'NOT ALIGNED'
        color = '#E74C3C'
    else:
        css = 'final-uncertain'
        icon = '⚠️'
        label = 'UNCERTAIN'
        color = '#F39C12'

    broken_text = f"<div style='font-size:0.85rem;color:#888;margin-top:0.4rem;'>Cascade broke at layer <strong style='color:{color};'>{broken}</strong></div>" if broken else ""

    st.markdown(f"""
    <div class="final-verdict-box {css}">
        <div style="font-size:2rem;">{icon}</div>
        <div style="font-size:1.4rem;font-weight:700;color:{color};margin:0.3rem 0;">{label}</div>
        <div style="font-size:0.9rem;color:#888;">{score:.1%} final confidence</div>
        {broken_text}
    </div>
    """, unsafe_allow_html=True)

    if final_narration:
        st.markdown(f"*{final_narration}*")


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

def main():
    # --- Header ---
    st.markdown("# 🧠 Ruled-DL Reasoner")
    st.markdown(
        "A 4-layer DNCR reasoning stack that evaluates statements through "
        "**Decision Rules → Neural-Symbolic → Constraint → Regularized** logic. "
        "An LLM narrator translates each layer's verdict into plain English — *outside* the reasoning protocol."
    )
    st.divider()

    # --- Sidebar: API Key ---
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        st.markdown("**Groq API Key**")
        st.markdown("Required for the LLM narrator. [Get free key →](https://groq.com)")
        api_key = st.text_input(
            "Groq API Key",
            type="password",
            placeholder="gsk_...",
            help="Your Groq API key. Never stored.",
            label_visibility="collapsed"
        )
        narrator_enabled = bool(api_key and api_key.strip().startswith('gsk_'))
        if api_key and not narrator_enabled:
            st.warning("Key should start with `gsk_`")
        elif narrator_enabled:
            st.success("✅ Narrator ready")
        else:
            st.info("ℹ️ Without a key, math scores still show — narration will be disabled.")

        st.divider()
        st.markdown("### 🏛 Architecture")
        st.markdown("""
        **Containment** (outer → inner):
        C → N → R → D

        **Upgrade Order** (cheapest first):
        D → N → C → R

        **Narrator** sits outside both — receives structured output only.
        """)

        st.divider()
        st.markdown("### 💡 Try These")
        examples = [
            "Drinking water causes dehydration",
            "Exercise generally improves cardiovascular health",
            "All antibiotics cure viral infections",
            "Sugar has no effect on blood glucose",
            "Sleep deprivation impairs cognitive function",
            "Does smoking cause cancer?",
            "Stop eating sugar",
            "Things are bad",
        ]
        for ex in examples:
            if st.button(ex, use_container_width=True, key=f"ex_{ex[:15]}"):
                st.session_state['prefill'] = ex

    # --- Input ---
    prefill = st.session_state.get('prefill', '')
    statement_input = st.text_input(
        "Enter a statement to evaluate:",
        value=prefill,
        placeholder="e.g. 'Drinking water causes dehydration'",
        key="statement_input"
    )

    run_btn = st.button("▶ Run DNCR Reasoning", type="primary", use_container_width=True)

    if run_btn and statement_input.strip():
        # Clear prefill
        if 'prefill' in st.session_state:
            del st.session_state['prefill']

        st.divider()

        # Step 1: Input Guard
        with st.spinner("🔍 Checking input..."):
            guard_result = input_guard.guard(statement_input)

        # Step 2: Handle vague/empty (no proceed)
        if not guard_result['proceed']:
            redirect_narration = ''
            if narrator_enabled:
                with st.spinner("💬 Narrator explaining..."):
                    redirect_narration = narrator.narrate_redirect(guard_result, api_key)
            render_redirect_box(guard_result, redirect_narration)
            return

        # Step 3: Show redirect if input was reframed
        if guard_result['input_type'] != 'clean':
            redirect_narration = ''
            if narrator_enabled:
                with st.spinner("💬 Narrator explaining reframe..."):
                    redirect_narration = narrator.narrate_redirect(guard_result, api_key)
            render_redirect_box(guard_result, redirect_narration)

        clean_statement = guard_result['clean_statement']

        # Step 4: Run DNCR engine
        with st.spinner("⚙️ Running DNCR stack..."):
            engine_result = dncr_engine.run(clean_statement)

        # Step 5: Render layers with narration
        st.markdown(f"### Reasoning: *\"{clean_statement}\"*")

        if guard_result['input_type'] == 'jargon':
            st.warning("⚠️ Specialized terminology detected — results are directional only.")

        cols = st.columns(2)
        layer_narrations = {}

        for i, layer_name in enumerate(['D', 'N', 'C', 'R']):
            layer_data = engine_result[layer_name]
            narration = ''

            if narrator_enabled:
                with st.spinner(f"💬 {LAYER_CONFIG[layer_name]['persona']} narrating layer {layer_name}..."):
                    narration = narrator.narrate_layer(layer_name, layer_data, clean_statement, api_key)
                    time.sleep(0.1)  # Avoid rate limit

            layer_narrations[layer_name] = narration

            with cols[i % 2]:
                render_layer_card(layer_name, layer_data, narration)

        # Step 6: Final verdict
        st.divider()
        final_narration = ''
        if narrator_enabled:
            with st.spinner("💬 Senior analyst delivering final verdict..."):
                final_narration = narrator.narrate_final(engine_result, api_key)

        render_final_verdict(engine_result, final_narration)

    elif run_btn:
        st.warning("Please enter a statement first.")


if __name__ == "__main__":
    main()