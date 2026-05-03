# OMNI Forge Roadmap

OMNI Forge is the long-term evolution of OMNI into an AI-assisted workshop operating system.

## Core Goal

Turn a natural-language engineering prompt into:

1. Structured engineering requirements
2. Design parameters
3. CAD generation plan
4. Validation report
5. Simulation plan
6. Fabrication preparation package
7. Human-approved execution workflow

## Safety Rule

OMNI may generate, validate, simulate, and prepare files automatically.

OMNI may not start physical fabrication, heat tools, move robots, or control workshop hardware without explicit human approval and safety checks.

## Phase 1: Digital Engineering Compiler

Input:

- User mission prompt

Output:

- Structured mission JSON
- Engineering validation report
- CAD parameter plan
- Artifact folder

## Phase 2: CAD Generation

Output:

- Fusion 360 scripts
- CadQuery scripts
- STL/STEP export plan

## Phase 3: Fabrication Preparation

Output:

- Slicer profile recommendation
- Print orientation notes
- Filament estimate
- G-code preparation plan

## Phase 4: Smart Workshop Integration

Integrations:

- Home Assistant
- MQTT
- OctoPrint
- Printer camera
- Emergency stop logic

## Phase 5: Semi-Autonomous Workshop

OMNI can queue and monitor jobs, but human approval remains required for physical execution.

## Current Progress

### Completed

- Level 1: Mission validation
- Level 2: CAD parameter planning
- Level 3: CadQuery script generation
- Level 4: CadQuery script execution and STEP/STL export

### Current Pipeline

Prompt → EngineeringMission → WorkshopPartSpec → ValidationReport → CADParameterPlan → CadQueryScript → STEP/STL Export

### Safety Status

- No printer control implemented.
- No physical fabrication started automatically.
- CAD scripts require generated file review.
- Human approval remains required before fabrication.

## Accountability Before Autonomy

OMNI is not being built to act first and explain later.

Before OMNI gains hands, it gets a black box.  
Before OMNI gains autonomy, it gets memory with consequences.  
Before OMNI controls anything physical, every action must answer five questions:

1. What did we believe?
2. What did we try?
3. What happened?
4. What did we learn?
5. What changes now?

OMNI becomes self-improving not because it is alive, but because it is accountable.

Every mission must preserve knowledge, punish bad assumptions, repeat what works, and institutionalize scars. A failed print, broken circuit, rejected design, simulation mismatch, or unsafe command is not wasted effort. It becomes engineering provenance.

**No mission dies as output. Every mission becomes provenance.**

Accountability is the difference between a genius lab assistant and a haunted toaster with Wi-Fi.