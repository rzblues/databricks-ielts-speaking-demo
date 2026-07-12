# LOOP.md

## Loop Name

IELTS Speaking Audio Scoring Demo Loop

## Loop Objective

Build a stable Databricks Free Edition demo that takes candidate speaking audio as input and produces an explainable IELTS-style speaking assessment report.

## North Star

A customer should be able to see:

Audio file -> transcript -> speech features -> four IELTS-style scores -> evidence-based feedback -> Databricks tables -> Streamlit report.

## Loop Law

Never continue to the next loop until the current loop has:
1. Code changes
2. Test or smoke check
3. Result summary
4. Updated docs/loop_state.md

## Operating Cycle

For every loop, follow this cycle:

1. OBSERVE
   Inspect existing repo, current files, Databricks availability, and previous loop state.

2. PLAN
   Write a short plan for only the next smallest useful increment.

3. BUILD
   Implement the increment.

4. TEST
   Run the narrowest relevant test first, then broader tests if possible.

5. SMOKE CHECK
   If Databricks is needed, run the smallest possible Databricks validation.
   If Databricks is unavailable, run the documented fallback smoke check.

6. REFLECT
   Write:
   - What changed
   - What passed
   - What failed
   - What is still risky
   - Next loop target

7. RECORD
   Update docs/loop_state.md.

## Capability Probe First

Before feature work, run Loop 0.

Loop 0 must detect:

- Python version
- Package manager
- Databricks CLI or connector availability
- Databricks auth status
- Current user if available
- Catalogs available
- Whether schema/table creation works
- Whether volume creation works
- Whether Apps are available
- Whether Model Serving endpoints are available
- Whether SQL warehouse is available
- Whether Databricks Bundles are available

Write results to:

docs/databricks_capability_probe.md

Classify environment as one of:

- FULL_DATABRICKS_DEMO
- TABLES_ONLY_DEMO
- LOCAL_PLUS_NOTEBOOK_DEMO
- LOCAL_ONLY_DEMO

Do not block if capabilities are missing. Choose the best fallback.

## Loop 0: Repo And Capability Probe

Goal:
Create initial repo structure and detect Databricks capabilities.

Build:
- Create AGENTS.md if missing.
- Create LOOP.md if missing.
- Create pyproject.toml.
- Create src/ielts_scorer package skeleton.
- Create tests skeleton.
- Create docs/loop_state.md.
- Create docs/databricks_capability_probe.md.

Test:
- python --version
- python -m pip install -e ".[dev]" or equivalent
- python -m pytest -q

Smoke:
- Try Databricks auth/capability checks if CLI or connector exists.
- If unavailable, document fallback.

Exit criteria:
- Repo structure exists.
- Capability probe written.
- Tests command runs, even if only placeholder tests exist.

## Loop 1: Core Schemas And Scoring Data Contract

Goal:
Create stable Pydantic schemas.

Build:
- Attempt
- ASRSegment
- SpeechFeatures
- DimensionScore
- ScoringReport
- Band rounding utility

Rules:
- Bands must be 0 to 9.
- Bands must normalize to nearest 0.5.
- Output must include caveats.
- All records must include attempt_id.

Test:
- test_schema_validation.py
- test_band_rounding.py

Exit criteria:
- Invalid JSON fails validation.
- Valid mock report passes validation.
- Band rounding works.

## Loop 2: Mock Vertical Slice

Goal:
Make the full pipeline work locally without Databricks, ASR, or LLM.

Build:
- sample_data/mock_transcripts.json
- sample_data/questions.json
- scripts/run_mock_demo.py
- deterministic mock scorer
- markdown report renderer

Pipeline:
mock attempt -> mock transcript segments -> features -> mock score -> report

Test:
- python scripts/run_mock_demo.py
- python -m pytest -q

Exit criteria:
- One complete report is generated locally.
- No external service calls are required.

## Loop 3: Feature Extraction

Goal:
Compute explainable features from ASR segments.

Build:
features.py must compute:
- duration_sec
- speaking_sec
- silence_ratio
- words_count
- words_per_min
- pause_count
- long_pause_count
- avg_pause_sec
- filler_count
- filler_ratio
- repetition_count
- lexical_diversity
- avg_sentence_len
- complex_sentence_proxy
- asr_confidence_proxy

Test:
- test_features.py with deterministic segment fixtures.

Exit criteria:
- Features are stable and explainable.
- Edge cases pass:
  - empty transcript
  - one segment
  - very short audio
  - repeated words
  - filler-heavy answer

## Loop 4: Databricks Schema And Delta IO

Goal:
Create Databricks tables and write/read records.

Build:
- notebooks/00_setup.sql
- delta_io.py
- notebooks/01_ingest_audio.py
- notebooks/03_extract_features.py

