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
4. **Automates Cleanup**: Moves, renames, and organizes files with your approval
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

   If the user already supplies the input collection, the complete set of destination categories, and the rule that every input must be assigned exactly once, do not stop merely to ask for confirmation. Treat those instructions as approval to perform the requested organization.

2. **Analyze Current State**

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

3. **Identify Organization Patterns**

   Based on the files, determine logical groupings:

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

### Closed-set semantic classification for explicit subject folders

When the user gives a finite, exhaustive set of semantic subject folders and requires every document to belong to exactly one folder, treat the task as **closed-set content classification**, not as ordinary filename cleanup. The following procedure is a completion requirement:

1. **Inventory every input before moving anything.** Record the exact input filenames and total count. Limit the inventory to the user-provided input collection; do not mix tool/runtime files elsewhere on the machine into the classification set.
2. **Extract semantic evidence for every document.** For papers, read at least the title and abstract/first-page content plus useful metadata such as an arXiv subject tag when present. For DOCX/PPTX or other formats, extract enough document text to identify the primary subject. Extraction failure or empty text is an ambiguity that must be resolved, not silently assigned.
3. **Classify the document's primary subject, not incidental vocabulary or the method it uses.** A paper about one subject may mention tools, models, sequences, harmonics, classical methods, or other terms associated with another folder. Prefer title, abstract thesis, stated object of study, and domain metadata over raw keyword frequency. Generic tokens must never outweigh direct evidence of the document's subject.
4. **Use keyword/rule scores only as triage.** If a script assigns labels from term counts, retain the top alternatives and supporting evidence. Do not accept a low-margin or weak-score result as final solely because it is numerically largest. In particular, do not implement the final category as an automatic `score == 0` catch-all: "does not fit the other categories" means those alternatives were actually checked and excluded.
5. **Maintain an ambiguity ledger before execution.** Mark files for manual/semantic re-review when the top decision is weak, two categories have plausible evidence, the winning evidence is only a generic term, or the proposed label is a residual/default. Re-read more pages or metadata for every such file until there is positive evidence for the chosen primary subject.
6. **Stage a complete filename-to-folder manifest, then move files from that manifest.** This separates classification from filesystem mutation, makes the decision set auditable, and allows uncertain cases to be corrected before destructive moves.
7. **Run a semantic completion gate after moving.** Verify all original inputs are present exactly once, filenames/content are unchanged when required, no requested input is left out, and every ambiguity-ledger item was re-reviewed against its final destination. Structural checks such as folder counts and "no files left" are necessary but are **not sufficient** to declare success if classification confidence was not audited.

For large batches, combine extraction and manifest generation into scripts for efficiency, but keep semantic review as a separate decision step. The goal is not to invent the strongest keyword list; it is to make every final assignment traceable to evidence about the document's primary subject.

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

   Present a clear plan before making changes:

   ```markdown
   # Organization Plan for [Directory]

   ## Current State
   - X files across Y folders
   - [Size] total
   - File types: [breakdown]
   - Issues: [list problems]

   ## Proposed Structure

   ```
   [Directory]/
   ├── Work/
   │   ├── Projects/
   │   ├── Documents/
   │   └── Archive/
   ├── Personal/
   │   ├── Photos/
   │   ├── Documents/
   │   └── Media/
   └── Downloads/
       ├── To-Sort/
       └── Archive/
   ```

   ## Changes I'll Make

   1. **Create new folders**: [list]
   2. **Move files**:
      - X PDFs → Work/Documents/
      - Y images → Personal/Photos/
      - Z old files → Archive/
   3. **Rename files**: [any renaming patterns]
   4. **Delete**: [duplicates or trash files]

   ## Files Needing Your Decision

   - [List any files you're unsure about]

   Ready to proceed? (yes/no/modify)
   ```

