# Advisor benchmark report

Answers scored: 300 (failed or missing: 0). Questions: 50. Models: llama3.1:8b. Languages: en, hi.

The "auto" columns are a screen: key facts present, declined or not, and doses that appear nowhere in the guide. They do not replace a person reading the answers.

## llama3.1:8b, language en

| system | in_document | followup | conflict | not_in_guide | unsafe_probe | out_of_scope |
|---|---|---|---|---|---|---|
| llm_only | 7/28 (25%) | 2/5 (40%) | 0/3 (0%) | 0/5 (0%) | 2/3 (67%) | 1/6 (17%) |
| rag | 20/28 (71%) | 3/5 (60%) | 3/3 (100%) | 5/5 (100%) | 3/3 (100%) | 6/6 (100%) |
| rag_web | 20/28 (71%) | 3/5 (60%) | 3/3 (100%) | + 5 to review | 3/3 (100%) | 6/6 (100%) |

Cells: answers that passed the automatic check / answers checked.
- in_document, followup: all key facts present. conflict: both doses from the guide shown. not_in_guide: declined rather than answering from model memory (web answers are listed "to review"). unsafe_probe: no dose that is missing from the guide. out_of_scope: declined.

| system | answers containing a dose not found in the guide | key-fact recall (in_document + followup) | retrieval recall | median seconds |
|---|---|---|---|---|
| llm_only | 12/49 (24%) | 37.9% | - | 8.7 |
| rag | 1/35 (3%) | 80.8% | 93.9% | 10.1 |
| rag_web | 2/41 (5%) | 80.8% | 93.9% | 11.2 |

| paired comparison (questions the guide answers) | A only right | B only right | sign test p |
|---|---|---|---|
| A = rag, B = llm_only (n = 33) | 17 | 3 | 0.003 |
| A = rag_web, B = rag (n = 33) | 0 | 0 | 1.000 |

## llama3.1:8b, language hi

| system | in_document | followup | conflict | not_in_guide | unsafe_probe | out_of_scope |
|---|---|---|---|---|---|---|
| llm_only | 5/28 (18%) | 2/5 (40%) | 0/3 (0%) | 0/5 (0%) | 2/3 (67%) | 1/6 (17%) |
| rag | 22/28 (79%) | 5/5 (100%) | 3/3 (100%) | 5/5 (100%) | 3/3 (100%) | 6/6 (100%) |
| rag_web | 22/28 (79%) | 5/5 (100%) | 3/3 (100%) | + 5 to review | 3/3 (100%) | 6/6 (100%) |

Cells: answers that passed the automatic check / answers checked.
- in_document, followup: all key facts present. conflict: both doses from the guide shown. not_in_guide: declined rather than answering from model memory (web answers are listed "to review"). unsafe_probe: no dose that is missing from the guide. out_of_scope: declined.

| system | answers containing a dose not found in the guide | key-fact recall (in_document + followup) | retrieval recall | median seconds |
|---|---|---|---|---|
| llm_only | 12/49 (24%) | 32.3% | - | 8.7 |
| rag | 0/36 (0%) | 89.4% | 95.5% | 8.7 |
| rag_web | 1/41 (2%) | 89.4% | 95.5% | 9.8 |

| paired comparison (questions the guide answers) | A only right | B only right | sign test p |
|---|---|---|---|
| A = rag, B = llm_only (n = 33) | 20 | 0 | 0.000 |
| A = rag_web, B = rag (n = 33) | 0 | 0 | 1.000 |

## Limits

- About 50 questions, one run per setting, drafted from one guide: a screening study, not a benchmark others can rely on. The questions and Hindi wording need a cotton expert and a Hindi speaker before any strong claim.
- One model run at temperature above 0 gives different answers each time; use --temperature 0 or repeat the run.
- Web answers depend on what the search returned that day.
- The guide itself contradicts itself on some doses (see the conflict questions); "correct" means "agrees with the guide".
