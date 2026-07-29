# prompts/v2/ — V2.1 Prompt Templates (Placeholder)

This directory is reserved for **TestGen AI V2.1** prompt templates.

## Status

⏳ **Not yet implemented.** V2.1 development begins after V1.0 freeze is complete.

## Expected structure

```
prompts/
    v1/                    ← V1.0 active templates (DO NOT MODIFY)
        system.txt
        developer.txt
        user.txt
    v2/                    ← V2.1 templates (this directory)
        system.txt         ← Enhanced system prompt with reliability instructions
        developer.txt      ← Extended with sandbox/review context
        user.txt           ← Extended with repository context (RAG)
        review.txt         ← NEW: Second-pass review prompt
        self_heal.txt      ← NEW: Self-healing repair prompt
```

## Rules

1. **Never overwrite `v1/`** — V1 prompts are frozen and must remain intact for historical comparison.
2. **V2 prompt loading** is controlled by `PROMPT_VERSION=v2` in `.env`.
3. The `PromptBuilder` loads from `prompts/<PROMPT_VERSION>/` — no code change needed to activate V2 prompts.
4. V2-specific prompts (`review.txt`, `self_heal.txt`) will be loaded by new V2 pipeline stages, not by `PromptBuilder` directly.

## References

- V1 templates: `../v1/`
- Prompt loading logic: `../../ai/prompt_builder.py`
- Prompt version config: `PROMPT_VERSION` in `../../../core/config.py`
