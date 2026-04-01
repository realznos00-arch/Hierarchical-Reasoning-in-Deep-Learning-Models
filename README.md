================================================================================
  RULED-DL REASONER
  README — Setup, Usage & DNCR Protocol Reference
================================================================================

--------------------------------------------------------------------------------
  HOW TO RUN THE APP
--------------------------------------------------------------------------------

1. INSTALL DEPENDENCIES
   Open a terminal and run:

       pip install streamlit groq python-dotenv

2. LAUNCH THE APP
   In your terminal, run the following command exactly:

       streamlit run c:/Users/name/OneDrive/Documents/DL_reasoning/app.py

   Replace "name" with your actual Windows username if different.
   The app will open automatically in your default browser.

3. ENTER YOUR GROQ API KEY
   - In the left sidebar, find the field labelled "Groq API Key"
   - Paste your key (it starts with gsk_...)
   - The sidebar will show: "Narrator ready" when the key is accepted
   - Get a free key at: https://console.groq.com

   Without a key, the app still works — math scores and verdicts display
   normally. Only the plain-English narrator narration is disabled.

4. EVALUATE A STATEMENT
   - Type a statement into the input field
     Example: "Drinking water causes dehydration"
   - Click "Run DNCR Reasoning"
   - The four layers (D, N, C, R) will evaluate the statement in sequence
   - Each layer shows its score, verdict, rule fired, and a narrator explanation
   - A final verdict panel appears at the bottom


--------------------------------------------------------------------------------
  FILE STRUCTURE
--------------------------------------------------------------------------------

  app.py            Streamlit UI — input field, layer cards, verdict panel
  dncr_engine.py    Pure rule logic — no LLM, no side effects
  narrator.py       LLM narrator only — speaks results in plain English
  input_guard.py    Input sanitiser — handles bad input before the engine runs
  requirements.txt  Python dependencies


--------------------------------------------------------------------------------
  WHAT THE APP ACCEPTS AS INPUT
--------------------------------------------------------------------------------

The input field accepts plain English declarative claims. The best inputs follow
a subject + verb + object structure that makes a falsifiable assertion.

  Good inputs:
    "Drinking water causes dehydration"
    "Exercise generally improves cardiovascular health"
    "All antibiotics cure viral infections"
    "Sugar has no effect on blood glucose"

  The app also handles bad inputs gracefully, handles it accordingly — for never throws an error:

    Questions     -> Auto-converted to a testable claim
                    "Does sugar affect blood glucose?"
                    becomes: "Sugar affects blood glucose"

    Commands      -> Implicit belief is extracted and tested
                    "Stop eating sugar"
                    becomes: "Stopping sugar has positive effects"

    Vague input   -> Soft prompt with rewrite suggestions
                    "Things are bad" -> asks for a specific subject and effect

    Jargon        -> Partial evaluation with a confidence warning
                    "SGLT2 inhibitors cause euglycemic DKA"
                    runs what it can, flags result as directional only


================================================================================
  DNCR REASONING PROTOCOL — FULL REFERENCE; 4 layers
================================================================================

DNCR stands for: Decision Rules — Neural-Symbolic — Constraint-Based — Regularized

It is a four-layer stacked reasoning architecture inspired by how deep learning
models process information through successive transformations, each layer adding
a different dimension of validation before a final verdict is produced.

The key insight from DL fundamentals that DNCR applies:
  Confidence scores cascade. A failure at any layer propagates forward.
  A statement that sounds plausible but fails one layer is still false —
  just as a neural network with a corrupted hidden layer produces wrong
  output even if the input and output layers are intact.


--------------------------------------------------------------------------------
  THE FOUR LAYERS — HOW EACH ONE IS WORKING
--------------------------------------------------------------------------------

LAYER D — DECISION RULES
  Role:         Output / Verdict
  DL Analogy:   Output layer + Semantic Parser
  Runs:         At serving time — no retraining needed
  Upgrade cost: Very low (add IF-THEN clauses directly)

  D is the most visible layer. It applies explicit IF-THEN pattern matching
  to produce a human-readable verdict. In deep learning terms, this is the
  output layer — the layer closest to the final answer, the one business
  stakeholders can read and understand without needing to know what happened
  inside.

  In the alignment demo mapping, D corresponds to the Semantic Parser —
  it breaks the statement into logical components (subject, predicate, object,
  qualifiers) and fires the first matching rule.

  Rules D fires (minimum demo set of 5):
    D1 — Causal inversion detected → verdict: FALSE
         Fires when cause and effect are logically reversed.
         Example: "Water causes dehydration" — water is the cure, not the cause.

    D2 — Negated domain fact → checks if negation flips a known truth
         Example: "Sugar does NOT affect glucose" — negation of a known true
         relationship means the statement is actually correct.

    D3 — Domain fact match → confirms or contradicts a known relationship
         Applies absolute-claim penalty if claim overgeneralises a true fact.

    D4 — Unverified absolute claim → verdict: FALSE
         Any absolute claim (all, always, never, entirely) with no domain
         backing is penalised. Absolute claims are rarely fully true.

    D5 — Fallback → verdict: UNCERTAIN
         No rule matched. Insufficient information for a verdict.
         This is the signal to add more D rules in production.

  Plateau: D rules plateau at 2,000–5,000. IF-THEN rules are orthogonal by
  nature — they do not conflict the way mathematical inequalities do, so D
  has the longest useful runway of all four layers.


