# Change classifier evaluation (Demo 2, Set B)

Model: `claude-sonnet-5-5` · 30 documents · 273,953 input / 14,842 output tokens

**Target (set before the run):** label accuracy at least 85.0%. **Result: 100.0%. Target met.**

| Measure | Result |
| --- | --- |
| Label accuracy (clarification vs possible change) | 100.0% |
| Change recall (real changes flagged) | 100.0% (15/15) |
| Change precision (flags that were real changes) | 100.0% |
| Notice rule correct (6.2 a/b/c/d), on flagged real changes | 100.0% (15) |
| Notice date correct: model's own date | 93.3% |
| Notice date correct: computed in code from the model's rule | 100.0% |
| Citation validity (quote found word for word) | 100.0% |
| Accuracy on the 10 tricky cases | 100.0% |

| | Predicted change | Predicted clarification |
| --- | --- | --- |
| **Real change** | 15 | 0 (missed) |
| **Real clarification** | 0 (false alarm) | 15 |

## Cases that went wrong

None.
