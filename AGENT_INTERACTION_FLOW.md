# Agent Interaction Flow — RepoSense

## Agent Lifecycle

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> RUNNING: task discovered
    RUNNING --> THINKING: analysis
    THINKING --> RUNNING: continue
    RUNNING --> WAITING: approval mode
    RUNNING --> REQUESTING_APPROVAL: critical fix
    REQUESTING_APPROVAL --> COMPLETED: approved
    REQUESTING_APPROVAL --> FAILED: rejected
    RUNNING --> COMPLETED: success
    RUNNING --> FAILED: error
    COMPLETED --> [*]
    FAILED --> [*]
```

## Task Propagation Flow

```mermaid
flowchart TD
    A[RepoNode created] --> B[DependencyAgent]
    B --> C[FileNodes + security_scan TaskNode]
    C --> D[SecurityAgent claims task]
    D --> E[VulnerabilityNodes]
    E --> F[generate_fix TaskNodes]
    F --> G[FixAgent claims tasks]
    G --> H{Approval mode?}
    H -->|yes| I[ApprovalNode pending]
    H -->|no| J[Auto-approved patches]
    I --> K[Supervisor Approve/Reject]
    K --> J
    B --> L[ImpactAgent blast radius]
    B --> M[ExplanationAgent summary]
```

## Graph Traversal Behavior

| Agent | Discovers work via | Creates |
|-------|-------------------|---------|
| DependencyAgent | `RepoNode` entry | `FileNode`, `TaskNode(security_scan)` |
| SecurityAgent | `pending_tasks(security_scan)` | `VulnerabilityNode`, `TaskNode(generate_fix)` |
| ImpactAgent | dependency graph | impact report on session |
| ExplanationAgent | repo analysis complete | summary, recommendations |
| FixAgent | `pending_tasks(generate_fix)` | `ApprovalNode`, patches |
| MonitorAgent | mission start/end | orchestration logs |

## Approval Workflow

1. FixAgent generates patch for high/medium finding
2. Creates `ApprovalNode` linked via `approval_request` edge
3. State → `REQUESTING_APPROVAL`
4. Frontend shows Agent Decision Console
5. `POST /approve` updates graph session
6. FixAgent → `COMPLETED`

## Autonomous Coordination Examples

```
[DependencyAgent] discovered 83 Python files
[SecurityAgent] identified insecure subprocess usage
[ImpactAgent] changing auth affects: Login, Billing, Session
[FixAgent] generated secure replacement patch
[ExplanationAgent] repo type: Flask Backend API
```

## Live Streaming

Frontend connects: `GET /stream/<session_id>` (EventSource)

Events:

- `log` — terminal execution stream
- `state` — agents, graph, findings, github metadata, summary
- `done` — mission complete

No mock data path—all events originate from real clone + scan + GitHub API + heuristics/LLM.
