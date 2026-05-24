# RESEARCH · ENGINEERING CHECKLIST v1.1 (2026)

## Статус документа

- **Protocol ID:** `NEOSYNAPTEX-PROTOCOL-v1.1`
- **Status:** ACTIVE
- **Scope:** PR/CI governance for research and engineering changes.
- **Canonical machine-readable payload:** `docs/research/NEOSYNAPTEX_PROTOCOL_V1_1.json`.

Цей документ є human-readable контрактом. JSON-файл є canonical machine-readable контрактом для policy tooling. Якщо між ними виникає розбіжність, PR не є merge-ready до синхронізації обох шарів.

---

## 0) Six-File Methodology

Перед імплементацією зміна має мати 6 мінімальних артефактів:

1. `docs/research/01_problem.md` — проблема + falsification condition (`PRE-01`).
2. `docs/research/02_contract.yaml` — I/O, типи, boundary conditions (`PRE-02`).
3. `docs/research/03_invariants.yaml` — інваріанти, метрики, pass conditions (`MATH-01`, `VAL-01`, `SEM-01`, `ARCH-01`).
4. `docs/research/04_test_plan.md` — red→green, contract coverage, adversarial cases (`VAL-01..03`).
5. `docs/research/05_governance.md` — human impact, rollback, CI mapping (`GOV-01..03`).
6. `docs/research/06_change_plan.md` — мінімальний implementation plan (`IMPL-01..03`).

**Gate rule:** якщо будь-який із 6 файлів відсутній або порожній, зміна не має проходити governance review.

---

## 1) Деідеологізація validation-layer

Цей протокол **не використовує як merge gate**:

- “Principle of Least Action” у метафоричному сенсі.
- “Сімку” як маркер стійкості без формальної метрики.
- `γ≈1.0` як універсальний “золотий режим” без estimator/CI/null/boundary.

Такі твердження можуть існувати лише як DECORATIVE research context. Вони не можуть бути доказом готовності PR.

---

## 2) Severity model

- **BLOCKER** — обов’язково до merge; failure блокує інтеграцію.
- **ADVISORY** — допустиме відхилення лише з явним override rationale у PR note.
- **DECORATIVE** — нефункціональний контекст; заборонено використовувати як validation gate.

---

## 3) Checklist schema

### PRE-WORK

- [ ] **PRE-01 (BLOCKER) · Falsifiable Hypothesis**  
  Проблема сформульована як falsifiable hypothesis з явною умовою спростування.  
  **Enforcement:** `01_problem.md` містить `Falsification Condition`.

- [ ] **PRE-02 (BLOCKER) · Contract Definition**  
  I/O, типи та межі визначені до імплементації.  
  **Enforcement:** `02_contract.yaml` містить non-empty `inputs`, `outputs`, `boundaries`.

- [ ] **PRE-03 (BLOCKER) · Six-File Presence Gate**  
  Усі 6 методологічних файлів існують і non-empty.  
  **Enforcement:** `tools/audit/check_six_file_presence.py` генерує `artifacts/audit/six_file_presence_report.json`.

### MATH

- [ ] **MATH-01 (BLOCKER) · Dimensional Consistency**  
  Розмірності/одиниці в формулах узгоджені або явно позначені як non-physical governance metadata.  
  **Enforcement:** `artifacts/audit/dimension_check_report.json` має `status = PASS`.

- [ ] **MATH-02 (BLOCKER) · No Magic Numbers**  
  Коефіцієнти мають бути виведені, параметризовані або задекларовані як DECORATIVE.  
  **Enforcement:** review/lint rule або явний override.

### IMPLEMENTATION

- [ ] **IMPL-01 (BLOCKER) · Single Responsibility**  
  Один модуль має одну основну відповідальність.

- [ ] **IMPL-02 (BLOCKER) · Minimal Sufficient Code**  
  Кожен блок підсилює контракт, інваріант або відтворюваність.

- [ ] **IMPL-03 (BLOCKER) · Isolated Side Effects**  
  Побічні ефекти локалізовані; мутації стану явні.

### VALIDATION

- [ ] **VAL-01 (BLOCKER) · Red-Green Evidence**  
  Для high-impact змін потрібні failing run URL і passing run URL або documented reason, чому red→green не застосовується до documentation-only governance change.

- [ ] **VAL-02 (BLOCKER) · Contract Coverage**  
  Перевіряється контракт, а не просто рядки.

- [ ] **VAL-03 (BLOCKER) · Adversarial Input**  
  Edge/malformed input має мати тест-план або executable check.

