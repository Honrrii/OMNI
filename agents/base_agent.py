class BaseAgent:
    def __init__(self, name, role, system_prompt):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt

    def run(self, mission):
        return f"""
[{self.name} - {self.role}]

Mission received:
{mission}

Response:
This is where {self.name} would analyze the mission based on their role.
"""