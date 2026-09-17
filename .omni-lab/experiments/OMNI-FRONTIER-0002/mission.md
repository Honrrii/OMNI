# OMNI Frontier Research Mission
## Component Intelligence v0.1 — Mechanical Assembly Knowledge Architecture

### Objective

Research and propose the architecture for OMNI Component Intelligence v0.1.

OMNI currently needs stronger understanding of how mechanical and mechatronic
components combine into coherent, manufacturable assemblies before detailed CAD
generation occurs.

The goal of this research shift is NOT to implement the subsystem.

The goal is for Claude and Codex to critically investigate, challenge, refine,
and converge on an architecture that OMNI can later implement and evaluate
through TestCube.

The proposed architecture should enable OMNI to reason about:

- what components exist in an assembly
- how components mechanically interface
- whether interfaces are compatible
- which supporting components are required
- what engineering information is missing or unknown
- what loads and constraints flow through an assembly
- what CAD features must exist for the assembly to be physically realizable
- why each conclusion was reached
- where each engineering fact or rule came from


## Initial Component Families

Focus deeply on these foundational families:

1. Fasteners and joining elements
   - bolts
   - nuts
   - screws
   - studs
   - washers
   - pins
   - dowels
   - circlips / snap rings
   - threaded inserts

2. Shafts and rotary members
   - shafts
   - axles
   - spindles
   - keyed shafts
   - splined interfaces

3. Bearings and support
   - ball bearings
   - roller bearings
   - tapered bearings
   - bushings
   - sleeve bearings

4. Couplings and torque-transfer interfaces
   - rigid couplings
   - flexible couplings
   - shaft couplings
   - universal joints

5. Rotary transmission
   - gears
   - pulleys
   - sprockets
   - belts
   - chains

6. Motors and rotary actuators
   - DC motors
   - BLDC motors
   - stepper motors
   - servomotors
   - gearmotors

7. Linear motion
   - leadscrews
   - ball screws
   - linear rails
   - guide blocks
   - carriages

8. Structural members
   - plates
   - sheets
   - tubes
   - beams
   - angles
   - extrusion / profile members


## Core Research Question

What representation and reasoning architecture should OMNI use so that
components are not merely catalog entries, but engineering objects that can be
combined into validated mechanical assemblies?

Investigate whether the strongest architecture should use:

- typed component records
- typed mechanical interfaces
- relationship / knowledge graphs
- deterministic compatibility rules
- reusable assembly patterns
- constraint propagation
- CAD obligation generation
- provenance-aware engineering facts

or an alternative architecture if evidence suggests a better design.


## Required Capabilities

The eventual system should be able to represent, where applicable:

### Identity

- component family
- subtype
- generic vs manufacturer-specific identity
- applicable standards
- source provenance

### Geometry

- dimensions
- envelope
- shaft diameters
- bores
- mounting holes
- bolt circles
- threads
- shoulders
- grooves
- keyways
- splines
- flange geometry

### Mechanical properties

- torque capability
- rotational speed
- radial load
- axial load
- stiffness
- backlash
- friction
- allowable misalignment
- duty limits
- thermal/environmental limits where relevant

### Interfaces

Examples include:

- shaft_to_bearing
- shaft_to_coupling
- shaft_to_gear
- bearing_to_housing
- threaded_joint
- motor_to_mount
- motor_to_coupling
- linear_rail_to_structure
- pulley_to_belt
- sprocket_to_chain

Interfaces should support machine-readable reasoning about:

- participants
- mating geometry
- dimensions
- tolerance/clearance requirements
- alignment
- retention
- load transfer
- compatibility
- CAD features required on each side

### Assembly requirements

Examples:

- axial retention
- radial support
- lubrication
- preload
- alignment
- tensioning
- mounting
- service access
- tool access
- installation direction
- companion components

### CAD obligations

The architecture should eventually allow OMNI to derive requirements such as:

Bearing BRG-001 requires:

shaft:
- bearing seat
- shoulder or equivalent axial locating feature
- retaining feature when required

housing:
- bearing bore/pocket
- outer-race retention where required
- assembly access

The research should determine where these obligations belong architecturally:
component definitions, interface definitions, assembly rules, derived
constraints, or another representation.


## Assembly Patterns

Investigate a reusable assembly-pattern representation.

Initial patterns of interest:

### Supported shaft

shaft
 -> bearing support
 -> structural housing
 -> retention

### Motor-to-shaft

motor
 -> coupling
 -> shaft
 -> bearings
 -> driven load

### Motor-to-leadscrew linear stage