### FALSIFICATION

- [ ] **FALS-01 (BLOCKER) · Independent Verification Protocol**  
  Валідація проходить через незалежний script/test harness, не через консенсус LLM-агентів.

- [ ] **FALS-02 (ADVISORY) · Negative Result Documentation**  
  Негативні результати зберігаються як інженерні дані.

> Інша модель/агент може бути adversarial reviewer, але не самодостатнім falsification evidence.

### ARTIFACT

- [ ] **ART-01 (BLOCKER) · Documentation as Contract**  
  Документи мають читатися як операційний контракт.

- [ ] **ART-02 (BLOCKER) · Reproducible Environment**  
  Має існувати відтворюваний шлях запуску validation scripts.

- [ ] **ART-03 (ADVISORY) · Tool-Agnostic Artifacts**  
  `Invariants.yaml` може бути обов’язковим; `CLAUDE.md` не є BLOCKER-вимогою.

### GOVERNANCE

- [ ] **GOV-01 (BLOCKER) · Human-in-the-Loop Safety**  
  Significant changes оцінюють вплив на людину: безпека, агентність, ризик виключення.

- [ ] **GOV-02 (BLOCKER) · Emergency Exit**  
  Rollback або kill-switch шлях задокументовано.

- [ ] **GOV-03 (BLOCKER) · CI Failure Mapping**  
  Кожен CI fail має бути прив’язаний до checklist ID перед фіксом.  
  **Accepted sources:** commit message або PR note.

---

## 4) CI Failure Protocol

1. CI падає (`exit code != 0`) → execution halt.
2. Failure класифікується по `checklist_id` та severity.
3. Для high-impact змін додається `Six-File Evidence`.
4. Фікс заборонений до ідентифікації порушеного інваріанта.
5. Merge дозволений лише якщо всі BLOCKER = PASS і всі ADVISORY violations мають override rationale.

Формат PR note:

```text
CI Failure Mapping:
- failure: <short description>
- checklist_id: <PRE-*|MATH-*|IMPL-*|VAL-*|FALS-*|ART-*|GOV-*|SEM-*|ARCH-*>
- severity: <BLOCKER|ADVISORY|DECORATIVE>
- fix_plan: <one paragraph>
```

Six-File Evidence:

```text
problem: docs/research/01_problem.md
contract: docs/research/02_contract.yaml
invariants: docs/research/03_invariants.yaml
test_plan: docs/research/04_test_plan.md
governance: docs/research/05_governance.md
change_plan: docs/research/06_change_plan.md
```

---

## 5) Cost Function Optimization Rule

Архітектурні рішення мають мінімізувати latency/compute **за збереження необхідної точності**. Будь-який tunable parameter, включно з `γ`, має мати всі 4 constraints:

1. `estimator_definition`
2. `uncertainty_or_confidence_interval`
3. `null_or_surrogate_baseline`
4. `applicability_boundary`

Якщо хоча б один constraint відсутній, параметр є DECORATIVE, а не доказовим.

---

## 6) Semantic anti-bullshit gate

`SEM-01` захищає від порожнього формалізму, де файл існує, але не має змістовної ролі.

- Script: `tools/audit/check_six_file_semantics.py`
- Report: `artifacts/audit/six_file_semantics_report.json`
- Required status: `PASS`

Перевіряє: falsification section, contract keys, invariant pass-conditions, red/green plan, adversarial cases, governance mapping, rollback і structured change plan.

---

## 7) First-principles & value-function alignment

`ARCH-01` перевіряє, що PR-структура не перетворюється на декоративний формалізм.

- Spec: `docs/research/07_first_principles_value_function.yaml`
- Script: `tools/audit/check_value_architecture_mapping.py`
- Report: `artifacts/audit/value_architecture_report.json`
- Required status: `PASS`

---

## 8) Canonical JSON payload

Canonical machine-readable schema lives in:

```text
docs/research/NEOSYNAPTEX_PROTOCOL_V1_1.json
```

The JSON must encode the same semantics as this document, including:

- full `cost_function_constraints` list;
- merge rule requiring BLOCKER pass and ADVISORY override rationale;
- GOV-03 accepted evidence sources: `commit_message` and `pr_note`.

---

## 9) Final merge condition

- All BLOCKER checks are PASS.
- Every ADVISORY violation has explicit override rationale.
- DECORATIVE claims are not used for approval.
- Canonical JSON and human-readable document are semantically aligned.

Якщо хоча б один BLOCKER не тримається — **not done**.

---

**Дисципліна = пройдений протокол.**
