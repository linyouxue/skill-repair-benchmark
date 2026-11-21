---
schema_version: '1.3'
metadata:
  author_name: Yueqian Lin
  author_email: yl768@duke.edu
  difficulty: medium
  category: office-white-collar
  subcategory: document-editing
  category_confidence: high
  secondary_category: media-content-production
  task_type:
  - transformation
  - detection
  modality:
  - pdf
  interface:
  - terminal
  - python
  skill_type:
  - file-format-knowledge
  - domain-procedure
  tags:
  - pdf
  - redaction
  - anonymization
  - blind-review
verifier:
  type: test-script
  timeout_sec: 300.0
  service: verifier
  hardening:
    cleanup_conftests: true
agent:
  timeout_sec: 1000.0
environment:
  network_mode: public
  build_timeout_sec: 1800.0
  os: linux
  cpus: 1
  memory_mb: 4096
  storage_mb: 10240
  gpus: 0
---

# Anonymize the papers for blind review

Edit every supplied `/root/paperN.pdf`. Save the edited PDFs under `/root/redacted/` using the same filenames, page order, dimensions and orientation.

Remove the printed author block, including author names, affiliations and contact details. Remove explicit author-identifying notes, personal author-repository addresses, the paper's own conference imprint, conference date/location, DOI and arXiv stamp where present. Remove identifying funding and acknowledgments paragraphs, including their continuation lines. A generic “Preprint” heading, an unidentifying contribution symbol, and ordinary citations to other papers can stay.

Use genuine PDF redaction with white space or a solid black fill. Clear the identifying lines so they cannot be read visually or copied from underneath, and remove active external links attached to those fields. Retain the scientific title on the page, abstract, body text, tables, figures and references. Clear the PDF's author, title, subject and keywords properties and remove XMP metadata.

The verifier gives partial credit for individual redacted regions, preserved content regions and clean document metadata. Each acknowledgment paragraph is checked across all of its marked lines. A missing or unreadable paper, a change in page geometry, or a paper with no preserved content earns zero for that paper.
