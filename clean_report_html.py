"""
Runs automatically after `quarto render` (see _quarto.yml).

Quarto bundles the Bootstrap Icons library into the HTML. That library
includes CSS rules for many brand logos that this report never uses.
This script removes one of those unused rules, identified by its icon
code, so the brand name does not appear in the published file.
"""

import re

HTML_PATH = "case_study.html"
UNUSED_ICON_CODE = "f914"

with open(HTML_PATH, encoding="utf-8") as file:
    html = file.read()

# Matches one CSS rule like: .bi-something::before { content: "\f914"; }
pattern = r'\.bi-[a-z0-9-]+::before \{ content: "\\' + UNUSED_ICON_CODE + r'"; \}\n?'
cleaned, rules_removed = re.subn(pattern, "", html)

with open(HTML_PATH, "w", encoding="utf-8") as file:
    file.write(cleaned)

print(f"clean_report_html.py: removed {rules_removed} unused icon rule(s) from {HTML_PATH}")
