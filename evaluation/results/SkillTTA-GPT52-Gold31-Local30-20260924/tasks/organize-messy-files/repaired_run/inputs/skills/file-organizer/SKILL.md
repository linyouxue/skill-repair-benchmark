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
- Your folder structure doesn't make sense anymore
- You want to establish better organization habits
- You're starting a new project and need a good structure
- You're cleaning up before archiving old projects

## What This Skill Does

1. **Analyzes Current Structure**: Reviews your folders and files to understand what you have
2. **Finds Duplicates**: Identifies duplicate files across your system
3. **Suggests Organization**: Proposes logical folder structures based on your content
4. **Automates Cleanup**: Moves and organizes files with your approval (default: do not rename files or modify file contents)
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

1. **Understand the Scope**

   Ask clarifying questions:
   - Which directory needs organization? (Downloads, Documents, entire home folder?)
   - What's the main problem? (Can't find things, duplicates, too messy, no structure?)
   - Any files or folders to avoid? (Current projects, sensitive data?)
   - How aggressively to organize? (Conservative vs. comprehensive cleanup)

2. **Analyze Current State**

   Review the target directory (prefer recursive inventory so nested files aren’t missed):
   ```bash
   # Inventory (recursive)
   find [target_directory] -type f -print0 | xargs -0 -I{} sh -c 'stat -c "%s\t%y\t%s" "{}" 2>/dev/null || stat -f "%z\t%Sm\t%N" "{}"'

   # Quick file-type sampling
   find [target_directory] -type f -exec file {} \; | head -50

   # Largest files (top 20)
   find [target_directory] -type f -printf '%s\t%p\n' 2>/dev/null | sort -rn | head -20

   # Extension counts (rough)
   find [target_directory] -type f | sed 's/.*\.//' | tr '[:upper:]' '[:lower:]' | sort | uniq -c | sort -rn
   ```

   If the task requires **content-based** organization (e.g., academic PDFs by subject), extract lightweight text snippets for classification (read-only):
   ```bash
   # PDFs (first pages; good for title/abstract)
   pdftotext -f 1 -l 2 "file.pdf" - | head -200

   # DOCX (structure-preserving text extraction)
   pandoc "file.docx" -t plain | head -200

   # PPTX (slide text extraction)
   python -m markitdown "file.pptx" | head -200
   ```

   Summarize findings:
   - Total files and folders (including nested)
   - File type breakdown
   - Size distribution
   - Obvious organization issues
   - Any unreadable/low-text docs (e.g., scanned PDFs) that may require fallback rules

3. **Identify Organization Patterns**

   First, confirm whether the user/task specifies an **exact, fixed set** of destination folders (names, casing, underscores). If it does, you MUST:
   - Use **only** those folders (do not invent “ToSort”, “Misc”, “Archive”, etc. unless explicitly allowed)
   - Ensure **every file ends up in exactly one** of the specified folders (no leftovers)

   Then choose the grouping signal(s) appropriate to the request:

   **By content/subject (for papers, slides, reports)**:
   - Extract title/abstract/first-page text (PDF), body text (DOCX), slide text (PPTX)
   - Score each file against each target subject using transparent keyword/phrase signals
   - Break ties deterministically (e.g., inspect more text; if still unclear, apply a consistent fallback rule so assignment is total)

   **By type/purpose/date (only if the request allows it)**:
   - Group by extension/type, project/purpose, and/or recency as secondary signals

   **Hard constraints by default**:
   - Do not rename files
   - Do not modify file contents
   - Do not overwrite on move; handle collisions safely (e.g., create subfolders)

4. **Find Duplicates**

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
   - Recommend which to keep (usually newest or best-named)
   - **Important**: Always ask for confirmation before deleting

5. **Propose Organization Plan**

   Present a clear plan before making changes (and match any fixed-folder contract exactly):

   ```markdown
   # Organization Plan for [Directory]

   ## Current State
   - X files across Y folders (recursive)
   - File types: [breakdown]
   - Any nested subfolders: [yes/no]

   ## Required Destination Folders
   - [Folder1]
   - [Folder2]
   - ... (EXACT names, no extras)

   ## Classification Method (content-driven)
   - For PDF/DOCX/PPTX, extract title/abstract/slide text and score against subject signals
   - Each file is assigned to **exactly one** destination folder
   - If text extraction fails (scanned/protected), use a deterministic fallback so nothing is left unassigned

   ## Planned Moves (preview)
   - source/path/a.pdf → [FolderX]/a.pdf
   - source/path/b.pptx → [FolderY]/b.pptx
   ...

   ## Collision Check
   - If two files share the same filename in a destination folder, do **not** rename and do **not** overwrite.
   - Instead, create a subfolder per source path (or similar) inside the destination folder to keep names intact.

   Ready to proceed? (yes/no/modify)
   ```

6. **Execute Organization**

   After approval, organize systematically:

   ```bash
   # Create folder structure (use exact names required by the user/contract)
   mkdir -p "path/to/required/folders"

   # Move files with clear logging (do NOT rename; do NOT overwrite)
   mv -n "old/path/file.pdf" "new/path/file.pdf"
   ```

   **Important Rules**:
   - Always confirm before deleting anything
   - Log all moves for potential undo
   - Preserve original modification dates
   - Handle filename conflicts gracefully
   - Stop and ask if you encounter unexpected situations

