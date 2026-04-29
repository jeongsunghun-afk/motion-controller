"""
motion_controller.py
궤적 실행 / moveJ / moveL / forceS / forceT / 제어 루프 / 이벤트 처리 전담 클래스
ROS2 의존성 없음 — joint_state_bridge 에서 생성하여 사용

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
동작 흐름 (JogMode=0 & PauseMode=0 진입 후)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [정상 운용 시퀀스]
    IdleMode → STANDBY → (sitting 궤적) → STANDING → (standing 궤적) → RL_trot
    Fall Recovery → STANDBY 복귀

  [Leg_test 이벤트]
    Jump, Gait, moveL, ForceT, ForceS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
이벤트 경로 (GRID root/UserParameters/*)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Sitting       — sitting 자세 전환 (→ STANDBY)
  Standing      — standing 자세 전환 (→ STANDING)
  RL_trot       — RL 명령 추종 (50Hz → 200Hz 선형 보간, → RL_POLICY 상태)
  Fall recovery — 낙상 복구
  jump          — 점프 궤적 실행 (.txt)
  gait          — Bezier 발걸음 패턴 (이전 moveL 구현)
  moveL         — Cartesian quintic polynomial 직선 이동
  forceT        — 발끝 고정 + 실측 토크 → GRF 추정 임피던스 제어
  forceF        — forceT 내 GRF 피드백 ON/OFF (레벨 신호, forceT 활성 시 유효)
  forceS        — moveL 임피던스 모드 토글 (ON시 moveL에 GRF+임피던스 토크 추가)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RL_trot 보간 (3차 Hermite, C1 연속):
  q(s) = h00*q0 + h10*T*m0 + h01*q1 + h11*T*m1      s ∈ [0, 1]
  h00=2s³−3s²+1, h10=s³−2s²+s, h01=−2s³+3s², h11=s³−s²
  m0 : 구간 시작 속도 (이전 Hermite 미분, C1 연속 보장)
  m1 : 구간 끝 속도  ((q_new − q_prev_target) / T 차분 추정)
  s = elapsed / CMD_PERIOD,   CMD_PERIOD = 1/50 s = 0.02 s
"""

import itertools
import threading
import time
import math
from collections import deque
import numpy as np

from motorcortex_bridge.motorcortex_interface import (
    MotorcortexInterface,
    N_AXES,
)

# ── 홈 자세 ────────────────────────────────────────────────────────────────────
Q_HOME_DEG = [0.0, -150.0, -90.0, 90.0]
Q_HOME_RAD = [math.radians(d) for d in Q_HOME_DEG]

# ── 기본값 ─────────────────────────────────────────────────────────────────────
TRAJ_FILE_DEFAULT  = '/home/jsh/leg_sim/trajectory_jump.txt'
TRAJ_DT_DEFAULT    = 0.005    # 200 Hz
CMD_PERIOD         = 0.02    # 외부 명령 수신 주기 [s] (tracking 모드 기준, 50 Hz)
HOLD_CYCLE         = 0.005   # 200 Hz (보간 루프 주기)
HOME_THRESHOLD_RAD = math.radians(0.01)  # 홈 판정 임계값 (0.01°)
HOME_SPEED_DEG     = 10.0                # ★ 홈 복귀 속도 조정 [°/s] ← 이 값만 변경
HOME_MAX_VEL       = math.radians(HOME_SPEED_DEG)        # [rad/s]
HOME_MAX_ACC       = math.radians(HOME_SPEED_DEG / 2.0)  # [rad/s²]

MOVEL_VEL          = 0.05               # moveL Cartesian 이동 속도 [m/s]
MOVEL_STEP_X       = -0.010             # moveL 기본 step: x축[m] 중력방향(-)
MOVEL_STEP_Z       = 0                  # moveL 기본 step: z축[m] 전방/후방

GAIT_STEP_X        = +0.050             # gait 기본 step: x축 발 높이 [m] (+x=위)
GAIT_STEP_Z        = +0.020             # gait 기본 step: z축 전후 반진폭 [m] (+z=전방)
GAIT_IMP_DELTA     = +0.008             # gait2 이륙/착지 임피던스 오프셋 [m] (δ, x축)


def _to_phy(mcx_j: list) -> list:
    """MCX 관절값 (home 기준 offset, rad) → 물리적 절대각 [rad].
    MCX actual = 0 → 물리각 = Q_HOME_RAD
    """
    return [mcx_j[i] + Q_HOME_RAD[i] for i in range(N_AXES)]


def _to_mcx(phy_j: list) -> list:
    """물리적 절대각 [rad] → MCX 관절값 (home 기준 offset, rad).
    IK 결과(물리각)를 MCX 명령으로 변환 시 사용.
    """
    return [phy_j[i] - Q_HOME_RAD[i] for i in range(N_AXES)]


def _hermite_pos(s: float, T: float,
                 q0: list, q1: list, m0: list, m1: list) -> list:
    """3차 Hermite 위치 보간 (s ∈ [0,1], T=구간 시간[s])."""
    h00 = 2*s**3 - 3*s**2 + 1;  h10 = s**3 - 2*s**2 + s
    h01 =-2*s**3 + 3*s**2;       h11 = s**3 - s**2
    return [h00*q0[i] + h10*T*m0[i] + h01*q1[i] + h11*T*m1[i]
            for i in range(len(q0))]


def _hermite_vel(s: float, T: float,
                 q0: list, q1: list, m0: list, m1: list) -> list:
    """3차 Hermite 속도 dq/dt (s ∈ [0,1], T=구간 시간[s])."""
    dh00 = 6*s**2 - 6*s;  dh10 = 3*s**2 - 4*s + 1
    dh01 =-6*s**2 + 6*s;  dh11 = 3*s**2 - 2*s
    return [(dh00*q0[i]+dh10*T*m0[i]+dh01*q1[i]+dh11*T*m1[i])/T
            for i in range(len(q0))]


# ── 임피던스 제어 게인 (leg_sim_v4.py 동기화) ─────────────────────────────────
KP_IMP  = np.array([ 80.0, 246.0, 246.0])   # Cartesian 강성 [N/m]  X(중력):≈80Nm/rad, Y/Z:≈80Nm/rad@hip
KD_IMP  = np.array([  5.0,  15.0,  15.0])   # Cartesian 감쇠 [N·s/m] X(중력):≈5Nms/rad, Y/Z:≈5Nms/rad@hip
KF_GRF  = np.array([  0.1,   0.1,   0.1])   # forceT GRF 피드백 게인 (무차원, force error → N)
MU_DAMP = 1e-3                               # Jacobian 댐핑 계수 (특이점 방지)

# ── Gait2 페이즈별 게인 ──────────────────────────────────────────────────────
GAIT_KP_LOW  = np.array([200.0, 200.0, 200.0])  # Late Swing / Touch-down / Pre-Swing [N/m]
GAIT_KD_MID  = np.array([ 20.0,  20.0,  20.0])  # Late Swing [N·s/m]
GAIT_KD_HIGH = np.array([ 60.0,  60.0,  60.0])  # Touch-down / Pre-Swing [N·s/m]
GAIT_KF_HIGH = np.array([  0.1,   0.1,   0.1])  # Mid Stance
GAIT_KF_LOW  = np.array([  0.03,  0.03,  0.03]) # Pre-Swing

# ── DH 파라미터 (leg_sim_v4.py 동기화) ─────────────────────────────────────────
# [alpha, a(m), d(m)]
_DH = [
    (-math.pi/2, 0.0,   0.0   ),   # Joint 1: Hip Abduction
    (0.0,        0.21,  0.0075),   # Joint 2: Hip Pitch
    (0.0,        0.21,  0.0   ),   # Joint 3: Knee
    (0.0,        0.148, 0.0   ),   # Joint 4: Ankle
]
_A2 = _DH[1][1]    # 0.21 m
_A3 = _DH[2][1]    # 0.21 m
_A4 = _DH[3][1]    # 0.148 m
_D2 = _DH[1][2]    # 0.0075 m

# ── 물리 파라미터 (leg_sim_v4.py 동기화) ─────────────────────────────────────
# 링크 질량 [kg]  (Hip Abduction / Thigh / Shin / Foot)
LINK_MASS = np.array([3.34, 0.8, 0.2, 0.2])
G         = 9.81
G_VEC     = np.array([-G, 0.0, 0.0])   # 중력 방향 (-X = 아래, 월드 기준)


# ── FK / Jacobian 공통 유틸 ───────────────────────────────────────────────────
def _dh_matrix(alpha, a, d, theta):
    ct, st = math.cos(theta), math.sin(theta)
    ca, sa = math.cos(alpha), math.sin(alpha)
    return np.array([
        [ct, -st*ca,  st*sa, a*ct],
        [st,  ct*ca, -ct*sa, a*st],
        [ 0,     sa,     ca,    d],
        [ 0,      0,      0,    1],
    ], dtype=float)