LAYER N — NEURAL-SYMBOLIC
  Role:         Causal Logic
  DL Analogy:   Hidden layer + Knowledge Base Lookup
  Runs:         Forward pass — no full retraining needed
  Upgrade cost: Low (inject rules into forward pass logic)

  N is the causal logic layer. It does not ask "is this true?" — it asks
  "does cause and effect work mechanistically?" In DL terms, N is a hidden
  layer that transforms the input representation before it reaches the output.
  A corrupted N layer (wrong causal logic) produces wrong verdicts even if
  D and C are intact.

  In the alignment demo mapping, N corresponds to Knowledge Base Lookup —
  the layer that retrieves mechanistic facts. N rules must be causal
  ("because X → Y"), never merely correlational ("when X, often Y").
  Correlation is not causation and N enforces this distinction structurally.

  Rules N fires (minimum demo set of 5):
    N1 — Causal inversion gate → hard failure, penalty -0.85
         If cause and effect are mechanistically opposed, this is a logic
         failure, not just a factual mismatch. The score collapses.

    N2 — Data integrity clamp → penalty -0.40
         Statement is too sparse (fewer than 3 tokens) to analyse causally.
         Equivalent to a null input hitting a hidden layer.

    N3 — Absolute claim in probabilistic domain → penalty -0.25
         Biology, medicine, and physics are inherently probabilistic.
         Absolute claims in these domains are epistemically wrong by structure.

    N4 — Hedged claim boost → bonus +0.10
         Claims using "generally", "may", "tends to", "typically" are
         epistemically appropriate for probabilistic domains. Rewarded.

    N5 — Null fallback → no penalty
         No causal anomaly detected. Score passes through unchanged.

  N scores flow forward: N receives D's score as input and adjusts it.
  This is the cascade mechanism — each layer transforms the prior layer's
  output, exactly as hidden layers transform activations in a neural network.

  Plateau: N rules plateau at 100–200. Conflicts and training instability
  increase rapidly past this point — causal rules can contradict each other
  in ways IF-THEN rules cannot.


LAYER C — CONSTRAINT-BASED
  Role:         Mathematical Boundaries
  DL Analogy:   Activation function + Consistency Checker
  Runs:         After N layer — partial retrain may be needed
  Upgrade cost: Medium

  C is the hard boundary layer. It does not interpret meaning — it enforces
  mathematical laws that no output is allowed to violate. In DL terms, C is
  the activation function: it clamps the signal into a valid range before it
  passes to the next stage. Nothing inside C can produce output outside C's
  mathematical boundary.

  In the alignment demo mapping, C corresponds to the Consistency Checker —
  the layer that cross-references across domains. C's simplex constraint
  (output must be in [0,1]) is the mathematical equivalent of saying "this
  claim violates physics, medicine, and biology simultaneously." A claim
  failing C fails everywhere at once.

  C is architecturally the outermost layer. This is the key distinction
  between containment order and execution order:

    Containment (architectural):  C → N → R → D  (C governs everything)
    Execution (upgrade sequence):  D → N → C → R  (D is upgraded first)

  These run in opposite directions intentionally. You cannot design good
  math constraints before your logic rules (N) are stable. C is upgraded
  third, not first, even though it is architecturally outermost.

  Rules C fires (minimum demo set of 2):
    C1 — Non-negativity → score must be >= 0
         If N produces a negative score (theoretically), C clamps it to 0.
         This is the floor constraint.

    C2 — Simplex constraint → score must be in [0, 1]
         All probability outputs must lie within the valid probability simplex.
         Also applies a cross-domain inconsistency penalty (-0.10) if a causal
         inversion was detected in context.

  Plateau: C plateaus fastest of all four layers — at just 40–80 constraints.
  Mathematical constraints conflict with each other and create infeasible
  regions where no valid output exists. Adding constraints past the plateau
  causes the gradient signal to cancel and training may diverge entirely.


