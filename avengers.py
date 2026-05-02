from agents.supervisor import SupervisorAgent
from datetime import datetime
import os


def save_report(report):
    os.makedirs("outputs", exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_path = f"outputs/mission_{timestamp}.md"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report)

    return file_path


def main():
    print("AI Avengers HQ")
    print("-" * 40)

    mission = input("Enter mission: ")

    supervisor = SupervisorAgent()
    report = supervisor.run_mission(mission)

    print(report)

    saved_file = save_report(report)
    print(f"\nSaved to: {saved_file}")


if __name__ == "__main__":
    main()