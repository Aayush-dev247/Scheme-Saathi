# Semantic review protocol

The project does **not** claim 100% LLM faithfulness. API credentials were unavailable during implementation.

After configuring a provider, run `python eval/run_eval.py --output eval/provider-results.json`.
For each factual claim, independently inspect the referenced PDF physical page or saved web passage:

1. Is the claim directly entailed by the cited passage, including all qualifications?
2. Are numeric amounts, eligibility rules and dates copied accurately?
3. Does the answer acknowledge historical/undated sources and missing current-cycle evidence?
4. Does it avoid making an individual eligibility decision without enough information?
5. Is each material claim cited, and does the cited passage answer the actual question?

Record supported/total factual claims for faithfulness, correct/total claim-citation pairs for semantic citation correctness, and answered/abstained for negative cases. Report zero-denominator metrics as unavailable. Use at least one independent reviewer, and add a new held-out multilingual set before quoting general quality claims. Keyword-based retrieval hit rate is only a weak proxy.

The baseline and final checked-in reports use the same questions: final negative cases benefited from rule changes made after inspecting the baseline. They are a development regression suite, not an unbiased research benchmark.
