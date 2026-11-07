# Symbolic Ducks HTB

Risk and user -> happy
Show to manager -> audit trail, why the decision made
Risk -> How is it relevant to policy
User -> Real time decision making

### Risk
Nodes/ sub decisions mapped to original document

### Manager
Complete audit trail of decision

### User
Minimal computation cost so no LLMs for inference ideally or just parsing

### Decision Making
- SMT -> Made by AI graph
- KAN -> Atomic claim input output generation

### Policy to Code
Input isolation -> Find all inputs relevant to policy
Output isolation -> What is the decision?

Atomic -> decompose large policy into smaller claim and group together (KAN)
One shot to create Graph (SMT)

### Data
Policy
Potential input
Targets

### MVP
Policy size? Breadth parrallel policy not a multi hop but scale problem

Input to output time LLM comparison vs symbolic
Accuracy

Explainability by default of symbolic design
Mapping to real policy if atomised correctly, solved issue

#### Pipeline
Give policy -> process policy -> symbolic system -> form or api -> output
Risk pipeline -> symbolic system -> processed policy

### Steps
#### Minimum data
2 policies synthetic

OR

2 real policies
search or generate data from LLMs and output

##### 1. Policy Generation
- Create or find graph or equations
- Have LLM render into NL
##### 2. IO isolation
- Find inputs and outputs within policy
##### 3. Atomisation
- Decompose NL into subclaims
- Group relevant subclaims
- Find subclaims relevant to input
- Formulate subclaim output and find nodes which take that as input
- Find all relevant subclaims to output

##### 4.1 Symbolic generator
- Take subclaim and input and convert to symbolic system
- Connect all sub equations into one big system

##### 4.2 Policy mapper (Maybe)
Purely UI thing

##### 5. DEMO
Create FE and BE to ingest and display
