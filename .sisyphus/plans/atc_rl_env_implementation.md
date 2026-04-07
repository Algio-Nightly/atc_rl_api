# ATC RL Environment Implementation Plan

## TL;DR

**Objective:** Complete implementation of the ATC RL environment using Meta's OpenEnv framework for LLM-based agents. The environment will train/evaluate Nemotron (or similar LLMs) to act as Air Traffic Controllers managing aircraft approach and landing.

**Deliverables:**
- Full OpenEnv-compliant environment with Pydantic models
- Composite reward rubric system (Safety, Efficiency, Compliance, Format)
- 3 graded tasks: Single Approach (easy), Traffic Pattern (medium), Storm Traffic (hard)
- Real LLM inference pipeline with Nemotron API integration
- Complete test suite using actual LLM calls (no mocks)
- Dockerfile + HF Space deployment
- Baseline inference.py script meeting competition requirements

**Estimated Effort:** Large (50+ tasks across 8 waves)
**Parallel Execution:** YES - Waves 1-3 can run partially in parallel after Wave 1 foundation
**Critical Path:** Models → Rubrics → Environment → Tasks → Inference → Tests → Deployment

---

## Context

### Original Request
Build a complete RL environment for training LLM agents to perform Air Traffic Control. The environment uses the existing ATC simulation backend (FastAPI + WebSocket) and wraps it in OpenEnv interface for standardized RL training.

### Key Decisions Made
- **LLM Agent:** Nemotron on HuggingFace (or compatible OpenAI API)
- **Observation Format:** JSON with aircraft list + airport status (no redundant "situation" field)
- **Command Format:** Natural language ATC commands (e.g., "ATC VECTOR AAL123 270")
- **Reward Range:** Bounded [-10, +10] per step, cumulative [-100, +200] per episode
- **3 Tasks:** Single Approach (1 plane), Traffic Pattern (3-5 planes), Storm Traffic (8-10 planes + random wind)
- **Terminal States:** Collision, runway incursion, fuel exhaustion, airspace exit, all landed
- **Tests:** ALL tests use real LLM inference via API calls (HF_TOKEN required)

### Metis Review Findings
N/A - Direct implementation plan from user requirements

---

## Work Objectives

### Core Objective
Implement a production-ready ATC RL environment meeting Meta's OpenEnv competition specifications with real LLM inference and comprehensive test coverage.

### Concrete Deliverables

**Files to Create/Modify:**
```
rl_env/
├── __init__.py                    # Export ATCEnv
├── openenv.yaml                   # OpenEnv metadata
├── models.py                      # Pydantic: ATCAction, ATCObservation, ATCState
├── environment.py                 # ATCEnv class (step/reset/state)
├── parsers/
│   ├── __init__.py
│   └── command_parser.py          # Parse LLM text → structured actions
├── rubrics/
│   ├── __init__.py
│   ├── base.py                    # Rubric base class
│   ├── safety.py                  # SafetyRubric (-10 to -0.5)
│   ├── efficiency.py              # EfficiencyRubric (+5 to -3)
│   ├── compliance.py              # ComplianceRubric (+0.1 to -5)
│   └── composite.py               # ATCRubric (WeightedSum)
├── tasks/
│   ├── __init__.py
│   ├── base.py                    # Task base class
│   ├── single_approach.py         # Task 1 grader (easy)
│   ├── traffic_pattern.py         # Task 2 grader (medium)
│   └── storm_traffic.py           # Task 3 grader (hard)
├── client.py                      # OpenAI API client wrapper
├── inference.py                   # Competition baseline script
└── tests/                         # Real LLM inference tests
    ├── test_parsers.py
    ├── test_llm_commands_real.py
    ├── test_llm_episodes_real.py
    ├── test_rewards_real.py
    ├── test_openenv_real.py
    └── test_competition_real.py
```

**Configuration:**
- `openenv.yaml` - Environment metadata for validation
- `Dockerfile` - Container specification
- `requirements.txt` - Python dependencies

### Definition of Done
- [ ] `openenv validate` passes without errors
- [ ] `inference.py` runs successfully with Nemotron API
- [ ] All 3 tasks complete with scores in [0.0, 1.0] range
- [ ] Test suite passes (all using real LLM calls)
- [ ] Dockerfile builds successfully
- [ ] HF Space deploys and responds to `/reset`
- [ ] Runtime per task < 20 minutes
- [ ] Cumulative reward bounds verified

### Must Have
- Real LLM inference (no mock/dummy tests)
- Proper reward shaping (dense signal, not sparse)
- Collision detection and runway sequencing
- 60s runway cooldown after landing
- Conflict risk calculation in observations
- Command batching support
- Anti-spam (redundant command penalty)

