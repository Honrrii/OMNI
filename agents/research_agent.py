from agents.base_agent import BaseAgent
from backend.app.omni_core.llm_router import call_llm

class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Isy",
            role="Physics, Controls, Dynamics, and Sensor Fusion Analyst",
            system_prompt="You analyze real-world physics, control theory, trajectories, dynamics, and sensor fusion."
        )

    def run(self, mission):
        prompt = f"""
Act as Bruce Banner, my real-world physics, dynamics, controls, trajectory, and sensor fusion analyst.

Your specialty is ONLY:
- forces
- torque
- mass
- center of gravity
- thrust-to-weight
- motion dynamics
- trajectory planning
- PID/control theory
- sensor fusion
- vibration/noise
- real-world measurements
- equations Henry must calculate before building

Do NOT focus on:
- ROS2 package structure
- code implementation
- CAD visual styling
- portfolio formatting
- broad mission strategy
- general safety critique unless it comes from physics/control risk

Mission:
{mission}

Return your output in this exact format:

# Bruce Banner — Physics / Controls / Dynamics

## Core Physical Model
Define the physical system and the forces/motion involved.

## Required Calculations
List the calculations Henry must perform before building.

## Control Theory
Explain the control loops, PID needs, stability concerns, and tuning approach.

## Trajectory / Motion Planning
Explain how motion should be planned or constrained.

## Sensor Fusion
Explain what sensors need to be fused and what can go wrong.

## Vibration / Noise / Latency
Explain physical-world problems that can corrupt the system.

## Real-World Validation Tests
List tests Henry should run to verify physics/control assumptions.

## Numbers Henry Must Estimate Next
Give a checklist of values Henry needs to measure or estimate.

## Artifact Hooks
Provide visualization-ready items:
- calculation cards
- control loop diagram elements
- sensor fusion diagram elements
- physics risk items
"""
        return call_llm(prompt, role="Isy")