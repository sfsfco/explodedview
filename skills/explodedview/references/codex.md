# Host adapter: Codex / OpenAI

## Constraint

"OpenAI" covers three different things, only two of which can run a script:

| Surface | Can run `generate.py`? |
|---|---|
| ChatGPT web / app | **No.** No shell. A SKILL.md is inert here. |
| Codex CLI | Yes — has a shell |
| OpenAI API directly | Yes — via the `openai` provider, with your own key |

If the user is in the ChatGPT app, this skill cannot help. Say so rather than
producing a long prompt they then have to paste somewhere else.

## Install

Codex does not have a single documented global skills directory that the test
suite here could verify. Two workable options:

**Option A — project-scoped.** Copy the skill into the repository you are
working in, under `.codex/skills/explodedview/`, and commit it. Travels with the
project, reviewable in a PR.

**Option B — reference it from `AGENTS.md`.** Point Codex at the skill
directory and paste the relevant sections. Less automatic, but works anywhere
the path is reachable.

Verify the exact directory your Codex version reads before publishing option A
as canonical. The script is host-agnostic; only the path is version-specific.

## Generating

```bash
export OPENAI_API_KEY=...
python3 scripts/generate.py --prompt-file prompt.txt --reference src.png --out exploded.png
```

For gpt-image-1, `--aspect-ratio` maps to the model's three real sizes:
`1:1` → `1024x1024`, `16:9` and `3:2` → `1536x1024`, `2:3` and `9:16` →
`1024x1536`. Anything else is rejected with a message naming the valid sizes
rather than silently sent through.

## Delivering the result

Confirm the file exists, then reference the absolute path in your reply. State
what the image shows and list the components you inferred rather than read off
the source.