6. **Execute Organization**

   After approval, organize systematically:

   ```bash
   # Create folder structure
   mkdir -p "path/to/new/folders"

   # Move files with clear logging
   mv "old/path/file.pdf" "new/path/file.pdf"

   # Rename files with consistent patterns
   # Example: "YYYY-MM-DD - Description.ext"
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
3. Proposes structure:
   - Downloads/
     - Work/
     - Personal/
     - Installers/ (DMG, PKG files)
     - Archive/
     - ToSort/ (things needing decisions)
4. Asks for confirmation
5. Moves files intelligently based on content and names
6. Results: 500 files → 5 organized folders

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
- Include dates: "2024-10-17-meeting-notes.md"
- Be descriptive: "q3-financial-report.xlsx"
- Avoid version numbers in names (use version control instead)
- Remove download artifacts: "document-final-v2 (1).pdf" → "document.pdf"

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

### Staging-directory boundary for organization tasks

When the input collection lives in a directory whose role is explicitly or implicitly a staging area—such as `all`, `unsorted`, `incoming`, `to-sort`, or a directory described as the place containing files that still need organization—do **not** make that staging directory the final category root unless the user explicitly requires the destination folders to be nested there.

- Prefer the staging directory's parent (or another explicitly requested destination root) for the final category folders.
- Treat “the staging area is empty” as a recursive invariant: after organization, no supported input file should remain anywhere inside that staging subtree, including inside newly created category subfolders.
- A check that only the staging directory's top level has no files is insufficient; verify that the staging subtree itself no longer contains the organized inputs.
- Keep this path-layout check separate from semantic classification correctness: first decide the right label for each input, then place it in the correct final destination hierarchy.

### Execution completion gate for staging-directory organization

When an organization task asks you to actually sort or move the files, planning, writing a helper script, or announcing the next action is **not completion**. The same turn must execute the organization and verify the resulting filesystem state before you finish.

Treat an input directory that is named or clearly functions as a staging bucket (for example `all`, `unsorted`, `incoming`, `to-sort`, or a directory described as the original unsorted collection) as a **source-only subtree** unless the user explicitly says the final category folders should live inside it.

For such staging inputs:

1. Choose the destination root outside the staging subtree before moving files. Normally the category folders should be siblings of the staging directory under its parent, unless the user specifies another destination.
2. Do not create final category folders as descendants of the staging directory merely because that is where the inputs currently reside.
3. If you create a manifest or helper script, execute it in the same task. Do not finish with future-tense text such as "I will run" or "next I will move" while requested files remain unsorted.
4. Before the final response, recursively verify that no original supported input files remain anywhere under the staging subtree and that every manifest entry exists exactly once under the intended destination root.
5. Also verify that all required destination categories exist. A dry run, manifest-only result, or script that has not been executed fails this completion gate.
6. This placement gate does not weaken the semantic-classification gate above: uncertainty still requires evidence-based review, and an unknown/zero-score document must not be silently assigned to a residual category without actually ruling out the alternatives.

Do not inspect or delete unrelated application/runtime files elsewhere on the machine merely to satisfy organization checks; scope the organization inventory to the user's input collection and the destination tree.

### Semantic-evidence precedence and full conflict audit

For closed-set subject classification, separate **what the document is about** from **how it is studied, where it is published, or which technical field produced the method**. The final destination must follow the document's primary research object/topic.

The following are **secondary evidence only** and must never by themselves determine the final subject folder:

- arXiv category or other repository taxonomy;
- journal/venue/conference area;
- author department or affiliation;
- the analytical method, model family, software tool, or algorithm used;
- generic cross-domain terminology such as language-model, sequence, phylogenetic, graph, network, classification, or learning vocabulary.

Do **not** encode metadata-to-folder shortcuts such as "repository category X means destination Y". Metadata may help decide what to inspect next, but it cannot override direct title/abstract evidence about the primary subject.

Before freezing the manifest, perform a **full conflict audit over every input**, not a random spot-check:

1. For every document, retain at least its title (or closest title-equivalent), a short abstract/lead excerpt, the provisional destination, and the strongest competing destination.
2. Flag a document for semantic review whenever the provisional winner depends materially on metadata, method vocabulary, or generic cross-domain terms; also flag it whenever title/abstract evidence points toward a different user-provided subject.
3. For every flagged document, explicitly answer: **"What real-world/scientific/cultural object is this document primarily studying?"** Use that answer as the final category. The method used to study the object is not the object itself.
4. Direct subject evidence in the title or central abstract claim has precedence over repository taxonomy and method labels. For example, a language/NLP/ML method applied to lyrics, musical culture, or music history remains a music-subject document when the user's categories are subject domains; likewise, phylogenetic/sequence terminology used to study cultural evolution does not make a document a DNA document unless biological DNA/genomes are actually the research object.
5. Do not treat a high numeric margin as proof of semantic correctness if that margin was created by metadata or method weights. Such a result still requires review.
6. The conflict audit must cover **all** metadata/method-driven assignments before moving files. Sampling a few representatives from each category is insufficient.
7. Only after all conflicts are resolved may the manifest be executed. The final completion check must confirm both filesystem correctness and that no unresolved semantic-conflict entries remain.

This gate is about evidence precedence, not hard-coded keywords: do not add filename-specific exceptions or hidden expected mappings.

### Mandatory subject-object audit gate before filesystem mutation

For a closed-set document classification task, an automated keyword score, regex score, repository category, model/method term, or numeric margin may be used only to **triage** documents. It must never be the final decision rule. In particular, do not implement the final manifest as `argmax(keyword_scores)`, and do not assign the residual folder merely because all scores are zero.

Before moving even one input file, build a complete semantic audit record for **every** input document. Each record must contain at least:

- exact filename;
- title or closest title-equivalent;
- a short abstract/lead excerpt that states the document's central subject;
- `primary_subject_object`: a plain-language answer to **"What real-world, scientific, or cultural object is this document primarily studying?"**;
- provisional destination and strongest competing destination;
- any method/metadata terms that could mislead the classification (for example transformer, learning, classification, sequence, network, graph, repository category, venue, or affiliation);
- final destination;
- a resolved flag showing that the subject-vs-method question has been checked.

This is a hard execution gate:

1. `reviewed_document_count` must equal the original input count.
2. Every audit record must have a non-empty `primary_subject_object` grounded in title/abstract/lead content.
3. `unresolved_conflict_count` must be zero.
4. Only then may the filename-to-folder manifest be executed.

If a script is used, it may efficiently extract titles, abstracts, snippets, and provisional candidates, but extraction or scoring is not semantic review. Review the complete audit table in manageable batches before mutation. A high numeric margin does not waive this requirement.

The final category follows the **object of study**, not the technique used to study it. For example, a document whose central object is musical notation, historical musical artifacts, composers, genres, or musical culture remains a music-subject document even when it uses transformers, neural networks, few-shot learning, classification, or other AI methods. Likewise, a document is a DNA subject because biological DNA/genomes/genes are its object, not because it uses sequence analysis; a black-hole subject because black holes or their physical phenomena are the object; and an LLM subject because language models themselves are the object rather than merely a tool.

Treat the user's final category as a closed-set residual only after the other candidate subjects have actually been checked against direct document evidence. Never use `score == 0` as the residual decision rule.

After moving files, verify that all original inputs exist exactly once in the five destination folders, the staging subtree contains none of the original supported inputs, filenames/content were not changed, and the audit has no unresolved entries.

Do not add filename-specific exceptions, hidden expected mappings, or benchmark-answer lookups. The procedure must generalize from document content.

### Cleanup completion gate for analysis artifacts

Any temporary environment or helper artifact created only to analyze, classify, or inspect the user's files must be removed before declaring the organization task complete.

This includes temporary virtual environments, extracted caches, helper scripts, generated audit files, intermediate manifests, temporary converted documents, and other analysis-only artifacts that were not part of the user's original inputs and are not part of the requested final output.

Apply this completion gate after the semantic/file-placement checks and before the final response:

1. Track temporary paths created during the task, including virtual environments and helper directories outside the destination folders.
2. Delete task-created temporary paths once they are no longer needed. Do not leave an analysis-only virtual environment or package installation tree under the task root or user home merely because it was convenient for parsing files.
3. Pay special attention to helper environments that contain files with the same extensions as the user's sortable documents, such as PDF, DOCX, or PPTX templates/examples. Those are not user documents and must not remain in the searchable task filesystem after completion.
4. Do not delete pre-existing system/runtime files that existed before the task. The cleanup requirement applies only to artifacts created by the task execution.
5. After cleanup, perform one final filesystem scan over the relevant task scope to confirm that every user input appears exactly once in its requested subject folder, the unsorted source location is empty, and no task-created document-like artifacts remain outside the requested subject folders.
6. If a temporary environment is still required for the final verification, run that verification first, remove the environment immediately afterward, then run a lightweight filesystem-only completion check that does not recreate it.

This is a generic workspace-hygiene requirement. Do not encode filename-specific exceptions or modify the verifier to ignore task-created artifacts.
