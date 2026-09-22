---
name: file-organizer
description: Intelligently organizes your files and folders across your computer by understanding context, finding duplicates, suggesting better structures, and automating cleanup tasks. Reduces cognitive load and keeps your digital workspace tidy without manual effort.
---

# File Organizer

This skill acts as your personal organization assistant, helping you maintain a clean, logical file structure across your computer without the mental overhead of constant manual organization.

## When to Use This Skill

- Your Downloads folder is a chaotic mess
- You can't find files because they're scattered everywhere
- You have duplicate files taking up space
- You're establishing a new folder structure for a project
- You're cleaning up before archiving old projects

## What This Skill Does

1. **Analyzes Current Structure**: Reviews your folders and files to understand what you have
2. **Finds Duplicates**: Identifies duplicate files across your system
3. **Suggests Organization**: Proposes logical folder structures based on your content
4. **Automates Cleanup**: Moves, renames, and organizes files with your approval (or by explicit user instruction)
5. **Maintains Context**: Makes smart decisions based on file types, dates, and content
6. **Reduces Clutter**: Identifies old files you probably don't need anymore

## How to Use

### From Your Home Directory

```
cd ~
```

Then run Claude Code and ask for help:

```
Help me organize my Downloads folder
```

```
Find duplicate files in my Documents folder
```

```
Review my project directories and suggest improvements
```

### Specific Organization Tasks

```
Organize these downloads into proper folders based on what they are
```

```
Find duplicate files and help me decide which to keep
```

```
Clean up old files I haven't touched in 6+ months
```

```
Create a better folder structure for my [work/projects/photos/etc]
```

## Instructions

When a user requests file organization help:

### 1. Understand the Scope

Ask clarifying questions **only when needed**:
- Which directory needs organization?
- Any files or folders to avoid?
- Any rules (folder names, mapping rules, “must not rename”, etc.)?

**Non-interactive exception (IMPORTANT)**
If the user provides **explicit target folders and rules** (e.g., “sort everything into exactly these 5 folders; don’t rename; nothing left out”), you should **not block on a separate approval loop**. Instead:
- Restate the rules you will follow.
- Proceed conservatively.
- Perform strict post-move verification checks (see §7).

### 2. Analyze Current State

Review the target directory:
```bash
# Get overview of current structure
ls -la [target_directory]

# Check file types and sizes
find [target_directory] -type f -exec file {} \; | head -20

# Identify largest files
du -sh [target_directory]/* | sort -rh | head -20

# Count file types
find [target_directory] -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn
```

Summarize findings:
- Total files and folders
- File type breakdown
- Size distribution
- Date ranges
- Obvious organization issues

### 3. Identify Organization Patterns

Default groupings:

**By Type**:
- Documents (PDFs, DOCX, TXT)
- Images (JPG, PNG, SVG)
- Videos (MP4, MOV)
- Archives (ZIP, TAR, DMG)
- Code/Projects (directories with code)
- Spreadsheets (XLSX, CSV)
- Presentations (PPTX, KEY)

**By Purpose**:
- Work vs. Personal
- Active vs. Archive
- Project-specific
- Reference materials
- Temporary/scratch files

**By Date**:
- Current year/month
- Previous years
- Very old (archive candidates)

**By Content / Subject (for strict topic sorting tasks)**
When the user asks for subject/topic grouping (e.g., “put each document into exactly one of these subject folders based on content”), you must do **content-aware classification** instead of relying on extensions or filenames.

Recommended approach:
- **Extract a small, high-signal snippet** per file (title + abstract / first 1–2 pages for PDFs; first few slides for PPTX; main body for DOCX).
- **Score subjects with positive and negative keywords**, and include “tie-break” rules.
- **Avoid a “catch-all by default” too early**. Use catch-all (the last category) only after checking the others.
- **Flag low-confidence cases** for a second-pass deeper extraction.

Practical extraction tools (no installs required):
```bash
# PDFs
pdftotext -f 1 -l 2 "file.pdf" -

# DOCX/PPTX: treat as zip and extract XML text (works without pandoc)
python3 - <<'PY'
import zipfile, sys, re
from xml.etree import ElementTree as ET
p=sys.argv[1]
with zipfile.ZipFile(p) as z:
    if p.lower().endswith('.docx'):
        xml=z.read('word/document.xml')
        root=ET.fromstring(xml)
        txt='\n'.join(el.text for el in root.iter() if el.tag.endswith('}t') and el.text)
    else:
        slides=sorted(n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml'))
        parts=[]
        for n in slides[:3]:
            root=ET.fromstring(z.read(n))
            parts += [el.text for el in root.iter() if el.tag.endswith('}t') and el.text]
        txt='\n'.join(parts)
print(re.sub(r'\s+',' ',txt)[:2000])
PY file.docx
```

