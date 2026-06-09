# biped_sim — Biped (HL/HR 2-leg) ROS2 simulation + WBIC controller

unitree_mujoco style ROS2 패키지. MuJoCo simulator + WBIC controller 분리,
topic interface 로 motorcortex_bridge 와 swap 가능 (sim ↔ real).

## Architecture

```
                  /low_cmd (JointState: position, velocity, effort)
                       ↓
  ┌─────────────────────────────────────────────────────────┐
  │ controller_node  (BipedMjModel + WBIC QP 28-dim @100Hz) │
  └─────────────────────────────────────────────────────────┘
       ↑ /joint_states  ↑ /imu  ↑ /base_state
  ┌─────────────────────────────────────────────────────────┐
  │ mujoco_node  (MuJoCo simulator + Hermite+PD @200Hz)     │
  │   sim 전용; r1.x 부터 motorcortex_bridge 로 교체 가능   │
  └─────────────────────────────────────────────────────────┘
```

## 파일 구조

```
biped_sim/
├── biped_sim/
│   ├── mujoco_node.py            # MuJoCo simulator (200Hz step + Hermite+PD)
│   ├── controller_node.py        # WBIC standing controller @ 100Hz
│   ├── standing_publisher.py     # manual /low_cmd Q_HOME publisher (PD-only test)
│   └── controllers/
│       ├── wbic.py               # biped WBIC QP 28-dim (body 6 + Δq̈ 8 + Δτ 8 + Δλ 6)
│       └── model.py              # DH constants + BipedMjModel (mj_jac wrapper)
├── launch/
│   ├── standing_test.launch.py   # PD-only standing test
│   └── wbic_standing.launch.py   # WBIC standing test (mujoco_node + controller_node)
├── package.xml
├── setup.py
└── README.md
```

## Topic interface (motorcortex_bridge 와 동일)

| Topic | Type | Direction | Hz | 설명 |
|---|---|---|---|---|
| `/low_cmd` | sensor_msgs/JointState | controller→sim | 100 | position=q_target, velocity=qdot, effort=tau_ff (8-dim) |
| `/joint_states` | sensor_msgs/JointState | sim→controller | 50 | RViz 호환 |
| `/low_state` | sensor_msgs/JointState | sim→controller | 50 | Unitree LowState 호환 |
| `/imu` | sensor_msgs/Imu | sim→controller | 50 | base orientation, angular velocity |
| `/base_state` | nav_msgs/Odometry | sim→controller | 50 | sim 전용 ground truth (r4.1 EKF 이전) |
| `/rl_gains` | std_msgs/Float64MultiArray | external→sim | event | Kp/Kd 동적 갱신 (옵션) |

## Build

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select biped_sim
source install/setup.bash
```

## 실행

### WBIC standing test (launch — 한 명령)

```bash
ros2 launch biped_sim wbic_standing.launch.py
# WSLg viewer 가능하면: use_viewer:=true
```

### 터미널 분리 (디버깅용)

```bash
# 터미널 1
ros2 run biped_sim mujoco_node

# 터미널 2
ros2 run biped_sim controller_node
```

### State 실시간 확인 (별도 터미널)

```bash
ros2 topic echo /base_state --field pose.pose.position   # base 위치 (z=0.532 유지?)
ros2 topic echo /low_cmd    --field effort               # WBIC tau (8-dim)
ros2 topic echo /imu        --field orientation          # base 자세 (w 가 1?)
ros2 topic hz   /low_cmd                                  # ~100 Hz 예상
```

## 현재 상태 (이번 세션 종료 시점)

- ✅ sim 인프라 완성 (mujoco_node, MJCF wrapper, URDF angle 매핑)
- ✅ WBIC QP 28-dim fork + sanity test pass
- ✅ BipedMjModel (mujoco mj_jac/mj_fullM 직접 사용, URDF 100% 일치 보장)
- ✅ controller_node + launch + base_state ground-truth pub
- ⚠️ WBIC standing 4회 시도 실패 — **좌우 비대칭 bug** (HR 만 saturate, HL 작은 tau).
  mj_inverse 는 HL_hip=-173, HR_hip=+172 (정확 mirror) 인데 WBIC 결과 비대칭.
  → 다음 세션 우선: BipedMjModel leg_dynamics HL vs HR diff + WBIC frame/sign 진단
- ⚠️ Hip roll 임시 200Nm (실제 max 84Nm × 2 초과) — robot geometry 한계로 정적 standing
  자체가 어려움. 향후 dynamic walking (MPC + ZMP/DCM) 필요할 수 있음

## Visualization 한계

- WSL + MuJoCo viewer: WSLg OpenGL 호환 안 됨 (검은 화면)
- 현재 대안: state echo (ros2 topic) + Windows native viewer (별도 sim, ROS2 무관)
- 진짜 해결: **native Ubuntu** (server PC) — motorcortex_bridge 연동 (r1.x) 시점 어차피 필요

## 참고

- 원본 URDF/MJCF: `/home/jsh/simulation/biped/`
- gait_sim (quadruped reference): `/home/jsh/simulation/gait_sim/`