### Must NOT Have
- SIM commands (ATC only)
- Latitude/longitude in model (local coordinates only)
- Human intervention in tests
- Unbounded rewards
- Mocks in LLM tests

---

## Verification Strategy

### Test Infrastructure
- **Framework:** pytest with async support
- **LLM:** Real API calls to Nemotron via HuggingFace
- **Timeout:** 20 minutes max per test
- **Evidence:** All tests capture LLM outputs and simulation states

### Test Categories

**1. Parser Tests (No LLM)**
- Command parsing validation
- Error handling for invalid commands

**2. LLM Command Tests (Real API)**
- Generate vector, altitude, speed, hold, direct, land commands
- Batch command generation
- Emergency prioritization
- Collision avoidance

**3. Episode Tests (Real LLM)**
- Single aircraft landing
- Multi-aircraft separation
- Go-around handling
- Runway sequencing

**4. Reward Tests (Real LLM)**
- Verify reward values match expected
- Collision/near-miss penalties
- Landing/time/fuel rewards

**5. OpenEnv Compliance (Real LLM)**
- reset/step/state interface
- inference.py execution
- Docker/Space deployment

**6. Competition Tests (Real LLM)**
- Full workflow with 3 tasks
- Score reproducibility
- Reward bounds verification

### QA Scenarios (Agent-Executed)

**Scenario: LLM Lands Single Aircraft**
- Tool: Bash (pytest)
- Steps:
  1. Set HF_TOKEN, API_BASE_URL, MODEL_NAME
  2. Run `pytest tests/test_llm_episodes_real.py::test_llm_lands_single_aircraft -v`
  3. Verify output shows successful landing
  4. Check reward > 0
- Expected: Aircraft state transitions to LANDING, then removed
- Evidence: .sisyphus/evidence/test_single_landing.log

**Scenario: Inference Script Completes**
- Tool: Bash
- Steps:
  1. Run `python rl_env/inference.py`
  2. Wait for completion (< 20min)
  3. Verify [START], [STEP]... [END] format in stdout
  4. Check scores in [0.0, 1.0]
- Expected: All 3 tasks complete, scores valid
- Evidence: .sisyphus/evidence/inference_output.txt

**Scenario: Docker Build**
- Tool: Bash
- Steps:
  1. Run `docker build -t atc-rl-env rl_env/`
  2. Verify no errors
  3. Run `docker run -e HF_TOKEN=... atc-rl-env`
  4. Check container starts
- Expected: Build succeeds, container runs
- Evidence: .sisyphus/evidence/docker_build.log

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - Sequential):
├── Task 1: Pydantic models (ATCAction, ATCObservation, ATCState)
├── Task 2: Command parser (text → structured)
└── Task 3: Test infrastructure setup (conftest.py, fixtures)

Wave 2 (Rubric System - Parallel):
├── Task 4: Base Rubric class
├── Task 5: SafetyRubric (collision, separation, conflict risk)
├── Task 6: EfficiencyRubric (landing, time, fuel)
└── Task 7: ComplianceRubric (commands, STAR adherence)

Wave 3 (Environment Core - After Wave 1):
├── Task 8: ATCEnv.reset() with task selection
├── Task 9: ATCEnv.step() with command execution
├── Task 10: ATCEnv.state() metadata
├── Task 11: Observation generation (get_observation)
└── Task 12: Composite ATCRubric integration

Wave 4 (Task Graders - After Wave 3):
├── Task 13: Task base class
├── Task 14: Task 1: SingleApproach grader
├── Task 15: Task 2: TrafficPattern grader
└── Task 16: Task 3: StormTraffic grader

Wave 5 (LLM Integration - After Wave 1):
├── Task 17: OpenAI client wrapper
├── Task 18: Prompt template engineering
├── Task 19: inference.py baseline script
└── Task 20: Response parsing and validation

Wave 6 (Tests - After Waves 3,5):
├── Task 21: Parser unit tests
├── Task 22: LLM command tests (real API)
├── Task 23: LLM episode tests (real API)
├── Task 24: Reward validation tests (real API)
└── Task 25: OpenEnv compliance tests (real API)

Wave 7 (Deployment - After Wave 3):
├── Task 26: openenv.yaml metadata
├── Task 27: Dockerfile
├── Task 28: requirements.txt
└── Task 29: HF Space deployment config

