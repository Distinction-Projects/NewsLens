# Issue: Clarify and Apply Directional Score Polarity

## Summary

NewsLens currently treats lens scores as raw agreement with rubric statements. That means higher values do not consistently mean "better," "more desirable," or "positive." Some rubric statements are `existence_good`, while others are `existence_bad`; however, the scoring and downstream analytics do not invert harmful-trait questions before producing lens percentages.

This should be addressed before making strong poster, paper, or UI claims that interpret high scores as normatively positive.

## Evidence

- The RSS scoring prompt explicitly instructs the model: "Do not invert scoring based on whether a trait is beneficial or harmful."
- `RSS_Feeds/lens.py` computes `Score.value` as `sum(question_scores)` without semantic-class adjustment.
- `RSS_Feeds/analysis_module/core.py` builds lens totals from raw rubric values without semantic-class adjustment.
- `RSS_Feeds/rss_pipeline/pipeline_publish.py` publishes `score.lens_scores[*].percent` from normalized raw totals.
- `NewsLens/src/services/rss_digest.py` consumes `score.lens_scores[*].percent` directly and only clamps values to `0..100`.

## Why This Matters

Current lens values are best understood as "rubric feature presence" or "agreement with rubric statements," not as uniformly positive quality scores.

Examples:

- High `Objectivity vs Opinion` may reasonably mean more straight-reporting style.
- High `Emotional Intensity` may mean more affective or escalatory language, not better writing.
- High `Causal Attribution` may mix desirable causal clarity with undesirable blame/reductionism unless polarity is handled at the question level.

Without a directional transform, visuals using language like "good," "bad," "positive," or "quality" can become misleading.

## Proposed Decision

Separate two score concepts:

1. **Feature-presence score**: raw agreement with rubric statements exactly as scored today.
2. **Directional/construct score**: polarity-adjusted value where higher consistently means more of the desired construct.

For the current interpretive-media framing, the safest default may be to keep feature-presence scores and label them clearly. If we want "good is positive," add an explicit polarity-adjusted view rather than silently changing existing contracts.

## Implementation Options

### Option A: Label-only Clarification

- Keep all numeric values unchanged.
- Rename UI/poster language from "good/bad" or "positive/negative" to "feature presence," "annotation intensity," or "rubric agreement."
- Add methodology text explaining that not all high values are normatively positive.

Payoff: Low risk, immediate interpretive correctness.

### Option B: Add Additive Polarity-Adjusted Fields

- Preserve existing `percent` fields.
- Add new fields such as:
  - `raw_percent`
  - `directional_percent`
  - `polarity_basis`
- Invert question-level values for semantic classes that represent harmful-trait presence or beneficial-trait absence, after deciding exact mappings.

Possible mapping:

- `existence_good`: keep score
- `nonexistence_good`: keep score
- `existence_bad`: invert score
- `nonexistence_bad`: invert score

Payoff: Allows "higher is better" analysis while preserving backward compatibility.

### Option C: Rebuild All Lens Definitions Around Neutral Construct Direction

- Rewrite rubrics so every question points in the same intended construct direction.
- Re-score or migrate historical scores.

Payoff: Cleanest long-term semantics, but expensive and disruptive.

## Recommended Next Step

Start with Option A for poster/UI language, then implement Option B as an additive backend feature when we are ready to distinguish raw interpretive intensity from directional quality/construct scores.

## Acceptance Criteria

- Existing API fields remain backward-compatible unless intentionally versioned.
- Any visual that uses raw scores is labeled as rubric agreement, annotation intensity, or feature presence.
- If directional scores are added, tests verify semantic-class inversion behavior.
- Poster materials avoid implying that all high lens values are "good."
- Documentation states whether each figure uses raw feature-presence values or polarity-adjusted values.

## Related Areas

- RSS scoring pipeline
- NewsLens derived stats
- Poster export labels and captions
- Source comparison interpretation
- Lens-level methodology documentation

