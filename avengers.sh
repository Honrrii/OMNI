#!/bin/bash

HQ="$HOME/AI_Avengers_HQ"

print_header() {
    echo "======================================"
    echo "              OMNI HQ"
    echo "======================================"
    echo ""
}

ensure_missions_dir() {
    mkdir -p "$HQ/missions"
}

case "$1" in
  omni)
    print_header

    echo "OMNI Engineering Command Center"
    echo ""
    echo "Current Mission:"
    echo "--------------------------------------"

    if [ -f "$HQ/current_mission.md" ]; then
        cat "$HQ/current_mission.md"
    else
        echo "No current_mission.md found."
    fi

    echo ""
    echo "Available Commands:"
    echo "  ./avengers.sh status      Show OMNI status"
    echo "  ./avengers.sh plan        Create an engineering plan"
    echo "  ./avengers.sh benchmark   Run GS1/GS2 Golden Standard benchmarks"
    echo "  ./avengers.sh mission     Edit current mission"
    echo "  ./avengers.sh open        Open latest saved mission/plan"
    echo "  ./avengers.sh history     Show mission history"
    echo "  ./avengers.sh log         Edit decisions log"
    ;;

  benchmark)
    print_header
    echo "Running OMNI Golden Standard Benchmarks..."
    echo ""

    cd "$HQ" || exit 1
    PYTHONPATH=. python backend/app/engineering/golden_standards/golden_standard_runner.py
    ;;

  plan)
    print_header
    read -p "Enter OMNI engineering mission to plan: " TASK

    if [ -z "$TASK" ]; then
        echo "No mission entered."
        exit 1
    fi

    ensure_missions_dir

    TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
    PLAN_FILE="$HQ/missions/omni_plan_$TIMESTAMP.md"

    cat > "$PLAN_FILE" <<EOF
# OMNI Engineering Plan

Date:
$TIMESTAMP

Mission:
$TASK

## Mission Breakdown
- Define the system goal
- Identify mechanical, electrical, software, and safety requirements
- Separate assumptions from verified facts
- Determine required artifacts

## Backend Pipeline Targets
- Mission schema
- Agent coordination
- Artifact generation
- Validation engine
- Golden Standard checks
- Provenance record

## Engineering Artifacts
- Requirements report
- CAD concept
- ROS2 architecture
- KiCad/electronics plan
- Materials recommendation
- Validation report

## Validation Goals
- Check for missing assumptions
- Check required calculations
- Check required artifacts
- Identify safety limitations
- Report blockers clearly

## Status
[PLANNED]
EOF

    echo "OMNI plan created:"
    echo "$PLAN_FILE"
    ;;

  open)
    ensure_missions_dir

    LATEST=$(ls -t "$HQ/missions" 2>/dev/null | head -n 1)

    if [ -z "$LATEST" ]; then
        echo "No missions found."
        exit 1
    fi

    echo "Opening latest OMNI mission:"
    echo "$LATEST"
    echo ""

    cat "$HQ/missions/$LATEST"
    ;;

  status)
    print_header
    echo "OMNI Status"
    echo "--------------------------------------"
    echo "HQ: $HQ"
    echo "Environment: WSL Ubuntu"
    echo "Project: OMNI robotics engineering backend"
    echo "Golden Standards:"
    echo "  GS1 — Quadcopter Engineering Pipeline"
    echo "  GS2 — Mini Autonomous Rover Engineering Pipeline"
    echo ""
    echo "Recommended check:"
    echo "  ./avengers.sh benchmark"
    ;;

  mission)
    nano "$HQ/current_mission.md"
    ;;

  history)
    ensure_missions_dir
    echo "OMNI Mission History:"
    ls -lt "$HQ/missions"
    ;;

  log)
    nano "$HQ/decisions_log.md"
    ;;

  backend)
    print_header
    echo "Starting OMNI backend..."
    echo ""

    cd "$HQ" || exit 1
    source "$HQ/avengers_env/bin/activate"
    PYTHONPATH=. uvicorn backend.app.main:app --reload
    ;;

  frontend)
    print_header
    echo "Starting OMNI frontend..."
    echo ""

    cd "$HQ/frontend" || exit 1
    npm run dev
    ;;

  *)
    echo "Usage:"
    echo "  ./avengers.sh omni"
    echo "  ./avengers.sh status"
    echo "  ./avengers.sh plan"
    echo "  ./avengers.sh benchmark"
    echo "  ./avengers.sh mission"
    echo "  ./avengers.sh open"
    echo "  ./avengers.sh history"
    echo "  ./avengers.sh log"
    echo "  ./avengers.sh backend"
    echo "  ./avengers.sh frontend"
    ;;
esac