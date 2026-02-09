# **Personal Local Assistant for Developer (PersLAD)**

## Architecture Specification (v3 — final for MVP)

---

## 1. System Goal

PersLAD is a **local intelligent assistant for developers** that provides:

* durable ownership of project context (code + documentation),
* correct and explainable change handling,
* minimization of hallucinations,
* reproducibility of decisions.

> The system **is not a source of truth** and **does not replace the developer**.
> It is a **tool for analysis, understanding, and change support**.

---

## 2. Core Principles (Non‑negotiable)

1. **Code and documentation are the source of truth**
2. **Generation ≠ knowledge**
3. **Understanding always precedes change**
4. **Uncertainty is acceptable and must be explicit**
5. **Evolution through seeds, not Big Design Up Front**
6. **MVP first**

---

## 3. Core User Flow

1. User submits a request
2. The system:

    * retrieves relevant context (RAG),
    * builds an **Understanding State**
3. Performs:

    * analysis,
    * conflict detection,
    * risk estimation
4. If required:

    * asks clarifying questions,
    * or escalates
5. Produces **proposals**, not direct changes
6. User makes a decision
7. Outcome is persisted in memory

---

## 4. High‑Level Architecture

```
┌─────────────┐
│   User      │
└─────┬───────┘
      ↓
┌─────────────┐
│ Interaction │
│   Layer     │
└─────┬───────┘
      ↓
┌──────────────────────────┐
│ Context & Reasoning Core │
│  - RAG                   │
│  - Understanding State   │
│  - Claims                │
│  - Risk Assessment       │
└─────┬────────────────────┘
      ↓
┌──────────────────┐
│ Knowledge Layer  │
│  - Code Index    │
│  - Docs Index    │
│  - Dialogue Mem  │
└─────┬────────────┘
      ↓
┌──────────────────┐
│ Execution Layer  │
│  - Proposal Gen  │
│  - Escalation    │
│  - Lineage       │
└──────────────────┘
```

---

## 5. Knowledge Sources (MVP)

### 5.1. Code Knowledge

* Source code
* AST / symbols (optional)
* Structural navigation

### 5.2. Documentation Knowledge

* Markdown / README / ADRs
* Code comments
* Local wiki (if present)

### 5.3. Dialogue Memory (Accepted, MVP)

**Purpose:**
Preserve **decision context**, not just chat history.

**Important:**

* ❌ not a source of truth
* ✅ a source of **project memory**

**Stored:**

* user query,
* project context used,
* system proposals,
* user decision.

```json
{
  "query": "...",
  "project_id": "...",
  "sources_used": ["chunk_12", "file_auth.py"],
  "proposals": ["proposal_42"],
  "decision": "accepted | rejected | modified",
  "timestamp": "..."
}
```

Indexed semantically with **time‑decay weighting**.

---

## 6. Knowledge Model

### 6.1. Claim

The minimal unit of knowledge.

```json
{
  "statement": "AuthService uses JWT",
  "source": "code | doc | inferred",
  "confidence": 0.8,
  "freshness": "commit_hash | timestamp"
}
```

> ❌ `completeness_score` — **rejected for MVP**
>
> **Reason:** difficult to measure and does not affect the core flow

---

### 6.2. Claims Extraction

Used for:

* conflict detection,
* risk estimation,
* user explanations.

Fallback on failure → simple RAG.

---

### 6.3. Dialogue Memory

See §5.3 — intentionally promoted to a first‑class concept.

---

## 7. Understanding State (System Core)

**Understanding State** is a **snapshot of the system’s understanding for a specific request**.

```json
{
  "task_goal": "...",
  "relevant_files": [...],
  "claims": [...],
  "unresolved_conflicts": [...],
  "confidence": 0.0-1.0,
  "change_radius": "local | medium | wide",
  "risk_assessment": {...}
}
```

> ❌ Persistent global **Project Context object** — **explicitly rejected**
>
> **Reason:**
>
> * over‑complicates MVP,
> * duplicates Dialogue Memory + Knowledge Index,
> * creates a false sense of consistency.

📌 Instead:
**The Understanding State of the last accepted decision serves as the implicit project context.**

---

## 8. Risk Assessment (Accepted)

```json
{
  "breaking_changes": [
    {"file": "auth.py", "probability": 0.6}
  ],
  "test_coverage": 0.4,
  "rollback_complexity": "medium",
  "documentation_impact": "high"
}
```

Used to:

* choose automation level,
* trigger escalation,
* explain trade‑offs to the user.

---

## 9. Uncertainty Management (New)

### 9.1. Types of Uncertainty

1. **Epistemic** — missing facts
2. **Semantic** — unclear meaning or intent
3. **Procedural** — unclear how to perform an action

---

### 9.2. Confidence Policy

| Confidence | Behavior                            |
| ---------- | ----------------------------------- |
| ≥ 0.7      | May propose concrete changes        |
| 0.3 – 0.7  | Proposals only, with explanations   |
| < 0.3      | Request verification, no generation |

---

## 10. Escalation (Clarified)

### 10.1. Escalation Triggers

1. `unresolved_conflicts ≥ 3` **and** `confidence < 0.6`
2. `change_radius == wide` **and** `risk == high`
3. Explicit user flag `/deep`

### 10.2. Mandatory Explanation

> “Escalating because 4 contradictions were detected between code and documentation.”

---

## 11. Change Model

### 11.1. Change Levels

| Level  | Behavior             |
| ------ | -------------------- |
| Local  | Auto‑generation      |
| Medium | Diff + confirmation  |
| Wide   | Recommendations only |

---

### 11.2. Lineage (Mandatory)

Each proposal must record:

* `proposal_id`,
* supporting claims,
* user decision,
* downstream effects (post‑hoc).

---

## 12. Explicitly Out of Scope for MVP

* Global persistent Project Context
* Active learning
* Full execution planning graphs
* Automatic rollback
* Formal project ontology

All items are **compatible with the architecture** but **must not block MVP delivery**.

---

## 13. MVP Checklist (For Engineering Team)

* [ ] Code + docs indexing
* [ ] RAG retrieval
* [ ] Minimal Understanding State
* [ ] Claims extraction (best‑effort)
* [ ] Dialogue Memory
* [ ] Risk assessment
* [ ] Rule‑based escalation
* [ ] Lineage tracking

---

## 14. Summary

**v3 delivers:**

✅ a coherent and pragmatic architecture
✅ no premature complexity
✅ explicit uncertainty handling
✅ a realistic, buildable MVP
✅ a clear evolution path