def _get_origins_zaxes(thetas: list):
    """
    DH 순기구학으로 관절 원점·z축 배열 반환.
    FK와 Jacobian이 공유하는 공통 유틸 — DH 행렬을 한 번만 계산.
    반환: (origins, z_axes)
      origins : [p0, p1, ..., p4]  각 관절 원점 (p0=힙)
      z_axes  : [z0, z1, ..., z4]  각 관절 z축
    """
    T       = np.eye(4)
    origins = [np.zeros(3)]
    z_axes  = [np.array([0.0, 0.0, 1.0])]
    for (alpha, a, d), theta in zip(_DH, thetas):
        T = T @ _dh_matrix(alpha, a, d, theta)
        origins.append(T[:3, 3].copy())
        z_axes.append(T[:3, 2].copy())
    return origins, z_axes


def forward_kinematics(thetas: list) -> list:
    """
    4축 FK. 각 관절 원점 좌표 반환 (힙=원점 기준).
    반환: [p0, p1, p2, p3, p4]  (p0=힙, p4=발끝)
    """
    origins, _ = _get_origins_zaxes(thetas)
    return origins


def compute_jacobian(thetas: list) -> np.ndarray:
    """
    3D 위치 자코비안 (3×N_AXES).
    J[:,i] = z_i × (p_e - p_i)
    반환: (3, N_AXES) ndarray
    """
    origins, z_axes = _get_origins_zaxes(thetas)
    pe = origins[-1]
    J  = np.zeros((3, len(thetas)))
    for i in range(len(thetas)):
        J[:, i] = np.cross(z_axes[i], pe - origins[i])
    return J


def compute_gravity_torque(thetas: list) -> np.ndarray:
    """
    링크 무게에 의한 중력 보상 토크 (N_AXES×1) [N·m].
    τ_g[j] = Σ_{k≥j} (z_j × (p_com_k − p_j)) · (m_k · G_VEC)

    p_com_k : 링크 k의 무게중심 = 관절 k와 k+1 원점의 중간점
    _get_origins_zaxes 재사용으로 DH 행렬 중복 계산 없음.
    """
    origins, z_axes = _get_origins_zaxes(thetas)
    n      = len(thetas)
    tau_g  = np.zeros(n)
    for k in range(n):                        # 링크 k (관절 k → k+1 사이)
        p_com  = (origins[k] + origins[k + 1]) / 2.0
        f_grav = LINK_MASS[k] * G_VEC        # 중력 하중 [N]
        for j in range(k + 1):               # 관절 j (j ≤ k 인 관절이 링크 k에 영향)
            tau_g[j] += np.dot(np.cross(z_axes[j], p_com - origins[j]), f_grav)
    return tau_g


def _fun_force_f(thetas: list):
    """
    동역학 계산 (단일 DH 패스): FK / Jacobian / 중력 토크.
    forceS / forceT 200Hz 루프에서 DH 행렬 중복 계산 방지용.

    반환: (x_foot, J, tau_dyn)
      x_foot  : 발끝 위치 [m]        (3,) ndarray
      J       : 위치 자코비안 (3, N_AXES)
      tau_dyn : 중력 보상 토크 [Nm]  (N_AXES,)
    """
    origins, z_axes = _get_origins_zaxes(thetas)
    pe = origins[-1]
    n  = len(thetas)

    J = np.zeros((3, n))
    for i in range(n):
        J[:, i] = np.cross(z_axes[i], pe - origins[i])

    tau_g = np.zeros(n)
    for k in range(n):
        p_com  = (origins[k] + origins[k + 1]) / 2.0
        f_grav = LINK_MASS[k] * G_VEC
        for j in range(k + 1):
            tau_g[j] += np.dot(np.cross(z_axes[j], p_com - origins[j]), f_grav)

    return pe.copy(), J, tau_g


def compute_grf(tau_actual, tau_gravity, J: np.ndarray) -> np.ndarray:
    """
    실제 관절 토크로부터 지면반력(GRF) 추정.
    τ_GRF,a = τ_actual - τ_gravity   (합력 토크 = 중력토크 + GRF 기여분)
    F_GRF   = (J·Jᵀ + μI)⁻¹ · J · τ_GRF,a  [N]

    tau_actual  : 실측 관절 합력 토크 [Nm]  (N_AXES,) — actuatorTorqueActual
    tau_gravity : 중력 보상 토크      [Nm]  (N_AXES,) — compute_gravity_torque()
    J           : 자코비안 (3, N_AXES) — compute_jacobian()
    반환        : GRF 추정값 [N]  (3,)  — [Fx, Fy, Fz]  (+X=위 기준, 지면 접촉 시 양수)
    """
    tau_a = np.asarray(tau_actual,  dtype=float)
    tau_g = np.asarray(tau_gravity, dtype=float)
    JJT   = J @ J.T + MU_DAMP * np.eye(3)
    return np.linalg.solve(JJT, J @ (tau_a - tau_g))


def compute_impedance_torque(x_r, x_a, J: np.ndarray,
                              dx_r=None, dx_a=None) -> np.ndarray:
    """
    Cartesian 공간 임피던스 제어 토크 (N_AXES×1) [N·m].

    f_imp   = Kp*(x_r - x_a) + Kd*(dx_r - dx_a)
    tau_imp = J^T · f_imp

    x_r, x_a  : 발끝 목표/실제 위치 [m]  (3,)
    J          : 자코비안 (3, N_AXES)   — compute_jacobian(q_actual)
    dx_r, dx_a : 발끝 목표/실제 속도 [m/s]  (3,) — None 이면 0으로 처리
    """
    x_r  = np.asarray(x_r,  dtype=float)
    x_a  = np.asarray(x_a,  dtype=float)
    dx_r = np.zeros(3) if dx_r is None else np.asarray(dx_r, dtype=float)
    dx_a = np.zeros(3) if dx_a is None else np.asarray(dx_a, dtype=float)

    f_imp = KP_IMP * (x_r - x_a) + KD_IMP * (dx_r - dx_a)
    return J.T @ f_imp


def analytical_ik(Px: float, Py: float, Pz: float,
                  phi: float, elbow_up: bool = True):
    """
    해석적 IK (leg_sim_v1.py 참조, 4축).
    Px, Py, Pz : 발끝 목표 좌표 [m]  (힙 원점 기준)
    phi        : θ2+θ3+θ4 유지 각도 [rad]
    반환       : [θ1, θ2, θ3, θ4] [rad]  또는 None (해 없음)
    """
    D2 = Px**2 + Py**2 - _D2**2
    if D2 < 0:
        return None
    R = math.sqrt(D2)

    theta1 = math.atan2(-Px, Py) - math.atan2(R, _D2)

    c1, s1 = math.cos(theta1), math.sin(theta1)
    x_s = c1 * Px + s1 * Py
    Z   = -Pz

    x3 = x_s - _A4 * math.cos(phi)
    z3 = Z   - _A4 * math.sin(phi)

    cos_th3 = (x3**2 + z3**2 - _A2**2 - _A3**2) / (2.0 * _A2 * _A3)
    cos_th3 = max(-1.0, min(1.0, cos_th3))
    theta3  = -math.acos(cos_th3) if elbow_up else math.acos(cos_th3)

    theta2 = (math.atan2(z3, x3)
              - math.atan2(_A3 * math.sin(theta3),
                           _A2 + _A3 * math.cos(theta3)))

    theta4 = phi - theta2 - theta3

    def wrap(a):
        return (a + math.pi) % (2 * math.pi) - math.pi

    return [wrap(theta1), wrap(theta2), wrap(theta3), wrap(theta4)]


# ── Trajectory 생성 ────────────────────────────────────────────────────────────
def _quintic_coeffs(t0, tf, p0, v0, a0, pf, vf, af):
    """5차 다항식 계수 계산 (경계조건: 위치·속도·가속도)"""
    T_mat = np.array([
        [1, t0, t0**2,   t0**3,   t0**4,   t0**5],
        [0,  1, 2*t0, 3*t0**2, 4*t0**3, 5*t0**4],
        [0,  0,    2,   6*t0, 12*t0**2, 20*t0**3],
        [1, tf, tf**2,   tf**3,   tf**4,   tf**5],
        [0,  1, 2*tf, 3*tf**2, 4*tf**3, 5*tf**4],
        [0,  0,    2,   6*tf, 12*tf**2, 20*tf**3],
    ])
    return np.linalg.solve(T_mat, np.array([p0, v0, a0, pf, vf, af]))


def _eval_quintic(c, t):
    return (c[0] + c[1]*t + c[2]*t**2 + c[3]*t**3
            + c[4]*t**4 + c[5]*t**5)


