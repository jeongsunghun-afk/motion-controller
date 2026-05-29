# motion-controller

> ROS2 bridge for **CM_HL quadruped leg** controlled via **Motorcortex (MCX)** EtherCAT controller.
> Last release: **v1.0.0** — 토크 식 모듈화 재설계 (forcePF/TF = Dynamic feedforward, RL auto-entry)

This workspace contains the bridge between a Motorcortex real-time controller (running on MCX-OS) and the ROS2 ecosystem. The bridge translates between MCX parameter tree (positions, torques, events) and ROS2 topics, providing RViz visualization, RL policy interface, and motion primitives (jump, gait, moveL, impedance / GRF control).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ MCX-OS (Real-time, EtherCAT master)                              │
│   - Drive control (CSP / CST)                                    │
│   - PVA Predictive Limiter                                       │
│   - GRID UI (parameter tree, events, gain tuning)                │
└────────────┬────────────────────────────────────────────────────┘
             │ WebSocket (WSS)
             │ motorcortex Python client
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ motorcortex_bridge (ROS2 node, this repo)                        │
│   ┌──────────────────────┐  ┌────────────────────────────────┐  │
│   │ motorcortex_interface │  │ motion_controller             │  │
│   │ - parameter tree IO   │  │ - state machine               │  │
│   │ - subscriptions       │  │   STANDBY/STANDING/RL_POLICY  │  │
│   │ - GRID event router   │  │   EXEC_TRAJ/CSP_IDLE/CST_IDLE │  │
│   └──────────┬───────────┘  │ - 200Hz torque/position synth  │  │
│              │              │ - safety limits                │  │
│              ▼              │ - jump/gait/moveL/home         │  │
│   ┌──────────────────────────────────────────┐                  │
│   │ joint_state_bridge (ROS2 node entrypoint) │                  │
│   │  - /joint_states (50Hz, RViz)              │                  │
│   │  - /low_state    (50Hz, RL observation)    │                  │
│   │  - /low_cmd      (RL target/torque cmd)    │                  │
│   │  - /rl_gains     (Kp/Kd)                   │                  │
│   └──────────────────────────────────────────┘                  │
└────────────┬────────────────────────────────────────────────────┘
             │ ROS2 topics
             ▼
        RViz2  /  RL policy node  /  external observers
```

### Packages in this workspace

| Path | 역할 |
|---|---|
| `src/motorcortex_bridge/` | **본 패키지** — MCX↔ROS2 브릿지, motion_controller, joint_state_bridge |
| `src/CM_HL_v8/` | URDF / mesh / Gazebo launch (로봇 모델 패키지) |
| `src/cpp_pubsub/` | (예시 / 보조) ROS2 C++ pub-sub |
| `src/my_package/` | (개발용) — push 안 됨, 로컬 전용 |
| `src/stella_ahrs/` | (개발용) — IMU 패키지, push 안 됨 |

---

## Prerequisites

### System
- **Ubuntu 22.04 LTS** (또는 WSL2 + Ubuntu 22.04)
- **Python 3.10**
- **CMake 3.16+**, **git**

### ROS2
- **ROS2 Humble Hawksbill**
- 의존 ROS2 패키지: `rclpy`, `sensor_msgs`, `std_msgs`, `builtin_interfaces`, `robot_state_publisher`, `rviz2`, `launch`, `launch_ros`, `ament_index_python`

### Motorcortex Python Client
별도 vendor (vectioneer) 라이브러리. 권장 설치: 별도 venv 에서 pip 설치.
- `motorcortex-python` (WSS 통신, parameter tree access)
- `protobuf`, `websockets`, `cryptography` (transitive deps)

### Hardware
- Motorcortex 컨트롤러 (MCX-OS) — 기본값 `wss://192.168.2.100`
- CM_HL 다리 actuator (CIA402 호환, CSP/CST mode)

---

## Setup

### 1. Clone

```bash
mkdir -p ~/ros2_ws
cd ~/ros2_ws
git clone --recurse-submodules \
  git@github.com:jeongsunghun-afk/motion-controller.git .
# 또는 https:
# git clone --recurse-submodules \
#   https://github.com/jeongsunghun-afk/motion-controller.git .
```

repo root = workspace root (`~/ros2_ws/`). 패키지는 `src/` 아래.

### 2. ROS2 Humble 설치

[공식 가이드](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html) 참조. 요약:
```bash
sudo apt update && sudo apt install -y software-properties-common curl
sudo add-apt-repository universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
sudo apt install -y ros-humble-desktop python3-colcon-common-extensions \
  ros-humble-robot-state-publisher ros-humble-rviz2

# 매 셸마다 (또는 ~/.bashrc 에 추가)
source /opt/ros/humble/setup.bash
```

