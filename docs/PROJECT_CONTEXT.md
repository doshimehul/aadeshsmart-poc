# AadeshSmart POC — Project Context

**Status:** Initial schema implemented as SQLAlchemy models and an Alembic migration. PostgreSQL provisioning and migration application remain pending.

## Product objective

Build a mobile-first PWA for Jain Sangh event volunteers to record Gujarati announcements, transcribe audio with Sarvam, extract structured donation details with Gemini, match a donor against the existing PostgreSQL ledger, and let a volunteer review and correct the result.

## Scope

### In scope

- Mobile-first Next.js, React and TypeScript PWA.
- FastAPI backend organized as Controller → Service → Repository.
- Sarvam Gujarati speech-to-text and Gemini structured extraction, reusing the supplied working integrations.
- Donor lookup against the project-owned PostgreSQL ledger described below, once PostgreSQL is set up and the table shape is approved.
- Local filesystem audio storage for the POC.
- FastAPI `BackgroundTasks` for initial processing.
- Human review and correction of extracted fields and donor match.

### Out of scope

Authentication, a Sangh management portal, multi-tenancy, payments, and additional infrastructure such as Redis or Celery. No changes to the existing donor database are authorized or planned.

## Decisions and constraints

- Frontend: Next.js, React, TypeScript; mobile-first PWA.
- Backend: Python and FastAPI.
- Persistence: PostgreSQL and SQLAlchemy; Alembic for migrations; Pydantic for validation.
- Architecture: Controller → Service → Repository.
- Audio: local filesystem in the POC.
- Background work: FastAPI `BackgroundTasks` initially.
- ASR: Sarvam API, Gujarati `gu-IN`, model `saaras:v4`, `transcribe` mode per the supplied script.
- Extraction: Gemini through the OpenAI Agents SDK and Gemini's OpenAI-compatible endpoint, with Pydantic structured output.
- No existing database is available to inspect. Do not treat the proposed table outline as a finalized schema until its open workflow fields are resolved and the owner approves implementation.
- Do not copy credentials from reference `.env` files. Configure secrets through local environment files or deployment secrets; never commit them.

## Reference integration findings

The reference scripts are now included in this project under `reference/`: `reference/sarvam_ref.py` and `reference/gemini_ai.py`. They are standalone examples and are not yet integrated into the application.

### Sarvam

`stt-sarvam/main.py` loads `SARVAM_API_KEY`, constructs `SarvamAI`, and calls `client.speech_to_text.transcribe(file=..., model="saaras:v4", language_code="gu-IN", mode="transcribe")`. This call and its Gujarati configuration are the reusable core. The current script reads a hard-coded `record_out.wav` and prints the response; the application will need to accept an uploaded/recorded file and return its transcript to the processing flow.

### Gemini extraction

`main.py` loads `GOOGLE_API_KEY`, disables Agents SDK tracing, constructs `AsyncOpenAI` with `https://generativelanguage.googleapis.com/v1beta/openai/`, wraps it in `OpenAIChatCompletionsModel`, and runs an `Agent` with `output_type=GujaratiParser`. Its prompt retains donor and event text in Gujarati and converts spoken amounts to integers. `GujaratiParser` currently contains `name`, `amount`, `amount_type` (described as `rupees` or `man`), and `event`.

Reuse the client/model/agent/Pydantic-output pattern and prompt intent. Adapt invocation to the async FastAPI service lifecycle and make configuration injectable. The reference uses `Runner.run_sync` in a CLI. Its configured model identifier is `gemini-3.8-flash`; confirm that this exact model ID is enabled for the target Google account before implementation. The reference schema does not establish all product semantics (for example, how a `man` amount converts to rupees), so do not add conversions without confirmation.

### Dependency candidates

- Backend foundation: `fastapi`, `uvicorn` (or equivalent ASGI server), `python-multipart` for uploads, `python-dotenv` for local development, `pydantic` / `pydantic-settings`.
- Existing integrations: `sarvamai`, `openai-agents` (which brings the Agents SDK and its OpenAI client dependency).
- Database: `sqlalchemy`, `alembic`, and a PostgreSQL driver (`psycopg` or `asyncpg`, selected with the SQLAlchemy sync/async design).
- Frontend: Next.js, React, TypeScript, and a PWA/service-worker approach selected during implementation planning.

