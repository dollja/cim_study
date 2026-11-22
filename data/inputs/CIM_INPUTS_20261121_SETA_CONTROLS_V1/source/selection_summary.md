# Pilot Selection Summary

**Status:** Pending independent human review (`adjudicated_label: "pending"` across all 20 pilot cases and 8 paired controls).

## 1. Deliverables Generated

- [screening_log.csv](file:///Users/sim/gemini/antigravity/scratch/consequential-mismatch-study/screening_log.csv) — 52 screened dev-split candidates (32 HCRC MapTask, 20 Werewolf Among Us).
- [pilot_cases.jsonl](file:///Users/sim/gemini/antigravity/scratch/consequential-mismatch-study/pilot_cases.jsonl) — 20 selected episodes (10 MapTask, 10 Werewolf), with `observer_input`, `cutoff`, `review_annotations`, `later_evidence`, and `verification_status` stored in separate fields.
- [paired_controls.jsonl](file:///Users/sim/gemini/antigravity/scratch/consequential-mismatch-study/paired_controls.jsonl) — 8 paired controls (`PC-01`–`PC-08`, outside the count of 20), each extending its linked parent case by the next 2 eligible responses before repair.
- [build_deliverables.py](file:///Users/sim/gemini/antigravity/scratch/consequential-mismatch-study/build_deliverables.py) — Reproducible generator script.

## 2. Counts Screened, Eligible, and Selected

| Dataset | Screened | Eligible | Excluded | Selected | Potential Consequential Mismatch | Aligned / Consequence-Equivalent | Unresolved | Shortfall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| HCRC MapTask v2.1 (`m2, m6, m9, m12`) | 32 | 32 | 0 | 10 | 4 (`MT-01`–`MT-04`) | 3 (`MT-05`–`MT-07`) | 3 (`MT-08`–`MT-10`) | 0 |
| Werewolf Among Us (`val.json`: 16 YouTube, 4 Ego4D) | 20 | 19 | 1 | 10 | 4 (`WW-01`–`WW-04`) | 3 (`WW-05`–`WW-07`) | 3 (`WW-08`–`WW-10`) | 0 |
| **Total** | **52** | **51** | **1** | **20** | **8** | **6** | **6** | **0** |

## 3. MapTask Map-Pair ID Verification (`m2` vs `m3`)

All 10 MapTask episodes were verified against [map_trans_mapping.txt](file:///Users/sim/gemini/antigravity/scratch/consequential-mismatch-study/repos/gmmt/annotations/assets/map_trans_mapping.txt), [dialogue_map_images.csv](file:///Users/sim/gemini/antigravity/scratch/consequential-mismatch-study/repos/gmmt/annotations/assets/dialogue_map_images.csv), and [proposed_maptask_split_manifest.json](file:///Users/sim/gemini/antigravity/scratch/consequential-mismatch-study/proposed_maptask_split_manifest.json):

- `q2nc4` (`MT-03`) and `q6ec4` (`MT-07`) are confirmed in both `map_trans_mapping.txt` and `dialogue_map_images.csv` as **`m2`** (`map2g.png` / `map2f.png`).
- `q5ec3` (`MT-09`) is confirmed as **`m6`**.
- `q5nc2` (`MT-01`), `q5ec2` (`MT-02`), `q1ec2` (`MT-06`), and `q1nc8` (`MT-10`) are confirmed as **`m9`**.
- `q1ec7` (`MT-04`), `q1nc7` (`MT-05`), and `q1ec1` (`MT-08`) are confirmed as **`m12`**.
- In `proposed_maptask_split_manifest.json`, `pilot_dev_map_pairs` is `["m12", "m2", "m6", "m9"]` and `m3` is in `held_out_map_pairs`. Because Chapter 5's earlier workbook is not present in this workspace, it cannot be inspected directly here; we record that this run's `m2` assignment is verified against the HCRC/GMMT source files and split manifest, and flag the `m2` vs `m3` discrepancy against Chapter 5's earlier workbook as either a different pilot selection or a bookkeeping error in the earlier workbook, pending human confirmation.

## 4. Werewolf Registration, Media Verification, and Exclusion

- **Excluded (`screening_log.csv`):** `ONE NIGHT ULTIMATE WEREWOLF 30  February 17th 2018__Game4` (`WW-EXCL-FEB17-G4`) is retained in `screening_log.csv` with `status=excluded` (`eligibility=ineligible`) after video review showed both Caitlynn and Justin claiming to rob Mike (a conflicting role claim rather than an interpretation mismatch), alongside a minor ASR difference (`"for"` vs `"from"` at turn 26).
- **10th Slot Filled (Aligned):** `64076f60-f3fc-4ee6-93e1-3489d8ec7b12__Game3` (`WW-07`, Ego4D `val.json`, cutoff turn 44) was verified via a trimmed clip (`64076f60_Game3_1_clip.mp4`, `--start 270 --duration 90`). Hailey claims Robber (swapping with Erin), Erin claims Troublemaker (swapping Hailey and Jack), and Jack says `"You Swapped our cards? Okay, I know you're the Werewolf."` Both the full Robber+Troublemaker chain and the Troublemaker-only chain assign Jack's Werewolf card to Hailey.
- **Minor ASR Notes Observed in Media Checks:** `ONE NIGHT ULTIMATE WEREWOLF  Retro 5__Game2` (`WW-03`) has `"swatched"` for `"swapped"` at turn 45; `ONE NIGHT ULTIMATE WEREWOLF 9  November 6th 2016__Game4` (`WW-06`) has `"claim all the inside"` at turn 41. Both were checked against video audio and do not alter the cutoff interpretations.

## 5. Paired Controls (Outside the Count of 20)

Eight paired controls (`PC-01`–`PC-08`) are stored in `paired_controls.jsonl`, each adding the next 2 eligible responses before repair:
- **MapTask:** `PC-01` (`MT-01`, `q5nc2`, `utt:72`→`74`), `PC-02` (`MT-02`, `q5ec2`, `utt:68`→`70`), `PC-03` (`MT-05`, `q1nc7`, `utt:31`→`33`), `PC-04` (`MT-07`, `q6ec4`, `utt:50`→`52`).
- **Werewolf:** `PC-05` (`WW-01`, turns `60`→`62`), `PC-06` (`WW-02`, turns `39`→`41`), `PC-07` (`WW-05`, turns `84`→`86`), `PC-08` (`WW-07`, turns `44`→`46`).

## 6. Cited Examples by Category (Proposed Labels Pending Human Review)

- **Potential Consequential Mismatch:** `WW-02` (`ONE NIGHT ULTIMATE WEREWOLF 4  July 14th 2016__Game2`, cutoff `turn:39`) — Paul asks `"Now I'm the werewolf, aren't I?"` and Justin replies `"No, you're a tanner. I was a tanner."`, yielding incompatible voting targets (Werewolf vs Tanner) until Mitchell later admits he lied (`turn:43`).
- **Aligned / Consequence-Equivalent:** `MT-06` (`q1ec2`, `m9`, cutoff `utt:50`) — Giver refers to `"to about the height of hot wells"` while Follower has `"some hot springs"`, yet both align on the same vertical stopping height (GMMT human-verified).
- **Unresolved:** `WW-08` (`0a6ef9dc-a2dc-452b-a907-d6fa2ed4cae0__Game1`, cutoff `turn:72`) — Hailey states `"I don't remember like who I switched around."`, leaving the current Werewolf card assignment underdetermined at cutoff.