def _quintic_segment(p0, pf, duration, dt):
    """
    단일 구간 5차 다항식 보간 (시작/끝 속도·가속도=0).
    반환: list of float (위치)
    """
    c = _quintic_coeffs(0, duration, p0, 0, 0, pf, 0, 0)
    n = max(1, int(duration / dt))
    return [_eval_quintic(c, k * duration / n) for k in range(1, n + 1)]


def trapezoid_profile(dist: float, max_vel: float, max_acc: float, dt: float) -> list:
    """
    단일 축 사다리꼴 속도 프로파일 생성.
    dist     : 이동 거리 (양수)
    max_vel  : 최대 속도 [단위/s]
    max_acc  : 최대 가속도 [단위/s²]
    dt       : 샘플 주기 [s]
    반환     : 각 스텝의 누적 이동량 리스트 (0 → dist)
    """
    d_acc = max_vel ** 2 / (2.0 * max_acc)

    if 2.0 * d_acc >= dist:
        # 삼각형 프로파일 (최대 속도 도달 전에 감속 시작)
        v_peak  = math.sqrt(max_acc * dist)
        t_acc   = v_peak / max_acc
        t_total = 2.0 * t_acc
    else:
        # 사다리꼴 프로파일
        t_acc   = max_vel / max_acc
        t_const = (dist - 2.0 * d_acc) / max_vel
        t_total = 2.0 * t_acc + t_const
        v_peak  = max_vel

    n_steps = max(1, int(t_total / dt))
    positions = []
    for k in range(1, n_steps + 1):
        t = t_total * k / n_steps
        if 2.0 * d_acc >= dist:
            t_acc_loc = v_peak / max_acc
            if t <= t_acc_loc:
                p = 0.5 * max_acc * t ** 2
            else:
                t2 = t - t_acc_loc
                p = 0.5 * max_acc * t_acc_loc ** 2 + v_peak * t2 - 0.5 * max_acc * t2 ** 2
        else:
            if t <= t_acc:
                p = 0.5 * max_acc * t ** 2
            elif t <= t_acc + t_const:
                p = d_acc + max_vel * (t - t_acc)
            else:
                t3 = t - t_acc - t_const
                p = d_acc + max_vel * t_const + max_vel * t3 - 0.5 * max_acc * t3 ** 2
        positions.append(min(p, dist))
    return positions


def load_trajectory(filepath: str) -> list:
    """
    trajectory_jump.txt 로드.
    형식: frame\\tth1_deg\\tth2_deg\\tth3_deg\\tth4_deg
    반환: list of tuple(th1, th2, th3, th4) [rad]
    각 waypoint에서 Q_HOME_RAD를 빼서 반환 (홈 기준 상대 궤적).
    """
    waypoints = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if not parts[0].lstrip('-').replace('.', '', 1).isdigit():
                continue
            if len(parts) < 5:
                continue
            waypoints.append(
                tuple(math.radians(float(parts[i])) - Q_HOME_RAD[i - 1] for i in range(1, 5))
            )
    return waypoints


def _bezier_curve(control_pts: list, n: int) -> list:
    """
    De Casteljau 알고리즘으로 베지어 곡선 이산화.
    control_pts : list of array-like (Px, Py, Pz) — 제어점 (차수 = len-1)
    n           : 샘플 수 (t = 1/n, 2/n, …, 1 ; 시작점 t=0 제외)
    반환        : list of np.ndarray, 길이 n
    """
    p = [np.asarray(pt, dtype=float) for pt in control_pts]
    deg = len(p) - 1
    pts = []
    for i in range(1, n + 1):
        t = i / n
        q = list(p)
        for _ in range(deg):
            q = [(1.0 - t) * q[j] + t * q[j + 1] for j in range(len(q) - 1)]
        pts.append(q[0])
    return pts


