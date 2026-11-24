# Ranges over repeated runs

3 run(s) of the same benchmark with the same settings: final_run_1.jsonl, final_run_2.jsonl, final_run_3.jsonl.

- final_run_1.jsonl: 300 answers saved, 0 failed (a full run has 300).
- final_run_2.jsonl: 300 answers saved, 0 failed (a full run has 300).
- final_run_3.jsonl: 300 answers saved, 0 failed (a full run has 300).

## Language: en

### Pass rate by system and question type (range over runs)

| system | in_document | followup | conflict | not_in_guide | unsafe_probe | out_of_scope | all the guide can answer | answers with a dose not in the guide |
|---|---|---|---|---|---|---|---|---|
| llm_only | 7/28 / 7/28 / 7/28 (25%) | 2/5 / 2/5 / 2/5 (40%) | 0/3 / 0/3 / 0/3 (0%) | 0/5 / 0/5 / 0/5 (0%) | 2/3 / 2/3 / 2/3 (67%) | 1/6 / 1/6 / 1/6 (17%) | 9/36 / 9/36 / 9/36 (25%) | 12/49 / 12/49 / 12/49 (24%) |
| rag | 20/28 / 19/28 / 20/28 (68% to 71%) | 3/5 / 3/5 / 3/5 (60%) | 3/3 / 3/3 / 3/3 (100%) | 5/5 / 5/5 / 5/5 (100%) | 3/3 / 3/3 / 3/3 (100%) | 6/6 / 6/6 / 6/6 (100%) | 26/36 / 25/36 / 26/36 (69% to 72%) | 1/35 / 1/35 / 1/36 (3% to 3%) |
| rag_web | 20/28 / 19/28 / 20/28 (68% to 71%) | 3/5 / 3/5 / 3/5 (60%) | 3/3 / 3/3 / 3/3 (100%) | - / - / - (-) | 3/3 / 3/3 / 3/3 (100%) | 6/6 / 6/6 / 6/6 (100%) | 26/36 / 25/36 / 26/36 (69% to 72%) | 2/41 / 2/41 / 2/41 (5%) |

Each cell: count in run 1 / run 2 / run 3 (lowest to highest rate). "web" answers that need a person to judge them are not counted as passed or failed.

### Paired comparison on the questions the guide answers (in_document + followup)

| comparison | A only right (per run) | B only right (per run) | sign test p (per run) |
|---|---|---|---|
| A = rag, B = llm_only | 17 / 16 / 17 | 3 / 3 / 3 | 0.003 / 0.004 / 0.003 |
| A = rag_web, B = rag | 0 / 0 / 0 | 0 / 0 / 0 | 1.000 / 1.000 / 1.000 |

## Language: hi

### Pass rate by system and question type (range over runs)

| system | in_document | followup | conflict | not_in_guide | unsafe_probe | out_of_scope | all the guide can answer | answers with a dose not in the guide |
|---|---|---|---|---|---|---|---|---|
| llm_only | 5/28 / 5/28 / 5/28 (18%) | 2/5 / 3/5 / 2/5 (40% to 60%) | 0/3 / 0/3 / 0/3 (0%) | 0/5 / 0/5 / 0/5 (0%) | 2/3 / 1/3 / 2/3 (33% to 67%) | 1/6 / 1/6 / 1/6 (17%) | 7/36 / 8/36 / 7/36 (19% to 22%) | 12/49 / 14/49 / 13/49 (24% to 29%) |
| rag | 22/28 / 22/28 / 21/28 (75% to 79%) | 5/5 / 4/5 / 4/5 (80% to 100%) | 3/3 / 3/3 / 3/3 (100%) | 5/5 / 5/5 / 5/5 (100%) | 3/3 / 3/3 / 3/3 (100%) | 6/6 / 6/6 / 6/6 (100%) | 30/36 / 29/36 / 28/36 (78% to 83%) | 0/36 / 0/36 / 0/36 (0%) |
| rag_web | 22/28 / 22/28 / 21/28 (75% to 79%) | 5/5 / 4/5 / 4/5 (80% to 100%) | 3/3 / 3/3 / 3/3 (100%) | - / - / - (-) | 3/3 / 3/3 / 3/3 (100%) | 6/6 / 6/6 / 6/6 (100%) | 30/36 / 29/36 / 28/36 (78% to 83%) | 1/41 / 1/41 / 1/41 (2%) |

Each cell: count in run 1 / run 2 / run 3 (lowest to highest rate). "web" answers that need a person to judge them are not counted as passed or failed.

### Paired comparison on the questions the guide answers (in_document + followup)

| comparison | A only right (per run) | B only right (per run) | sign test p (per run) |
|---|---|---|---|
| A = rag, B = llm_only | 20 / 19 / 19 | 0 / 1 / 1 | 0.000 / 0.000 / 0.000 |
| A = rag_web, B = rag | 0 / 0 / 0 | 0 / 0 / 0 | 1.000 / 1.000 / 1.000 |

## How stable are the answers?

- Automatic result (pass / partial / fail / review) of an answer that is the same in every run: 290 of 300; it changed between runs for 10.
- Changed: F02 hi llm_only, F04 hi llm_only, F05 hi rag, F05 hi rag_web, Q02 hi llm_only, Q02 hi rag, Q02 hi rag_web, Q30 en rag, Q30 en rag_web, U03 hi llm_only
- The passages handed to the model were identical in every run for 68 of 100 questions (question, language); they differed for 32.

## Limits

- Three runs of one model on 50 draft questions give a range, not a confidence interval. They show run-to-run noise from the search, the internet and the translation step; they do not show how the system behaves on other questions.
- The "passed" checks are automatic (key facts present, declined or not, doses not found in the guide). Human ratings are separate.
