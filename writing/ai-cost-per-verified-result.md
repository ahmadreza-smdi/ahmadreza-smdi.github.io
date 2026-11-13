Analysis · AI product economics

# AI cost per accepted result

Divide the full recorded workflow cost, including failed attempts, retries, tools and human review, by distinct results accepted under a rule fixed before the test. With no accepted results, unit cost is undefined. This is a measurement method, not independent certification of the outputs.

## Key points

- Include all recorded attempts, retries, tools and review costs.

- Count distinct accepted results under a fixed rule.

- With zero accepted results, unit cost is undefined.

Original editorial comparison — all amounts and cases are fictional

Step

Value or evidence

Interpretation

Attempt 1, result A

0.25

Rejected

Attempt 2, result A

0.40

Accepted

Attempt 3, result B

0.20

Rejected

Total / one accepted result

0.85

Fictional costs, not a measured benchmark

By [Ahmadreza Samadi](https://a-samadi.com/about.html) · 24 September 2026 · Updated 21 October 2026

## Measure cost per accepted result

Divide all recorded workflow costs by the number of distinct results accepted under a rule fixed before the test. Include retries and rejected attempts in cost; do not count repeated attempts as new accepted results.

All attempt costs

Acceptance rule

Cost per accepted result

Total recorded cost ÷ distinct accepted results. With none accepted, unit cost is undefined.

This guide uses “accepted result” for an output that meets the complete acceptance rule recorded before the test. “Verified result” in the historical URL and earlier title refers to that same rule; neither term establishes independent certification. Keep unknown costs separate from explicit zero. Compare the same intended result batch and currency, and report acceptance counts alongside unit cost. A lower unit cost with a weaker acceptance rule is not a like-for-like improvement.

### A checklist for the next experiment

- Freeze the task, intended result IDs and acceptance rule.

- Record model, tool, labor and other costs consistently for all attempts.

- Retain rejected attempts and retries in the numerator.

- Count each accepted result once; report unknown cost inputs as unknown.

- If no result is accepted, report total spend and zero accepted results, with unit cost undefined.

[Use the decision brief or tool](https://github.com/ahmadreza-smdi/ai-workflow-cost) · [Explore the three signature ideas](https://a-samadi.com/ideas.html)

### Primary references

- [Holistic Evaluation of Language Models (2022)](https://arxiv.org/abs/2211.09110)

- [NIST AI RMF 1.0](https://www.nist.gov/itl/ai-risk-management-framework)

- [AI workflow cost ledger: source and measurement limits](https://github.com/ahmadreza-smdi/ai-workflow-cost)

These references inform the evaluation and interaction principles. The workflow above is an editorial synthesis, not an endorsed standard or a reported company outcome.

## How can I try this with my own ledger?

The offline ledger records costs and acceptance labels supplied by the user; it does not independently verify outputs. The teaching fixture has three attempts, two intended results, one accepted result and a total cost of 0.85. All amounts are fictional. Missing costs are rejected; explicit zero remains zero. Use the same task, currency and acceptance rule for both workflows.

Choose an existing resource:

- [AI workflow cost ledger v0.1.0](https://github.com/ahmadreza-smdi/ai-workflow-cost/releases/tag/v0.1.0)

- [English instructions](https://github.com/ahmadreza-smdi/ai-workflow-cost#try-the-fictional-example)

- [fictional sample ledger](https://github.com/ahmadreza-smdi/ai-workflow-cost/blob/v0.1.0/examples/fictional-attempts.csv)

- [AI workflow experiment workbook (XLSX, in English)](https://github.com/ahmadreza-smdi/ai-workflow-cost/releases/download/v0.1.1/AI-Workflow-Experiment.xlsx)

- [workbook starting guide (in English)](https://github.com/ahmadreza-smdi/ai-workflow-cost/blob/b26e9759dec443e265df6e4d08f5b411ebb3c635/docs/workbook-start.md)

- [paired-ledger comparison guide (in English)](https://github.com/ahmadreza-smdi/ai-workflow-cost/tree/5eb52dc449cda3b3af6a14881a8801b31002fd94#compare-two-ledgers-for-the-same-recorded-results)

- [Download the offline paired-ledger kit (in English)](https://github.com/ahmadreza-smdi/ai-workflow-cost/blob/11d627b9ddb0d1d778373c9bb6537b74c9e1c467/examples/AI-Cost-Paired-Ledgers.zip)

- [input-error guide (in English)](https://github.com/ahmadreza-smdi/ai-workflow-cost/blob/050e51d437cc38c7616be1acb63958ea58e32e54/docs/input-errors.md#the-comparison-has-unmatched-result-ids)

- [worked AI cost examples (ZIP, in English)](https://github.com/ahmadreza-smdi/ai-workflow-cost/releases/download/v0.1.2/AI-Cost-Worked-Examples.zip)

## How do you calculate cost per accepted result?

I would start with a simple measure:

Cost per accepted result = total workflow cost ÷ distinct results meeting the declared acceptance rule.

The numerator includes model input and output, cached context, tool calls, retries, failed runs, and human review time. The denominator counts outputs that meet a defined standard for the task. A low price per request can still produce an expensive result when many requests fail or need extensive correction.

If no output meets the acceptance rule, report the experiment’s total spend and zero accepted outputs separately. Cost per accepted result is undefined for that run; do not report it as zero or infinity.

Compare workflows only for the same defined task and acceptance criterion, and include the relevant cost categories consistently. Read cost per accepted result alongside precision, recall and time to a decision; a lower cost figure alone does not show that the workflow is more useful.

This is a measurement framework, not a universal benchmark. Teams need to define what “accepted” means for their own workflow and record the assumptions behind any cost comparison.

## Does passing review mean the work is accepted?

Define the full acceptance rule before the test. Passing review may be the entire rule, or only one requirement. If the rule also requires use in a stated destination, delivering a file or passing review alone does not fulfill it.

Fictional example: spend 15 currency units across three intended results. Two pass review, but only one is also used in the stated destination. If acceptance requires both checks, count one accepted result: 15 / 1 = 15. Dividing by two gives 15 / 2 = 7.50 per review-passed result, a different denominator rather than evidence of improvement.

Record who will use the output, where it must be used, which checks and rework come first, and who records acceptance. The ledger calculates the labels you supply; it does not independently verify quality, use or business outcomes.

[Read the published acceptance guidance (English)](https://github.com/ahmadreza-smdi/ai-workflow-cost/blob/df7ed996e3d1520a7a365bc697a276903b1d4386/README.md)

Before recording a run, complete the [blank experiment notes (in English)](https://github.com/ahmadreza-smdi/ai-workflow-cost/blob/63bd930f33bf102f4b634f73eb364c181edadb6c/templates/experiment-notes.txt), or read the [filled fictional notes (in English)](https://github.com/ahmadreza-smdi/ai-workflow-cost/blob/63bd930f33bf102f4b634f73eb364c181edadb6c/examples/fictional-experiment-notes.txt). Identify the intended user, destination and acceptance evidence, and record checking and rework under your stated rule. The filled notes explain the original fictional fixture only; they supply no actual output evaluation or destination test.

## How does this connect to my work?

I am Co-Founder & Technical Lead of [Appraiva](https://a-samadi.com/work/appraiva.html), a US company in Cleveland, Ohio, and work remotely from Dubai. Appraiva builds AI tools that help real estate investors and developers find distressed and off-market properties through imagery analysis and enriched property data. The property-research test in this article is a proposed experiment, not a description of an Appraiva feature or a reported company result.

## How would you test a property-research workflow?

Imagine testing a tool that flags property records for further investigation. Start with a human-labeled set of records. Ask the system to surface candidates with supporting evidence. Have a reviewer accept or reject each suggestion, then measure precision, recall, total cost, and time to a decision.

That is a proposed experiment, not a description of an Appraiva feature or a reported company result. It illustrates why a model that is cheaper to call might still cost more per accepted candidate if it sends too many false leads to a reviewer.

### What would I test first?

- Choose one repetitive task and write down the current human process.

- Define a clear acceptance rule before running the AI test.

- Track model, tool, retry and review costs for every attempt.

- Compare accepted results and time to decision against the current process.

The useful question is whether the workflow helps someone reach a reliable decision at a cost that makes sense. Lower model prices make that test easier to run; they do not answer it by themselves.

## Continue the discussion

New: how an [AI decision model like Jev](https://a-samadi.com/writing/jev-ai-decision-model.html) changes the cost per accepted decision, and what to check before giving an assistant [access to your apps](https://a-samadi.com/writing/connected-ai-apps.html).

I covered the same idea in an [eight-page LinkedIn document](https://www.linkedin.com/feed/update/urn:li:activity:7508805808802086912/) for product and engineering teams and a [plain-language Instagram carousel](https://www.instagram.com/p/Ddqbo0civsp/). For the broader product approach, read [Start with the decision, then build the AI](https://a-samadi.com/writing/start-with-the-decision.html) or use the [interactive decision brief](https://a-samadi.com/tools/before-you-build-ai.html).

Continue with the [AI property decisions reference](https://a-samadi.com/writing/ai-human-review-real-estate.html) and the [practical decision tool](https://a-samadi.com/tools/before-you-build-ai.html).

## Primary sources and scope

These three primary sources were opened on 20 October 2026. Access dates do not establish a new source publication date.

- [Stanford researchers: Holistic Evaluation of Language Models](https://arxiv.org/abs/2211.09110). Original preprint 16 November 2022.

- [NIST: AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework). AI RMF 1.0 released January 2023.

- [Google: Rules of Machine Learning](https://developers.google.com/machine-learning/guides/rules-of-ml). Living engineering guide; no new publication date asserted.

The examples and proposed methods are editorial teaching work. They are not company results or independently certified findings. Educational, not financial advice.

For a fictional example of task-specific checks, read the [business AI evaluation cases](https://a-samadi.com/writing/business-ai-evaluation-cases.html) and watch the [accompanying film](https://a-samadi.com/watch/business-ai-evaluation-cases.html).