Pin and verify compatible versions when bootstrapping. The reference project's `pyproject.toml` currently declares `openai-agents>=0.25.0` and `python-dotenv>=1.2.4`; it does not declare the Sarvam SDK in that project manifest.

### Environment configuration candidates

- `SARVAM_API_KEY` — confirmed by the Sarvam reference.
- `GOOGLE_API_KEY` — confirmed by the Gemini reference.
- `DATABASE_URL` — needed for the application, but no value or database access method was discovered in the supplied project files.
- `AUDIO_STORAGE_DIR` — configurable local audio directory.
- `MAX_UPLOAD_SIZE_BYTES` and allowed audio content types — operational limits to agree and enforce.
- `GEMINI_MODEL` — make the model configurable after confirming the working model identifier.

Do not put any secret values in this document or source control.

## Proposed initial data model and matching discovery

The owner clarified that PostgreSQL is not set up yet and proposed two tables:

```text
ledger
- id
- ledger_name
- contact_person
- mobile
- created
- modified

recordings
- id
- ledger_id (nullable; selected donor contact)
- file_name
- size
- transcript
- progress_status: uploaded | transcribing | extracting | matching | pending_review | completed | failed
- extracted_json
```

Each `ledgers` row represents a donor contact. The donor is identified by name and may no longer be alive; `contact_person` is the person responsible for payments. `recordings.ledger_id` is nullable and stores the volunteer's selected donor contact. The transcript is stored separately from `extracted_json`. `pending_review` means automated processing has reached the volunteer review step; `completed` means the volunteer has finished review.

This is the owner's proposed starting outline, with spelling normalized for readability and the above clarifications incorporated. The initial implementation uses integer identity primary keys; required `ledger_name`; optional `contact_person` and `mobile`; and timezone-aware `created` and `modified` timestamps. `recordings.file_name` is a generated, unique storage key (not an untrusted upload filename), `size` is a nonnegative byte count, and `ledger_id` uses `ON DELETE SET NULL`. `transcript` and PostgreSQL `JSONB` `extracted_json` are nullable until populated. `extracted_json` holds the current structured extraction and volunteer corrections; no correction audit history is stored. `transcript` is the editable/current transcript value. Status is constrained to `uploaded`, `transcribing`, `extracting`, `matching`, `pending_review`, `completed`, and `failed`. Match the extracted donor name primarily against `ledger_name`; display `contact_person` as payment-responsibility context for volunteer review, rather than treating it as the donor's name by default. No matching strategy can be validated without representative examples. Preserve Gujarati names as entered; do not normalize destructively.

The outline also leaves several end-to-end workflow decisions open:

- **Chosen donor link:** owner confirmed nullable `recordings.ledger_id` for the selected donor contact.
- **Transcript and review:** transcript edits replace the current `recordings.transcript` value; no transcript revision history is kept in the initial schema.
- **Correction lifecycle:** corrected extraction values replace the current `extracted_json` value; the initial schema does not store correction audit history or a separate volunteer acceptance state.
- **Status vocabulary:** owner specified `uploaded`, `transcribing`, `extracting`, `matching`, `pending_review`, `completed`, and `failed`; `pending_review` identifies records ready for volunteer review, while `completed` means volunteer review is finished.
- **File storage:** `file_name` is reserved for the generated unique storage key and `size` stores bytes; upload code must still validate the original filename/content and apply storage limits.
- **Ledger semantics:** owner clarified each row is a donor contact. The donor may be deceased; `contact_person` is responsible for payments. Matching should not assume the contact person is the donor.
- **No live records:** until sample donors exist, matching can only be implemented against synthetic/local development examples. Matching quality thresholds must wait for representative real data and owner review.

No database connection was attempted and no database exists to inspect or modify. The matching repository will map the approved new schema. The owner has confirmed that `reference/sarvam_ref.py` and `reference/gemini_ai.py` are the intended Sarvam and Gemini integration references.

## Proposed initial project structure

```text
.
├── docs/
│   └── PROJECT_CONTEXT.md
├── frontend/
│   ├── app/
│   ├── public/
│   └── package.json
└── backend/
    ├── app/
    │   ├── api/                 # Controllers / HTTP routes
    │   ├── services/            # Workflow orchestration, ASR, extraction, matching
    │   ├── repositories/        # Existing-ledger read-only access
    │   ├── models/              # SQLAlchemy mappings; only after schema inspection
    │   ├── schemas/             # Pydantic request/response contracts
    │   ├── core/                # Settings and shared configuration
    │   └── main.py
    ├── alembic/                 # Only for POC-owned tables, if needed
    └── pyproject.toml
```

