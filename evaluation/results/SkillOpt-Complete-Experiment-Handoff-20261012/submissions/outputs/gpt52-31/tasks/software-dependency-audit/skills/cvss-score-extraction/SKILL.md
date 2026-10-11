---
name: cvss-score-extraction
description: Extract CVSS (Common Vulnerability Scoring System) scores from vulnerability data sources with proper fallback handling. This skill covers understanding CVSS v3, handling multiple score sources (NVD, GHSA, RedHat), implementing source priority logic, and dealing with missing scores in security reporting.
---

# CVSS Score Extraction from Vulnerability Data

This skill provides guidance on extracting CVSS scores from vulnerability data—a critical component of security report generation.

## Overview

CVSS (Common Vulnerability Scoring System) provides a standardized way to assess the severity of security vulnerabilities. When generating security reports, extracting the correct CVSS score from multiple data sources is essential for accurate risk assessment.

## What is CVSS?

### CVSS Scoring System

CVSS assigns a numerical score (0.0-10.0) representing vulnerability severity:

| Score Range | Severity Level | Description |
|-------------|----------------|-------------|
| 0.0 | None | No impact |
| 0.1-3.9 | **Low** | Minimal impact |
| 4.0-6.9 | **Medium** | Moderate impact |
| 7.0-8.9 | **High** | Significant impact |
| 9.0-10.0 | **Critical** | Severe impact |

### CVSS Versions

- **CVSS v2**: Legacy scoring system (0-10 scale)
- **CVSS v3**: Current standard with refined metrics
- **CVSS v3.1**: Minor refinement of v3

**Best Practice**: Prefer CVSS v3/v3.1 scores when available.

## Multiple Vulnerability Data Sources

Vulnerability scanners often aggregate data from multiple sources, each providing their own CVSS assessment:

### Common Sources

1. **NVD (National Vulnerability Database)**
   - Maintained by NIST (U.S. government)
   - Most authoritative source
   - **Priority: Highest**

2. **GHSA (GitHub Security Advisory)**
   - Community-driven vulnerability database
   - Strong for open-source packages
   - **Priority: Medium**

3. **RedHat Security Data**
   - RedHat's security team assessments
   - Focused on enterprise Linux ecosystem
   - **Priority: Lower**

### Why Multiple Sources?

- Not all sources have scores for every CVE
- Scores may differ based on interpretation
- Need fallback logic when primary source unavailable



### Required Source and Version Selection Rules

When extracting CVSS values from Trivy-style vulnerability JSON:

1. Prefer CVSS v3.1 or v3 scores over CVSS v2.
2. Use this source priority order:
   - `nvd`
   - `ghsa`
   - `redhat`
3. Only fall back to CVSS v2 when no v3/v3.1 score exists from any source.
4. Ignore non-numeric or malformed scores.
5. If multiple scores exist within the same source:
   - Prefer `V3Score`
   - Otherwise use `V2Score`
6. If no valid score exists anywhere, serialize the final score as `N/A`.

Typical Trivy advisory structure:

```json
{
  "VulnerabilityID": "CVE-2023-1234",
  "CVSS": {
    "nvd": {
      "V3Score": 9.8,
      "V3Vector": "CVSS:3.1/..."
    },
    "ghsa": {
      "V3Score": 8.9
    },
    "redhat": {
      "V2Score": 6.5
    }
  }
}
```

Expected extraction result for the example above:

```python
9.8  # NVD V3Score wins
```






## Usage in Report Generation

### Integrating CVSS Extraction

```python
import json

def parse_vulnerabilities(json_file):
    """Parse Trivy JSON and extract vulnerabilities with CVSS scores."""
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    vulnerabilities = []
    
    if 'Results' in data:
        for result in data['Results']:
            for vuln in result.get('Vulnerabilities', []):
                # Extract basic fields
                record = {
                    'Package': vuln.get('PkgName'),
                    'Version': vuln.get('InstalledVersion'),
                    'CVE_ID': vuln.get('VulnerabilityID'),
                    'Severity': vuln.get('Severity'),
                    
                    'Fixed_Version': vuln.get('FixedVersion', 'N/A'),
                    'Title': vuln.get('Title', 'No description')
                }
                vulnerabilities.append(record)
    
    return vulnerabilities
```

## Common Patterns

### Pattern 1: Numeric Score or 'N/A'

```python
cvss_score = get_cvss_score(vuln)
# Returns: 9.8 or 'N/A'
```

**Use case**: Simple reports where missing scores are acceptable

### Pattern 2: Score with Metadata

```python
cvss_info = get_cvss_score_with_fallback(vuln)
# Returns: {'score': 9.8, 'version': 'v3', 'source': 'nvd'}
```

**Use case**: Detailed reports showing data provenance

### Pattern 3: Filtering by Score Threshold

