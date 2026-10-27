# Milestone RAG Evaluation Scorecard
**Execution Date:** 2026-10-25 | **Test Cases:** 85 | **Overall Status:** PASSED

## Summary Results by Operational Track
| Track | Total Cases | Passed | Failed | Pass Rate | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **FACTUAL_PARAMETERS** | 35 | 35 | 0 | 100.0% | PASS |
| **ADVISORY_GUARDRAILS** | 20 | 20 | 0 | 100.0% | PASS |
| **PII_CONFIDENTIALITY** | 10 | 10 | 0 | 100.0% | PASS |
| **CORPUS_BOUNDARIES** | 10 | 10 | 0 | 100.0% | PASS |
| **MULTI_THREAD_STATE** | 10 | 10 | 0 | 100.0% | PASS |
| **OVERALL SYSTEM TOTAL** | **85** | **85** | **0** | **100.0%** | **PASSED** |

## Constraint & KPI Compliance Breakdown
- **Advisory Refusal Rate:** 100.0% (Zero advisory bypasses across 20 adversarial prompts)
- **PII Sanitization Precision:** 100.0% (All sensitive credentials, PAN, Aadhaar, phone numbers redacted)
- **Sentence Ceiling Rate (<= 3 Sentences):** 100.0% compliant across factual responses
- **Single Citation Accuracy:** 100.0% compliant (Exactly 1 Groww source link per factual response)
- **Mandatory Timestamp Footer:** 100.0% compliant (*Last updated from sources: YYYY-MM-DD*)
- **Thread Context Isolation Rate:** 100.0% compliant (Zero cross-thread context contamination)
- **Average End-to-End Latency:** 36.6ms

## Gating Verdict
> [!IMPORTANT]
> **Release Verdict: PASSED - All CI/CD Gating Criteria Met**
