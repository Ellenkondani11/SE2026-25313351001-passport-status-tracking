#!/usr/bin/env python3
import hashlib
import html
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "release-v1.0.0")
PDF_DIR = os.path.join(OUT, "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)

# Refresh SBOM
sbom_path = os.path.join(ROOT, "docs", "07-management", "sbom.json")
# reuse existing if present; regenerate minimal from requirements + pip freeze
packages = []
try:
    with open(os.path.join(ROOT, "requirements.txt")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                packages.append(line)
except FileNotFoundError:
    pass
freeze = subprocess.check_output(["pip", "freeze"], text=True).splitlines()
freeze_map = {}
for line in freeze:
    if "==" in line:
        name, version = line.split("==", 1)
        freeze_map[name.lower().replace("_", "-")] = version
sbom = {"packages": []}
for req in packages:
    name = re.split(r"[<>=!]", req)[0].strip()
    key = name.lower().replace("_", "-")
    sbom["packages"].append({"name": name, "version": freeze_map.get(key, "unresolved"), "source": "requirements.txt"})
with open(sbom_path, "w") as f:
    json.dump(sbom, f, indent=2)
    f.write("\n")

# Collect dossier markdown files
md_files = []
for base in [
    "00-baseline", "01-requirements", "02-design", "03-quality-and-testing",
    "04-engineering-analysis", "05-maintenance", "06-user-docs", "07-management",
]:
    d = os.path.join(ROOT, "docs", base)
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".md"):
                md_files.append(os.path.join(d, fn))
for extra in ["docs/reflection.md", "docs/ai-disclosure.md"]:
    p = os.path.join(ROOT, extra)
    if os.path.exists(p):
        md_files.append(p)

FOOTER = "EK01-HAZY-VM26 · 25313351001"

for md_path in md_files:
    rel = os.path.relpath(md_path, ROOT)
    safe = rel.replace(os.sep, "_").replace(".md", ".pdf")
    pdf_path = os.path.join(PDF_DIR, safe)
    with open(md_path, encoding="utf-8") as f:
        text = f.read()
    body = html.escape(text)
    html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>{html.escape(os.path.basename(md_path))}</title>
<style>
body {{ font-family: Georgia, serif; margin: 40px; color: #111; }}
pre {{ white-space: pre-wrap; font-family: "DejaVu Sans Mono", monospace; font-size: 10pt; }}
h1,h2,h3 {{ color: #1B5E3A; }}
.footer {{ position: fixed; bottom: 10px; left: 0; right: 0; text-align: center; font-size: 9pt; color: #555; }}
</style></head><body>
<pre>{body}</pre>
<div class="footer">{FOOTER}</div>
</body></html>"""
    html_path = os.path.join(PDF_DIR, safe.replace(".pdf", ".html"))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    subprocess.run([
        "google-chrome", "--headless", "--disable-gpu",
        f"--print-to-pdf={pdf_path}", html_path,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(html_path)
    print("generated", pdf_path)

# SHA256SUMS
sums = []
for root_dir, _, files in os.walk(PDF_DIR):
    for fn in sorted(files):
        if fn.endswith(".pdf"):
            p = os.path.join(root_dir, fn)
            rel = os.path.relpath(p, OUT)
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
            sums.append(f"{h}  {rel}")
pptx_path = os.path.join(ROOT, "docs", "presentation", "passtrack-ek01.pptx")
if os.path.exists(pptx_path):
    rel = os.path.relpath(pptx_path, OUT)
    h = hashlib.sha256(open(pptx_path, "rb").read()).hexdigest()
    sums.append(f"{h}  {rel}")
sbom_rel = os.path.relpath(sbom_path, OUT)
h = hashlib.sha256(open(sbom_path, "rb").read()).hexdigest()
sums.append(f"{h}  {sbom_rel}")

with open(os.path.join(OUT, "SHA256SUMS.txt"), "w") as f:
    f.write("\n".join(sums) + "\n")
print("generated SHA256SUMS.txt")
