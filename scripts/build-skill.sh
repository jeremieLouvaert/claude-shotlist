#!/usr/bin/env bash
# build-skill.sh — package this repo as a claude.ai-upload-ready .skill file.
# Usage: bash scripts/build-skill.sh  (run from repo root)
#
# Produces dist/shotlist.skill, a zip with a single top-level `shotlist/` directory
# containing SKILL.md and the scripts/ runtime. claude.ai's skill upload has a
# 200-file cap; `export-ignore` in .gitattributes + the zip -d strips below
# keep the bundle lean.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "error: working tree is dirty; commit or stash before building" >&2
  exit 1
fi

mkdir -p dist
OUT="dist/shotlist.skill"
git archive --format=zip --prefix=shotlist/ --output="$OUT" HEAD

# claude.ai's .skill bundle needs only SKILL.md + scripts/ runtime. Claude Code
# needs hooks/, commands/, and .claude-plugin/ in the git archive (that's why
# they are NOT in .gitattributes export-ignore), but the .skill bundle should
# strip them to keep a single canonical SKILL.md and stay well under the
# 200-file cap. Stripping is done in Python because Info-ZIP's `zip -d` is not
# installed everywhere (a silent no-op behind `|| true` shipped an unstripped
# bundle once); the rewrite below fails loudly instead.
PYBIN=""
for c in python3 python; do
  if "$c" -c "" >/dev/null 2>&1; then PYBIN="$c"; break; fi
done
if [ -z "$PYBIN" ]; then
  echo "error: python is required to strip the bundle" >&2
  exit 1
fi
"$PYBIN" - "$OUT" <<'PY'
import fnmatch, os, sys, zipfile

EXCLUDE = [
    "shotlist/hooks/*",
    "shotlist/commands/*",
    "shotlist/.claude-plugin/*",
    "shotlist/.codex-plugin/*",
    "shotlist/decisions.md",
    "shotlist/session-log.md",
]

out = sys.argv[1]
tmp = out + ".tmp"
with zipfile.ZipFile(out) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    zout.comment = zin.comment  # git archive stores the commit hash here
    for info in zin.infolist():
        name = info.filename
        # a pattern like "shotlist/hooks/*" also drops the "shotlist/hooks/" dir entry
        if any(fnmatch.fnmatch(name, p) for p in EXCLUDE):
            continue
        zout.writestr(info, zin.read(name))
with zipfile.ZipFile(tmp) as z:
    leftover = [n for n in z.namelist() if any(fnmatch.fnmatch(n, p) for p in EXCLUDE)]
if leftover:
    sys.exit(f"error: strip left excluded entries in bundle: {leftover}")
os.replace(tmp, out)
PY

COUNT=$(unzip -l "$OUT" | tail -1 | awk '{print $2}')
SIZE=$(du -h "$OUT" | cut -f1)

if [ "$COUNT" -gt 200 ]; then
  echo "error: $COUNT files in zip, claude.ai's cap is 200" >&2
  echo "       check .gitattributes export-ignore entries and this script's zip -d excludes" >&2
  exit 1
fi

SKILL_MD_COUNT=$(unzip -l "$OUT" | grep -c "SKILL.md" || true)
if [ "$SKILL_MD_COUNT" -ne 1 ]; then
  echo "error: expected exactly one SKILL.md, found $SKILL_MD_COUNT" >&2
  exit 1
fi

echo "built $OUT ($COUNT files, $SIZE)"
echo "upload via the claude.ai skill UI"
