---
name: testing-app
description: Test the DomainFi Agent Toolkit static site and repo validator end-to-end. Use when validating UI changes to index.html, changes to scripts/validate_repo.py, or CI workflow changes.
---

# Testing the DomainFi Agent Toolkit

This repo is a static GitHub Pages site (`index.html`) + Markdown docs + a dependency-free Python validator. There is no backend, no build step, and no JS interactivity beyond an inert `<script type="application/ld+json">` block. All testing is local against the working tree.

## Prerequisites

Nothing to install. The repo only needs Python 3 (already on the VM) and a browser. There are no secrets, no `.env`, no auth.

## 1. Run the validator (cheap, deterministic, run first)

```bash
python3 scripts/validate_repo.py
```

Exit `0` and stdout `validation passed` means CI's `Validate static site` workflow will pass too — they run the exact same script.

The validator enforces:

- presence of every entry in `REQUIRED_FILES` (README, LICENSE, SECURITY, CONTRIBUTING, CODE_OF_CONDUCT, docs/{ARCHITECTURE,ROADMAP,GRANT_SCOPE}.md, index.html)
- no obvious credential patterns (the validator's own regex literals are allowlisted via `SECRET_SCAN_SKIP`)
- safe HTML in `index.html`:
  - inline-only scripts, and only inert types (`application/ld+json`, `application/json`, `text/plain`)
  - no inline `on*=` event handlers
  - no `javascript:` hrefs
  - every internal `#anchor` resolves to an actual `id`
  - every `target="_blank"` link carries `rel="noopener noreferrer"` (case-insensitive)
  - every `<img>` has `alt`
  - `<html lang>`, `<meta charset>`, `<meta name="viewport">`, and a non-empty `<meta name="description">` are present

### Adversarial sanity checks for the validator (use when changing `validate_repo.py`)

Always verify the validator still rejects what it claims to reject. Pattern: snapshot, mutate, run, restore.

```bash
cp index.html /tmp/index.html.bak
sed -i 's/<html lang="en">/<html>/' index.html
python3 scripts/validate_repo.py     # expect: validation failed: ... lang attribute
cp /tmp/index.html.bak index.html
python3 scripts/validate_repo.py     # expect: validation passed
```

```bash
cp index.html /tmp/index.html.bak
python3 -c "p='index.html';t=open(p).read();open(p,'w').write(t.replace('</body>','<script>alert(1)</script></body>'))"
python3 scripts/validate_repo.py     # expect: validation failed: ... executable scripts
cp /tmp/index.html.bak index.html
```

## 2. Preview the site locally

Always serve over HTTP rather than `file://` — the canonical/OG meta and CSP behave the way they will on GitHub Pages only over HTTP.

```bash
python3 -m http.server 8080
# then in the browser: http://localhost:8080/
```

Kill the server when done; `python3 -m http.server` blocks the shell.

## 3. Browser-only assertions

These can't be checked with curl because they depend on layout/keyboard/scroll behavior. Test all of them after any change to `index.html`.

- **Anchor nav.** Click each item in the top nav (Workflows, Doma Integration, Milestones, Docs). The URL hash should change to `#workflows`, `#integration`, `#milestones`, `#docs` and the viewport should land on the matching `<section>` heading. The nav is **not** sticky — scroll to the top before each click.
- **GitHub pill in nav.** Opens `github.com/Anstrays/domainfi-agent-toolkit` in a new tab.
- **Direct deep links.** `http://localhost:8080/#docs` should load already scrolled to the "Read the plan in full." section. If `id="docs"` is missing, the page silently lands at the top.
- **Skip-to-content (a11y).** Press `Tab` once on a freshly loaded page. A green "Skip to content" pill must appear at the top-left. Click anywhere else and it must disappear (it's positioned at `left: -9999px` until focused).
- **Favicon.** The browser tab should show a gradient "D" icon. It is encoded as an inline `data:image/svg+xml` URI, so DevTools network tab should show **zero** favicon requests, not even a failed `/favicon.ico`.
- **Mobile breakpoint.** The CSS breakpoint is `@media (max-width: 860px)`. On a narrow window (~420px wide is a good test target):
  - the primary `<nav>` is hidden (`display: none`)
  - the hero collapses to one column (heading on top, terminal card below)
  - the docs grid collapses to one column
  - no horizontal scroll

  To resize the Chrome window from a shell, use `wmctrl`:

  ```bash
  WIN=$(wmctrl -l | grep -i 'Google Chrome' | head -1 | awk '{print $1}')
  wmctrl -ir "$WIN" -b remove,maximized_vert,maximized_horz
  wmctrl -ir "$WIN" -e 0,40,40,420,800
  # ... test ...
  wmctrl -ir "$WIN" -b add,maximized_vert,maximized_horz
  ```

  `wmctrl` is not preinstalled; `sudo apt-get install -y wmctrl` is fast and harmless.

## 4. Shell-only assertions (curl + grep)

Use these instead of clicking when you just need to confirm a URL list or a meta tag. Server must be running on :8080.

```bash
# Doc-card URLs in the new "Docs" section, in order
curl -s http://localhost:8080/ | python3 -c '
import sys, re
html = sys.stdin.read()
m = re.search(r"<section id=.docs.>(.*?)</section>", html, re.S)
print(*re.findall(r"<a class=.btn secondary. href=.([^\"]+)", m.group(1)), sep="\n")
'
```

```bash
# Footer link rels
curl -s http://localhost:8080/ | python3 -c '
import sys, re
html = sys.stdin.read()
m = re.search(r"<footer>(.*?)</footer>", html, re.S)
for h, rel in re.findall(r"<a href=.([^\"]+).[^>]*target=._blank.[^>]*rel=.([^\"]+)", m.group(1)):
    print(h, rel)
'
```

```bash
# Confirm SEO meta basics actually served
curl -s http://localhost:8080/ | grep -E '<meta charset=|<meta name="viewport"|<meta name="description"'
```

## 5. Verify pinned CI action SHAs (when the workflow changes)

The `Validate static site` workflow pins `actions/checkout` and `actions/setup-python` by SHA. If you bump or change them, sanity-check that the SHAs still resolve to a real published tag:

```bash
git ls-remote https://github.com/actions/checkout      refs/tags/v4.1.1
git ls-remote https://github.com/actions/setup-python  refs/tags/v5.0.0
```

## 6. What is explicitly out of scope

- The live `https://anstrays.github.io/domainfi-agent-toolkit/` — that reflects `main`, not the working branch. Always test against the local `python3 -m http.server` first.
- Cross-browser testing — the bundled Chrome on the VM is sufficient for this static page.
- The future Doma SDK/API integration, alerts, and bots — none of them exist yet. If they do later, they belong in a separate skill, not this one.
