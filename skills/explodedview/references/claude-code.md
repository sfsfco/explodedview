# Host adapter: Claude Code

## The important constraint

**Claude cannot generate images.** Anthropic does not offer an image-generation
API. If you have only `ANTHROPIC_API_KEY`, this skill cannot produce a picture.

That is not a limitation of the skill, and it is worth being upfront about rather
than discovering it after a long run. The division of labour:

| Job | Who does it |
|---|---|
| Read the drawing, identify components, decide explosion axes | Claude |
| Write the prompt | Claude |
| **Draw the image** | **Gemini or OpenAI — not Claude** |

So in a Claude host you need a *second* key for the drawing step:

```bash
export GEMINI_API_KEY=...   # or OPENAI_API_KEY
```

If neither is set, `generate.py` exits with a message saying so instead of
failing somewhere deep.

## Install

The directory is `skills/explodedview/`; it must be reachable from wherever
Claude Code loads skills. For a user-level install that is
`~/.claude/skills/explodedview/`:

```bash
ln -s "$PWD/skills/explodedview" ~/.claude/skills/explodedview
```

> Install path is stated from the conventional Claude Code layout. Confirm it
> against your version before publishing this as authoritative — it is the one
> detail here not verified by the test suite.

## Generating

```bash
python3 scripts/generate.py --prompt-file prompt.txt --reference src.png --out exploded.png
```

`--provider auto` will select `gemini` if `GEMINI_API_KEY` is set, otherwise
`openai`. It will never select Anthropic.

Inspect what will be sent without sending it:

```bash
python3 scripts/generate.py --prompt-file prompt.txt --provider gemini --dry-run
```

## Delivering the result

Verify the file exists (`test -f exploded.png`), then reference its absolute
path in the reply so Claude Code renders it inline. Follow with a sentence
naming each component you inferred rather than read from the source.

---

## When to use the parts of this skill without generating anything

The engineering-fidelity and explosion-logic sections are useful even when you
cannot draw. If the user asks you to *explain* how an assembly comes apart, or to
list components, or to sanity-check a vendor drawing, follow SKILL.md directly
and skip PRODUCTION. Do not generate an image nobody asked for.