Databricks behavior:
- Try preferred namespace: main.ielts_demo.
- If unavailable, use discovered fallback namespace.
- Create tables if permissions allow.
- Do not fail entire project if volume creation fails.
- Document exact fallback in docs/databricks_capability_probe.md.

Test:
- Unit tests should mock Spark.
- Databricks smoke check should create or validate tables.

Exit criteria:
- Tables exist or fallback is documented.
- One mock attempt can be written and read.

## Loop 5: ASR Boundary

Goal:
Add real ASR integration behind a clean interface while preserving mock mode.

Build:
- asr.py with ASRClient interface.
- MockASRClient.
- Optional local WhisperASRClient.
- notebooks/02_transcribe.py.

Rules:
- Default to MOCK_ASR=true.
- Do not require GPU.
- Do not initialize ASR model per row.
- If using Spark, initialize ASR once per partition or process.
- If real ASR fails, write clear error and continue with mock mode.

Test:
- test_mock_asr.py.
- Local mock pipeline still passes.

Exit criteria:
- Mock ASR works.
- Real ASR is optional.
- Transcript segments are saved in the same schema regardless of ASR source.

## Loop 6: LLM Scoring Boundary

Goal:
Add LLM scoring behind a clean interface.

Build:
- llm_client.py
- rubric.py
- scoring.py
- notebooks/04_score_with_llm.py

Rules:
- Default to MOCK_LLM=true.
- If Databricks Model Serving or Foundation Model API is available, support it via environment variables.
- LLM output must be strict JSON.
- Validate with Pydantic.
- If LLM returns malformed JSON, repair once; if repair fails, fallback to mock scorer.
- Never invent audio details not present in transcript or features.

Test:
- test_mock_scoring.py.
- test_schema_validation.py.
- test_report_rendering.py.

Exit criteria:
- Mock scoring works.
- LLM client is replaceable.
- Scoring report is always valid JSON after validation.

## Loop 7: Streamlit / Databricks App

Goal:
Create customer-facing UI.

Build:
- app/app.py
- app/app.yaml
- app/requirements.txt

UI must show:
- Candidate / attempt metadata
- Audio path or upload placeholder
- Transcript
- Overall estimated band
- FC, LR, GRA, P scores
- Evidence per dimension
- Feedback per dimension
- Extracted features
- Caveats and privacy note

Rules:
- If Databricks SQL connection is unavailable, read sample local JSON.
- Do not hardcode tokens.
- Use environment variables for warehouse/resource IDs.

Test:
- Run streamlit locally if possible.
- Smoke check import of app/app.py.

Exit criteria:
- App renders sample report.
- App clearly labels scores as estimated demo output.

## Loop 8: Databricks Orchestration

Goal:
Add optional Databricks Bundle / Jobs orchestration.

Build:
- databricks.yml if supported.
- resources/jobs.yml if useful.
- README deployment section.

Rules:
- Bundle is optional.
- If Databricks Bundle commands fail because Free Edition lacks support, document manual notebook execution order.

Preferred job order:
1. 00_setup.sql
2. 01_ingest_audio.py
3. 02_transcribe.py
4. 03_extract_features.py
5. 04_score_with_llm.py
6. 05_review_results.py

Test:
- databricks bundle validate if available.
- Otherwise, notebook-by-notebook smoke check.

Exit criteria:
- Either bundle deploy path works or manual path is clearly documented.

## Loop 9: Demo Hardening

Goal:
Make the customer demo reliable.

Build:
- README.md
- docs/demo_script.md
- docs/architecture.md
- docs/known_limitations.md

Demo script must include:
- What customer sees
- What Databricks stores
- Why each score was given
- Why pronunciation is an intelligibility estimate
- How this becomes production-grade later

Test:
- Fresh clone local setup instructions.
- Mock demo from README.

Exit criteria:
- A non-author can run the mock demo.
- Customer narrative is clear.
- Known limitations are explicit.

## Loop 10: Final Verification

Goal:
End-to-end verification.

Run:
- python -m pytest -q
- python scripts/run_mock_demo.py
- Databricks table smoke check if available
- Streamlit app smoke check if available

Update:
- docs/loop_state.md final section
- README final setup
- docs/demo_script.md final talking points

Exit criteria:
- Demo is runnable in at least one mode.
- All known missing Databricks capabilities have fallbacks.
- Final answer to user summarizes status and exact run commands.

## Quality Gates

- Gate A: Local package imports successfully.
- Gate B: Unit tests pass.
- Gate C: Mock vertical slice produces a report.
- Gate D: Delta table schema exists or fallback documented.
- Gate E: One attempt_id can be traced across all outputs.
- Gate F: UI renders one completed report.
- Gate G: README run commands are accurate.
- Gate H: No real user audio committed.
- Gate I: No token or secret committed.
- Gate J: Report says "estimated", not "official".