The `ledgers` and `recordings` tables are POC-owned tables. PostgreSQL is not yet provisioned. Alembic creates or manages only these tables. Confirm `DATABASE_URL` points to the intended project database before applying migrations. Do not connect to or alter an unrelated database.

## Integration risks and open decisions

- **Database provisioning is pending:** no PostgreSQL instance or sample donor rows exist yet, so matching behavior cannot be evaluated against real data.
- **Model identifier:** `gemini-3.8-flash` from the working script must be verified against the intended Gemini account/API.
- **Amount semantics:** `amount_type` distinguishes rupees and `man`, but the conversion and normalization rules are unspecified.
- **Name matching:** Gujarati spelling variation, ASR errors, honorifics, household/family names, and transliteration could produce false matches. The algorithm and review threshold depend on actual ledger data and volunteer workflow.
- **BackgroundTasks durability:** suitable for a small POC but jobs can be lost if the process stops; expose processing status and allow retry. Do not add a queue without discussing it.
- **Local audio storage:** requires upload size/type limits, safe generated filenames, access controls, retention/deletion policy, and a deployment model with persistent disk. These need product/operations decisions.
- **PWA recording:** mobile browser microphone permissions, supported audio encodings, interruptions, and upload behavior require device testing.
- **Sensitive information:** recordings and donor identities require a retention/access policy before deployment beyond local development.
- **Workflow persistence:** decide whether audio/transcript/extraction/review state is persisted and where; no existing schema can be assumed for these records.

## Phased implementation plan

### Phase 0 — Discovery (current)

**Deliverables:** reference integration findings, dependency/configuration inventory, architecture proposal, proposed initial data model, this context document, phased plan.

**Acceptance criteria:** working ASR/extraction call patterns and limitations are identified; proposed table outline and unresolved workflow data are documented; matching evaluation is deferred until donor samples exist; no application code or database changes occur.

**Status:** reference integrations inspected; the owner has asked to proceed with schema implementation. SQLAlchemy models and the initial Alembic migration now capture the initial workflow fields and donor/contact meaning. PostgreSQL provisioning and migration application remain pending. No existing records are available for matching evaluation because the database is not set up.

### Phase 1 — Project foundation

**Deliverables:** frontend/backend skeleton, local setup instructions, settings/env templates without secrets, health endpoint, lint/type-check configuration, initial PWA shell.

**Acceptance criteria:** frontend and API start locally; configuration fails clearly for missing required secrets; no donor database schema is modified; PWA loads on a mobile viewport.

### Phase 2 — Audio capture and Sarvam transcription

**Deliverables:** mobile recording/upload flow, bounded local audio storage, transcription service and status UI.

**Acceptance criteria:** a supported Gujarati recording is uploaded, stored under a generated safe name, transcribed by Sarvam in Gujarati, and the transcript is shown; invalid/oversized input and provider errors are surfaced clearly.

### Phase 3 — Gemini extraction and review

**Deliverables:** Gemini service adapted from the existing script, Pydantic extraction contract, review/edit screen.

**Acceptance criteria:** transcript yields validated structured fields; malformed/provider failures are recoverable; volunteer can inspect and correct extracted fields before acceptance; no undocumented amount conversion is applied.

### Phase 4 — Donor matching against the new ledger

**Deliverables:** repository mapped to the approved `ledgers` table, matching service, candidate/ambiguity UI, selected-donor persistence according to the approved recording relationship.

**Acceptance criteria:** donor lookup is non-destructive; match candidates show explainable fields; ambiguous/no-match cases remain for human review; matching is evaluated against owner-provided representative data when available; database schema stays within the approved design.

### Phase 5 — End-to-end POC hardening

**Deliverables:** workflow status/retry behavior, configuration/deployment notes, retention handling, device/provider error handling.

**Acceptance criteria:** a volunteer can complete record → transcription → extraction → donor review on a target mobile browser; interrupted/failed jobs are visible and recoverable; deployment preserves required local audio files; operational limits and retention are documented.

## Approval gate

The initial schema implementation resolves the open type, constraint, index, correction persistence, and transcript edit choices as described above. Matching behavior can be refined after representative donor rows are available.
