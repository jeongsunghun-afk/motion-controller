# Installation — biped_sim

Ubuntu 22.04 + ROS2 Humble 환경 가정. WSL 도 ROS2 부분만 동작 (viewer 제외).

## 1. ROS2 Humble

```bash
sudo apt update && sudo apt install -y curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
sudo apt install -y ros-humble-desktop python3-colcon-common-extensions ros-humble-rclpy ros-humble-sensor-msgs ros-humble-nav-msgs ros-humble-std-msgs
```

## 2. Python 의존성

```bash
pip install --user mujoco>=3.0 numpy qpsolvers trimesh fast_simplification
# QP solver: qpsolvers + quadprog 또는 osqp 중 1개
pip install --user quadprog   # 권장
```

## 3. 워크스페이스 + 빌드

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone git@github.com:jeongsunghun-afk/motion-controller.git .   # 또는 fork 후 clone
# biped_sim 외에 gait_sim_mujoco, motorcortex_bridge 도 함께 clone 됨

# biped 의 URDF/MJCF asset 위치 별도 (leg_sim repo)
mkdir -p ~/simulation && cd ~/simulation
git clone git@github.com:jeongsunghun-afk/leg_sim.git .
# → /home/jsh/simulation/biped/  (MJCF 및 mesh)

# Build
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select biped_sim
source install/setup.bash
```

## 4. MJCF 경로 확인

기본 경로: `/home/jsh/simulation/biped/biped_wrapper.mjcf`
다른 경로면 launch 또는 node parameter `mjcf_path` 로 override:

```bash
ros2 run biped_sim mujoco_node --ros-args -p mjcf_path:=/path/to/biped_wrapper.mjcf
```

## 5. 동작 확인

```bash
ros2 launch biped_sim wbic_standing.launch.py
```

→ log 에 `BipedMujocoNode ready ... viewer=False` + `BipedControllerNode ready @ 100Hz` 떠야 정상.

별도 터미널에서:
```bash
ros2 topic list   # /joint_states /imu /low_cmd /low_state /base_state /rl_gains 확인
ros2 topic hz /low_cmd   # ~100 Hz
```

## 6. Viewer (선택)

### Windows native (권장, 가장 안정)
1. Anaconda + mujoco 설치 (`pip install mujoco`)
2. MJCF + mesh 를 Windows 쪽으로 복사
3. batch 파일로 viewer launch (예: `C:\Users\jsh\run_biped_viewer.bat`)

### WSL (검은 화면 가능)
```bash
ros2 launch biped_sim wbic_standing.launch.py use_viewer:=true
```

### Native Ubuntu (server PC, 최고 fidelity)
- 모든 visualization + ROS2 + motorcortex_bridge native 동작
- 향후 sim2real (r1.x) 시점 필수
