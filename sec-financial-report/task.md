---
schema_version: '1.3'
metadata:
  difficulty: hard
  category: finance-economics
  subcategory: sec-filings-analysis
  category_confidence: high
  task_type:
  - search
  - analysis
  modality:
  - database
  - json
  interface:
  - terminal
  - python
  skill_type:
  - domain-procedure
  - tool-workflow
  tags:
  - data processing
  - financial analysis
verifier:
  type: test-script
  timeout_sec: 900.0
  service: main
  hardening:
    cleanup_conftests: true
agent:
  timeout_sec: 900.0
environment:
  network_mode: public
  build_timeout_sec: 600.0
  os: linux
  cpus: 1
  memory_mb: 4096
  storage_mb: 10240
  gpus: 0
---

Analyze SEC Form 13F holdings from baseline period 2024-q1 to current period 2024-q2.
The source tables are under `/root/2024-q1/` and `/root/2024-q2/`.
Use the following case IDs and lookup names. Each case names one filing manager and one target security.

| Case ID | Filing manager | Target security issuer | Target security class |
| --- | --- | --- | --- |
| case_001 | CWS Financial Advisors, LLC | HEIDRICK & STRUGGLES INTL IN | cmn |
| case_002 | Marion Wealth Management | MINK THERAPEUTICS INC | com |
| case_003 | Teza Capital Management LLC | BALLYS CORPORATION | cmn |
| case_004 | Birchview Capital, LP | DAYFORCE INC | cmn |
| case_005 | Dynamic Wealth Strategies, LLC | LEMAITRE VASCULAR INC | cmn |
| case_006 | Red Wave Investments LLC | NETAPP INC | adr |
| case_007 | EDMP, INC. | DANA HOLDING CORP | com |
| case_008 | ARQ WEALTH ADVISORS, LLC | TELEPHONE & DATA SYS INC | cmn |
| case_009 | NICHOLAS COMPANY, INC. | ONEOK INC NEW | cmn |
| case_010 | Gallagher Fiduciary Advisors, LLC | AEVA TECHNOLOGIES INC | cmn |

The input contains the complete SEC archives for both periods. For each period,
join COVERPAGE and SUBMISSION by ACCESSION_NUMBER. Keep 13F-HR filings with
COVERPAGE.REPORTCALENDARORQUARTER and SUBMISSION.PERIODOFREPORT both equal to
the stated quarter-end date and COVERPAGE.ISAMENDMENT other than Y. For each
manager CIK, use the filing with the earliest SUBMISSION.FILING_DATE, breaking
same-day ties by ascending ACCESSION_NUMBER. Match the manager by COVERPAGE name.
To locate the target CUSIP, match the current-period issuer name and specified
TITLEOFCLASS on eligible holding rows with an empty PUTCALL field.
Use raw integer VALUE in US dollars. For stock-only questions, lowercase TITLEOFCLASS
and use these exact allowed values: `com`, `common stock`, `cl a`, `com new`, `class a`, `stock`, `common`, `com cl a`, `com shs`, `sponsored adr`, `sponsored ads`, `adr`, `equity`, `cmn`, `cl b`, `ord shs`, `cl a com`, `class a com`, `cap stk cl a`, `comm stk`, `cl b new`, `cap stk cl c`, `cl a new`, `foreign stock`, `shs cl a`. The class list alone controls the stock-row filter.

For each case answer the following seven questions in order.

1. What is the baseline-period total reported holdings value for the named manager, summing VALUE across all rows of the filing?
2. What is the current-period total reported holdings value for that manager, using the same rule?
3. How many baseline-period holding rows remain after applying the stock-class filter? Count rows.
4. How many current-period holding rows remain after applying the same filter? Count rows.
5. Which two stocks had the largest positive change in reported holdings value from baseline to current? Filter each period first, sum VALUE by CUSIP, use zero when a CUSIP is absent in a period, and rank by current minus baseline, descending. Return two CUSIPs.
6. Which two stocks had the largest decline in reported holdings value? Use the same filtered aggregates and rank strictly negative changes, largest decline first. Return two CUSIPs.
7. Which two managers held the target security at the highest reported value in the current period? Sum all rows matching its CUSIP for each eligible current filing. Return the managers' COVERPAGE names in descending value order.

Write `/root/answers.json`. Include every case ID as a top-level key. Each case uses this schema, with numeric answers for questions 1–4 and ordered lists for 5–7.

```json
{
  "case_001": {
    "q1_answer": 0,
    "q2_answer": 0,
    "q3_answer": 0,
    "q4_answer": 0,
    "q5_answer": ["CUSIP1", "CUSIP2"],
    "q6_answer": ["CUSIP1", "CUSIP2"],
    "q7_answer": ["MANAGER1", "MANAGER2"]
  }
}
```
