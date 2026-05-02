#!/bin/bash

HQ="$HOME/AI_Avengers_HQ"

case "$1" in
  assemble)
    echo "======================================"
    echo "        🛡️  AI AVENGERS HQ 🛡️"
    echo "======================================"
    echo ""
    echo "Avengers Assemble."
    echo ""

    echo "📌 Current Mission:"
    cat "$HQ/current_mission.md"
    echo ""

    echo "🧠 Agents:"
    cat "$HQ/agent_roles.md"
    echo ""

    echo "--------------------------------------"
    read -p "Enter a new task (or press Enter to skip): " TASK

    if [ -n "$TASK" ]; then
        echo ""
        echo "🧭 Routing Task..."
        echo ""

        TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
        MISSION_FILE="$HQ/missions/mission_$TIMESTAMP.md"

        mkdir -p "$HQ/missions"

cat > "$MISSION_FILE" <<EOF
# Mission Report

Date:
$TIMESTAMP

Task:
$TASK

## ChatGPT — Architect Prompt
Break this into steps:
$TASK

## Claude — Engineer Prompt
Write code / implementation for:
$TASK

## Gemini — Researcher Prompt
Research + summarize relevant info for:
$TASK

## Status
[ROUTED]
EOF

        echo "📝 Mission saved to:"
        echo "$MISSION_FILE"
        echo ""

        echo "📤 ChatGPT (Architect):"
        echo "Break this into steps:"
        echo "$TASK"
        echo ""

        echo "📤 Claude (Engineer):"
        echo "Write code / implementation for:"
        echo "$TASK"
        echo ""

        echo "📤 Gemini (Researcher):"
        echo "Research + summarize relevant info for:"
        echo "$TASK"
        echo ""

        echo "✅ Copy each section into the respective AI."
    fi
    ;;

    plan)
    read -p "Enter mission to plan: " TASK

    if [ -z "$TASK" ]; then
        echo "No task entered."
        exit 1
    fi

    TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
    PLAN_FILE="$HQ/missions/plan_$TIMESTAMP.md"

    mkdir -p "$HQ/missions"

    cat > "$PLAN_FILE" <<EOF
# Engineering Plan

Date:
$TIMESTAMP

Mission:
$TASK

## System Architecture (ChatGPT)
- Define system components
- Identify inputs/outputs
- Determine constraints

## Implementation Tasks (Claude)
- ROS2 nodes
- Control logic (PID / state machine)
- Hardware interface code

## Research Tasks (Gemini)
- Required components
- Datasheets
- Similar existing systems

## Execution Steps
1. Define architecture
2. Build simulation (Gazebo/ROS2)
3. Implement control logic
4. Test and iterate

## Status
[PLANNED]
EOF

    echo "🧠 Plan created:"
    echo "$PLAN_FILE"
    ;;

    open)
    LATEST=$(ls -t "$HQ/missions" | head -n 1)

    if [ -z "$LATEST" ]; then
        echo "No missions found."
        exit 1
    fi

    echo "📂 Opening latest mission:"
    echo "$LATEST"
    echo ""

    cat "$HQ/missions/$LATEST"
    ;;

    agents)
    LATEST=$(ls -t "$HQ/missions" | head -n 1)

    if [ -z "$LATEST" ]; then
        echo "No missions found."
        exit 1
    fi

    FILE="$HQ/missions/$LATEST"
    MISSION=$(awk '/Mission:/{getline; print}' "$FILE")

    echo "🤖 Copy-Ready Agent Prompts"
    echo "Source: $LATEST"
    echo ""

    echo "===== CHATGPT / SYSTEMS ARCHITECT ====="
    echo "Act as my robotics systems architect. Break this mission into architecture, milestones, risks, and next actions:"
    echo "$MISSION"
    echo ""

    echo "===== CLAUDE / ENGINEERING BUILDER ====="
    echo "Act as my robotics engineering implementation assistant. Create code structure, ROS2 node ideas, pseudocode, and implementation steps for:"
    echo "$MISSION"
    echo ""

    echo "===== GEMINI / MULTIMODAL RESEARCHER ====="
    echo "Act as my robotics research assistant. Identify datasheets, components, visual references, reports, and research questions needed for:"
    echo "$MISSION"
    ;;

  status)
    echo "📊 AI Avengers Status"
    echo "- HQ: Online"
    echo "- Location: $HQ"
    echo "- Environment: WSL Ubuntu 22.04"
    echo "- Chief Engineer: Henry"
    ;;

  mission)
    nano "$HQ/current_mission.md"
    ;;

  history)
    echo "📜 Mission History:"
    ls -lt "$HQ/missions"
    ;;  

  log)
    nano "$HQ/decisions_log.md"
    ;;

  *)
    echo "Usage:"
    echo "  ./avengers.sh assemble"
    echo "  ./avengers.sh status"
    echo "  ./avengers.sh mission"
    echo "  ./avengers.sh log"
    echo "  avengers history"
    echo "  avengers agents"
    ;;
esac