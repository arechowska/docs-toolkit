# docs-toolkit

A language-agnostic documentation toolkit: Markdown linter/autofixer, pre-commit hook, VS Code snippets, screenshot renaming, and Selenium-based screenshot automation.
Configure your own style rules and conventions. Default examples use Russian typography, but the engines work with any language.

*Русская версия: [README.ru.md](README.ru.md)*

## What's inside

| Tool | What it does |
| --- | --- |
| [doccheck](#doccheck) | Markdown linter and autofixer — style checks, broken links, config-driven rules |
| [Makefile](#makefile--quick-commands) | Short commands (`make check`, `make fix`) wrapping doccheck |
| [pre-commit hook](#pre-commit-hook) | Runs doccheck and compresses PNGs automatically before every commit |
| [VS Code snippets](#vs-code-snippets) | Fast-typing blocks for notes, warnings, navigation paths, form fields |
| [rename_images](#rename_images--screenshot-renaming) | Renames `imageN.png` files from Word/Pandoc conversion using captions |
| [screenshots](#screenshots--automated-screenshots) | Selenium-based screenshot capture, with a runnable demo (no real app needed) |

Detailed description of each tool follows below.

## doccheck

A Markdown documentation linter and autofixer. Checks style, fixes common mistakes, and finds broken links. Rules are defined in a config file, so it works with any project.

### Features

- **Autofix** — replaces letters, punctuation, and patterns defined in the config
- **Style checks** — warns about issues that cannot be fixed automatically
- **Link checks** — finds internal links pointing to nonexistent files
- **Colored output** — errors in red, warnings in yellow, fixes in green
- **CI-friendly** — exits with code `1` when errors are found

```text
My Project — checked: 44 files

✗ docs/user-guide/payments/payment-order.md
  ! line 12: Image without alt text
  ! line 34: Dash after a term — should be a colon

✓ docs/user-guide/general-principles/lifecycle.md
  fixed: ё → е (3×)
  fixed: trailing period in note heading (1×)
```

**Symbol legend:**

| Symbol | Meaning |
| --- | --- |
| `✓` | File is clean or was fixed |
| `✗` | File has issues |
| `!` | Warning — worth a manual look |
| `×` | Error — must be fixed manually, blocks CI |

### Requirements

- Python 3.11+ (no dependencies)
- Python 3.10: `pip install tomli`

### Quick start

**1. Copy the script into your project:**

```bash
curl -O https://raw.githubusercontent.com/yourname/doc-tools/main/doccheck.py
```

**2. Create a config:**

```bash
python3 doccheck.py --init
```

This opens `doccheck.toml` — edit the rules for your project.

**3. Run a check:**

```bash
python3 doccheck.py
```

### Commands

```bash
# Check all documentation
python3 doccheck.py

# Auto-fix issues from the [[fix]] section
python3 doccheck.py --fix

# Check a specific file or folder
python3 doccheck.py docs/user-guide/payments/

# Show only files with problems
python3 doccheck.py --quiet

# Use a different config
python3 doccheck.py --config path/to/custom.toml

# Generate an example config
python3 doccheck.py --init
```

### Configuration

All rules live in `doccheck.toml`, next to your docs project. These are the actual default rules — written for Russian text, shown here as a real example of what the config format looks like:

```toml
[project]
name   = "Project name"
docs   = "docs/"              # folder with Markdown files
ignore = ["docs/archive/"]    # folders to skip

# Autofix: applied with --fix
[[fix]]
pattern     = "ё"
replacement = "е"
description = "ё → е"

[[fix]]
pattern     = '!!! note "Примечание\."'
replacement = '!!! note "Примечание"'
description = "trailing period in note heading"

# Checks: reported as warnings or errors
[[check]]
pattern     = '!\[\]\('
description = "Image without alt text"
severity    = "warn"   # or "error" — blocks CI

[[check]]
pattern     = 'Перейдите в'
description = "Use «Откройте» instead of «Перейдите в»"
severity    = "warn"
```

To adapt this for another language, just replace the `pattern`/`replacement`/`description` values with your own style rules — the engine is language-agnostic.

#### Severity levels

| Value | Behavior |
| --- | --- |
| `warn` | Prints a warning, does not block |
| `error` | Prints an error, exits with code 1 |

`[[fix]]` rules are reported as `error` when running without `--fix`.

## Makefile — quick commands

The `Makefile` lives in the root of your documentation project (not in `tools/`).

```bash
make install   # install the pre-commit hook (once)
make check     # check documentation
make fix       # auto-fix
```

`make` is preinstalled on Mac. On Windows, use Git Bash.

## Pre-commit hook

Runs the check and compresses PNGs automatically before every commit.

```bash
# Install (from the project root)
cp pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Requires [oxipng](https://github.com/shssoichiro/oxipng) for PNG compression:

```bash
brew install oxipng   # macOS
```

## VS Code snippets

`snippets.json` contains ready-made blocks for fast typing (triggers written for Russian docs, e.g. `nav` for a navigation path template).

**Setup in VS Code:**
`Cmd+Shift+P` → Configure User Snippets → markdown → paste the contents of `snippets.json`.

## rename_images — screenshot renaming

After converting Word → Markdown via Pandoc, all images are named `image1.png`, `image2.png`, etc. This script finds the nearest caption (or a `Рис. N — ...` line), suggests a readable filename, renames the file, and updates links in the `.md` file.

```bash
# Preview suggestions without changing anything
python3 rename_images.py --dry-run docs/

# Rename, confirming each name
python3 rename_images.py docs/

# Accept all suggestions automatically
python3 rename_images.py --auto docs/

# Auto + strip «Рис. N — ...» caption lines
python3 rename_images.py --auto --strip-captions docs/
```

In the prompt: **Enter** — accept, **type a name** — use your own, **s** — skip, **Ctrl+C** — quit.

No dependencies — transliteration is built in.

## screenshots — automated screenshots

Automates screenshots via Selenium: opens app pages in a browser, captures either the full page or a single element, optionally clicks through to a modal first, and compresses the resulting PNGs.

```bash
python3 screenshots.py --list           # list screens from the config
python3 screenshots.py --page payment   # capture one screen
python3 screenshots.py                  # capture all
```

Screen settings live in `screenshots.toml`:

```toml
[[pages]]
id          = "payment_order"
url         = "/payments/payment-order"
file        = "payment_order_form.png"
element     = ".form-container"   # screenshot just this element, not the whole page
wait_for    = ".form-container"

[[pages]]
id          = "sign_modal"
url         = "/payments/payment-order/1"
file        = "sign_modal.png"
element     = ".modal-dialog"
actions     = [
  {click = "button.sign-btn"},    # click through to a modal before capturing
  {wait  = ".modal-dialog"},
]
```

Requires Selenium and real CSS selectors from your app:

```bash
pip install selenium
```

### Try it without a real app

`tools/demo/` contains a tiny self-contained login + form page and a matching config, so you can see the tool actually run without any real target application:

```bash
python3 -m http.server 8010 --directory tools/demo
python3 tools/screenshots.py --config tools/demo/screenshots.demo.toml
```

This logs in, opens the demo form, and saves an element-only screenshot to `tools/demo/output/`.

## Repository structure

```text
doccheck.py        — linter and style autofixer
rename_images.py   — screenshot renaming after Word conversion
screenshots.py      — automated screenshots via Selenium
pre-commit          — git hook: doccheck + PNG compression
snippets.json        — VS Code snippets
screenshots.toml     — screen config for screenshots.py
demo/                — self-contained example for screenshots.py, no real app needed
README.md            — this file
README.ru.md         — Russian version
```

`doccheck.toml` and `screenshots.toml` are kept per-project, not in this repo.