### 3. Motorcortex Python Client (venv)

기본 launch 파일은 `/home/jsh/mcx-client-app-template/.venv/...` 경로를 가정합니다. 다른 경로면 [launch 파일](src/motorcortex_bridge/launch/motorcortex_sim.launch.py) 의 `mcx_venv_site_packages` 변수를 수정.

```bash
# venv 생성 (위치는 자유, 예시는 사용자 홈)
cd ~
python3 -m venv mcx-client-app-template/.venv
source mcx-client-app-template/.venv/bin/activate

# motorcortex 설치 (vendor 측 wheel 또는 pypi)
pip install motorcortex-python   # 또는 vendor 측 wheel
pip install protobuf websockets cryptography

deactivate
```

> **참고**: motorcortex python 패키지는 vendor (vectioneer) 측에서 받아야 합니다. 자세한 설치는 vendor 문서 참조.

### 4. 워크스페이스 빌드

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
# 또는 특정 패키지만:
# colcon build --packages-select motorcortex_bridge --symlink-install
```

`--symlink-install` 덕에 Python 파일은 rebuild 없이 수정 즉시 반영 (launch 만 재실행).

### 5. 환경 source

매 새 셸:
```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
```

`~/.bashrc` 에 추가하면 매번 안 해도 됨.

---

## Usage

### Launch (시뮬레이션 + bridge + RViz)

```bash
ros2 launch motorcortex_bridge motorcortex_sim.launch.py
```

옵션 (launch arg):
```bash
ros2 launch motorcortex_bridge motorcortex_sim.launch.py \
    mcx_url:=wss://192.168.2.100 \
    mcx_login:=admin \
    mcx_password:=vectioneer \
    use_rviz:=true \
    traj_file:=/path/to/trajectory_jump.txt