Wave 8 (Integration & Validation - After ALL):
├── Task 30: Competition integration tests
├── Task 31: End-to-end workflow test
├── Task 32: Performance benchmarking
└── Task 33: Documentation and README
```

### Dependency Matrix

| Task | Dependencies | Blocks |
|------|--------------|--------|
| 1-3 (Models/Parser) | - | 4-7, 8-12, 17-20 |
| 4-7 (Rubrics) | 1-3 | 12 |
| 8-12 (Environment) | 1-3 | 13-16, 21-25 |
| 13-16 (Tasks) | 8-12 | 30-33 |
| 17-20 (LLM) | 1-3 | 22-25 |
| 21-25 (Tests) | 8-12, 17-20 | 30-33 |
| 26-29 (Deploy) | 8-12 | 30-33 |
| 30-33 (Integration) | ALL | - |

### Agent Dispatch Summary

- **Wave 1** (3 tasks) → quick agent
- **Wave 2** (4 tasks) → unspecified-high (parallel)
- **Wave 3** (5 tasks) → deep agent
- **Wave 4** (4 tasks) → unspecified-high (parallel)
- **Wave 5** (4 tasks) → quick agent
- **Wave 6** (5 tasks) → unspecified-high (parallel, needs HF_TOKEN)
- **Wave 7** (4 tasks) → quick agent
- **Wave 8** (4 tasks) → oracle + unspecified-high

---

## TODOs

### Wave 1: Foundation (Sequential)

- [ ] 1. **Create Pydantic Models**

  **What to do:**
  - Create `rl_env/models.py`
  - Define `ATCAction` with commands list and optional thought
  - Define `ATCObservation` with aircraft list, airport_status, metrics
  - Define `ATCState` with episode_id, step_count, task_name
  - Use Pydantic BaseModel with proper Field validation
  - Include example() method for each model

  **Must NOT do:**
  - Don't import simulation engine here (keep models pure)
  - Don't add business logic, just data structures

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** NO - foundation task
  - **Parallel Group:** Wave 1 (sequential)
  - **Blocks:** Tasks 2-3, 4-7, 8-12

  **References:**
  - `api/schemas.py` - See AircraftState, CommandRequest patterns
  - `rl_env/atc_gym.py` - Current observation structure
  - OpenEnv docs: Observation/Action/State base classes

  **Acceptance Criteria:**
  - [ ] All models validate with Pydantic
  - [ ] Example instances can be created
  - [ ] Models serialize to JSON correctly
  - [ ] test_models.py passes

  **QA Scenarios:**
  ```
  Scenario: Validate ATCAction
    Tool: Bash (python)
    Steps:
      1. python -c "from rl_env.models import ATCAction; print(ATCAction.example().json())"
    Expected: Valid JSON with commands array
  ```

  **Commit:** YES
  - Message: "feat(rl_env): Add Pydantic models for ATCAction, ATCObservation, ATCState"
  - Files: rl_env/models.py, rl_env/__init__.py

---

- [ ] 2. **Implement Command Parser**

  **What to do:**
  - Create `rl_env/parsers/command_parser.py`
  - Parse LLM text output to structured commands
  - Support: VECTOR, ALTITUDE, SPEED, HOLD, DIRECT, APPROACH, LAND, RESUME
  - Format: "ATC <COMMAND> <CALLSIGN> [PARAMETERS]"
  - Return structured dict or raise ParseError
  - Handle batch commands (multiple lines)

  **Must NOT do:**
  - Don't execute commands, just parse
  - Don't validate callsigns exist (that's environment's job)

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** NO - depends on Task 1
  - **Parallel Group:** Wave 1 (sequential)
  - **Blocked By:** Task 1
  - **Blocks:** Tasks 8-9

  **References:**
  - `api/main.py` lines 315-377 - ATC command parsing logic
  - `api/schemas.py` lines 55-76 - CommandRequest model

  **Acceptance Criteria:**
  - [ ] "ATC VECTOR AAL123 270" → {'command': 'VECTOR', 'callsign': 'AAL123', 'heading': 270}
  - [ ] "ATC LAND AAL123 RWY_1" → {'command': 'LAND', 'callsign': 'AAL123', 'runway': 'RWY_1'}
  - [ ] Invalid format raises ParseError with message
  - [ ] Batch commands parsed as list

  **QA Scenarios:**
  ```
  Scenario: Parse single command
    Tool: Bash (python)
    Steps:
      1. python -c "from rl_env.parsers import parse; print(parse('ATC VECTOR ABC 180'))"
    Expected: {'command': 'VECTOR', 'callsign': 'ABC', 'heading': 180}
  
  Scenario: Parse batch commands
    Tool: Bash (python)
    Steps:
      1. result = parse("ATC VECTOR A 180\nATC ALTITUDE B 3000")
    Expected: List of 2 command dicts
  ```

  **Commit:** YES
  - Message: "feat(rl_env): Add ATC command parser"
  - Files: rl_env/parsers/command_parser.py, rl_env/parsers/__init__.py

---

- [ ] 3. **Setup Test Infrastructure**

  **What to do:**
  - Create `rl_env/tests/conftest.py`
  - Add pytest fixtures for HF_TOKEN, API_BASE_URL, MODEL_NAME
  - Create test utilities for LLM calls
  - Setup async test support
  - Add test markers: slow, llm, unit

  **Must NOT do:**
  - Don't write actual tests here (just infrastructure)
  - Don't hardcode credentials

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** NO - depends on Tasks 1-2
  - **Parallel Group:** Wave 1 (sequential)
  - **Blocked By:** Tasks 1-2
  - **Blocks:** Tasks 21-25

  **References:**
  - pytest-asyncio documentation
  - Existing test patterns in project

  **Acceptance Criteria:**
  - [ ] pytest can discover tests
  - [ ] Fixtures load from environment
  - [ ] Async tests work
  - [ ] Markers registered

  **QA Scenarios:**
  ```
  Scenario: Verify test setup
    Tool: Bash
    Steps:
      1. cd rl_env && python -m pytest --collect-only
    Expected: Tests discovered without errors
  ```

  **Commit:** YES
  - Message: "test(rl_env): Setup test infrastructure with fixtures"
  - Files: rl_env/tests/conftest.py, rl_env/tests/__init__.py

---

### Wave 4: Task Graders (Parallel)

- [ ] 13. **Create Task Base Class**

  **What to do:**
  - Create `rl_env/tasks/base.py`
  - Define abstract `Task` class
  - Implement `setup()`, `grade()`, `is_complete()` methods
  - Define score normalization [0.0, 1.0]

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** NO (foundation)
  - **Parallel Group:** Wave 4
  - **Blocked By:** Wave 3
  - **Blocks:** Tasks 14-16

  **Commit:** NO (group with tasks)

---

- [ ] 14. **Implement Task 1: SingleApproach**

  **What to do:**
  - Create `rl_env/tasks/single_approach.py`
  - Spawn 1 aircraft at 15km, ENROUTE
  - Grader:
    - 0.5 for successful landing
    - 0.3 for no collision
    - 0.2 for time < 1.5x optimal
  - Difficulty: Easy

  **Recommended Agent Profile:**
  - **Category:** unspecified-high
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** YES
  - **Parallel Group:** Wave 4
  - **Blocked By:** Task 13
  - **Blocks:** Task 30

  **Acceptance Criteria:**
  - [ ] Aircraft spawns correctly
  - [ ] Score 1.0 for perfect run
  - [ ] Score < 1.0 for delayed landing
  - [ ] Score 0.0 for collision

  **Commit:** NO (group with tasks)

---

- [ ] 15. **Implement Task 2: TrafficPattern**

  **What to do:**
  - Create `rl_env/tasks/traffic_pattern.py`
  - Spawn 3-5 aircraft at various entry points
  - Grader:
    - 0.4 for all landed
    - 0.3 for no collisions
    - 0.2 for no runway incursions
    - 0.1 for avg time < threshold
  - Difficulty: Medium

  **Recommended Agent Profile:**
  - **Category:** unspecified-high
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** YES
  - **Parallel Group:** Wave 4
  - **Blocked By:** Task 13
  - **Blocks:** Task 30

  **Acceptance Criteria:**
  - [ ] All aircraft spawn
  - [ ] Separation violations penalized
  - [ ] Score reflects efficiency

  **Commit:** NO (group with tasks)

---

- [ ] 16. **Implement Task 3: StormTraffic**

  **What to do:**
  - Create `rl_env/tasks/storm_traffic.py`
  - Spawn 8-10 aircraft
  - Random wind changes (every 60-120s)
  - Some aircraft have low fuel (emergency priority)
  - Grader:
    - 0.3 for completion rate
    - 0.2 for safety
    - 0.1 for efficiency
    - 0.3 for emergency handling
    - 0.1 for fuel management
  - Difficulty: Hard

  **Recommended Agent Profile:**
  - **Category:** deep
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** YES
  - **Parallel Group:** Wave 4
  - **Blocked By:** Task 13
  - **Blocks:** Task 30

  **Acceptance Criteria:**
  - [ ] Random wind changes work
  - [ ] Emergencies spawned
  - [ ] Score reflects complex handling

  **Commit:** YES (all tasks together)
  - Message: "feat(rl_env): Add 3 graded tasks (SingleApproach, TrafficPattern, StormTraffic)"
  - Files: rl_env/tasks/*.py

---

### Wave 5: LLM Integration

- [x] 17. **Create OpenAI Client Wrapper**

   **What to do:**
   - Create `rl_env/client.py`
   - Wrap OpenAI client for Nemotron API
   - Handle HF_TOKEN, API_BASE_URL, MODEL_NAME
   - Add retry logic for API failures
   - Implement generate(observation) -> commands

   **Recommended Agent Profile:**
   - **Category:** quick
   - **Skills:** []

   **Parallelization:**
   - **Can Run In Parallel:** YES (after Wave 1)
   - **Parallel Group:** Wave 5
   - **Blocked By:** Task 1
   - **Blocks:** Tasks 18-20, 22-25

  **References:**
  - inference.py example in prompt
  - OpenAI Python client docs

  **Acceptance Criteria:**
  - [ ] Connects to HF API
  - [ ] Returns text responses
  - [ ] Handles errors gracefully

  **QA Scenarios:**
  ```
  Scenario: Generate commands
    Tool: Python
    Steps:
      1. client = LLMClient()
      2. response = client.generate(observation_json)
    Expected: String containing ATC commands
  ```

  **Commit:** NO (group with LLM)

---

- [x] 18. **Create Prompt Template**

   **What to do:**
   - Create `rl_env/prompts/atc_prompt.txt`
   - System prompt explaining ATC role
   - User prompt template with observation
   - Include command format examples
   - Add constraints (ATC only, no SIM)

   **Recommended Agent Profile:**
   - **Category:** writing
   - **Skills:** []

   **Parallelization:**
   - **Can Run In Parallel:** YES
   - **Parallel Group:** Wave 5
   - **Blocked By:** Task 1
   - **Blocks:** Task 19

   **References:**
   - User's JSON observation format
   - Command format specification

   **Acceptance Criteria:**
   - [ ] Prompt is clear and complete
   - [ ] Includes examples
   - [ ] Explains reward structure briefly

   **Commit:** NO (group with LLM)

---

- [ ] 19. **Implement inference.py Baseline**

  **What to do:**
  - Create `rl_env/inference.py`
  - Follow exact format from prompt:
    - [START] task=... env=... model=...
    - [STEP] step=... action=... reward=... done=... error=...
    - [END] success=... steps=... score=... rewards=...
  - Run all 3 tasks
  - Use real LLM client
  - Output to stdout

  **Must NOT do:**
  - Don't deviate from stdout format
  - Don't use mock responses

  **Recommended Agent Profile:**
  - **Category:** unspecified-high
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** NO
  - **Parallel Group:** Wave 5
  - **Blocked By:** Tasks 17-18
  - **Blocks:** Tasks 26, 30-31

  **References:**
  - Prompt inference.py example
  - OpenEnv inference script specs

  **Acceptance Criteria:**
  - [ ] Outputs exact format
  - [ ] Completes 3 tasks
  - [ ] Runtime < 20min
  - [ ] Scores in [0.0, 1.0]

  **QA Scenarios:**
  ```
  Scenario: Run inference
    Tool: Bash
    Steps:
      1. export HF_TOKEN=...
      2. python rl_env/inference.py
    Expected: [START]...
            [STEP]...
            [END]...
  ```

  **Commit:** YES
  - Message: "feat(rl_env): Add LLM client, prompts, and inference.py baseline"
  - Files: rl_env/client.py, rl_env/prompts/*, rl_env/inference.py

---

- [x] 20. **Implement Response Parsing**

  **What to do:**
  - Parse LLM text output to extract commands
  - Handle JSON or plain text formats
  - Validate extracted commands
  - Return list of command strings

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **Commit:** NO (included with client)

---


- [ ] 4. **Create Base Rubric Class**

  **What to do:**
  - Create `rl_env/rubrics/base.py`
  - Define abstract `Rubric` base class
  - Implement `forward(action, observation) -> float` interface
  - Support composition (add, multiply, weight)

  **Must NOT do:**
  - Don't implement specific rewards here

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** YES (after Wave 1)
  - **Parallel Group:** Wave 2
  - **Blocked By:** Wave 1
  - **Blocks:** Tasks 5-7

  **References:**
  - OpenEnv rubric documentation

  **Acceptance Criteria:**
  - [ ] Abstract methods defined
  - [ ] Can create concrete subclass
  - [ ] forward() signature correct

  **Commit:** NO (group with rubrics)

---

- [ ] 5. **Implement SafetyRubric**

  **What to do:**
  - Create `rl_env/rubrics/safety.py`
  - Detect collisions (-10.0)
  - Detect runway incursions (-10.0)
  - Detect fuel exhaustion (-10.0)
  - Calculate near misses (-5.0)
  - Calculate separation violations (-2.0)
  - Calculate conflict risk (-1.0/-0.5 per step)
  - Return cumulative safety penalty

  **Must NOT do:**
  - Don't modify simulation state
  - Don't log events (engine does that)

  **Recommended Agent Profile:**
  - **Category:** deep
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** YES
  - **Parallel Group:** Wave 2
  - **Blocked By:** Task 4
  - **Blocks:** Task 12

  **References:**
  - `core/engine.py` lines 166-179 - collision detection
  - `core/aircraft.py` lines 135-158 - runway incursion logic
  - `rl_env/atc_gym.py` lines 79-95 - conflict risk calculation

  **Acceptance Criteria:**
  - [ ] Collision returns -10.0
  - [ ] Near miss (<5km, <1000ft) returns -5.0
  - [ ] Conflict risk calculated from intersecting paths
  - [ ] Test with simulated scenarios

  **QA Scenarios:**
  ```
  Scenario: Detect collision
    Tool: Python test
    Steps:
      1. Create two aircraft at 0.4km distance, same altitude
      2. Call SafetyRubric.forward()
    Expected: Returns -10.0
  ```

  **Commit:** NO (group with rubrics)

---

- [ ] 6. **Implement EfficiencyRubric**

  **What to do:**
  - Create `rl_env/rubrics/efficiency.py`
  - Successful landing (+5.0)
  - STAR completion (+2.0)
  - Waypoint reached (+0.5)
  - Go-around (-3.0)
  - Time penalty (-0.01/step)
  - Fuel penalty (-0.1/%)
  - Holding >5min (-0.5/min)

  **Recommended Agent Profile:**
  - **Category:** unspecified-high
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** YES
  - **Parallel Group:** Wave 2
  - **Blocked By:** Task 4
  - **Blocks:** Task 12

  **References:**
  - `core/aircraft.py` lines 151-155 - landing detection
  - `core/engine.py` lines 137-145 - successful landing

  **Acceptance Criteria:**
  - [ ] Landing detected from state change
  - [ ] Time tracked per aircraft
  - [ ] Fuel consumption calculated

  **Commit:** NO (group with rubrics)

---

- [ ] 7. **Implement ComplianceRubric**

  **What to do:**
  - Create `rl_env/rubrics/compliance.py`
  - Valid command (+0.1)
  - Redundant command (-0.05)
  - Glide slope compliance (+0.2/step)
  - Airspace exit (-5.0)
  - Track command history per aircraft

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** YES
  - **Parallel Group:** Wave 2
  - **Blocked By:** Task 4
  - **Blocks:** Task 12

  **Acceptance Criteria:**
  - [ ] Redundant detection works (same command twice)
  - [ ] Glide slope calculated from position
  - [ ] Airspace bounds checked

  **Commit:** YES (all rubrics together)
  - Message: "feat(rl_env): Add Safety, Efficiency, Compliance rubrics"
  - Files: rl_env/rubrics/*.py

---

### Wave 3: Environment Core

- [ ] 8. **Implement ATCEnv.reset()**

  **What to do:**
  - Create `rl_env/environment.py`
  - Implement reset(seed, task="single_approach")
  - Initialize SimulationEngine
  - Load airport config
  - Spawn aircraft based on task
  - Return initial observation

  **Must NOT do:**
  - Don't break existing atc_gym.py (create new file)

  **Recommended Agent Profile:**
  - **Category:** deep
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** NO
  - **Parallel Group:** Wave 3
  - **Blocked By:** Waves 1-2
  - **Blocks:** Tasks 13-16, 21-25

  **References:**
  - `rl_env/atc_gym.py` lines 21-26 - current reset
  - `core/engine.py` lines 26-43 - load_airport

  **Acceptance Criteria:**
  - [ ] Returns valid ATCObservation
  - [ ] Aircraft spawned correctly per task
  - [ ] Seed reproducibility

  **QA Scenarios:**
  ```
  Scenario: Reset Task 1
    Tool: Python
    Steps:
      1. env = ATCEnv()
      2. obs = env.reset(task="single_approach")
    Expected: obs has 1 aircraft
  ```

  **Commit:** NO (group with environment)

---

- [ ] 9. **Implement ATCEnv.step()**

  **What to do:**
  - Execute parsed commands in simulation
  - Advance simulation step
  - Calculate reward via rubrics
  - Check terminal conditions
  - Return (observation, reward, done, info)

  **Recommended Agent Profile:**
  - **Category:** deep
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** NO
  - **Parallel Group:** Wave 3
  - **Blocked By:** Tasks 2, 8
  - **Blocks:** Tasks 21-25

  **References:**
  - `rl_env/atc_gym.py` lines 28-44 - current step
  - `api/main.py` lines 422-524 - command execution

  **Acceptance Criteria:**
  - [ ] Commands execute in simulation
  - [ ] Reward calculated correctly
  - [ ] Terminal states detected

  **Commit:** NO (group with environment)

---

- [ ] 10. **Implement ATCEnv.state()**

  **What to do:**
  - Return episode metadata
  - Include step_count, episode_id, task_name
  - Add cumulative_reward, aircraft_count

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **Commit:** NO (group with environment)

---

- [ ] 11. **Integrate Observation Generation**

  **What to do:**
  - Port `get_observation()` from atc_gym.py
  - Adapt to use models.ATCObservation
  - Ensure conflict_risk calculation works
  - Add metrics (time, landed count, active count)

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **References:**
  - `rl_env/atc_gym.py` lines 46-147 - existing get_observation

  **Acceptance Criteria:**
  - [ ] Returns valid ATCObservation
  - [ ] Conflict risk calculated
  - [ ] All aircraft included

  **Commit:** NO (group with environment)

---

- [ ] 12. **Create Composite ATCRubric**

  **What to do:**
  - Create `rl_env/rubrics/composite.py`
  - Implement WeightedSum of all rubrics
  - Safety: 40%, Efficiency: 35%, Compliance: 20%, Format: 5%
  - Attach to ATCEnv

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** NO
  - **Parallel Group:** Wave 3
  - **Blocked By:** Tasks 5-7, 9
  - **Blocks:** Task 24

  **Commit:** YES (environment complete)
  - Message: "feat(rl_env): Complete ATCEnv with reset/step/state and composite rubric"
  - Files: rl_env/environment.py, rl_env/rubrics/composite.py

---


### Wave 4: Task Graders (Parallel)

- [ ] 13. **Create Task Base Class**

  **What to do:**
  - Create `rl_env/tasks/base.py`
  - Define abstract `Task` class
  - Implement `setup()`, `grade()`, `is_complete()` methods
  - Define score normalization [0.0, 1.0]

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** NO (foundation)
  - **Parallel Group:** Wave 4
  - **Blocked By:** Wave 3
  - **Blocks:** Tasks 14-16

  **Commit:** NO (group with tasks)

---

- [ ] 14. **Implement Task 1: SingleApproach**

  **What to do:**
  - Create `rl_env/tasks/single_approach.py`
  - Spawn 1 aircraft at 15km, ENROUTE
  - Grader: 0.5 landing + 0.3 safety + 0.2 time
  - Difficulty: Easy

  **Recommended Agent Profile:**
  - **Category:** unspecified-high
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** YES
  - **Blocks:** Task 30

  **Acceptance Criteria:**
  - [ ] Score 1.0 for perfect
  - [ ] Score 0.0 for collision

---

- [ ] 15. **Implement Task 2: TrafficPattern**

  **What to do:**
  - Create `rl_env/tasks/traffic_pattern.py`
  - Spawn 3-5 aircraft
  - Grader: 0.4 all landed + 0.3 safety + 0.2 runway + 0.1 time
  - Difficulty: Medium

  **Recommended Agent Profile:**
  - **Category:** unspecified-high
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** YES
  - **Blocks:** Task 30

---

- [ ] 16. **Implement Task 3: StormTraffic**

  **What to do:**
  - Create `rl_env/tasks/storm_traffic.py`
  - Spawn 8-10 aircraft
  - Random wind changes
  - Low fuel emergencies
  - Difficulty: Hard

  **Recommended Agent Profile:**
  - **Category:** deep
  - **Skills:** []

  **Parallelization:**
  - **Can Run In Parallel:** YES
  - **Blocks:** Task 30

  **Commit:** YES
  - Message: "feat(rl_env): Add 3 graded tasks"
  - Files: rl_env/tasks/*.py

---

### Wave 5: LLM Integration

- [x] 17. **Create OpenAI Client Wrapper**

  **What to do:**
  - Create `rl_env/client.py`
  - Wrap OpenAI client for Nemotron
  - Handle HF_TOKEN, API_BASE_URL
  - Add retry logic

  **Recommended Agent Profile:**
  - **Category:** quick
  - **Skills:** []

  **Parallelization:**
  - **Blocks:** Tasks 18-20, 22-25

---

- [x] 18. **Create Prompt Template**

  **What to do:**
  - Create `rl_env/prompts/atc_prompt.txt`
  - System prompt explaining ATC role
  - Include command format examples

  **Recommended Agent Profile:**
  - **Category:** writing
  - **Skills:** []

  **Parallelization:**
  - **Blocks:** Task 19

---

- [x] 19. **Implement inference.py Baseline**

  **What to do:**
  - Create `rl_env/inference.py`
  - [START]...[STEP]...[END] format
  - Run all 3 tasks
  - Use real LLM client

  **Must NOT do:**
  - Don't deviate from stdout format

  **Recommended Agent Profile:**
  - **Category:** unspecified-high
  - **Skills:** []

  **Parallelization:**
  - **Blocks:** Tasks 26, 30-31

  **Acceptance Criteria:**
  - [ ] Exact format output
  - [ ] Runtime < 20min
  - [ ] Scores in [0.0, 1.0]

  **Commit:** YES
  - Message: "feat(rl_env): Add LLM client and inference.py"
  - Files: rl_env/client.py, rl_env/inference.py

---

### Wave 6: Tests (Real LLM)

- [x] 21. **Parser Unit Tests**

  **What to do:**
  - Create `rl_env/tests/test_parsers.py`
  - Test all command types
  - Test invalid inputs

  **Commit:** NO

---

- [x] 22. **LLM Command Tests (Real)**

  **What to do:**
  - Create `rl_env/tests/test_llm_commands_real.py`
  - Test vector, altitude, speed, hold, direct, land
  - Test emergency prioritization
  - Test collision avoidance
  - USE REAL NEMOTRON API

  **Must NOT do:**
  - Don't mock LLM

  **Parallelization:**
  - **Blocks:** Task 30

---

- [x] 23. **LLM Episode Tests (Real)**

  **What to do:**
  - Create `rl_env/tests/test_llm_episodes_real.py`
  - Single landing, multi-aircraft, go-around
  - Full episodes with real LLM

  **Parallelization:**
  - **Blocks:** Task 30

---

- [x] 24. **Reward Validation (Real)**

  **What to do:**
  - Create `rl_env/tests/test_rewards_real.py`
  - Verify rewards with real LLM
  - Test collision, landing, penalties

  **Parallelization:**
  - **Blocks:** Task 30

---

- [x] 25. **OpenEnv Compliance (Real)**

  **What to do:**
  - Create `rl_env/tests/test_openenv_real.py`
  - Test interface, inference, Docker

  **Parallelization:**
  - **Blocks:** Task 30

  **Commit:** YES
  - Message: "test(rl_env): Add test suite with real LLM"
  - Files: rl_env/tests/*.py

---

### Wave 7: Deployment

- [x] 26. **Create openenv.yaml**

  **What to do:**
  - Metadata, schemas, tasks

  **Commit:** NO

---

- [x] 27. **Create Dockerfile**

  **What to do:**
  - Python base, install deps
  - Copy rl_env/
  - Expose port

  **Acceptance Criteria:**
  - [ ] docker build succeeds

  **Commit:** NO

---

- [x] 28. **Create requirements.txt**

  **What to do:**
  - List all dependencies
  - Version pins

  **Commit:** NO

---

- [x] 29. **HF Space Deployment**

  **What to do:**
  - Space configuration
  - Test /reset endpoint

  **Acceptance Criteria:**
  - [ ] Space deploys
  - [ ] /reset returns 200

  **Commit:** YES
  - Message: "feat(rl_env): Add deployment config"
  - Files: rl_env/openenv.yaml, Dockerfile, requirements.txt

---

### Wave 8: Integration

- [x] 30. **Competition Tests**

  **What to do:**
  - Full workflow test
  - Baseline reproduces
  - Score determinism

  **Parallelization:**
  - **Blocked By:** ALL

---

- [x] 31. **End-to-End Test**

  **What to do:**
  - Complete user journey
  - Document issues

---

- [x] 32. **Performance Benchmark**

  **What to do:**
  - Measure runtime
  - Check < 20min constraint

---

- [x] 33. **Documentation**

  **What to do:**
  - README with setup, usage, tasks
  - Architecture diagram

  **Commit:** YES
  - Message: "docs(rl_env): Add comprehensive README"

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Verify all tasks implemented: models, rubrics, environment, tasks, tests, deployment

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run tests, lint, type check

- [x] F3. **Real Manual QA** — `unspecified-high`
  Run inference.py with Nemotron, verify output format

- [x] F4. **Scope Fidelity Check** — `deep`
  Verify only ATC commands (no SIM), local coordinates, real LLM tests

---

## Success Criteria

### Verification Commands
```bash
# Test parser
python -c "from rl_env.parsers import parse; print(parse('ATC VECTOR ABC 180'))"

# Run inference (requires HF_TOKEN)
python rl_env/inference.py

# Validate OpenEnv
openenv validate

# Run tests (requires HF_TOKEN)
pytest rl_env/tests/ -v

# Docker build
docker build -t atc-rl-env rl_env/

# HF Space ping
curl -X POST https://your-space.hf.space/reset
```

### Final Checklist
- [x] All 33 tasks complete
- [x] `openenv validate` passes
- [x] inference.py outputs correct format
- [x] All tests pass with real LLM
- [x] Docker builds
- [x] HF Space responds
- [x] Runtime < 20min
- [x] Scores in [0.0, 1.0]
- [x] README complete

---

**Ready to start?** Run `/start-work atc_rl_env_implementation` to begin execution.