LAYER R — REGULARIZED
  Role:         Weight Geometry / Learning Foundation
  DL Analogy:   Regularization + Architecture shape
  Runs:         During training only — full retrain required
  Upgrade cost: High (most expensive of all four layers)

  R is the deepest and most expensive layer. It governs how the model learns —
  the shape of the weight space, the regularization pressure applied during
  training, the dropout rates in hidden layers. In DL terms, R is the
  architectural foundation. Changing R does not change what the model says
  today — it changes what the model can learn tomorrow.

  In the alignment demo mapping, R corresponds to the Logic Validator —
  the layer that sets fundamental shape constraints. A bad R (wrong weight
  geometry) corrupts learning the same way a 0.01% Logic Validator score
  collapses alignment: irreversibly, and from the inside out.

  R is upgraded last because it requires a full retrain. You should only
  change R when D, N, and C are all confirmed stable and the remaining
  bottleneck is clearly in weight geometry — not in rules, not in constraints.

  Rules R fires (minimum demo set of 2):
    R1 — L1/L2 regularization signal
         If cascaded score (from C) is below 0.15: high regularization needed.
         The weight geometry has not learned this pattern correctly.
         If between 0.15 and 0.40: moderate regularization uncertainty.

    R2 — Dropout rate nominal
         Cascaded score is healthy (>= 0.40). Weight geometry is consistent
         with input confidence. No structural intervention needed.

  Plateau: R plateaus at 20–50 hyperparameter combinations. Diminishing
  returns dominate rapidly — over-tuning R adds noise, not signal.


--------------------------------------------------------------------------------
  THE CASCADE MECHANISM — HOW REASONING FLOWS
--------------------------------------------------------------------------------

Scores flow forward through the stack in one direction:

  Statement → D (scores 0–1) → N (adjusts D's score) → C (clamps N's score)
                             → R (final geometric check) → Final Verdict

This is the core DL insight applied to rule-based reasoning:
A high score at D does not guarantee alignment. N can collapse it.
A high score at N does not guarantee alignment. C can clamp it.
R sees the final cascaded score and determines whether the model's weight
geometry supports or undermines the conclusion.

The cascade breaks the moment any layer returns verdict: FALSE.
The engine records which layer broke the cascade (cascade_broken_at).
A broken cascade at C is more serious than at D — C governs more.

Example cascade on "Drinking water causes dehydration":
  D: score 0.02  — D1 fires, causal inversion detected. Verdict: FALSE.
  N: score 0.02  — N1 fires, causal logic failure. Penalty -0.85 applied.
  C: score 0.00  — C1/C2 clamp. Cross-domain inconsistency confirmed.
  R: score 0.00  — R1 fires, high regularization signal.
  Final: NOT ALIGNED. Cascade broke at D.


--------------------------------------------------------------------------------
  THE NARRATOR — WHY THE LLM IS OUTSIDE THE PROTOCOL
--------------------------------------------------------------------------------

The LLM (Groq / llama-3.3-70b-versatile) sits entirely outside the reasoning
chain. It receives structured output only — scores, flags, verdicts, rule names.
It makes zero decisions. It adds zero logic.

This is a deliberate architectural choice:
  - The DNCR engine produces deterministic, auditable results
  - The narrator translates those results into plain English
  - If the narrator hallucinates, the math is still correct and visible
  - If the narrator is unavailable, the app still runs fully

Each layer has a distinct narrator persona that matches its function:
  D — Judge:        "I rule that..."
  N — Scientist:    "The causal mechanism failed because..."
  C — Mathematician: "The claim falls outside valid bounds because..."
  R — Architect:    "The weight geometry does not support..."

This separation preserves the integrity of the reasoning protocol.
The LLM explains. It does not reason.


--------------------------------------------------------------------------------
  DNCR UPGRADE SEQUENCE (PRODUCTION GUIDE)
--------------------------------------------------------------------------------

Upgrade from cheapest and most visible to most expensive and least visible:

  Step 1 — D (Decision Rules)
    No retraining. Highest business visibility.
    Start at 5–10 rules. Target 50–500.
    Add rules where D5 fallback fires most frequently.
    Stop when new rules cover less than 1% of new cases.

  Step 2 — N (Neural-Symbolic)
    No full retraining. Inject into forward pass only.
    Start at 3–5 rules. Target 10–50.
    Add causal gates first, then domain penalties, then hedging boosts.
    Rules must be causal, not correlational.

  Step 3 — C (Constraint-Based)
    Partial retrain may be needed.
    Design constraints around the score range your N rules actually produce.
    Start at 1–3 constraints. Target 5–15.
    C1 (non-negativity) and C2 (simplex) always go first.

  Step 4 — R (Regularized)
    Full retrain required. Most expensive.
    Only upgrade R when D, N, C are all confirmed and the bottleneck is
    clearly in weight geometry.
    Start at 1–3 params. Target 5–15.
    R1 (L1/L2 alpha) first. R2 (dropout rate) second.


================================================================================
  MODEL USED for narrator of reasoning
================================================================================

  LLM:      llama-3.3-70b-versatile  (Groq)
  API:      https://console.groq.com
  Tier:     Free — 30 req/min, 14,400 req/day
  Note:     llama-3.1-70b-versatile was decommissioned (April 2026).
            llama-3.3-70b-versatile is the direct successor.

================================================================================
