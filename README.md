# OMNI — Multi-Agent AI Robotics Builder

OMNI is a multi-agent AI robotics system that converts natural-language engineering missions into structured ROS2 project artifacts, including package files, launch scripts, documentation, and validation tools.

## Overview

OMNI is designed as an AI-assisted robotics development workflow. Instead of producing only a single text response, OMNI coordinates multiple specialized agents to interpret a mission, generate robotics software artifacts, critique the result, and prepare outputs that can be tested or expanded.

The long-term goal is to build an engineering assistant capable of helping with robotics, drones, ROS2 systems, embedded workflows, and future CAD/Fusion 360 concept generation.

## Key Features

- Multi-agent supervisor architecture
- Natural-language robotics mission input
- ROS2 package and node generation
- Artifact synthesis for project outputs
- Validation-focused workflow
- FastAPI backend
- React frontend
- Expandable agent roles for research, robotics, code, critique, and validation

## Tech Stack

- Python
- FastAPI
- React
- ROS2 Humble
- Bash
- Git/GitHub
- Linux/WSL2
- NVIDIA / OpenAI / Gemini API-ready architecture

## Project Structure

```text
OMNI/
├── agents/              # Multi-agent system logic
├── backend/app/         # FastAPI backend and robotics generation tools
├── frontend/            # React frontend interface
├── knowledge/           # ROS2 examples and pattern references
├── memory/              # Project memory system
├── avengers.py          # Command entry point
├── avengers.sh          # Shell launcher
└── README.md
