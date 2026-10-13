**Dataset: synthetic, 12 notes x 3 seeds**

| Ablation | ΔFK patient | ΔFK child | Child sentences ≥8 words | ROUGE-L patient | Retention patient | Retention caregiver | 1st-try retention patient | Unsupported numbers / note (patient) | Fallback rate | Truncated (patient) | JSON valid | Retries / note | Latency / note (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | -2.69 ± 0.15 | -4.89 ± 0.24 | 74.1% ± 4.3 | 0.21 ± 0.00 | 96.3% ± 1.9 | 99.8% ± 0.4 | 81.0% ± 3.8 | 0.14 ± 0.05 | 13.0% ± 7.0 | 0.0% ± 0.0 | 100.0% ± 0.0 | 2.14 ± 0.54 | 98.6 ± 15.3 |
| child_v1 | -2.69 ± 0.15 (+0.00) | -3.67 ± 0.15 (+1.22) | 88.3% ± 4.4 (+14.1 pp) | 0.21 ± 0.00 (+0.00) | 96.3% ± 1.9 (+0.0 pp) | 99.8% ± 0.4 (+0.0 pp) | 81.0% ± 3.8 (+0.0 pp) | 0.14 ± 0.05 (+0.00) | 13.0% ± 7.0 (+0.0 pp) | 0.0% ± 0.0 (+0.0 pp) | 100.0% ± 0.0 (+0.0 pp) | 2.14 ± 0.54 (+0.00) | 73.9 ± 8.0 (-24.68) |
| no_ner_injection | -2.58 ± 0.04 (+0.11) | -4.99 ± 0.28 (-0.10) | 75.8% ± 9.2 (+1.7 pp) | 0.20 ± 0.01 (-0.01) | 88.3% ± 2.3 (-7.9 pp) | 91.0% ± 2.8 (-8.8 pp) | 69.3% ± 2.8 (-11.8 pp) | 0.28 ± 0.17 (+0.14) | 30.6% ± 5.6 (+17.6 pp) | 2.8% ± 4.8 (+2.8 pp) | 100.0% ± 0.0 (+0.0 pp) | 3.42 ± 0.08 (+1.28) | 86.1 ± 8.8 (-12.45) |

_Values are mean ± std across 3 seeds; parentheses give the difference of means from **baseline** (pp = percentage points). ΔFK = persona grade minus source grade (more negative = simpler). Retention is the model's own text after retries but before the fallback. 1st-try retention is the cleanest measure of entity injection, since retries re-inject missing facts. Fallback rate = share of all persona outputs that needed the fallback. Truncated = generation stopped at max_new_tokens._
