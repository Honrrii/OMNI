# OMNI — Multi-Agent AI Robotics Builder

OMNI is a multi-agent AI robotics engineering system that converts natural-language project ideas into structured robotics artifacts, ROS2 packages, validation reports, and Fusion 360 CAD concept scripts.

Instead of only returning a text response, OMNI acts like an early-stage engineering command center. It interprets a mission, expands the requirements, coordinates specialist agents, generates project files, validates build outputs, and exports artifacts that can be tested, reviewed, or developed further.

<p align="center">
  <img src="frontend/src/assets/hero.png" alt="OMNI Command Interface" width="850"/>
</p>

---

## Why OMNI Matters

Personal robotics and mechatronics projects are difficult because they require several disciplines to work together at the same time: software, mechanical design, electronics, controls, simulation, documentation, and validation. A simple idea like “build a drone,” “design a rover,” or “make a robotic desk assistant” quickly turns into many smaller engineering tasks.

OMNI was built to speed up that early development process.

The goal of OMNI is to help a builder move from a rough idea to a structured engineering foundation faster. Instead of manually starting from an empty folder, OMNI can help generate project structure, ROS2 package files, CAD concept scripts, validation plans, test checklists, and documentation that can be reviewed and improved.

OMNI is especially useful for personal mechatronics development because it helps organize the messy early stage of a project. It gives the user a starting point for:

- Defining system requirements
- Planning sensors, actuators, and control logic
- Creating ROS2 nodes, topics, launch files, and package structure
- Generating CAD concept scripts for Fusion 360 or related design workflows
- Producing validation reports and safety notes
- Creating reviewable artifacts before physical hardware is built
- Reducing the time between idea, prototype plan, and testable output

OMNI does not replace engineering judgment. Its purpose is to accelerate the design and validation workflow so a human builder can spend more time testing, improving, and understanding the system.

---

## Project Vision

OMNI is designed to become a personal AI-assisted mechatronics lab.

The long-term vision is to let a user describe a robotics or hardware idea in natural language and receive a full engineering starting package. That package may include ROS2 software, CAD design logic, validation steps, simulation planning, wiring assumptions, risk notes, and artifact manifests.

The project explores a central question:

> How can AI agents help individuals build, validate, and iterate on complex robotics and mechatronics projects faster?

For students, hobbyists, and early-stage engineers, OMNI can act as a bridge between an idea and a buildable prototype. It creates momentum by giving the user a structured first version instead of forcing them to start every subsystem from scratch.

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
- ROS2 simulation status monitoring from the dashboard
- CAD artifact pipeline for generated engineering outputs

---

## Core Workflow

OMNI follows a mission-based workflow.

A user provides a prompt such as:

```text
Design a ROS2-based robotic desk assistant with a Raspberry Pi, camera module, servo-mounted sensor head, IMU, productivity logging, Fusion 360 enclosure concept, risk matrix, and validation checklist.