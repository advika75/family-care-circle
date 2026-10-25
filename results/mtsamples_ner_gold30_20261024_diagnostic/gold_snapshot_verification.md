# MTSamples gold snapshot verification

**Snapshot date:** 2026-10-24  
**Purpose:** Preserve the current working-tree gold annotations before any adjudication. This is a file-copy snapshot only; no labels were adjudicated or changed.

## Snapshot location and contents

- Snapshot directory: `data/public/mtsamples/gold_adjudication_v1_20261024/`
- Manifest: `data/public/mtsamples/gold_adjudication_v1_20261024/annotation_manifest.json`
- Annotation files: 30 JSON files listed below (31 files total including the manifest).
- Source of copies: the current working-tree files under `data/public/mtsamples/gold/`, including the current working-tree manifest. No Git revision was used as the copy source.
- Manifest byte comparison: copied manifest is byte-identical to the current working-tree manifest.
- Each copied annotation JSON is byte-identical to its corresponding current working-tree JSON.

| Snapshot annotation JSON | Manifest source note | Manifest status |
|---|---|---|
| `mtsamples_2-D_Echocardiogram_-_1.json` | `mtsamples_2-D_Echocardiogram_-_1.txt` | `complete` |
| `mtsamples_Acute_Inferior_Myocardial_Infarction.json` | `mtsamples_Acute_Inferior_Myocardial_Infarction.txt` | `complete` |
| `mtsamples_Aortobifemoral_Bypass_-_1.json` | `mtsamples_Aortobifemoral_Bypass_-_1.txt` | `complete` |
| `mtsamples_Bunionectomy_Osteotomy.json` | `mtsamples_Bunionectomy_Osteotomy.txt` | `complete` |
| `mtsamples_Carotid_Cerebral_Arteriograms.json` | `mtsamples_Carotid_Cerebral_Arteriograms.txt` | `complete` |
| `mtsamples_Carotid_Ultrasound.json` | `mtsamples_Carotid_Ultrasound.txt` | `complete` |
| `mtsamples_Chest_Pulmonary_Angio.json` | `mtsamples_Chest_Pulmonary_Angio.txt` | `complete` |
| `mtsamples_EMG_Nerve_Conduction_Study_-_6.json` | `mtsamples_EMG_Nerve_Conduction_Study_-_6.txt` | `complete` |
| `mtsamples_Epididymectomy.json` | `mtsamples_Epididymectomy.txt` | `complete` |
| `mtsamples_Escharotomy.json` | `mtsamples_Escharotomy.txt` | `complete` |
| `mtsamples_Esophagogastroduodenoscopy_-_3.json` | `mtsamples_Esophagogastroduodenoscopy_-_3.txt` | `complete` |
| `mtsamples_Fat_Harvesting.json` | `mtsamples_Fat_Harvesting.txt` | `complete` |
| `mtsamples_Full-Field_Digital_Mammogram_FFDM_-_2.json` | `mtsamples_Full-Field_Digital_Mammogram_FFDM_-_2.txt` | `complete` |
| `mtsamples_Leaking_Nephrostomy_Tube.json` | `mtsamples_Leaking_Nephrostomy_Tube.txt` | `complete` |
| `mtsamples_Low-Transverse_C-Section.json` | `mtsamples_Low-Transverse_C-Section.txt` | `complete` |
| `mtsamples_MGUS_Followup.json` | `mtsamples_MGUS_Followup.txt` | `complete` |
| `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064.json` | `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064.txt` | `complete` |
| `mtsamples_Pectoralis_Tendon_Repair.json` | `mtsamples_Pectoralis_Tendon_Repair.txt` | `complete` |
| `mtsamples_Prostate_Adenocarcinoma_-_H_P.json` | `mtsamples_Prostate_Adenocarcinoma_-_H_P.txt` | `complete` |
| `mtsamples_Psychosocial_Eval_for_Kidney_Transplant.json` | `mtsamples_Psychosocial_Eval_for_Kidney_Transplant.txt` | `complete` |
| `mtsamples_Radical_Mastectomy.json` | `mtsamples_Radical_Mastectomy.txt` | `complete` |
| `mtsamples_Sebaceous_Cyst_Removal.json` | `mtsamples_Sebaceous_Cyst_Removal.txt` | `complete` |
| `mtsamples_Spinal_fluid_evaluation.json` | `mtsamples_Spinal_fluid_evaluation.txt` | `complete` |
| `mtsamples_Status_Post_T_A.json` | `mtsamples_Status_Post_T_A.txt` | `complete` |
| `mtsamples_Tenosynovectomy_Cortisone_Injection.json` | `mtsamples_Tenosynovectomy_Cortisone_Injection.txt` | `complete` |
| `mtsamples_Tilt_Table_Test_-_1.json` | `mtsamples_Tilt_Table_Test_-_1.txt` | `complete` |
| `mtsamples_Total_Knee_Replacement.json` | `mtsamples_Total_Knee_Replacement.txt` | `complete` |
| `mtsamples_Total_Thyroid_Lumpectomy.json` | `mtsamples_Total_Thyroid_Lumpectomy.txt` | `complete` |
| `mtsamples_Transesophageal_Echocardiogram.json` | `mtsamples_Transesophageal_Echocardiogram.txt` | `complete` |
| `mtsamples_Weight_Gain_and_Edema.json` | `mtsamples_Weight_Gain_and_Edema.txt` | `complete` |

## Verification results

- Manifest entries: **30**; all statuses are **`complete`**.
- Expected snapshot files: **31**; actual files: **31**. Missing files: **0**. Unexpected files: **0**.
- Annotation entities checked: **529**.
- Annotation file IDs inconsistent with manifest: **0**.
- Annotation `source_file` values inconsistent with manifest: **0**.
- Missing manifest-referenced source notes: **0**.
- Invalid offsets or entity text not equal to `source[start:end]`: **0**.
- Overlapping spans within annotation files: **0**.

The checks compare each entity's saved text to the corresponding source note using zero-based Python character offsets and an exclusive end. No discrepancy was automatically corrected.

## Existing worktree state and preservation

Before copying, `git status` and the manifest diff were inspected read-only. The manifest was already modified in the worktree: its 30 statuses differ from the base version as `pending` → `complete`; the IDs and source filenames are unchanged. This snapshot preserves that current manifest state. No existing manifest, annotation, source note, policy, code, or experiment result was changed by this snapshot task. The worktree may contain other pre-existing changes; they were left untouched.
