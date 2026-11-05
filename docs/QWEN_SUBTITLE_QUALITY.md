# Qwen original-subtitle quality audit

Date: 2026-11-05. Video: https://www.youtube.com/watch?v=YGi-aPUsZrQ

Historical baseline audit. Subsequent fixes and measured acceptance are in
QWEN_T4_REMEDIATION.md. The findings below describe the pre-fix output.

## Verdict

The sampled narration is broadly recognizable, but the output is not accepted as
polished, high-quality original subtitles. There are meaningful homophone errors,
inconsistent proper names, lost punctuation/CJK formatting, and confirmed token
duplication at chunk boundaries. Successful full-video GPU execution does not
establish linguistic accuracy. This audit changes no production code or prompts.

## Evidence and limits

- Exact retained 8996.72-second mono 16kHz audio from the GPU benchmarks; no new
  Qwen run. Full T4 output: 13,905 aligned tokens, 1,093 display cues, 788 speech units.
- Gemini gemini-3.8-flash independently transcribed 21 selected clips totaling
  580.72 seconds. Deepgram nova-3/zh independently transcribed 14 of those clips,
  totaling 384.72 seconds. Both received audio without the Qwen transcript.
- Clips cover distributed positions and targeted difficult regions. This is not
  random sampling, and the two sets overlap; do not add their durations as coverage.
- There is no manually verified ground truth, human listening acceptance, full-video
  semantic review, validated word-level timing error, or defensible CER/WER score.
  Automated references can be wrong. Character disagreement ratios in the raw
  numeric reports are not accuracy: numeral forms, names, pronouns and clipped
  sentence boundaries also affect them.

## Findings

### Confirmed postprocessing defects

1. **Punctuation and Chinese spacing.** None of the 1,093 resulting cues contain
   punctuation; 1,063 contain spaces between Chinese characters. `gpu/asr.py`
   aligns recognized text and returns only aligned tokens; `words_to_cues` in
   `backend/subtitles.py` joins them using a space. The resulting display text
   loses sentence structure. This does not prove the raw Qwen recognizer cannot
   produce punctuation: raw pre-alignment text was not retained in this benchmark.

2. **Duplicate tokens from adjacent windows.** Four locations are established by
   comparing both raw window outputs with the final retained output:

   | Video time | Both raw windows | Joined output |
   | --- | --- | --- |
   | 00:19:14 | 成为强者 | 成为为强者 |
   | 00:43:14 | 难得一见 | 难得一一见 |
   | 01:12:50 | 很不满 | 很不不满 |
   | 02:16:50 | 辽阔 | 辽辽阔 |

   `backend/jobs.py::modal_asr` retains words by the midpoint of each independent
   alignment relative to window ownership. Slight timing differences put the same
   spoken token on opposite sides of the boundary, retaining it twice. For example,
   the two 不 tokens at 4370s overlap for 160ms. These are confirmed merger defects,
   not independent evidence that the acoustic model heard a repeated word.

   The structural scan finds five overlapping equal-token pairs; the fifth at
   00:32:02 is 妈妈, a legitimate two-character word present in both windows.
   Do not blindly delete all adjacent identical characters. The scan is a lower
   bound for merger defects, not proof that all omissions/duplicates were found.

### Strongly supported recognition errors

| Approximate time | Qwen | Audio references and context |
| --- | --- | --- |
| 01:54:48 | 头鸟 (lead bird) | Both independent references say 头牛 (lead bull); the scene concerns takin. |
| 01:20:07 | 相族 | Both references say 象族; the narration concerns elephant herd rules. |

Both errors occur in retained T4, A10, A100-40GB and A100-80GB output.
Increasing GPU size did not correct these examples.

### Issues requiring lexical verification

- Around 01:12:32 and 01:12:48, Qwen uses 封侯, a title-granting expression, as an
  animal name. Gemini suggests 蜂猴; Deepgram repeats 封侯. The context indicates
  an animal-name homophone issue, but the replacement should be checked against
  reliable species spelling/the original program, not automatically trusted.
- Elephant names vary between 多里/多利 and 戴亚/歹亚. The audio references also
  vary on name spellings. A program-specific name glossary is needed; audio
  agreement cannot establish a unique canonical written name.
- Around 01:14:53, Qwen writes 项家族 in the elephant passage. Gemini gives 象家族,
  while Deepgram gives 向家族. This is another context-sensitive spelling concern.

### Rejected false alarm in the evaluator

At 02:29:36, the final 20.72-second audio clip is entirely digital zero (every PCM
byte zero). Gemini nevertheless generated a counting sentence. Qwen and Deepgram
returned no words. Exclude that reference hallucination from Qwen omission claims.
This result does not establish that the entire preceding tail is silent.

## Timing

All retained word timestamps are finite, ordered within each word and inside the
audio duration. That is structural validity, not measured subtitle/audio sync.
The duplicate-token overlaps demonstrate why successful bounds checks alone are
insufficient. Playback-based timing acceptance remains unperformed in this audit.

## Remediation priorities (not implemented by this assessment)

1. Reconcile overlapping window text and time before cue creation. Preserve real
   repetitions such as 妈妈. Test positive duplicates, repetitions, omissions,
   timing drift, punctuation and mixed-language transitions with retained evidence.
2. Preserve recognized text/punctuation through forced alignment, then render CJK
   without inter-character spaces. Keep existing Latin word boundaries and true
   token timestamps. Test Chinese, Vietnamese, English and mixed text separately.
3. Add context-aware, conservative spelling/name normalization with a reviewed
   glossary. Never let an unconstrained rewrite invent speech or change timestamps.
4. Re-run these exact clips and a broader manually verified sample after a fix;
   distinguish formatting acceptance, semantic quality and playback timing.

## Reproduction and records

Offline structural audit: `.venv/Scripts/python.exe tools/summarize_qwen_quality.py`.
The private retained audio/transcripts are required and are excluded from Git.
The script makes no network requests or production writes.

`tools/audit_qwen_quality.py` reproduces the blinded provider sampling when local
credentials/audio are available. Missing cached clips result in real API calls.
It writes a provider report for the requested set of indices; preserve/merge the
previous report before using a different set. Do not interpret disagreement as CER.

- `research/qwen-quality-summary.json`: full structural metrics and short boundary evidence.
- `research/qwen-quality-gemini.json`: 21 completed audio cross-checks, numeric results.
- `research/qwen-quality-deepgram.json`: 14 completed independent cross-checks.
- `research/qwen-quality-sources.json`: official documentation URLs and retrieval hashes.
- Private full reference output: `.private/qwen-quality/`.

The preceding Vietnamese translation sample was superseded by the owner's
clarification. Its records remain separate and establish no translation-quality verdict.
