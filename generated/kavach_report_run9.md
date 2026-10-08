# KAVACH AI - Document Analysis Report

**Source document: inspection_report.pdf**  
**Generated:** 2026-10-08T19:40:30.760727+00:00  
**Mode:** `airgapped`  |  **Run ID:** 9
**Profile:** General documents  |  **Analysis:** Risk review

> LOCAL ANALYSIS OUTPUT - REVIEW BEFORE OPERATIONAL USE

## Executive Summary

- **Verification score:** 100.0%
- **Evidence-backed:** 1/1
- **Model routing:** llama3.2:3b (code)

## Findings

### 1. Recommend follow-up ultrasonic thickness survey within 90 days.

- **Severity:** low
- **Equipment:** 
- **Confidence:** 80.0%
- Matched risk terms: recommend, follow-up. Recommend follow-up ultrasonic thickness survey within 90 days.

| Source | Page | Confidence | Excerpt |
|---|---|---|---|
| inspection_report.pdf | 1 | 80.0% | Recommend follow-up ultrasonic thickness survey within 90 days. |

## Verification

- Score: **100.0%**
- Evidence-backed: **1/1**
- Flagged for review: none

## Pipeline Trace

1. **security_agent** - Security perimeter verified
1. **router_agent** - Task routed to llama3.2:3b
1. **router_agent** - Execution plan created
1. **document_agent** - Uploaded document loaded
1. **document_agent** - Document analysis prepared
1. **vision_agent** - Vision analysis skipped
1. **knowledge_agent** - Knowledge retrieved
1. **reasoning_agent** - Reasoning analysis captured
1. **reasoning_agent** - Profile-based risk review completed
1. **verification_agent** - Evidence cross-check completed