```python
def is_high_severity(vuln_data, threshold=7.0):
    """Check if vulnerability meets severity threshold."""
    score = get_cvss_score(vuln_data)
    if score == 'N/A':
        # If no score, use severity label
        return vuln_data.get('Severity') in ['HIGH', 'CRITICAL']
    return score >= threshold
```

## Error Handling

### Handling Missing Data

```python
def safe_get_cvss_score(vuln_data):
    """Safely extract CVSS score with comprehensive error handling."""
    try:
        cvss = vuln_data.get('CVSS', {})
        
        # Validate cvss is a dictionary
        if not isinstance(cvss, dict):
            return 'N/A'
        
        for source in ['nvd', 'ghsa', 'redhat']:
            if source in cvss and isinstance(cvss[source], dict):
                score = cvss[source].get('V3Score')
                # Validate score is numeric
                if score is not None and isinstance(score, (int, float)):
                    return score
        
        return 'N/A'
    except (AttributeError, TypeError):
        return 'N/A'
```



### Recommended Production Extraction Logic

```python
def get_cvss_score_with_metadata(vuln_data):
    """Extract CVSS using deterministic source/version priority."""
    cvss = vuln_data.get('CVSS', {})

    if not isinstance(cvss, dict):
        return {
            'score': 'N/A',
            'version': 'N/A',
            'source': 'N/A'
        }

    source_order = ['nvd', 'ghsa', 'redhat']

    # Pass 1: Prefer V3/V3.1 scores
    for source in source_order:
        source_data = cvss.get(source)

        if not isinstance(source_data, dict):
            continue

        score = source_data.get('V3Score')

        if isinstance(score, (int, float)):
            return {
                'score': round(float(score), 1),
                'version': 'v3',
                'source': source
            }

    # Pass 2: Fall back to V2 only if no V3 exists
    for source in source_order:
        source_data = cvss.get(source)

        if not isinstance(source_data, dict):
            continue

        score = source_data.get('V2Score')

        if isinstance(score, (int, float)):
            return {
                'score': round(float(score), 1),
                'version': 'v2',
                'source': source
            }

    return {
        'score': 'N/A',
        'version': 'N/A',
        'source': 'N/A'
    }
```
## Best Practices

1. **Always provide fallback**: Use 'N/A' when scores unavailable
2. **Prefer newer versions**: V3 > V2
3. **Respect source hierarchy**: NVD is most authoritative
4. **Validate data types**: Ensure scores are numeric before using
5. **Document source**: In detailed reports, note which source provided the score



### CSV Output Requirements

For the `security_audit.csv` task format:

- Serialize `CVSS_Score` as:
  - Numeric value like `9.8`
  - Or literal `N/A` if no score exists
- Do not emit nested JSON structures into CSV cells.
- Preserve one decimal place when possible.
- Use the selected score after applying source/version priority rules.

Example CSV row:

```csv
Package,Version,CVE_ID,Severity,CVSS_Score,Fixed_Version,Title,Url
lodash,4.17.20,CVE-2021-23337,HIGH,7.2,4.17.21,Command Injection,https://nvd.nist.gov/vuln/detail/CVE-2021-23337
```
## Complete Example

```python
import json

def get_cvss_score(vuln_data):
    """Extract CVSS v3 score with source priority."""
    cvss = vuln_data.get('CVSS', {})
    
    for source in ['nvd', 'ghsa', 'redhat']:
        if source in cvss:
            score = cvss[source].get('V3Score')
            if score is not None:
                return score
    
    return 'N/A'

def generate_report_with_cvss(json_file):
    """Generate vulnerability report with CVSS scores."""
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    print(f"{'Package':<20} {'CVE ID':<20} {'CVSS':<8} {'Severity':<10}")
    print("-" * 60)
    
    if 'Results' in data:
        for result in data['Results']:
            for vuln in result.get('Vulnerabilities', []):
                pkg = vuln.get('PkgName', 'Unknown')
                cve = vuln.get('VulnerabilityID', 'N/A')
                cvss = get_cvss_score(vuln)
                severity = vuln.get('Severity', 'UNKNOWN')
                
                print(f"{pkg:<20} {cve:<20} {cvss:<8} {severity:<10}")

# Usage
generate_report_with_cvss('trivy_report.json')
```

## Dependencies

### Python Modules
- `json` (standard library)

### Data Format
- Expects Trivy JSON format or similar structured vulnerability data

## References

- [CVSS v3.1 Specification](https://www.first.org/cvss/v3.1/specification-document)
- [NVD CVSS Calculator](https://nvd.nist.gov/vuln-metrics/cvss/v3-calculator)
- [GitHub Security Advisories](https://github.com/advisories)


# Example conflict resolution behavior:
#
# CVSS = {
#   'nvd': {'V2Score': 5.0},
#   'ghsa': {'V3Score': 8.1},
#   'redhat': {'V3Score': 7.5}
# }
#
# Result: 8.1 from GHSA
# Reason: any V3 score beats all V2 scores, and GHSA outranks RedHat.