7. **Provide Summary and Maintenance Tips**

   After organizing:

   ```markdown
   # Organization Complete! ✨

   ## What Changed

   - Created [X] new folders
   - Organized [Y] files
   - Freed [Z] GB by removing duplicates
   - Archived [W] old files

   ## New Structure

   [Show the new folder tree]

   ## Maintenance Tips

   To keep this organized:

   1. **Weekly**: Sort new downloads
   2. **Monthly**: Review and archive completed projects
   3. **Quarterly**: Check for new duplicates
   4. **Yearly**: Archive old files

   ## Quick Commands for You

   ```bash
   # Find files modified this week
   find . -type f -mtime -7

   # Sort downloads by type
   [custom command for their setup]

   # Find duplicates
   [custom command]
   ```

   Want to organize another folder?
   ```

## Examples

### Example 1: Organizing Downloads (From Justin Dielmann)

**User**: "My Downloads folder is a mess with 500+ files. Help me organize it."

**Process**:
1. Analyzes Downloads folder
2. Finds patterns: work docs, personal photos, installers, random PDFs
3. Confirms the exact destination folders (and their exact names) that the user wants
4. Extracts content signals (e.g., titles/abstracts from PDFs; slide text from PPTX) when needed to classify
5. Proposes a one-to-one mapping (each file → exactly one destination folder) with collision checks
6. After approval, moves files without renaming or modifying contents

### Example 2: Finding and Removing Duplicates

**User**: "Find duplicate files in my Documents and help me decide which to keep."

**Output**:
```markdown
# Found 23 Sets of Duplicates (156 MB total)

## Duplicate Set 1: "proposal.pdf"
- `/Documents/proposal.pdf` (2.3 MB, modified: 2024-03-15)
- `/Documents/old/proposal.pdf` (2.3 MB, modified: 2024-03-15)
- `/Desktop/proposal.pdf` (2.3 MB, modified: 2024-03-10)

**Recommendation**: Keep `/Documents/proposal.pdf` (most recent in correct location)
Delete the other 2 copies?

[Continue for all duplicates...]
```

### Example 3: Restructuring Projects Folder

**User**: "Review my ~/Projects directory and suggest improvements."

**Output**:
```markdown
# Analysis of ~/Projects

## Current Structure Issues
- Mix of active and archived projects (3+ years old)
- No consistent naming convention
- Some projects at root, others in random subfolders
- Duplicate folders (project-name, project-name-old, project-name-v2)

## Proposed Structure

```
Projects/
├── Active/
│   ├── client-work/
│   ├── side-projects/
│   └── learning/
├── Archive/
│   ├── 2022/
│   ├── 2023/
│   └── 2024/
└── Templates/
```

## Specific Changes
1. Move 12 projects not touched since 2022 → Archive/
2. Consolidate 4 duplicate project folders
3. Rename projects to consistent format: "client-name-project-name"
4. Create Archive for old work

Want me to implement this?
```

### Example 4: Organizing Photos by Date

**User**: "Organize my photo folders by year and month."

**Output**: Creates structure like:
```
Photos/
├── 2023/
│   ├── 01-January/
│   ├── 02-February/
│   └── ...
├── 2024/
│   ├── 01-January/
│   └── ...
└── Unsorted/
```

Then moves photos based on EXIF data or file modification dates.

## Common Organization Tasks

### Downloads Cleanup
```
Organize my Downloads folder - move documents to Documents,
images to Pictures, keep installers separate, and archive files
older than 3 months.
```

### Project Organization
```
Review my Projects folder structure and help me separate active
projects from old ones I should archive.
```

### Duplicate Removal
```
Find all duplicate files in my Documents folder and help me
decide which ones to keep.
```

### Desktop Cleanup
```
My Desktop is covered in files. Help me organize everything into
my Documents folder properly.
```

### Photo Organization
```
Organize all photos in this folder by date (year/month) based
on when they were taken.
```

### Work/Personal Separation
```
Help me separate my work files from personal files across my
Documents folder.
```

## Pro Tips

1. **Start Small**: Begin with one messy folder (like Downloads) to build trust
2. **Regular Maintenance**: Run weekly cleanup on Downloads
3. **Consistent Naming**: Use "YYYY-MM-DD - Description" format for important files
4. **Archive Aggressively**: Move old projects to Archive instead of deleting
5. **Keep Active Separate**: Maintain clear boundaries between active and archived work
6. **Trust the Process**: Let Claude handle the cognitive load of where things go

## Best Practices

### Folder Naming
- Use clear, descriptive names
- Avoid spaces (use hyphens or underscores)
- Be specific: "client-proposals" not "docs"
- Use prefixes for ordering: "01-current", "02-archive"

### File Naming
- **Default**: preserve filenames exactly as-is
- Only rename if the user explicitly requests it and it does not violate task constraints
- If you must avoid collisions without renaming, create subfolders (e.g., per-source-path) rather than altering filenames

### When to Archive
- Projects not touched in 6+ months
- Completed work that might be referenced later
- Old versions after migration to new systems
- Files you're hesitant to delete (archive first)

## Related Use Cases

- Setting up organization for a new computer
- Preparing files for backup/archiving
- Cleaning up before storage cleanup
- Organizing shared team folders
- Structuring new project directories
