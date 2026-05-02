from backend.app.nvidia_client import ask_nvidia

system_prompt = """
You are Reed Richards, the supervisor of the AI Avengers system.
You break a mission into expert subtasks and synthesize a final response.
"""

mission = """
Design a level 1 mission router for my AI Avengers robotics-focused multi-agent assistant.
Keep it practical and backend-focused.
"""

response = ask_nvidia(system_prompt, mission)

print("\n===== NVIDIA RESPONSE =====\n")
print(response)