```

### GRID 운용 모드 (v1.0.0)

bridge 연결 후 GRID UI 에서:

| 토글 | 의미 | 모드 |
|---|---|---|
| `opmode` | 0 = CSP (위치 제어) / 1 = CST (토크 제어) | 드라이브 |
| `forcePI` | Cartesian impedance (`J^T·(kp_imp·Δx − kd_imp·ẋ)`) | CSP |
| `forcePF` | **Dynamic feedforward** (`tau_dyn` 가산, 중력 보상) | CSP |
| `forcePC` | GRF FF+FB (`J^T·(F_ref + kf·(F_ref − F̂))`) | CSP |
| `forceTJ` | Joint impedance (`kp_joint·Δq − kd_joint·q̇`) | CST |
| `forceTF` | **Dynamic feedforward** (`tau_dyn` 가산, 중력 보상) | CST |
| `forceTC` | GRF FF+FB | CST |
| `torque_reset` | 비상 정지 (모든 force* OFF + tau=0 + STANDBY) | 공통 |
| `reset` | 게인 default 복원 | 공통 |

### 액션 이벤트

| 이벤트 | 동작 |
|---|---|
| `jump` | trajectory_jump.txt 점프 궤적 실행 |
| `gait` | Bezier 발걸음 패턴 |
| `moveL` | Cartesian quintic polynomial 직선 이동 |
| `home` | POS 직접 홈 복귀 (STANDBY 전용, CSP) |
| `homeAdditive` | ADDITIVE 홈 복귀 (비STANDBY) |
| `Sitting` / `Standing` | 자세 전환 (구현 TODO) |
| `RL_trot` | RL_POLICY 전환 (구현 TODO; v1.0.0 부터 `/low_cmd` 수신만으로 자동 진입) |

### RL 정책 연결 (v1.0.0 — auto-entry)

별도 force 토글 없이 `/low_cmd` 토픽 publish 자체가 RL_POLICY 진입 시그널.

**CSP + RL**:
```bash
ros2 topic pub --rate 50 /low_cmd sensor_msgs/JointState "{
  position: [q1, q2, q3, q4],
  effort:   [tau_off1, tau_off2, tau_off3, tau_off4]
}"
```
→ drive 위치 PID + bridge tau_offset (feedforward) 가산.

**CST + RL (raw torque)**:
```bash
ros2 topic pub --rate 50 /low_cmd sensor_msgs/JointState "{
  position: [],
  effort:   [tau1, tau2, tau3, tau4]
}"
```
→ bridge 가 `axesTorquesInput = effort` 만 송신 (drive 위치 무시).

종료: publisher 중단 (200ms timeout → 자동 STANDBY 복귀) 또는 GRID `torque_reset`.

### 강성 (impedance gain) 조정

GRID `kp_joint / kd_joint / kp_imp / kd_imp / kf_grf` 변경 시 bridge subscribe 가 거의 실시간 (수 ms) 반영. push subscription (`frq_divider=10` ≈ 400Hz).

`forceTJ` (CST 측) Joint impedance 운용 권장 범위 (CM_HL 기준):
- compliant: `kp = 25 ~ 100`
- medium: `100 ~ 300`
- stiff: `300 ~ 1000`

자세한 토크 식 / 모드별 매핑은 [TODO.md](src/motorcortex_bridge/TODO.md) 와 [motion_controller.py docstring](src/motorcortex_bridge/motorcortex_bridge/motion_controller.py) 참조.

---

## ROS2 Topics

| Topic | Type | Direction | Rate |
|---|---|---|---|
| `/joint_states` | `sensor_msgs/JointState` | publish | 50Hz |
| `/low_state` | `sensor_msgs/JointState` | publish | 50Hz |
| `/low_cmd` | `sensor_msgs/JointState` | subscribe | (외부 publisher 측) |
| `/rl_gains` | `std_msgs/Float64MultiArray` | subscribe | (외부 publisher 측) |

`/low_state` 의 필드 (RL observation 호환):
- `position` = `axesPositionsActual` [rad]
- `velocity` = `axesVelocitiesActual` [rad/s]
- `effort` = `actuatorTorqueActual` [N·m]

---

## Troubleshooting

### bridge 실행 시 `connect 실패` 로그
- MCX 컨트롤러 IP 확인 (`ping 192.168.2.100`)
- 사용자 / 비밀번호 launch arg 로 전달
- WSS 인증서 경로 — launch arg `mcx_cert:=/path/to/cert.crt`

### `gait` / `jump` 가 무반응 (CST 모드)
- CST 에서는 drive 가 위치 무시 → bridge 가 토크 직접 송신해야 함
- `forceTJ` + `forceTF` 모두 ON 권장 (impedance + 중력보상)
- 자세한 운용 가이드는 [TODO.md 운용 메모](src/motorcortex_bridge/TODO.md#운용-메모) 참조

### `axesVelocitiesActual` 단위 의심
- 1초에 90° 회전시키면서 monitor 로그의 raw vel 값 확인
- rad/s 면 peak ≈ 1.5~1.6, deg/s 면 90~100 — GRID 측 설정 단위와 일치해야

### RViz 자세 이상 (영점 변경 후)
- GRID 영점 calibration 변경 후 `motion_controller.py:Q_HOME_DEG` 갱신 필요
- 또는 publish 좌표를 mechanical 으로 변환 (조정 필요 시 [TODO.md](src/motorcortex_bridge/TODO.md) 참조)

### `colcon build` 실패
- `CM_HL_v8` 패키지명 경고 (대문자) — 무시 가능, 빌드는 진행됨
- ROS2 / ament_python 의존성 확인: `sudo apt install ros-humble-ament-cmake ros-humble-ament-python`

### WSL2 환경에서 control_loop rate 부정확
- `ros2 topic hz /joint_states` 로 publish rate 확인 (50Hz 정상)
- 200Hz control_loop rate 측정 디버그 로그 추가 필요 시 `_control_loop` 안에 cycle 카운터

---

## 버전 / 변경 이력

[TODO.md](src/motorcortex_bridge/TODO.md) 의 "완료 (Done)" 섹션 참조.

주요 마일스톤:
- **v1.0.0** (2026-05-28) — 토크 식 모듈화 재설계 (forcePF/TF = Dynamic FF), RL_POLICY auto-entry
- **v0.9.x** — Joint impedance default 튜닝, `torque_reset` 버튼, 5축 (toe) 지원, `disableDrive` 기반 자동 감지
- **v0.8.x** — N_AXES 4↔5 토글, SW joint safety limit, 통합 idle state (CSP_IDLE / CST_IDLE)
- **v0.7.x** — force* 토글 GRID 명명 정합, axesVelocitiesActual 구독, EXEC_TRAJ 토크 합성

---

## License

BSD-style (벤더/하드웨어 의존). 상세는 각 패키지의 `package.xml` 참조.

## References

- [Motorcortex 공식 문서](https://www.vectioneer.com/) — vendor
- [ROS2 Humble docs](https://docs.ros.org/en/humble/)
- [CIA402 standard](https://www.can-cia.org/can-knowledge/canopen/cia402/) — drive control mode
