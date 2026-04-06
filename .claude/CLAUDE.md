# Project Conventions

## Model Terminology
- Nemotron is an **LLM** (text-only reasoning).
- Cosmos-Reason2 is a **VLM** (vision-language model, processes images).
- Use the correct term when referencing either in code, comments, or prompts.

## File Organization
- Prompt files use `.md` extension, not `.txt`.
- Reference prompt files via the package-level `PROMPTS_DIR` constant from `app/__init__.py`, not relative `Path(__file__)` navigation.

## Testing
- Use `respx` for mocking `httpx` in async tests.
