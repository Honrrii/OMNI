"""
backend/app/knowledge/morphology_pattern_library.py

OMNI Morphology Engine — Pattern Library
=========================================
Stores all known body-plan patterns.
Each pattern is a template that the morphology_planner uses
to resolve a mission text into a structured MorphologyPlan.

To add a new robot type:
  1. Add its trigger keywords to PATTERN_KEYWORDS.
  2. Add a builder function named _build_<pattern_name>().
  3. Register it in PATTERN_REGISTRY.

The planner scores patterns by keyword hit count and picks the winner.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable

from backend.app.engineering.design_intent_schema import (
    MorphologyPlan,
    BodyPlan,
    ElectronicsIntent,
    ROS2Intent,
    ProjectFamily,
    LocomotionType,
    ScaleClass,
    MorphologyConfidence,
)


# ---------------------------------------------------------------------------
# Pattern keyword registry
# ---------------------------------------------------------------------------
# Each entry maps a pattern name to a list of trigger keywords.
# The planner tokenizes the mission text and scores each pattern.
# Higher hit count = stronger match.

PATTERN_KEYWORDS: dict[str, list[str]] = {

    "segmented_insect_robot": [
        "insect", "hexapod", "six-legged", "six legged", "segmented",
        "bio-inspired", "bio inspired", "bioinspired", "insect-inspired",
        "insect inspired", "ant", "beetle", "arthropod", "appendage",
        "thorax", "abdomen", "head pod", "sensor pod", "exoskeleton",
        "six legs", "6 legs", "legged robot", "walker",
    ],

    "wheeled_rover": [
        "rover", "wheeled", "wheel", "differential drive", "skid steer",
        "ground vehicle", "ugv", "unmanned ground", "four wheel",
        "six wheel", "mobile robot", "autonomous vehicle", "car-like",
        "ackermann", "omniwheel", "omnidirectional wheel",
    ],

    "quadcopter_drone": [
        "quadcopter", "quad", "drone", "multirotor", "quadrotor",
        "four rotor", "4 rotor", "fpv", "uav rotor", "copter",
        "aerial", "hovering", "propeller", "prop", "flight controller",
        "esc", "brushless motor", "lipo", "px4", "ardupilot",
    ],

    "fixed_wing_uav": [
        "fixed wing", "fixed-wing", "airplane", "plane", "fuselage",
        "wing", "empennage", "aileron", "elevator", "rudder",
        "tail", "glider", "uav wing", "rc plane", "vtail",
        "pusher", "tractor prop", "wingspan", "control surface",
        "aerodynamic", "lift", "drag", "camber", "airfoil",
    ],

    "vtol_uav": [
        "vtol", "vertical takeoff", "vertical take-off", "hybrid uav",
        "tiltrotor", "tilt rotor", "tailsitter", "tail sitter",
        "fixed wing with rotors", "transition", "cruise and hover",
    ],

    "robot_arm": [
        "robot arm", "robotic arm", "manipulator", "serial arm",
        "6dof", "6 dof", "degrees of freedom", "end effector",
        "gripper", "wrist", "elbow", "shoulder joint", "revolute",
        "prismatic joint", "reach", "payload arm", "cobot",
    ],

    "sensor_module": [
        "sensor module", "sensor node", "sensor hub", "breakout board",
        "data logger", "monitoring node", "environmental sensor",
        "standalone sensor", "fixed sensor", "stationary", "no locomotion",
        "embedded sensor", "iot sensor", "edge sensor",
    ],

    "humanoid": [
        "humanoid", "biped", "two-legged", "two legged", "bipedal",
        "anthropomorphic", "walking robot", "human-like", "torso",
        "pelvis", "leg link", "ankle", "knee joint", "hip joint",
        "arm swing", "balance", "zmp",
    ],

    "aquatic_robot": [
        "aquatic", "underwater", "auv", "rov", "submarine",
        "water", "buoyancy", "thruster", "propeller underwater",
        "waterproof", "pressure hull", "ocean", "marine",
        "torpedo", "submerged",
    ],
}

# Scale trigger keywords
SCALE_KEYWORDS: dict[ScaleClass, list[str]] = {
    ScaleClass.NANO:       ["nano", "tiny", "microscale", "micro-scale"],
    ScaleClass.MICRO:      ["micro", "small", "compact", "miniature"],
    ScaleClass.PALM_SIZED: ["palm-sized", "palm sized", "handheld", "hand-sized"],
    ScaleClass.TABLETOP:   ["tabletop", "desktop", "bench", "mid-sized"],
    ScaleClass.FIELD:      ["field", "outdoor", "terrain", "large scale"],
    ScaleClass.LARGE:      ["full-size", "full size", "industrial", "human-scale"],
}


# ---------------------------------------------------------------------------
# Pattern builder functions
# ---------------------------------------------------------------------------
# Each builder returns a fully populated MorphologyPlan.
# The planner calls the winning builder and injects matched keywords + confidence.

def _build_segmented_insect_robot() -> MorphologyPlan:
    return MorphologyPlan(
        morphology_id   = "segmented_insect_robot",
        project_family  = ProjectFamily.BIO_INSPIRED_GROUND,
        display_name    = "Segmented Insect-Inspired Ground Robot",
        description     = (
            "A bio-inspired legged ground robot with a three-segment body plan "
            "(head, thorax, abdomen), six appendage mounts, and modular sensor pod."
        ),
        locomotion_type = LocomotionType.LEGGED,
        body_plan = BodyPlan(
            segments = [
                "head_sensor_pod",
                "thorax_electronics_core",
                "abdomen_battery_module",
            ],
            required_features = [
                "three distinct body segments (head, thorax, abdomen)",
                "six appendage mounting points",
                "front camera or sensor pod on head segment",
                "internal electronics bay in thorax",
                "battery bay in abdomen",
                "segmented external shell",
            ],
            avoid_features = [
                "quadcopter cross frame",
                "four exposed drone arms",
                "generic circular drone body",
                "fixed wing fuselage shape",
                "rover chassis rail",
            ],
            mounting_points = [
                "left_front_appendage_mount",
                "right_front_appendage_mount",
                "left_mid_appendage_mount",
                "right_mid_appendage_mount",
                "left_rear_appendage_mount",
                "right_rear_appendage_mount",
                "head_camera_mount",
            ],
        ),
        electronics_intent = ElectronicsIntent(
            primary_pcb_location = "thorax_electronics_core",
            battery_location     = "abdomen_battery_module",
            sensor_connectors    = [
                "head_camera_connector",
                "head_imu_connector",
            ],
            actuator_connectors  = [
                "thorax_servo_bank_left",
                "thorax_servo_bank_right",
                "abdomen_rear_servo_bank",
            ],
            power_rails = [
                "5V logic rail",
                "7.4V servo rail",
                "3.3V sensor rail",
            ],
        ),
        ros2_intent = ROS2Intent(
            base_frame = "base_link",
            recommended_frames = [
                "base_link",
                "head_sensor_pod_link",
                "thorax_link",
                "abdomen_link",
                "left_front_appendage_link",
                "right_front_appendage_link",
                "left_mid_appendage_link",
                "right_mid_appendage_link",
                "left_rear_appendage_link",
                "right_rear_appendage_link",
            ],
            recommended_nodes = [
                "locomotion_controller",
                "head_camera_node",
                "imu_node",
                "battery_monitor",
                "appendage_controller",
                "sensor_fusion_node",
            ],
            recommended_topics = [
                "/cmd_vel",
                "/head_camera/image_raw",
                "/imu/data",
                "/battery_state",
                "/appendage/joint_states",
                "/appendage/joint_commands",
            ],
        ),
    )


def _build_wheeled_rover() -> MorphologyPlan:
    return MorphologyPlan(
        morphology_id   = "wheeled_rover",
        project_family  = ProjectFamily.WHEELED_ROVER,
        display_name    = "Wheeled Autonomous Rover",
        description     = (
            "A ground-based wheeled robot with a chassis deck, "
            "electronics bay, sensor mast, and motor drive system."
        ),
        locomotion_type = LocomotionType.WHEELED,
        body_plan = BodyPlan(
            segments = [
                "chassis_base",
                "electronics_deck",
                "sensor_mast",
                "payload_bay",
            ],
            required_features = [
                "chassis rail or frame",
                "wheel mounts (minimum 4)",
                "motor/gearbox mounting points",
                "electronics deck plate",
                "sensor mast or front sensor bracket",
                "battery bay in chassis",
            ],
            avoid_features = [
                "body segments (head/thorax/abdomen)",
                "appendage mounts",
                "rotor arms",
                "wing structure",
            ],
            mounting_points = [
                "front_left_wheel_hub",
                "front_right_wheel_hub",
                "rear_left_wheel_hub",
                "rear_right_wheel_hub",
                "sensor_mast_base",
                "payload_rail_front",
                "payload_rail_rear",
            ],
        ),
        electronics_intent = ElectronicsIntent(
            primary_pcb_location = "electronics_deck",
            battery_location     = "chassis_base",
            sensor_connectors    = [
                "sensor_mast_camera_connector",
                "lidar_connector",
                "imu_connector",
            ],
            actuator_connectors  = [
                "left_motor_driver_connector",
                "right_motor_driver_connector",
            ],
            power_rails = [
                "12V motor rail",
                "5V logic rail",
                "3.3V sensor rail",
            ],
        ),
        ros2_intent = ROS2Intent(
            base_frame = "base_link",
            recommended_frames = [
                "base_link",
                "chassis_link",
                "front_left_wheel_link",
                "front_right_wheel_link",
                "rear_left_wheel_link",
                "rear_right_wheel_link",
                "sensor_mast_link",
                "camera_link",
                "lidar_link",
            ],
            recommended_nodes = [
                "differential_drive_controller",
                "camera_node",
                "lidar_node",
                "imu_node",
                "battery_monitor",
                "navigation_node",
            ],
            recommended_topics = [
                "/cmd_vel",
                "/odom",
                "/camera/image_raw",
                "/scan",
                "/imu/data",
                "/battery_state",
            ],
        ),
    )


def _build_quadcopter_drone() -> MorphologyPlan:
    return MorphologyPlan(
        morphology_id   = "quadcopter_drone",
        project_family  = ProjectFamily.QUADCOPTER_DRONE,
        display_name    = "Quadcopter Multirotor Drone",
        description     = (
            "A four-arm multirotor UAV with central electronics frame, "
            "four brushless motor mounts, and payload bay."
        ),
        locomotion_type = LocomotionType.ROTARY_WING,
        body_plan = BodyPlan(
            segments = [
                "central_frame",
                "arm_front_left",
                "arm_front_right",
                "arm_rear_left",
                "arm_rear_right",
                "payload_bay",
                "landing_gear",
            ],
            required_features = [
                "four rotor arm extensions from central frame",
                "motor mount at each arm tip",
                "central electronics bay",
                "flight controller mount",
                "ESC mounting points",
                "battery tray on underside",
                "landing gear or skid legs",
            ],
            avoid_features = [
                "segmented insect body",
                "appendage mounts",
                "wing structure",
                "fuselage tube",
                "wheel mounts",
            ],
            mounting_points = [
                "front_left_motor_mount",
                "front_right_motor_mount",
                "rear_left_motor_mount",
                "rear_right_motor_mount",
                "payload_mount_center",
                "camera_gimbal_mount",
            ],
        ),
        electronics_intent = ElectronicsIntent(
            primary_pcb_location = "central_frame",
            battery_location     = "payload_bay",
            sensor_connectors    = [
                "gps_connector",
                "barometer_connector",
                "camera_connector",
            ],
            actuator_connectors  = [
                "esc_front_left",
                "esc_front_right",
                "esc_rear_left",
                "esc_rear_right",
            ],
            power_rails = [
                "14.8V LiPo main rail",
                "5V BEC logic rail",
                "3.3V sensor rail",
            ],
        ),
        ros2_intent = ROS2Intent(
            base_frame = "base_link",
            recommended_frames = [
                "base_link",
                "imu_link",
                "camera_link",
                "gps_link",
                "front_left_motor_link",
                "front_right_motor_link",
                "rear_left_motor_link",
                "rear_right_motor_link",
            ],
            recommended_nodes = [
                "flight_controller_node",
                "motor_mixing_node",
                "gps_node",
                "imu_node",
                "camera_node",
                "battery_monitor",
                "telemetry_node",
            ],
            recommended_topics = [
                "/cmd_vel",
                "/mavros/state",
                "/mavros/imu/data",
                "/mavros/global_position/global",
                "/camera/image_raw",
                "/battery_state",
            ],
        ),
    )


def _build_fixed_wing_uav() -> MorphologyPlan:
    return MorphologyPlan(
        morphology_id   = "fixed_wing_uav",
        project_family  = ProjectFamily.FIXED_WING_UAV,
        display_name    = "Fixed-Wing UAV",
        description     = (
            "An aerodynamic fixed-wing UAV with fuselage, wings, empennage, "
            "and control surfaces (aileron, elevator, rudder)."
        ),
        locomotion_type = LocomotionType.FIXED_WING,
        body_plan = BodyPlan(
            segments = [
                "nose_section",
                "fuselage",
                "port_wing",
                "starboard_wing",
                "empennage",
                "vertical_stabilizer",
                "horizontal_stabilizer",
            ],
            required_features = [
                "aerodynamic fuselage tube or shell",
                "port and starboard wing panels",
                "empennage (tail assembly)",
                "aileron control surfaces on wings",
                "elevator control surface on horizontal stabilizer",
                "rudder on vertical stabilizer",
                "propulsion motor/prop mount on nose or tail",
                "electronics bay in fuselage",
                "battery bay in fuselage",
                "wing attachment ribs or spars",
            ],
            avoid_features = [
                "multirotor arm layout",
                "quad rotor cross frame",
                "segmented insect body",
                "appendage mounts",
                "wheel-chassis rail",
            ],
            mounting_points = [
                "motor_firewall_mount",
                "port_wing_spar_root",
                "starboard_wing_spar_root",
                "empennage_boom_attach",
                "aileron_hinge_port",
                "aileron_hinge_starboard",
                "elevator_hinge",
                "rudder_hinge",
                "landing_gear_mount",
            ],
        ),
        electronics_intent = ElectronicsIntent(
            primary_pcb_location = "fuselage",
            battery_location     = "fuselage",
            sensor_connectors    = [
                "nose_pitot_connector",
                "nose_camera_connector",
                "gps_connector",
                "airspeed_connector",
            ],
            actuator_connectors  = [
                "motor_esc_connector",
                "aileron_servo_port",
                "aileron_servo_starboard",
                "elevator_servo_connector",
                "rudder_servo_connector",
            ],
            power_rails = [
                "11.1V LiPo main rail",
                "5V BEC servo rail",
                "3.3V avionics rail",
            ],
        ),
        ros2_intent = ROS2Intent(
            base_frame = "base_link",
            recommended_frames = [
                "base_link",
                "fuselage_link",
                "port_wing_link",
                "starboard_wing_link",
                "empennage_link",
                "camera_link",
                "gps_link",
                "pitot_link",
            ],
            recommended_nodes = [
                "autopilot_node",
                "airspeed_node",
                "gps_node",
                "imu_node",
                "camera_node",
                "control_surface_node",
                "battery_monitor",
                "telemetry_node",
            ],
            recommended_topics = [
                "/cmd_vel",
                "/airspeed",
                "/altitude",
                "/mavros/imu/data",
                "/mavros/global_position/global",
                "/camera/image_raw",
                "/battery_state",
                "/control_surfaces/commands",
            ],
        ),
    )


def _build_vtol_uav() -> MorphologyPlan:
    return MorphologyPlan(
        morphology_id   = "vtol_uav",
        project_family  = ProjectFamily.VTOL_UAV,
        display_name    = "VTOL Hybrid UAV",
        description     = (
            "A hybrid VTOL UAV combining fixed-wing aerodynamic surfaces "
            "with multirotor lift for vertical takeoff and transition flight."
        ),
        locomotion_type = LocomotionType.HYBRID_VTOL,
        body_plan = BodyPlan(
            segments = [
                "fuselage",
                "port_wing",
                "starboard_wing",
                "empennage",
                "vtol_rotor_mounts",
            ],
            required_features = [
                "fixed wing aerodynamic surfaces",
                "vertical lift rotor mounts (minimum 2)",
                "transition mechanism or tiltrotor axis",
                "fuselage electronics bay",
                "control surfaces",
            ],
            avoid_features = [
                "pure quad cross frame with no wings",
                "segmented insect body",
                "wheel-chassis rail",
            ],
            mounting_points = [
                "vtol_rotor_front_port",
                "vtol_rotor_front_starboard",
                "vtol_rotor_rear_port",
                "vtol_rotor_rear_starboard",
                "cruise_motor_mount",
                "port_wing_spar_root",
                "starboard_wing_spar_root",
            ],
        ),
        electronics_intent = ElectronicsIntent(
            primary_pcb_location = "fuselage",
            battery_location     = "fuselage",
            sensor_connectors    = ["gps_connector", "airspeed_connector", "camera_connector"],
            actuator_connectors  = [
                "vtol_esc_bank",
                "cruise_esc_connector",
                "aileron_servo_connectors",
                "elevator_rudder_connectors",
            ],
            power_rails = ["14.8V LiPo main rail", "5V BEC logic rail"],
        ),
        ros2_intent = ROS2Intent(
            base_frame = "base_link",
            recommended_frames = ["base_link", "fuselage_link", "port_wing_link",
                                  "starboard_wing_link", "empennage_link"],
            recommended_nodes = ["vtol_flight_controller", "transition_manager",
                                 "gps_node", "imu_node", "camera_node", "battery_monitor"],
            recommended_topics = ["/cmd_vel", "/flight_mode", "/airspeed",
                                  "/mavros/imu/data", "/battery_state"],
        ),
    )


def _build_robot_arm() -> MorphologyPlan:
    return MorphologyPlan(
        morphology_id   = "robot_arm",
        project_family  = ProjectFamily.ROBOT_ARM,
        display_name    = "Serial Robot Arm / Manipulator",
        description     = (
            "A serial-chain robotic manipulator with base, links, "
            "joints, and end-effector."
        ),
        locomotion_type = LocomotionType.MANIPULATOR,
        body_plan = BodyPlan(
            segments = [
                "base_mount",
                "shoulder_joint",
                "upper_arm_link",
                "elbow_joint",
                "forearm_link",
                "wrist_joint",
                "end_effector",
            ],
            required_features = [
                "fixed base mount plate",
                "rotary joints at shoulder, elbow, wrist",
                "rigid link segments between joints",
                "end-effector attachment interface",
                "servo or motor housing at each joint",
                "cable management channels",
            ],
            avoid_features = [
                "rotor arms",
                "wheel chassis",
                "fuselage shape",
                "segmented insect body",
            ],
            mounting_points = [
                "base_plate_bolts",
                "shoulder_axis",
                "elbow_axis",
                "wrist_axis",
                "tool_changer_flange",
            ],
        ),
        electronics_intent = ElectronicsIntent(
            primary_pcb_location = "base_mount",
            battery_location     = "base_mount",
            sensor_connectors    = ["wrist_imu_connector", "force_torque_sensor_connector"],
            actuator_connectors  = [
                "shoulder_motor_connector",
                "elbow_motor_connector",
                "wrist_motor_connector",
                "gripper_servo_connector",
            ],
            power_rails = ["24V motor rail", "5V logic rail", "3.3V sensor rail"],
        ),
        ros2_intent = ROS2Intent(
            base_frame = "base_link",
            recommended_frames = [
                "base_link", "shoulder_link", "upper_arm_link",
                "elbow_link", "forearm_link", "wrist_link", "end_effector_link",
            ],
            recommended_nodes = [
                "joint_trajectory_controller", "moveit_move_group",
                "gripper_controller", "force_torque_node", "trajectory_planner",
            ],
            recommended_topics = [
                "/joint_states", "/joint_trajectory_controller/command",
                "/gripper/command", "/force_torque/data",
            ],
        ),
    )


def _build_sensor_module() -> MorphologyPlan:
    return MorphologyPlan(
        morphology_id   = "sensor_module",
        project_family  = ProjectFamily.SENSOR_MODULE,
        display_name    = "Standalone Sensor Module / Node",
        description     = (
            "A static or embedded sensor node with no locomotion, "
            "housing sensors, processing electronics, and communication interfaces."
        ),
        locomotion_type = LocomotionType.STATIC,
        body_plan = BodyPlan(
            segments = [
                "sensor_housing",
                "pcb_core",
                "connector_panel",
            ],
            required_features = [
                "sensor mounting face or aperture",
                "PCB enclosure or carrier",
                "power and data connector panel",
                "mounting bracket or rail interface",
            ],
            avoid_features = [
                "wheel mounts", "rotor arms", "wing structure",
                "appendage mounts", "segmented body",
            ],
            mounting_points = [
                "wall_mount_bracket",
                "din_rail_clip",
                "sensor_face_mount",
            ],
        ),
        electronics_intent = ElectronicsIntent(
            primary_pcb_location = "pcb_core",
            battery_location     = "pcb_core",
            sensor_connectors    = ["sensor_i2c_connector", "sensor_spi_connector",
                                    "analog_input_connector"],
            actuator_connectors  = [],
            power_rails          = ["5V input rail", "3.3V sensor rail"],
        ),
        ros2_intent = ROS2Intent(
            base_frame = "sensor_link",
            recommended_frames = ["sensor_link", "camera_optical_link"],
            recommended_nodes  = ["sensor_driver_node", "data_logger_node",
                                  "health_monitor_node"],
            recommended_topics = ["/sensor/data", "/sensor/status", "/diagnostics"],
        ),
    )


def _build_humanoid() -> MorphologyPlan:
    return MorphologyPlan(
        morphology_id   = "humanoid_robot",
        project_family  = ProjectFamily.HUMANOID,
        display_name    = "Humanoid Bipedal Robot",
        description     = (
            "A bipedal humanoid robot with torso, head, two arms, and two legs."
        ),
        locomotion_type = LocomotionType.LEGGED,
        body_plan = BodyPlan(
            segments = [
                "head", "neck", "torso",
                "left_upper_arm", "left_forearm", "left_hand",
                "right_upper_arm", "right_forearm", "right_hand",
                "pelvis",
                "left_thigh", "left_shin", "left_foot",
                "right_thigh", "right_shin", "right_foot",
            ],
            required_features = [
                "head sensor platform",
                "torso electronics core",
                "bilateral arm assemblies",
                "bilateral leg assemblies with hip/knee/ankle joints",
                "foot contact sensors",
                "balance/IMU module in torso",
            ],
            avoid_features = [
                "rotor arms", "wheel chassis", "fuselage", "insect segments",
            ],
            mounting_points = [
                "head_neck_joint", "neck_torso_joint",
                "left_shoulder_joint", "right_shoulder_joint",
                "left_hip_joint", "right_hip_joint",
            ],
        ),
        electronics_intent = ElectronicsIntent(
            primary_pcb_location = "torso",
            battery_location     = "torso",
            sensor_connectors    = ["head_camera_connector", "imu_connector",
                                    "foot_contact_connectors"],
            actuator_connectors  = ["left_arm_servo_bank", "right_arm_servo_bank",
                                    "left_leg_servo_bank", "right_leg_servo_bank"],
            power_rails = ["24V actuator rail", "5V logic rail", "3.3V sensor rail"],
        ),
        ros2_intent = ROS2Intent(
            base_frame = "base_link",
            recommended_frames = ["base_link", "torso_link", "head_link",
                                  "left_hand_link", "right_hand_link",
                                  "left_foot_link", "right_foot_link"],
            recommended_nodes = ["balance_controller", "gait_planner",
                                 "arm_controller", "head_camera_node", "imu_node"],
            recommended_topics = ["/joint_states", "/cmd_vel", "/imu/data",
                                  "/balance/state", "/gait/command"],
        ),
    )


def _build_aquatic_robot() -> MorphologyPlan:
    return MorphologyPlan(
        morphology_id   = "aquatic_robot",
        project_family  = ProjectFamily.AQUATIC,
        display_name    = "Aquatic / Underwater Robot (AUV/ROV)",
        description     = (
            "An underwater vehicle with pressure hull, thruster mounts, "
            "buoyancy system, and waterproof electronics bay."
        ),
        locomotion_type = LocomotionType.ROTARY_WING,
        body_plan = BodyPlan(
            segments = [
                "pressure_hull",
                "nose_sensor_dome",
                "thruster_frame",
                "tail_section",
                "buoyancy_module",
            ],
            required_features = [
                "pressure-rated hull or enclosure",
                "waterproof electronics bay",
                "thruster mounts (minimum 4 for 4-DOF)",
                "cable penetrators for wiring",
                "buoyancy foam or variable buoyancy system",
                "nose sensor dome or camera port",
            ],
            avoid_features = [
                "open air electronics", "non-sealed connectors",
                "wheel mounts", "rotor arms above water", "wing lift surfaces",
            ],
            mounting_points = [
                "horizontal_thruster_port", "horizontal_thruster_starboard",
                "vertical_thruster_fore", "vertical_thruster_aft",
                "tether_attach_point", "manipulator_arm_mount",
            ],
        ),
        electronics_intent = ElectronicsIntent(
            primary_pcb_location = "pressure_hull",
            battery_location     = "pressure_hull",
            sensor_connectors    = ["dvl_connector", "depth_sensor_connector",
                                    "camera_connector", "sonar_connector"],
            actuator_connectors  = ["thruster_esc_bank"],
            power_rails = ["24V thruster rail", "5V logic rail", "3.3V sensor rail"],
        ),
        ros2_intent = ROS2Intent(
            base_frame = "base_link",
            recommended_frames = ["base_link", "pressure_hull_link",
                                  "camera_link", "dvl_link", "sonar_link"],
            recommended_nodes = ["thruster_controller", "depth_hold_node",
                                 "camera_node", "dvl_node", "mission_planner"],
            recommended_topics = ["/cmd_vel", "/depth", "/dvl/data",
                                  "/camera/image_raw", "/battery_state"],
        ),
    )


# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------
# Maps pattern name -> builder function.
# The planner uses this to call the correct builder after scoring.

PATTERN_REGISTRY: dict[str, Callable[[], MorphologyPlan]] = {
    "segmented_insect_robot": _build_segmented_insect_robot,
    "wheeled_rover":          _build_wheeled_rover,
    "quadcopter_drone":       _build_quadcopter_drone,
    "fixed_wing_uav":         _build_fixed_wing_uav,
    "vtol_uav":               _build_vtol_uav,
    "robot_arm":              _build_robot_arm,
    "sensor_module":          _build_sensor_module,
    "humanoid":               _build_humanoid,
    "aquatic_robot":          _build_aquatic_robot,
}


def get_all_pattern_names() -> list[str]:
    """Returns a sorted list of all registered pattern names."""
    return sorted(PATTERN_REGISTRY.keys())


def build_pattern(pattern_name: str) -> MorphologyPlan:
    """
    Build and return the MorphologyPlan for a named pattern.
    Raises KeyError if the pattern name is not registered.
    """
    if pattern_name not in PATTERN_REGISTRY:
        raise KeyError(
            f"Unknown morphology pattern: '{pattern_name}'. "
            f"Available: {get_all_pattern_names()}"
        )
    return PATTERN_REGISTRY[pattern_name]()