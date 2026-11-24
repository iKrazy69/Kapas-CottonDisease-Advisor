# Retrieval cutoff calibration

Current cutoff in config.py: 0.3. Decision: **ADOPT 0.67**. gap 0.643 to 0.689; every held-out answerable question scored at or above it and every held-out off-topic question below it.

| group | best-passage similarity range |
|---|---|
| development, guide answers it (benchmark, en + hi) | 0.689 to 0.878 (n = 72) |
| development, off-topic (benchmark, en + hi) | 0.507 to 0.643 (n = 12) |
| development, cotton but not in the guide (benchmark, en + hi) | 0.652 to 0.755 (n = 10) |
| held-out, guide answers it | 0.694 to 0.861 (n = 24) |
| held-out, off-topic | 0.519 to 0.660 (n = 12) |
| held-out, cotton but not in the guide | 0.603 to 0.724 (n = 6) |

Cotton questions the guide does not cover score as high as covered ones, so a similarity cutoff cannot catch them. The model's refusal and the internet-fallback rules handle those.

Held-out questions are drafts written for this check and in English only; the Hindi questions reach the search as English translations.

### held-out: answerable

- 0.694  What is Verticillium wilt?
- 0.715  What is the Per Cent Disease Index?
- 0.737  What is the role of Trichoderma in cotton disease management?
- 0.767  What does pink bollworm damage look like?
- 0.772  How should I dispose of crop residue to reduce disease?
- 0.785  What are mirid bugs and how do I manage them?
- 0.803  How do jassids damage cotton?
- 0.804  What is Target spot of cotton and how do I recognise it?
- 0.804  How do I manage aphids on cotton?
- 0.807  How does weather affect boll rot?
- 0.813  How do I control thrips in my cotton field?
- 0.814  Which weeds should I remove to reduce leaf curl virus?
- 0.814  What are the symptoms of Alternaria leaf spot?
- 0.817  How can I tell if my cotton has bacterial blight?
- 0.817  How does neem help against sucking pests in cotton?
- 0.821  How many pheromone traps should I install for pink bollworm?
- 0.824  What are the symptoms of Fusarium wilt in cotton?
- 0.829  How can I control mealybugs in cotton?
- 0.830  How do I use pheromone traps to monitor bollworm?
- 0.832  How do yellow sticky traps help against whitefly?
- 0.834  How can I manage grey mildew in cotton?
- 0.836  How do I manage root-knot nematodes in cotton?
- 0.837  How can I recognise cotton leaf curl disease in the field?
- 0.861  How do I manage dusky cotton bug?

### held-out: off_topic

- 0.519  Which laptop should I buy?
- 0.527  How do I reset my phone password?
- 0.545  What is the price of gold today?
- 0.549  How do I lose weight fast?
- 0.579  Translate hello into French.
- 0.580  Explain how aeroplanes fly.
- 0.591  What is a good recipe for paneer?
- 0.624  Who is the prime minister of India?
- 0.634  Write a poem about the moon.
- 0.654  How do I apply for a driving licence?
- 0.656  What is the weather today in Delhi?
- 0.660  When is the next cricket match?

### held-out: cotton_not_covered

- 0.603  What subsidy is there for buying a tractor?
- 0.653  What price will the government pay for my cotton?
- 0.670  What is the cotton market price today?
- 0.678  How do I get a loan for my cotton farm?
- 0.710  What are the rules for exporting cotton?
- 0.724  Which cotton variety gives the highest yield?
