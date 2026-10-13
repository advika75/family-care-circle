**Dataset: MTSamples, 100 real clinical notes (backend: llama_cpp)**

| Text | FK grade ↓ | Reading Ease ↑ | ROUGE-1 | ROUGE-L |
|---|---|---|---|---|
| Source note | 9.82 ± 1.96 | 46.1 ± 12.8 | – | – |
| Patient | 5.31 ± 1.00 | 80.7 ± 5.4 | 0.25 ± 0.08 | 0.14 ± 0.05 |
| Caregiver | 8.05 ± 3.58 | 58.9 ± 10.9 | 0.20 ± 0.08 | 0.11 ± 0.04 |
| Child | 2.77 ± 0.97 | 91.7 ± 4.7 | 0.10 ± 0.04 | 0.06 ± 0.03 |

_Mean ± SD over 100 notes. ROUGE is computed against the source note._
