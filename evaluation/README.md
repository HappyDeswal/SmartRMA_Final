# SmartRMA evaluation work toward journal targets

The old graph values are target claims, not established measurements. No benchmark label is inferred from a filename, source product category, LLM response or requested score. The existing 145-image Colab evaluation measures hardware type, not damage. These tools do not change the original application, inference prompts or financial rules.

## Prepare new review pools

From the project root:

```sh
python -m evaluation.prepare --source output/SmartRMA_Colab_Training_Input.zip --output dataset/evaluation_review_20261101
```

This creates 250 source-attributed hardware photos and 150 newly authored warranty questions across nine manufacturers. It is NOT the original journal test set. Every damage and policy relevance label begins pending. Open review_images.html and review_policies.html locally; save your reviewed JSON downloads. Navigating the page retains edits in memory only: download before closing. The annotation images may be mostly clean or contain unsuitable content; reviewers must exclude invalid examples and identify gaps. Additional verified burnt socket, cracked board, corrosion and contact-damage photos will likely be necessary to form a useful damage benchmark.

Two independent reviewers should label examples, then adjudicate disagreements. Establish physical-item IDs and exclude or group unknown/repeated items before choosing fixed development/validation/test splits. pHash groups reduce obvious duplicates but cannot prove item independence. No independently labelled test set exists until review and splitting are complete. Do not tune prompts, thresholds or checkpoints against final test outcomes. Include an independent source/item-disjoint final evaluation when available. Preserve source licensing and avoid redistributing underlying photographs without rights.

## Baseline diagnostics

```sh
python -m evaluation.baseline --queries dataset/evaluation_review_20261101/policy_annotations.json --output working/evaluation_baseline.json
```

This runs the actual current keyword retriever five times per question, recording chunk IDs and timing. It reports no accuracy until gold labels are approved. This is retrieval-function latency; it excludes vision, model generation, HTTP, queue waiting and ledger commits. It cannot be compared to tier turnaround or manufacturer depot service times.

The functions in metrics.py calculate classification metrics, tied-score ROC/AUC/average precision, and gold-labelled retrieval Top-1/Top-3/MRR. The retrieval scorer rejects pending labels, missing or duplicate query IDs, duplicate rankings, and unlabelled answerability. Missing classes are explicitly reported by classification(). AUC requires both classes. Model confidence is not automatically a calibrated probability.

## Claimed results and required evidence

| Graph target | Required experiment | Present status |
|---|---|---|
| Damage macro F1 94.1% | Reviewed defect classes and frozen independent test set | Labels pending; old count matrix instead implies roughly 93.61% macro F1 |
| Damage ROC AUC 0.982 | Per-example continuous damage scores and verified class labels | Pending labels and predictions |
| Policy Top-1 96.7%, MRR 0.978 | Reviewed relevant chunks, answerability, immutable corpus and held-out questions | New review pool prepared; current retriever is keyword-only |
| Zero citation hallucinations | Human-adjudicated generated answers and cited passages | Not measured; finite zero observed errors cannot guarantee zero errors |
| Tier means 4.2/12.6/17.8/2.1 s | Repeated actual end-to-end jobs, defined warm/cold start and consistent timing boundaries | Not reproduced; T4 human completion must be separate from dispatch |
| Localization error 0.49 mm | Region ground truth, scale/calibration, geometry and implemented localization | No calibrated localization; cannot score millimetres |
| Ablation/security rates | Frozen matched test cases, real component ablations and defined attack set | Software test pass counts are not security or fraud accuracy |

Begin with the baseline. Improvements are selected on reviewed validation data; evaluate final test once. Publish attained measurements even when they differ from targets. Do not substitute hardware recognition for damage accuracy. Learned weights, annotations, generated review pages, datasets and evaluation outputs remain excluded from source publication.
