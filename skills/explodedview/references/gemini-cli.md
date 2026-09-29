# Host adapter: Gemini CLI

## The convenient case

This is the one host where the reasoning model and the image model are the same
vendor. Gemini can read the drawing, decide the explosion axes, write the
prompt, and draw it with one `GEMINI_API_KEY`.

## Install

Make `skills/explodedview/` visible to the CLI. For a user-level install:

```bash
ln -s "$PWD/skills/explodedview" ~/.gemini/skills/explodedview
```

> Confirm the directory your Gemini CLI version reads — this path is stated
> from the conventional layout and is not covered by the test suite.

## Generating

```bash
export GEMINI_API_KEY=...
python3 scripts/generate.py --prompt-file prompt.txt --reference src.png --out exploded.png
```

`--provider auto` selects `gemini` when `mcode-tools` is absent.

## Model choice

Imagen is shut down and is no longer served by the Gemini API. The Nano Banana
family is the only option:

| `--model` | Use when |
|---|---|
| `gemini-3.1-flash-image` | Default. Best balance of quality, cost, latency. |
| `gemini-3-pro-image` | Complex instructions, professional asset work, up to 4K. |
| `gemini-2.5-flash-image` | High volume, 1024px, cheapest. |

```bash
python3 scripts/generate.py --model gemini-3-pro-image --prompt-file prompt.txt --out exploded.png
```

Valid `--aspect-ratio` values: `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`,
`9:16`, `16:9`, `21:9`, `1:4`, `4:1`, `1:8`, `8:1`.

## Delivering the result

Confirm the file exists, then reference the absolute path in your reply. State
what the image shows and list the components you inferred rather than read off
the source.
