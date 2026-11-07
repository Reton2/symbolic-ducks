# @policyguard/client

Official TypeScript/JavaScript client package and String Enums for the **PolicyGuard Deep Neuro-Symbolic SMT OS**, generated directly from the FastAPI OpenAPI 3.1 specification.

## Directory Structure

```
packages/policyguard-client/
├── dist/
│   └── index.js          # Pre-bundled ESM distribution for browsers & Node.js
├── models/               # Domain models and String Enums
│   ├── VariableRole.ts
│   ├── VariableSort.ts
│   ├── ConstraintOperator.ts
│   ├── AbductiveSolveStatus.ts
│   ├── CounterfactualStatus.ts
│   └── VerificationStatus.ts
├── services/
│   └── DefaultService.ts # Typed async endpoints
├── core/                 # Fetch HTTP layer & CancelablePromise
├── PolicyGuardClient.ts  # Client root class
├── index.ts              # Entrypoint barrel
└── package.json
```

## Quick Start (Frontend / Browser / Node.js)

```typescript
import {
  PolicyGuardClient,
  VariableRole,
  VariableSort,
  ConstraintOperator,
  AbductiveSolveStatus
} from '@policyguard/client';

const client = new PolicyGuardClient();

// 1. Fetch system state & Z3 verification status
const state = await client.default.getSystemStateApiStateGet();
console.log(state.verification.status);

// 2. Abductive backward solve with String Enum target constraints
const solved = await client.default.solveForInputsEndpointApiSmtSolveInputsPost({
  target_constraints: {
    directive_execution_status: {
      op: ConstraintOperator.EQ,
      val: "EMERGENCY_HALT" // Accepts enum string name or numeric index
    }
  }
});

// 3. Connect to live telemetry WebSocket stream
const ws = new WebSocket(`ws://${location.host}/ws`);
ws.onmessage = (e) => {
  const { data } = JSON.parse(e.data);
  console.log(`DAG tick evaluated in ${data.latency_us} µs`);
};
```
