# Host adapter: anything else with a shell

If your agent can run a shell command, this file is the whole adapter. Read
`SKILL.md` for the domain logic and the four steps, and follow the two
requirements below.

## Requirements

1. **Python 3.9+.** No third-party packages. `generate.py` is stdlib-only on
   purpose — a skill that needs `pip install` fails for a large share of users.
2. **One image provider credential**, from this list:
   - `GEMINI_API_KEY` — Nano Banana
   - `OPENAI_API_KEY` — gpt-image-1
   - `MINIMAX_API_KEY` — MiniMax image-01, text only (cannot take the source
     image; prompt ≤ 1,500 characters). See `minimax-api.md`.
   - or `mcode-tools` on PATH (works in any shell host, not just MiniMax Code)
3. **A model that can see the source image**, or an image-understanding tool
   to stand in for it. See Input Analysis in SKILL.md.

`<skill-dir>` in the commands below is the directory containing SKILL.md.

## Run

```bash
python3 <skill-dir>/scripts/generate.py --prompt-file prompt.txt --reference src.png --out exploded.png
```

`--provider auto` picks whatever is available, in the order `mcode`, `gemini`,
`openai`, `minimax`, preferring one that takes the source image. To see what it
would pick and what it would send, without spending anything:

```bash
python3 <skill-dir>/scripts/generate.py --list
python3 <skill-dir>/scripts/generate.py --prompt-file prompt.txt --dry-run
```

## Deliver the image

This is the one part with no universal answer, because media embedding is a
host feature, not a script feature. Whatever your host uses:

1. Verify the file exists — `test -f <absolute-path>`.
2. Open it with your image-reading tool and check it against the source.
   Then surface it using your host's media syntax. If your host has none, give the
   absolute path and say plainly that the file is at that path.
3. Follow with a sentence describing what the image shows, and name every
   component you **inferred** rather than read directly off the source.

Step 3 is not optional bookkeeping. In an exploded view, an invented nozzle or
a missing handrail is the kind of error an engineer will not catch by looking,
and they will not remember to check. Say what you guessed.

## If you have no image credential at all

The skill still has value. The engineering-fidelity rules, the explosion-logic
heuristics, the industrial parts checklist, and the "no baked-in text" lesson
are all usable without drawing anything.

If the user asked for an illustration and you cannot produce one, say that
plainly and offer what you *can* do: a component list, a parts table, an
assembly sequence, or a ready-to-run command once they add a key. Do not
substitute a long textual description for the image and present it as though
it were the deliverable.
