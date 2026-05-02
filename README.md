# OMNI — Multi-Agent AI Robotics Builder

OMNI is a multi-agent AI robotics engineering system that converts natural-language project ideas into structured robotics artifacts, ROS2 packages, validation reports, and Fusion 360 CAD concept scripts.

Instead of only returning a text response, OMNI acts like an early-stage engineering command center: it interprets a mission, expands the requirements, coordinates specialist agents, generates project files, validates build outputs, and exports artifacts that can be tested or developed further.

---

## Current Status

OMNI currently supports:

- Natural-language mission input
- Echo quick-idea interpretation
- Multi-agent mission synthesis
- ROS2 Python package generation
- ROS2 node, topic, launch, config, docs, and test script export
- Automatic `colcon build` validation
- ROS2 launch/topic smoke testing
- Build report generation
- Fusion 360 Python script generation
- CAD pattern context for rover, drone, enclosure, and robotics concepts
- React frontend for mission control and artifact viewing
- FastAPI backend for mission execution and export workflows

---

## Demo Screenshots

> Add screenshots to the `assets/` folder and uncomment/update these paths.

![OMNI Command Interface](assets/omni-ui-command.png)

![ROS2 Build Verification](assets/build-verified-card.png)

![Fusion 360 Rover Concept](assets/fusion-rover-concept.png)

---

## Overview

OMNI is designed as an AI-assisted robotics development workflow. The system takes a rough engineering idea, expands it into a structured mission, and generates practical project artifacts that can be inspected, built, validated, and improved.

A user can submit a prompt such as:

```text
Yo Echo, build a ROS2 rover with camera, motor control, telemetry, URDF, RViz, config YAML, topic contracts, launch files, a topic smoke test script, and a Fusion 360 CAD concept for the rover chassis.
