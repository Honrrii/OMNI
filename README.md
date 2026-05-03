# OMNI — Multi-Agent AI Robotics Builder

OMNI is a multi-agent AI robotics engineering system that converts natural-language project ideas into structured robotics artifacts, ROS2 packages, validation reports, and Fusion 360 CAD concept scripts.

Instead of only returning a text response, OMNI acts like an early-stage engineering command center. It interprets a mission, expands the requirements, coordinates specialist agents, generates project files, validates build outputs, and exports artifacts that can be tested, reviewed, or developed further.

---

## OMNI Dashboard Preview

<p align="center">
  <img src="docs/screenshots/omni-command-screen.png" alt="OMNI Command Screen" width="900"/>
</p>

OMNI provides a mission-control style interface where users can submit full engineering missions or use Echo to translate rough ideas into structured robotics prompts.

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

## ROS2 Mission Control

<p align="center">
  <img src="docs/screenshots/ros2-mission-control.png" alt="ROS2 Mission Control" width="900"/>
</p>

The ROS2 Mission Control panel is a read-only dashboard for monitoring simulation-related system status. It is designed to help track ROS2 nodes, topics, RViz, Gazebo, rosbridge, and Foxglove bridge availability from inside the OMNI interface.

This page does **not** directly control physical robots. It is intended for monitoring, debugging, and simulation workflow visibility.

---

## Workshop Artifact Pipeline

<p align="center">
  <img src="docs/screenshots/workshop-artifact-pipeline.png" alt="Workshop Artifact Pipeline" width="900"/>
</p>

The Workshop Artifact Pipeline converts an engineering prompt into structured build artifacts. The goal is to move from a rough idea into reviewable engineering outputs such as validation data, CAD parameters, generated CadQuery scripts, exported STEP/STL files, and a human-review artifact manifest.

---

## Overview

OMNI is designed as an AI-assisted robotics development workflow.

The system takes a rough engineering idea, expands it into a structured mission, and generates practical project artifacts that can be inspected, built, validated, and improved.

A user can submit a prompt such as:

```text
Design a ROS2-based robotic desk assistant with a Raspberry Pi, camera module, servo-mounted sensor head, IMU, productivity logging, Fusion 360 enclosure concept, risk matrix, and validation checklist.