motor
 -> coupling
 -> leadscrew
 -> fixed/floating support
 -> nut
 -> carriage
 -> linear guide

### Belt drive

motor
 -> pulley
 -> belt
 -> driven pulley
 -> shaft
 -> bearings
 -> tensioning mechanism

### Geared output

motor
 -> gear reduction
 -> output shaft
 -> bearings
 -> driven load


## Deterministic Reasoning

The architecture must distinguish at least:

PASS
WARN
FAIL
UNKNOWN

UNKNOWN is a valid and important engineering state.

The system must never silently transform unknown information into PASS.

Examples:

bearing bore != shaft seat diameter
    -> FAIL

bearing speed rating known and sufficient
    -> PASS

bearing speed rating unavailable
    -> UNKNOWN

rotating shaft has no support relationship
    -> FAIL or an explicitly justified warning depending on context

belt drive has no tensioning strategy
    -> finding requiring resolution


## Provenance

Engineering knowledge must distinguish sources such as:

STANDARD
MANUFACTURER
HANDBOOK
OMNI_VALIDATED
OMNI_HEURISTIC
USER_PROVIDED

An AI-generated assertion must not automatically become trusted engineering
knowledge simply because Claude and Codex agree.

Research how provenance should attach to:

- components
- properties
- rules
- interfaces
- relationships
- derived findings
- assembly patterns


## Relationship to OMNI Agents

Consider how this subsystem should eventually interact with:

Echo
- converts mission requirements into structured engineering requirements

Vega
- proposes conceptual architectures and component families

Korva
- reasons about motors, sensors, electronics, actuation and integration

Isy
- evaluates physics, loads and feasibility

Oli
- consumes component/interface/CAD obligations to generate detailed geometry

Pluto
- critiques architecture and failure modes

QaZ
- validates resulting component and assembly constraints

Do not redesign these agents unless necessary to define a clean integration
contract.


## Relationship to CAD

The research should explicitly address the boundary between:

component knowledge

and

CAD generation.

Oli should not have to invent missing mechanical relationships while drawing.

Ideally:

mission requirements
 -> functional decomposition
 -> component architecture
 -> interface graph
 -> compatibility analysis
 -> engineering calculations
 -> CAD obligations
 -> Oli CAD generation
 -> QaZ validation

Determine whether that flow is appropriate or propose a stronger alternative.


## Relationship to TestCube / Super-Build

The architecture should support future learning from validated engineering
experience.

Example:

Candidate assembly A:
- immediate tests pass
- later produces alignment and maintenance problems

Candidate assembly B:
- slightly more complex initially
- survives later design changes with fewer regressions

OMNI should eventually be able to retain evidence about those outcomes without
allowing model opinion alone to become engineering truth.

Research what identifiers/provenance would make this possible later.

Do NOT implement machine learning in this mission.


## Scale

Do not design a one-off structure that only handles the eight seed families.

The architecture should plausibly extend later to:

- seals and gaskets
- springs and dampers
- brakes and clutches
- pneumatics
- hydraulics
- hinges and latches
- wheels and casters
- sensors
- electrical connectors
- wire routing
- thermal components
- enclosure hardware
- jigs and fixtures
- precision locating hardware

At the same time, avoid premature complexity.

Component Intelligence v0.1 should be implementable and testable.


## Research Constraints

Do not modify repository files.

Do not commit, push, merge, or change git state.

Do not invoke another AI provider.

Do not invent manufacturer specifications.

Do not invent tolerance values and present them as fact.

Do not treat semantic similarity as mechanical compatibility.

Do not treat Claude/Codex agreement as engineering validation.

Use repository inspection and static analysis where useful.

Clearly distinguish:

- known facts
- architectural proposals
- assumptions
- unresolved questions
- evidence
- recommendations


## Desired Conclusion

By the end of the research shift, produce a defensible recommendation for:

1. the core data model
2. the interface model
3. the relationship representation
4. the compatibility/rule engine
5. assembly-pattern representation
6. CAD-requirement generation
7. provenance representation
8. UNKNOWN/fail-closed semantics
9. proposed module boundaries inside OMNI
10. a small v0.1 implementation scope suitable for a TestCube trial

Prefer an architecture that is:

- deterministic where engineering correctness can be checked deterministically
- inspectable
- extensible
- provenance-aware
- easy to test
- compatible with OMNI's existing architecture
- resistant to fabricated engineering knowledge

The final recommendation should contain enough specificity that the same frozen
specification could later be handed independently to Claude and Codex as a
TestCube implementation task.