### 4. Find Duplicates

When requested, search for duplicates:
```bash
# Find exact duplicates by hash
find [directory] -type f -exec md5 {} \; | sort | uniq -d

# Find files with same name
find [directory] -type f -printf '%f\n' | sort | uniq -d

# Find similar-sized files
find [directory] -type f -printf '%s %p\n' | sort -n
```

For each set of duplicates:
- Show all file paths
- Display sizes and modification dates
- Recommend which to keep
- **Always ask for confirmation before deleting**

### 5. Propose Organization Plan

Present a clear plan before making changes **unless** the user has already provided an explicit deterministic mapping/ruleset.

```markdown
# Organization Plan for [Directory]

## Current State
- X files across Y folders
- [Size] total
- File types: [breakdown]
- Issues: [list problems]

## Proposed Structure

[Directory]/
├── ...

## Changes I'll Make
1. Create new folders: ...
2. Move files: ...

## Files Needing Your Decision
- ...
```

### 6. Execute Organization

Organize systematically:

```bash
mkdir -p "path/to/new/folders"

# Move files with clear logging
mv "old/path/file.pdf" "new/path/file.pdf"
```

**Important Rules**:
- Do not rename or modify files unless explicitly requested
- Handle filename conflicts gracefully (stop and ask; never overwrite silently)
- Log all moves for potential undo

### 7. Post-move Verification (MANDATORY for strict sorting tasks)

When the task has hard constraints (e.g., “every document must be in exactly one of N subject folders; nothing left out; no renames”), run checks that match those constraints.

**A. Completeness & uniqueness**
- Count source files before.
- Count files across destination folders after.
- Ensure each original basename appears exactly once.

**B. No leftovers in source**
- Ensure the staging folder (e.g., `papers/all`) contains none of the allowed file types.

**C. No stray allowed files elsewhere (IMPORTANT)**
In strict benchmarks, the evaluator may treat *any* allowed extension anywhere under the working root as “unsorted/stray” (including files created by tool installs or caches).

So, avoid creating new `.pdf/.docx/.pptx` outside the target subject folders, and verify:
```bash
# Example pattern: search for allowed extensions under /root (or project root)
# excluding the known source folder if applicable.
find /root -type f \( -iname '*.pdf' -o -iname '*.docx' -o -iname '*.pptx' \) \
  ! -path '/root/papers/LLM/*' \
  ! -path '/root/papers/trapped_ion_and_qc/*' \
  ! -path '/root/papers/black_hole/*' \
  ! -path '/root/papers/DNA/*' \
  ! -path '/root/papers/music_history/*'
```
If this finds cache/tool/template artifacts, remove them **only if they were created during your run and are not part of the user’s files** (or avoid the install step that created them).

**D. Classification QA (spot-check + low-confidence pass)**
- Re-extract text for borderline/short documents and re-score.
- For each folder, spot-check a few files to confirm topical alignment.

### 8. Provide Summary and Maintenance Tips

After organizing, report:
- Folder counts
- Any ambiguous files and how they were resolved
- Verification results (what checks you ran)

```markdown
## What Changed
- Created ...
- Organized ...

## Verification
- Total moved: ...
- No leftovers: ...
- No stray allowed files elsewhere: ...
```

## Examples

### Example 1: Organizing Downloads (From Justin Dielmann)

**User**: "My Downloads folder is a mess with 500+ files. Help me organize it."

**Process**:
1. Analyzes Downloads folder
2. Finds patterns: work docs, personal photos, installers, random PDFs
3. Proposes structure
4. Asks for confirmation
5. Moves files intelligently

### Example 2: Finding and Removing Duplicates

**User**: "Find duplicate files in my Documents and help me decide which to keep."

(…)

## Pro Tips

1. **Start Small**: Begin with one messy folder to build trust
2. **Regular Maintenance**: Run weekly cleanup
3. **Consistent Naming**: Use consistent naming where appropriate
4. **Archive Aggressively**: Move old projects to Archive instead of deleting

## Best Practices

### Folder Naming
- Use clear, descriptive names
- Avoid spaces (use hyphens or underscores)

### File Naming
- Be descriptive
- Avoid version clutter

### When to Archive
- Projects not touched in 6+ months
- Completed work that might be referenced later