class MotionController:
    """
    운동 제어 클래스.
    MCX 통신은 MotorcortexInterface 에 위임.

    제어 모드는 GRID controlMode 값으로 결정:
      set_control_mode(mode) 를 통해 외부에서 갱신.
    """

    def __init__(self, mcx: MotorcortexInterface,
                 traj_file: str = TRAJ_FILE_DEFAULT,
                 traj_dt: float = TRAJ_DT_DEFAULT):
        self._mcx      = mcx
        self.traj_file = traj_file
        self.traj_dt   = traj_dt

        self._lock = threading.Lock()

        # 상태 머신 (STANDBY / STANDING / RL_POLICY / EXEC_TRAJ / FORCE_T_IDLE / FORCE_S_IDLE / HOME)
        self._ctrl_state = 'STANDBY'

        # 마지막 명령 위치 (위치 유지 / publish 참조용)
        self._last_cmd_pos = list(Q_HOME_RAD)

        # ── tracking 모드: Hermite 보간 상태 ──────────────────────────────
        self._interp_prev   = list(Q_HOME_RAD)
        self._interp_target = list(Q_HOME_RAD)
        self._interp_time   = time.monotonic()
        self._interp_dq0    = [0.0] * N_AXES   # 구간 시작 속도 [rad/s]
        self._interp_dq1    = [0.0] * N_AXES   # 구간 끝 속도   [rad/s]

        # ── tracking 모드: 외부 명령 부가 정보 ────────────────────────────
        self._cmd_dq  = [0.0]  * N_AXES
        self._cmd_kp  = [20.0] * N_AXES
        self._cmd_kd  = [0.5]  * N_AXES
        self._cmd_tau = [0.0]  * N_AXES

        # 이벤트 트리거 (GRID → Python Event)
        self._idle_ev          = threading.Event()   # JogMode=0 & PauseMode=0 전환
        # [자세/액션 이벤트]
        self._sitting_ev       = threading.Event()   # Sitting → STANDBY 전환
        self._standing_ev      = threading.Event()   # Standing → STANDING 전환
        self._fall_recovery_ev = threading.Event()   # Fall Recovery
        self._jump_ev          = threading.Event()   # 점프 궤적
        self._home_ev          = threading.Event()   # 홈 복귀 (POS, STANDBY 전용)
        self._home_additive_ev = threading.Event()   # 홈 복귀 (ADDITIVE, 비STANDBY)
        self._movel_ev         = threading.Event()   # moveL
        self._force_t_active   = False        # forceT 활성 플래그 (signal=1 → True, 0 → False)
        self._force_grf_active = False        # GRF 피드백 포함 여부: True=tau_dyn+tau_grf / False=tau_dyn only
        self.force_t_ref       = np.zeros(3)  # forceT 목표 GRF [N] (힙 원점 기준, 초기=0 → GRF 상쇄)
        self._force_s_active   = False        # forceS 임피던스 토글

        # 궤적 실행 중 힘 제어 게인 — 외부/콜백에서 직접 설정 (0 = 비활성)
        self.kp_imp = np.zeros(3)   # Cartesian 강성 게인 [N/m]
        self.kd_imp = np.zeros(3)   # Cartesian 감쇠 게인 [N·s/m]
        self.kf_grf = np.zeros(3)   # GRF 피드백 게인
        self._gait_ev          = threading.Event()   # Gait

        # moveL 목표 좌표 (힙 원점 기준, [m])  — 외부에서 set_movel_target()으로 설정
        self._movel_target: list = None   # (Px, Py, Pz)  or  [(Px,Py,Pz), ...]

        # gait 시작점/끝점 (힙 원점 기준, [m])  — 외부에서 set_gait_waypoints()으로 설정
        # None 이면 _run_gait() 에서 p_cur ± GAIT_STEP_X 로 자동 계산
        self._gait_p_start: tuple = None  # (Px, Py, Pz)
        self._gait_p_end:   tuple = None  # (Px, Py, Pz)

        self._waypoints: list = []   # start()에서 로드; 접근 전 초기화 보장

        # EXEC_TRAJ 큐
        self._traj_queue     = deque()
        self._cart_queue     = deque()
        self._traj_dt_active = TRAJ_DT_DEFAULT
        self._traj_label     = ''
        self._traj_t0        = 0.0
        self._traj_idx       = 0
        self._traj_done_ev   = threading.Event()

        # FORCE_T/S_IDLE 기준 위치
        self._stance_q_r_mcx = [0.0] * N_AXES
        self._stance_x_r     = np.zeros(3)

        # 제어 루프 스레드 시작
        self._control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self._control_thread.start()

    # ── 프로퍼티 ─────────────────────────────────────────────────────────────
    @property
    def in_movel(self) -> bool:
        return self._ctrl_state == 'EXEC_TRAJ'

    @property
    def last_cmd_positions(self) -> list:
        with self._lock:
            return list(self._last_cmd_pos)

    # ── moveL 목표 좌표 설정 ──────────────────────────────────────────────────
    def set_movel_target(self, target):
        """
        moveLEvent 트리거 전에 호출하여 목표 좌표를 설정.
        target : (Px, Py, Pz) [m]  or  [(Px,Py,Pz), ...]  (힙 원점 기준)
        """
        if target is not None and not isinstance(target[0], (list, tuple)):
            target = [target]   # 단일 점 → 리스트로 통일
        with self._lock:
            self._movel_target = target

    # ── gait 시작점/끝점 설정 ─────────────────────────────────────────────────
    def set_gait_waypoints(self, p_start, p_end):
        """
        gaitEvent 트리거 전에 호출하여 Bezier 발걸음의 시작점·끝점을 설정.
        p_start, p_end : (Px, Py, Pz) [m]  (힙 원점 기준)
        None 전달 시 해당 점을 p_cur ± GAIT_STEP_X 자동 계산으로 복귀.
        """
        with self._lock:
            self._gait_p_start = tuple(p_start) if p_start is not None else None
            self._gait_p_end   = tuple(p_end)   if p_end is not None else None

    # ── 초기 위치 설정 (MCX joint offset 기준) ───────────────────────────────
    def set_initial_positions(self, positions: list):
        """
        MCX joint offset에서 읽은 값을 제어 루프 초기 위치로 설정.
        _control_loop 시작 전 (연결 완료 후 1회) 호출해야 함.
        """
        with self._lock:
            self._last_cmd_pos  = list(positions[:N_AXES])
            self._interp_prev   = list(positions[:N_AXES])
            self._interp_target = list(positions[:N_AXES])
            self._interp_dq0    = [0.0] * N_AXES
            self._interp_dq1    = [0.0] * N_AXES

    # ── jump / home 이벤트 루프 시작 ──────────────────────────────────────────
    def start(self, log_cb=None) -> int:
        """
        궤적 로드 + 전체 이벤트 구독 + 이벤트 루프 스레드 시작.
        연결 완료 후 1회 호출.
        반환: waypoint 수
        """
        waypoints = load_trajectory(self.traj_file)
        self._waypoints = waypoints
        time.sleep(0.01)
        # 이전 세션에서 남은 값 초기화 (구독 전 리셋 — 초기값 즉시 발화 방지)
        self._mcx.reset_sitting_event()
        self._mcx.reset_standing_event()
        self._mcx.reset_rl_trot_event()
        self._mcx.reset_fall_recovery_event()
        self._mcx.reset_jump_event()
        self._mcx.reset_home_event()
        self._mcx.reset_home_additive_event()
        self._mcx.reset_movel_event()
        self._mcx.reset_force_s_event()
        self._mcx.reset_force_t_event()
        self._mcx.reset_force_f_event()
        self._mcx.reset_gait_event()

        # 이벤트 구독
        self._mcx.subscribe_idle_mode(self._on_idle_mode, self._on_busy_mode)
        # [자세/모드 이벤트]
        self._mcx.subscribe_sitting_event(self._on_sitting)
        self._mcx.subscribe_standing_event(self._on_standing)
        self._mcx.subscribe_rl_trot_event(self._on_rl_trot)
        self._mcx.subscribe_fall_recovery_event(self._on_fall_recovery)
        # [액션 이벤트]
        self._mcx.subscribe_jump_event(self._on_jump)
        self._mcx.subscribe_home_event(self._on_home)
        self._mcx.subscribe_home_additive_event(self._on_home_additive)
        self._mcx.subscribe_movel_event(self._on_movel)
        self._mcx.subscribe_force_s_event(self._on_force_s)
        self._mcx.subscribe_force_t_event(self._on_force_t_start, self._on_force_t_stop)
        self._mcx.subscribe_force_f_event(self._on_force_f_start, self._on_force_f_stop)
        self._mcx.subscribe_gait_event(self._on_gait)

        self._event_thread = threading.Thread(
            target=self._event_loop, args=(log_cb,), daemon=True
        )
        self._event_thread.start()

        return len(waypoints)

    # ── 이벤트 콜백 (MCX GRID → Python Event) ────────────────────────────────
    def _on_idle_mode(self):
        self._mcx.reset_additive()
        with self._lock:
            self._traj_queue.clear()
            self._cart_queue.clear()
            self._last_cmd_pos  = [0.0] * N_AXES
            self._interp_prev   = [0.0] * N_AXES
            self._interp_target = [0.0] * N_AXES
            self._interp_dq0    = [0.0] * N_AXES
            self._interp_dq1    = [0.0] * N_AXES
        self._ctrl_state = 'STANDBY'
        self._traj_done_ev.set()
        self._idle_ev.set()

    def _on_busy_mode(self):
        with self._lock:
            self._traj_queue.clear()
            self._cart_queue.clear()
        self._traj_done_ev.set()
        self._idle_ev.clear()
        self._ctrl_state = 'STANDBY'

    def _on_sitting(self):
        """Sitting 이벤트 → STANDBY 전환 트리거."""
        self._sitting_ev.set()
        self._mcx.reset_sitting_event()

    def _on_standing(self):
        """Standing 이벤트 → standing 동작 트리거."""
        self._standing_ev.set()
        self._mcx.reset_standing_event()

    def _on_rl_trot(self):
        """RL_trot 이벤트 → RL_POLICY 상태 전환 (STANDING에서만)."""
        if self._ctrl_state == 'STANDING':
            self._ctrl_state = 'RL_POLICY'
        self._mcx.reset_rl_trot_event()

    def _on_fall_recovery(self):
        """Fall Recovery 이벤트 → 뼈대 (상세 구현 추후)."""
        self._fall_recovery_ev.set()
        self._mcx.reset_fall_recovery_event()

    def _on_jump(self):
        """jump=1 수신 — EXEC_TRAJ / HOME / RL_POLICY 중이 아닐 때만 트리거."""
        if self._ctrl_state not in ('EXEC_TRAJ', 'HOME', 'RL_POLICY'):
            self._jump_ev.set()

    def _on_home(self):
        if self._ctrl_state not in ('HOME', 'STANDING', 'RL_POLICY', 'FORCE_T_IDLE', 'FORCE_S_IDLE'):
            self._home_ev.set()

    def _on_home_additive(self):
        if self._ctrl_state != 'HOME':
            if self._ctrl_state == 'EXEC_TRAJ':
                with self._lock:
                    self._traj_queue.clear()
                    self._cart_queue.clear()
                self._traj_done_ev.set()
            self._ctrl_state = 'HOME'
            self._home_additive_ev.set()

    def _on_movel(self):
        if self._ctrl_state not in ('EXEC_TRAJ', 'HOME'):
            self._movel_ev.set()

    def _on_force_s(self):
        """forceS 버튼: moveL 임피던스 모드 ON/OFF 토글."""
        self._force_s_active = not self._force_s_active
        if self._force_s_active:
            self.kp_imp = KP_IMP.copy()
            self.kd_imp = KD_IMP.copy()
        else:
            self.kp_imp = np.zeros(3)
            self.kd_imp = np.zeros(3)
        self._mcx.reset_force_s_event()

    def _on_force_t_start(self):
        """forceT=1 수신 — GRF 제어 시작 (동작 중에도 즉시 활성)."""
        self._force_t_active = True
        self._mcx.reset_force_t_event()

    def _on_force_t_stop(self):
        """forceT=0 수신 — GRF 제어 종료."""
        self._force_t_active = False
        self._force_grf_active = False
        self.kf_grf = np.zeros(3)

    def _on_force_f_start(self):
        """forceF=1 수신 — forceT 활성 시에만 GRF 피드백 ON."""
        if not self._force_t_active:
            self._mcx.reset_force_f_event()
            return
        self._force_grf_active = True
        self.kf_grf = KF_GRF.copy()
        self._mcx.reset_force_f_event()

    def _on_force_f_stop(self):
        """forceF=0 수신 — GRF 피드백 OFF (tau_dyn only)."""
        self._force_grf_active = False
        self.kf_grf = np.zeros(3)

    def _on_gait(self):
        if self._ctrl_state not in ('EXEC_TRAJ', 'HOME'):
            self._gait_ev.set()

    def _event_loop(self, log_cb=None):
        while True:
            # ── IdleMode 대기 (JogMode=0 & PauseMode=0) ───────────────────────
            if not self._idle_ev.is_set():
                if log_cb:
                    log_cb('JogMode/PauseMode 대기 중...')
                self._idle_ev.wait()
                self._ctrl_state = 'STANDBY'
                if log_cb:
                    log_cb('제어권 획득 — 이벤트 수신 대기 중')

            # ── [정상 운용] Sitting → STANDBY ──────────────────────────────────
            if self._sitting_ev.is_set():
                self._sitting_ev.clear()
                self._ctrl_state = 'STANDBY'
                if log_cb:
                    log_cb('Sitting: STANDBY 전환 (궤적 TODO)')
                # TODO: sitting 궤적 실행

            # ── [정상 운용] Standing → STANDING ────────────────────────────────
            elif self._standing_ev.is_set():
                self._standing_ev.clear()
                self._ctrl_state = 'STANDING'
                if log_cb:
                    log_cb('Standing: STANDING 전환 (궤적 TODO)')
                # TODO: standing 궤적 실행

            # ── [정상 운용] Fall Recovery → STANDBY ────────────────────────────
            elif self._fall_recovery_ev.is_set():
                self._fall_recovery_ev.clear()
                self._ctrl_state = 'STANDBY'
                if log_cb:
                    log_cb('Fall Recovery: STANDBY 복귀 (궤적 TODO)')
                # TODO: fall recovery 궤적 실행

            # ── [Leg_test] Home (POS, STANDBY 전용) ────────────────────────────
            elif self._home_ev.is_set():
                self._home_ev.clear()
                if log_cb:
                    log_cb('Home(POS): POS 직접 명령으로 홈 복귀')
                self.move_to_home(log_cb=log_cb)
                self._ctrl_state = 'STANDBY'
                self._mcx.reset_home_event()
                time.sleep(0.05)
                self._home_ev.clear()

            # ── [Leg_test] Home Additive (ADDITIVE, 비STANDBY) ─────────────────
            elif self._home_additive_ev.is_set():
                self._home_additive_ev.clear()
                if log_cb:
                    log_cb('Home(ADDITIVE): ADDITIVE 명령으로 홈 복귀')
                self.move_to_home_additive(log_cb=log_cb)
                self._mcx.reset_home_additive_event()
                time.sleep(0.05)
                self._home_additive_ev.clear()

            # ── [Leg_test] Jump ─────────────────────────────────────────────────
            elif self._jump_ev.is_set():
                self._jump_ev.clear()
                if log_cb:
                    log_cb('Jump: 점프 궤적 실행')
                self._load_exec_traj(self._waypoints, self.traj_dt, 'jump', log_cb=log_cb)
                self._traj_done_ev.wait()
                if log_cb:
                    log_cb('jump 완료.')
                self._mcx.reset_jump_event()
                time.sleep(0.05)
                self._jump_ev.clear()

            # ── [Leg_test] Gait ─────────────────────────────────────────────────
            elif self._gait_ev.is_set():
                self._gait_ev.clear()
                if log_cb:
                    log_cb('Gait: Bezier 발걸음 패턴 실행')
                self._run_gait(log_cb=log_cb)
                #self._run_gait2(log_cb=log_cb)
                self._mcx.reset_gait_event()
                time.sleep(0.05)
                self._gait_ev.clear()

            # ── [Leg_test] moveL ────────────────────────────────────────────────
            elif self._movel_ev.is_set():
                self._movel_ev.clear()
                actual_j_mcx = self._mcx.actual_positions
                actual_j_phy = _to_phy(actual_j_mcx)
                p_cur        = np.array(forward_kinematics(actual_j_phy)[-1])
                phi          = actual_j_phy[1] + actual_j_phy[2] + actual_j_phy[3]
                with self._lock:
                    self._last_cmd_pos = list(actual_j_mcx)
                    x_target = self._movel_target[0] if self._movel_target \
                        else (p_cur[0] + MOVEL_STEP_X, p_cur[1], p_cur[2] + MOVEL_STEP_Z)
                if log_cb:
                    log_cb(
                        f'moveL(quintic, φ={math.degrees(phi):.1f}°): '
                        f'target=({x_target[0]*1e3:.1f},'
                        f'{x_target[1]*1e3:.1f},{x_target[2]*1e3:.1f})mm'
                    )
                self.move_l(x_target, phi=phi, log_cb=log_cb)
                self._mcx.reset_movel_event()
                time.sleep(0.05)
                self._movel_ev.clear()

            elif self._force_t_active:
                self._run_force_t_idle(log_cb=log_cb)
                time.sleep(0.001)

            elif self._force_s_active:
                self._run_force_s_idle(log_cb=log_cb)
                time.sleep(0.001)

            else:
                time.sleep(0.01)


    # ── forceT idle: 현재 위치 기준 GRF 제어 ────────────────────────────────
    def _run_force_t_idle(self, log_cb=None):
        """
        forceT 활성 시 stance 위치 기준 GRF 제어.
        _control_loop의 FORCE_T_IDLE 상태로 위임 — 실제 200Hz 루프는 _control_loop가 실행.
        non-blocking: stance 초기화 후 즉시 반환 — event_loop가 계속 이벤트를 처리.
        """
        if self._ctrl_state == 'FORCE_T_IDLE':
            return

        q_a_phy = _to_phy(self._mcx.actual_positions)
        x_r     = np.array(forward_kinematics(q_a_phy)[-1])
        phi     = q_a_phy[1] + q_a_phy[2] + q_a_phy[3]

        q_r_phy = analytical_ik(x_r[0], x_r[1], x_r[2], phi)
        if q_r_phy is None:
            if log_cb:
                log_cb('forceT idle: IK 실패 — 중단')
            return

        self._stance_q_r_mcx = _to_mcx(q_r_phy)
        self._stance_x_r     = x_r

        if log_cb:
            log_cb(
                f'forceT idle 시작: '
                f'({x_r[0]*1e3:.1f}, {x_r[1]*1e3:.1f}, {x_r[2]*1e3:.1f}) mm'
                f'  GRF={"ON" if self._force_grf_active else "OFF"}'
            )

        self._ctrl_state = 'FORCE_T_IDLE'

    # ── IK 루프 공통 헬퍼 ────────────────────────────────────────────────────
    def _ik_trajectory(self, cart_pts, phi: float, prev_phy: list,
                       log_cb=None, label: str = 'IK') -> list:
        """cart_pts(Cartesian 위치 목록) → MCX offset 관절각 목록. IK 실패 시 이전 해 유지."""
        dense_j = []
        for pt in cart_pts:
            r = analytical_ik(float(pt[0]), float(pt[1]), float(pt[2]), phi)
            if r is None:
                if log_cb:
                    log_cb(f'{label} IK 실패: ({pt[0]*1e3:.1f},{pt[1]*1e3:.1f},{pt[2]*1e3:.1f})mm')
                r = prev_phy
            prev_phy = r
            dense_j.append(_to_mcx(r))
        return dense_j

    # ── forceS idle: 현재 위치 임피던스 유지 ────────────────────────────────────
    def _run_force_s_idle(self, log_cb=None):
        """
        forceS 단독 활성 시 stance 위치 기준 임피던스 루프.
        _control_loop의 FORCE_S_IDLE 상태로 위임.
        non-blocking: stance 초기화 후 즉시 반환 — event_loop가 계속 이벤트를 처리.
        """
        if self._ctrl_state == 'FORCE_S_IDLE':
            return

        q_a_phy = _to_phy(self._mcx.actual_positions)
        x_r     = np.array(forward_kinematics(q_a_phy)[-1])
        phi     = q_a_phy[1] + q_a_phy[2] + q_a_phy[3]

        q_r_phy = analytical_ik(x_r[0], x_r[1], x_r[2], phi)
        if q_r_phy is None:
            if log_cb:
                log_cb('forceS idle: IK 실패 — 중단')
            return

        self._stance_q_r_mcx = _to_mcx(q_r_phy)
        self._stance_x_r     = x_r

        if log_cb:
            log_cb(
                f'forceS idle 시작: '
                f'({x_r[0]*1e3:.1f}, {x_r[1]*1e3:.1f}, {x_r[2]*1e3:.1f}) mm'
            )

        self._ctrl_state = 'FORCE_S_IDLE'

    # ── 궤적 큐 적재 (비차단) ────────────────────────────────────────────────
    def _load_exec_traj(self, waypoints, dt: float, label: str,
                        cartesian_refs=None, log_cb=None):
        """비차단: 큐 적재 후 EXEC_TRAJ 전환. 완료는 _traj_done_ev로 통보."""
        wps = list(waypoints)
        crs = list(cartesian_refs) if cartesian_refs is not None else []
        if log_cb:
            log_cb(f'{label} 큐 적재 ({len(wps)} pts / dt={dt*1e3:.1f}ms)')
        self._traj_done_ev.clear()
        with self._lock:
            self._traj_queue     = deque(wps)
            self._cart_queue     = deque(crs)
            self._traj_dt_active = dt
            self._traj_label     = label
            self._traj_idx       = 0
        self._ctrl_state = 'EXEC_TRAJ'

    # ── gait: Bezier 발걸음 패턴 ─────────────────────────────────────────────
    def _run_gait(self, log_cb=None):
        """
        Bezier 발걸음 패턴 (blocking): p_cur → +x → +z(peak) → −x.
        forceS(_force_s_active) 플래그를 실시간 체크 — gait 실행 중 forceS ON/OFF 가능.
        """
        actual_j_mcx = self._mcx.actual_positions
        actual_j_phy = _to_phy(actual_j_mcx)
        p_cur = np.array(forward_kinematics(actual_j_phy)[-1])
        phi   = actual_j_phy[1] + actual_j_phy[2] + actual_j_phy[3]
        with self._lock:
            self._last_cmd_pos = list(actual_j_mcx)
            gp_start = self._gait_p_start
            gp_end   = self._gait_p_end

        p_start    = np.array(gp_start) if gp_start is not None \
            else p_cur.copy()
        p_end      = np.array(gp_end)   if gp_end is not None \
            else np.array([p_cur[0], p_cur[1], p_cur[2] + GAIT_STEP_Z])

        p_start_up = np.array([p_start[0] + GAIT_STEP_X, p_start[1], p_start[2]])
        p_end_up   = np.array([p_end[0]   + GAIT_STEP_X, p_end[1],   p_end[2]])
        ctrl_pts   = [p_start, p_start_up, p_end_up, p_end]
        chord     = sum(np.linalg.norm(ctrl_pts[i + 1] - ctrl_pts[i])
                        for i in range(len(ctrl_pts) - 1))
        dt        = self.traj_dt
        n         = max(10, int(chord / (MOVEL_VEL * dt)))
        bezier_pts = _bezier_curve(ctrl_pts, n)

        dense_j = self._ik_trajectory(bezier_pts, phi, actual_j_phy, log_cb=log_cb, label='gait')

        if log_cb:
            log_cb(
                f'gait step (φ={math.degrees(phi):.1f}°): '
                f'{n}pts / chord={chord*1e3:.1f}mm / dt={dt*1e3:.1f}ms'
            )

        self._load_exec_traj(dense_j, dt, 'gait', cartesian_refs=bezier_pts, log_cb=log_cb)
        self._traj_done_ev.wait()

    # ── gait2: 5차 Bezier 2단계 + forceS δ 임피던스 ─────────────────────────
    def _run_gait2(self, log_cb=None):
        """
        5차 Bezier 발걸음 — 6페이즈 게인 스케줄링 (blocking).
          Leave-off  : KP=0,   KD=0,    KF=0
          Mid Swing  : KP=0,   KD=0,    KF=0
          Late Swing : KP=낮음, KD=중간, KF=0
          Touch-down : KP=낮음, KD=높음, KF=0
          Mid Stance : KP=0,   KD=0,    KF=높음
          Pre-Swing  : KP=낮음, KD=높음, KF=낮음
        """
        actual_j_mcx = self._mcx.actual_positions
        actual_j_phy = _to_phy(actual_j_mcx)
        p_cur = np.array(forward_kinematics(actual_j_phy)[-1])
        phi   = actual_j_phy[1] + actual_j_phy[2] + actual_j_phy[3]
        with self._lock:
            self._last_cmd_pos = list(actual_j_mcx)
            gp_start = self._gait_p_start
            gp_end   = self._gait_p_end

        p_start = np.array(gp_start) if gp_start is not None else p_cur.copy()
        p_end   = np.array(gp_end)   if gp_end is not None \
            else np.array([p_cur[0], p_cur[1], p_cur[2] + GAIT_STEP_Z])

        p_peak = np.array([p_start[0] + GAIT_STEP_X, p_start[1],
                           (p_start[2] + p_end[2]) / 2])

        # ── 경유점 정의 ──────────────────────────────────────────────────────
        p_start_imp = np.array([p_start[0] + GAIT_IMP_DELTA, p_start[1], p_start[2]])
        p_sw_mid    = np.array([p_start[0] + GAIT_STEP_X * 0.5, p_start[1],
                                p_start[2] + (p_peak[2] - p_start[2]) * 0.5])
        p_td        = p_peak + 0.25 * (p_end - p_peak)
        p_ms        = p_peak + 0.65 * (p_end - p_peak)
        p_end_imp   = np.array([p_end[0] + GAIT_IMP_DELTA, p_end[1], p_end[2]])

        dt   = self.traj_dt
        _z   = np.zeros(3)

        def _set_gains(kp, kd, kf):
            self.kp_imp = kp.copy()
            self.kd_imp = kd.copy()
            self.kf_grf = kf.copy()

        def _run_seg(ctrl, label, j_phy):
            chord = sum(np.linalg.norm(ctrl[i+1] - ctrl[i]) for i in range(len(ctrl)-1))
            n = max(10, int(chord / (MOVEL_VEL * dt)))
            pts = _bezier_curve(ctrl, n)
            dense_j = self._ik_trajectory(pts, phi, j_phy, log_cb=log_cb, label=label)
            if log_cb:
                log_cb(f'{label}: {n}pts / chord={chord*1e3:.1f}mm')
            self._load_exec_traj(dense_j, dt, label, cartesian_refs=pts, log_cb=log_cb)
            self._traj_done_ev.wait()
            return _to_phy(self._mcx.actual_positions)

        # ── Leave-off (KP=0, KD=0, KF=0) ────────────────────────────────────
        _set_gains(_z, _z, _z)
        cur = _run_seg([p_start, p_start_imp], 'leave_off', actual_j_phy)

        # ── Mid Swing (KP=0, KD=0, KF=0) ─────────────────────────────────────
        c1 = np.array([p_start_imp[0] + GAIT_STEP_X * 0.3, p_start_imp[1], p_start_imp[2]])
        _set_gains(_z, _z, _z)
        cur = _run_seg([p_start_imp, c1, p_sw_mid], 'mid_swing', cur)

        # ── Late Swing (KP=낮음, KD=중간, KF=0) ──────────────────────────────
        c2 = np.array([p_sw_mid[0] + GAIT_STEP_X * 0.3, p_sw_mid[1],
                       p_sw_mid[2] + (p_peak[2] - p_sw_mid[2]) * 0.7])
        _set_gains(GAIT_KP_LOW, GAIT_KD_MID, _z)
        cur = _run_seg([p_sw_mid, c2, p_peak], 'late_swing', cur)

        # ── Touch-down (KP=낮음, KD=높음, KF=0) ──────────────────────────────
        c3 = np.array([p_td[0], p_td[1], p_peak[2] - (p_peak[2] - p_td[2]) * 0.5])
        _set_gains(GAIT_KP_LOW, GAIT_KD_HIGH, _z)
        cur = _run_seg([p_peak, c3, p_td], 'touch_down', cur)

        # ── Mid Stance (KP=0, KD=0, KF=높음) ─────────────────────────────────
        _set_gains(_z, _z, GAIT_KF_HIGH)
        cur = _run_seg([p_td, p_ms], 'mid_stance', cur)

        # ── Pre-Swing (KP=낮음, KD=높음, KF=낮음) ────────────────────────────
        _set_gains(GAIT_KP_LOW, GAIT_KD_HIGH, GAIT_KF_LOW)
        cur = _run_seg([p_ms, p_end_imp, p_end], 'pre_swing', cur)

        # ── 게인 리셋 ─────────────────────────────────────────────────────────
        _set_gains(_z, _z, _z)

    # ── 궤적 실행 공통 내부 함수 ──────────────────────────────────────────────
    def load_trajectory(self) -> list:
        return load_trajectory(self.traj_file)

    # ── 단일 200Hz 제어 루프 (상태 머신) ─────────────────────────────────────
    def _control_loop(self):
        """
        STANDBY       → last_cmd_pos 유지 (set_target_positions)
        STANDING      → last_cmd_pos 유지 (RL_POLICY / EXEC_TRAJ 대기)
        RL_POLICY     → set_command() 50Hz 입력을 200Hz 선형 보간
        EXEC_TRAJ     → home_ev 감지 시 queue 클리어
                         wp 소모 → set_pos_and_torque(wp, tau)
                         큐 소진 → STANDBY + traj_done_ev.set()
        FORCE_T_IDLE  → force_t_active=False → 토크 0, STANDBY
                         force_t_active=True  → GRF 임피던스 제어
        FORCE_S_IDLE  → force_s_active=False → 토크 0, STANDBY
                         force_s_active=True  → 임피던스 제어
        HOME          → move_to_home_additive()가 event_loop 스레드에서 직접 제어
                         완료 시 STANDBY
        """
        zero_torque = [0.0] * N_AXES
        x_a_prev    = np.zeros(3)
        prev_state  = None

        while True:
            t_next = time.monotonic() + HOLD_CYCLE

            if not self._mcx.is_connected:
                slack = t_next - time.monotonic()
                if slack > 0:
                    time.sleep(slack)
                continue

            state = self._ctrl_state

            if state != prev_state:
                try:
                    x_a_prev = _fun_force_f(_to_phy(self._mcx.actual_positions))[0]
                except Exception:
                    x_a_prev = np.zeros(3)
                prev_state = state

            # ── STANDBY ──────────────────────────────────────────────────
            if state == 'STANDBY':
                with self._lock:
                    positions = list(self._last_cmd_pos)
                try:
                    self._mcx.set_target_positions(positions)
                except Exception:
                    pass

            # ── STANDING ─────────────────────────────────────────────────
            elif state == 'STANDING':
                with self._lock:
                    positions = list(self._last_cmd_pos)
                try:
                    self._mcx.set_target_positions(positions)
                except Exception:
                    pass

            # ── RL_POLICY ─────────────────────────────────────────────────
            elif state == 'RL_POLICY':
                with self._lock:
                    elapsed   = time.monotonic() - self._interp_time
                    s         = min(elapsed / CMD_PERIOD, 1.0)
                    positions = _hermite_pos(
                        s, CMD_PERIOD,
                        self._interp_prev, self._interp_target,
                        self._interp_dq0,  self._interp_dq1,
                    )
                try:
                    self._mcx.set_target_positions(positions)
                except Exception:
                    pass

            # ── EXEC_TRAJ ────────────────────────────────────────────────
            elif state == 'EXEC_TRAJ':
                if self._home_ev.is_set() and self._traj_label != 'homePos':
                    with self._lock:
                        self._traj_queue.clear()
                        self._cart_queue.clear()
                    wp = None
                else:
                    with self._lock:
                        if self._traj_queue:
                            wp       = list(self._traj_queue.popleft())
                            x_r_cart = self._cart_queue.popleft() if self._cart_queue else None
                            dt       = self._traj_dt_active
                            self._traj_idx += 1
                        else:
                            wp = None

                if wp is None:
                    self._mcx.set_target_torques(zero_torque)
                    with self._lock:
                        self._interp_prev   = list(self._last_cmd_pos)
                        self._interp_target = list(self._last_cmd_pos)
                    self._ctrl_state = 'STANDBY'
                    self._traj_done_ev.set()
                else:
                    kp = self.kp_imp
                    kd = self.kd_imp
                    kf = self.kf_grf

                    if np.any(kp) or np.any(kd) or np.any(kf):
                        x_r             = (np.asarray(x_r_cart) if x_r_cart is not None
                                           else np.array(forward_kinematics(_to_phy(wp))[-1]))
                        q_now_phy       = _to_phy(self._mcx.actual_positions)
                        x_a, J, tau_dyn = _fun_force_f(q_now_phy)
                        dx_a            = (x_a - x_a_prev) / dt
                        x_a_prev        = x_a.copy()

                        f_cart = kp * (x_r - x_a) - kd * dx_a
                        if np.any(kf):
                            grf_est = compute_grf(self._mcx.actual_torque, tau_dyn, J)
                            f_cart += kf * (self.force_t_ref - grf_est)
                        tau = (tau_dyn + J.T @ f_cart).tolist()
                    else:
                        q_now_phy = _to_phy(self._mcx.actual_positions)
                        x_a_prev  = np.array(forward_kinematics(q_now_phy)[-1])
                        tau       = zero_torque

                    self._mcx.set_pos_and_torque(wp, tau)
                    with self._lock:
                        self._last_cmd_pos = wp

            # ── FORCE_T_IDLE ─────────────────────────────────────────────
            elif state == 'FORCE_T_IDLE':
                if not self._force_t_active:
                    self._mcx.set_target_torques(zero_torque)
                    q_r_mcx = self._stance_q_r_mcx
                    with self._lock:
                        self._last_cmd_pos  = list(q_r_mcx)
                        self._interp_prev   = list(q_r_mcx)
                        self._interp_target = list(q_r_mcx)
                    self._ctrl_state = 'STANDBY'
                else:
                    q_r_mcx         = self._stance_q_r_mcx
                    x_r             = self._stance_x_r
                    q_now_phy       = _to_phy(self._mcx.actual_positions)
                    x_a, J, tau_dyn = _fun_force_f(q_now_phy)
                    dx_a            = (x_a - x_a_prev) / HOLD_CYCLE
                    x_a_prev        = x_a.copy()

                    f_cart = self.kp_imp * (x_r - x_a) - self.kd_imp * dx_a
                    if np.any(self.kf_grf):
                        grf_est = compute_grf(self._mcx.actual_torque, tau_dyn, J)
                        f_cart += self.kf_grf * (self.force_t_ref - grf_est)

                    tau = (tau_dyn + J.T @ f_cart).tolist()
                    self._mcx.set_pos_and_torque(q_r_mcx, tau)

            # ── FORCE_S_IDLE ─────────────────────────────────────────────
            elif state == 'FORCE_S_IDLE':
                if not self._force_s_active:
                    self._mcx.set_target_torques(zero_torque)
                    q_r_mcx = self._stance_q_r_mcx
                    with self._lock:
                        self._last_cmd_pos  = list(q_r_mcx)
                        self._interp_prev   = list(q_r_mcx)
                        self._interp_target = list(q_r_mcx)
                    self._ctrl_state = 'STANDBY'
                else:
                    q_r_mcx         = self._stance_q_r_mcx
                    x_r             = self._stance_x_r
                    q_now_phy       = _to_phy(self._mcx.actual_positions)
                    x_a, J, tau_dyn = _fun_force_f(q_now_phy)
                    dx_a            = (x_a - x_a_prev) / HOLD_CYCLE
                    x_a_prev        = x_a.copy()

                    f_cart = self.kp_imp * (x_r - x_a) - self.kd_imp * dx_a
                    tau = (tau_dyn + J.T @ f_cart).tolist()
                    self._mcx.set_pos_and_torque(q_r_mcx, tau)

            # ── HOME ─────────────────────────────────────────────────────
            elif state == 'HOME':
                pass   # event_loop 스레드의 move_to_home_additive()가 직접 제어

            slack = t_next - time.monotonic()
            if slack > 0:
                time.sleep(slack)

    # ── moveJ ─────────────────────────────────────────────────────────────────
    def move_j(self, joint_waypoints: list, dt: float = None,
               max_vel: float = HOME_MAX_VEL, max_acc: float = HOME_MAX_ACC,
               log_cb=None):
        """
        Joint 공간 moveJ.
        joint_waypoints : list of list[float] [rad]
                          waypoint가 1개이면 현재 위치 → 목표 사다리꼴 프로파일 생성.
                          여러 개이면 순서대로 각 구간을 5차 다항식으로 보간.
        dt              : 전송 주기 [s] (기본 200Hz)
        max_vel / max_acc : 단일 목표점 이동 시 사다리꼴 프로파일 파라미터
        log_cb          : 로그 콜백 fn(str)
        """
        dt = dt if dt is not None else self.traj_dt

        with self._lock:
            current = list(self._last_cmd_pos)

        all_waypoints = [current] + [list(wp) for wp in joint_waypoints]
        dense = []

        for seg_i in range(len(all_waypoints) - 1):
            p0 = all_waypoints[seg_i]
            pf = all_waypoints[seg_i + 1]
            dists = [abs(pf[i] - p0[i]) for i in range(N_AXES)]
            max_dist = max(dists) if max(dists) > 0 else 1e-6

            # 사다리꼴 프로파일로 구간 시간 결정
            profile = trapezoid_profile(max_dist, max_vel, max_acc, dt)
            n = len(profile)
            duration = n * dt

            # 각 축을 5차 다항식으로 보간
            segs = [_quintic_segment(p0[i], pf[i], duration, dt)
                    for i in range(N_AXES)]
            n_pts = len(segs[0])
            for k in range(n_pts):
                dense.append([segs[i][k] for i in range(N_AXES)])

        self._load_exec_traj(dense, dt, 'moveJ', log_cb=log_cb)
        self._traj_done_ev.wait()

    # ── moveL ─────────────────────────────────────────────────────────────────
    def move_l(self, x_target, phi: float = None, v0=None, vf=None,
               duration: float = None, dt: float = None, log_cb=None):
        """
        Cartesian 공간 quintic polynomial 직선 이동 (blocking).
        forceS 임피던스 적용 여부는 _force_s_active 플래그로 실시간 제어 (control_loop 내부).

        x_target  : (Px, Py, Pz) [m] — 발끝 목표 좌표 (힙 원점 기준)
        phi       : θ2+θ3+θ4 유지 각도 [rad]. None이면 현재 관절값에서 자동 계산.
        v0, vf    : 시작/끝 발끝 속도 벡터 [m/s] (3,). None이면 0.
        duration  : 이동 시간 [s]. None이면 거리/MOVEL_VEL로 자동 계산.
        dt        : 전송 주기 [s] (기본 200Hz)
        """
        dt = dt if dt is not None else self.traj_dt

        with self._lock:
            current_j_mcx = list(self._last_cmd_pos)
        current_j_phy = _to_phy(current_j_mcx)

        if phi is None:
            phi = current_j_phy[1] + current_j_phy[2] + current_j_phy[3]

        x0     = np.array(forward_kinematics(current_j_phy)[-1], dtype=float)
        xf     = np.asarray(x_target, dtype=float)
        v0_arr = np.zeros(3) if v0 is None else np.asarray(v0, dtype=float)
        vf_arr = np.zeros(3) if vf is None else np.asarray(vf, dtype=float)

        dist = float(np.linalg.norm(xf - x0))
        if duration is None:
            duration = max(dist / MOVEL_VEL, 3 * dt)

        # 각 축 독립 quintic 계수 (3, 6)
        coeffs = np.array([
            _quintic_coeffs(0, duration, x0[i], v0_arr[i], 0.0, xf[i], vf_arr[i], 0.0)
            for i in range(3)
        ])

        n        = max(1, int(round(duration / dt)))
        t_arr    = np.linspace(0, duration, n + 1)[1:]   # t=0 제외, t[-1]=duration
        T_pow    = np.column_stack([t_arr**k for k in range(6)])   # (n, 6)
        cart_pts = list(T_pow @ coeffs.T)                           # list of (3,) ndarray

        dense_j = self._ik_trajectory(cart_pts, phi, current_j_phy, log_cb=log_cb, label='moveL')

        if log_cb:
            log_cb(
                f'moveL(quintic): {n}pts / dist={dist*1e3:.1f}mm'
                f' / T={duration:.2f}s / dt={dt*1e3:.1f}ms'
            )

        self._load_exec_traj(dense_j, dt, 'moveL', cartesian_refs=cart_pts, log_cb=log_cb)
        self._traj_done_ev.wait()

    # ── 홈 복귀 궤적 ─────────────────────────────────────────────────────────────
    def move_to_home_additive(self, max_vel: float = HOME_MAX_VEL,
                     max_acc: float = HOME_MAX_ACC, log_cb=None):
        """
        현재 actual 위치 → [0, 0, 0, 0] additive 위치 명령으로 홈 복귀 (blocking).
        hostInJointAdditivePosition2 사용.

        HomeEvent 발생마다 그 시점의 actual 위치를 기준으로
        사다리꼴 프로파일로 0° 수렴. 완료 후 실측 기반 1회 보정.
        속도는 HOME_SPEED_DEG [°/s] 상수로 조정.
        """
        # HomeEvent 발생 시점 실제 위치 읽기 — 매번 fresh하게 기준점 설정
        start_pos = self._mcx.get_actual_positions_snapshot()
        self._mcx.set_base_pos(start_pos)   # additive 기준 = 현재 위치

        if all(abs(p) < HOME_THRESHOLD_RAD for p in start_pos):
            if log_cb:
                log_cb('홈 복귀: 이미 홈 위치 — 스킵.')
            return

        max_dist = max(abs(p) for p in start_pos)
        profile  = trapezoid_profile(max_dist, max_vel, max_acc, self.traj_dt)
        n_steps  = len(profile)
        t_total  = n_steps * self.traj_dt

        if log_cb:
            log_cb(
                f'홈 복귀 시작: {n_steps} steps / {t_total:.2f}s '
                f'({HOME_SPEED_DEG:.1f}°/s)  '
                + ', '.join(f'j{i+1}={math.degrees(start_pos[i]):+.1f}°→0°'
                            for i in range(N_AXES))
            )

        self._ctrl_state = 'HOME'
        try:
            t0 = time.monotonic()
            for k, p in enumerate(profile):
                # 각 축을 start_pos → 0 비례 보간
                target = [start_pos[i] * (1.0 - p / max_dist) for i in range(N_AXES)]
                self._mcx.set_additive_positions(target)
                with self._lock:
                    self._last_cmd_pos = target

                sleep_t = t0 + (k + 1) * self.traj_dt - time.monotonic()
                if sleep_t > 0:
                    time.sleep(sleep_t)

            # 실측 위치 기반 1회 보정
            time.sleep(0.2)   # 궤적 완료 후 정착 대기
            actual = self._mcx.actual_positions
            correction = [-p for p in actual]
            self._mcx.set_additive_positions(correction, blocking=True)

            # hostInJointPosition2도 0으로 동기화
            self._mcx.set_target_positions([0.0] * N_AXES, blocking=True)
            with self._lock:
                self._last_cmd_pos = [0.0] * N_AXES

        finally:
            with self._lock:
                self._interp_prev   = [0.0] * N_AXES
                self._interp_target = [0.0] * N_AXES
            self._ctrl_state = 'STANDBY'

    # ── 홈 복귀 (POS 직접, STANDBY 전용) ────────────────────────────────────────
    def move_to_home(self, max_vel: float = HOME_MAX_VEL,
                         max_acc: float = HOME_MAX_ACC, log_cb=None):
        """
        STANDBY 상태 전용 POS_CMD_PATH 홈 복귀 (blocking).
        hostInJointPosition2 직접 명령 — additive 계산 없음.
        사다리꼴 프로파일 + 5차 다항식으로 [0,0,0,0] (MCX offset) 수렴.
        """
        if self._ctrl_state != 'STANDBY':
            if log_cb:
                log_cb('move_to_home: STANDBY 상태 아님 — 스킵')
            return

        with self._lock:
            current = list(self._last_cmd_pos)

        if all(abs(p) < HOME_THRESHOLD_RAD for p in current):
            if log_cb:
                log_cb('홈 복귀(POS): 이미 홈 위치 — 스킵.')
            return

        max_dist = max(abs(p) for p in current)
        profile  = trapezoid_profile(max_dist, max_vel, max_acc, self.traj_dt)
        n        = len(profile)
        duration = n * self.traj_dt

        segs  = [_quintic_segment(current[i], 0.0, duration, self.traj_dt)
                 for i in range(N_AXES)]
        n_pts = len(segs[0])
        dense = [[segs[i][k] for i in range(N_AXES)] for k in range(n_pts)]

        if log_cb:
            log_cb(
                f'홈 복귀(POS): {n_pts}pts / {duration:.2f}s '
                f'({HOME_SPEED_DEG:.1f}°/s)  '
                + ', '.join(f'j{i+1}={math.degrees(current[i]):+.1f}°→0°'
                            for i in range(N_AXES))
            )

        self._load_exec_traj(dense, self.traj_dt, 'homePos', log_cb=log_cb)
        self._traj_done_ev.wait()

    # ── tracking 모드: 외부 명령 수신 ─────────────────────────────────────────
    def set_command(self,
                    q:   list,
                    dq:  list = None,
                    kp:  list = None,
                    kd:  list = None,
                    tau: list = None):
        """
        외부 제어기(RL 등) 명령 수신 — tracking 모드에서만 유효.
        보간 시작점을 현재 진행률 기준으로 갱신하여 불연속 방지.

        Parameters
        ----------
        q   : target joint positions  [rad]   (4축, 필수)
        dq  : target joint velocities [rad/s] (선택, 현재 MCX 미지원)
        kp  : position gains                  (선택, 현재 MCX 미지원)
        kd  : velocity gains                  (선택, 현재 MCX 미지원)
        tau : feedforward torques     [Nm]    (선택, 현재 MCX 미지원)
        """
        now = time.monotonic()
        with self._lock:
            # 현재 Hermite 진행률로 시작점·속도 갱신 (C1 연속 보장)
            elapsed = now - self._interp_time
            s = min(elapsed / CMD_PERIOD, 1.0)
            cur_pos = _hermite_pos(
                s, CMD_PERIOD,
                self._interp_prev, self._interp_target,
                self._interp_dq0,  self._interp_dq1,
            )
            cur_vel = _hermite_vel(
                s, CMD_PERIOD,
                self._interp_prev, self._interp_target,
                self._interp_dq0,  self._interp_dq1,
            )
            # 새 구간 끝 속도: RL 명령 차분으로 추정
            new_dq1 = [(q[i] - self._interp_target[i]) / CMD_PERIOD
                       for i in range(N_AXES)]

            self._interp_prev   = cur_pos
            self._interp_dq0    = cur_vel
            self._interp_target = list(q)
            self._interp_dq1    = new_dq1
            self._interp_time   = now

            self._cmd_dq  = list(dq)  if dq  is not None else [0.0]  * N_AXES
            self._cmd_kp  = list(kp)  if kp  is not None else [20.0] * N_AXES
            self._cmd_kd  = list(kd)  if kd  is not None else [0.5]  * N_AXES
            self._cmd_tau = list(tau) if tau is not None else [0.0]  * N_AXES
            self._last_cmd_pos = list(q)

    def get_monitor_snapshot(self) -> list:
        """모니터 로그용: [(tgt_rad, act_rad), ...] for ch0~ch3."""
        actual = self._mcx.actual_positions
        with self._lock:
            return [(self._last_cmd_pos[i], actual[i]) for i in range(N_AXES)]
