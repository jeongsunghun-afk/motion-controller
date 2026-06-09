"""biped_sim.controllers.model — DH + frame transform + foot kinematics/Jacobian.

좌표계 변환 (user 제공):
    {Base} → {HL}: x=-0.225, y=+0.0225, Rotz(180°) → Roty(-90°)
    {Base} → {HR}: x=-0.225, y=-0.0225, Rotz(180°) → Roty(-90°)

DH 파라미터 (standard DH, HL 기준; HR 좌우 대칭으로 동일 적용):
    i  α_i      a_i     d_i      θ_i (home)
    1  π/2      0.0     0.115    0        ← HL_hip_joint     (axis x, hip roll)
    2  0        0.230   0        160°     ← HL_thigh_joint   (axis y, hip pitch)
    3  0        0.245   0        50°      ← HL_calf_joint    (axis y, knee)
    4  0        0.180   0        -50°     ← HL_foot_joint    (axis y, ankle)
    5  0        0.0     0        -160°    ← HL_foot_contact_joint (fixed)

Joint angle convention:
    q_robot = q_URDF + θ_home    (robot encoder angle)
    URDF q=0 (모두) = robot home pose (그림의 standing 자세)

j5 (foot_contact) 는 fixed orientation; controller 는 j1~j4 (4 actuated) 만 사용.
"""
import numpy as np


# ── 상수 ─────────────────────────────────────────────────────────────────────
DEG = np.pi / 180.0

# DH (alpha, a, d, theta_home_deg)
DH_HL = [
    (np.pi/2,  0.000, +0.115,    0.0),
    (0.0,      0.230,  0.000,  160.0),
    (0.0,      0.245,  0.000,   50.0),
    (0.0,      0.180,  0.000,  -50.0),
    (0.0,      0.000,  0.000, -160.0),    # foot_contact (fixed)
]
# HR mirror: d_1 부호 반전 (URDF 의 thigh y offset HL=+0.115, HR=-0.115 반영)
DH_HR = [
    (np.pi/2,  0.000, -0.115,    0.0),    # d_1 반전
    (0.0,      0.230,  0.000,  160.0),
    (0.0,      0.245,  0.000,   50.0),
    (0.0,      0.180,  0.000,  -50.0),
    (0.0,      0.000,  0.000, -160.0),
]

# Base→Leg base transform: x=-0.225, y=±0.0225, Rz(180°) Ry(-90°)
BASE_HIP_TX = -0.225
BASE_HL_TY  = +0.0225
BASE_HR_TY  = -0.0225

# joint torque limit — max torque (URDF rated × 3)
# hip_roll 만 임시 200Nm (standing geometry 검증용)
JOINT_TORQUE_LIMIT_BIPED = np.array([200.0, 84.0, 126.0, 168.0])

NJ_PER_LEG = 4    # j1~j4 actuated, j5 fixed


# ── 회전 / 변환 ──────────────────────────────────────────────────────────────
def Rx(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[1, 0,  0],
                     [0, c, -s],
                     [0, s,  c]])

def Ry(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[ c, 0, s],
                     [ 0, 1, 0],
                     [-s, 0, c]])

def Rz(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s, 0],
                     [s,  c, 0],
                     [0,  0, 1]])


def homog(R, p):
    T = np.eye(4)
    T[:3, :3] = R
    T[:3,  3] = p
    return T


def dh_transform(alpha, a, d, theta):
    """Craig modified DH: T_i = Rx(α_{i-1})·Tx(a_{i-1})·Rz(θ_i)·Tz(d_i)."""
    ca, sa = np.cos(alpha), np.sin(alpha)
    ct, st = np.cos(theta), np.sin(theta)
    return np.array([
        [ct,    -st,     0,     a    ],
        [st*ca,  ct*ca, -sa,   -sa*d ],
        [st*sa,  ct*sa,  ca,    ca*d ],
        [0,      0,      0,     1    ],
    ])


# ── Base → Leg base frame ────────────────────────────────────────────────────
def T_base_leg(side):
    """side ∈ {'HL', 'HR'}; returns 4×4 transform from base frame to leg base frame."""
    ty = BASE_HL_TY if side == 'HL' else BASE_HR_TY
    T_tr = homog(np.eye(3), np.array([BASE_HIP_TX, ty, 0.0]))
    T_rz = homog(Rz(np.pi),   np.zeros(3))   # Rotz(180°)
    T_ry = homog(Ry(-np.pi/2), np.zeros(3))  # Roty(-90°)
    return T_tr @ T_rz @ T_ry


# ── Forward kinematics (single leg) ──────────────────────────────────────────
def fk_leg(q_urdf, side='HL'):
    """Forward kinematics for one leg (HL or HR).

    q_urdf : np.ndarray (4,)  — URDF joint angle (URDF zero = robot home)
    side   : 'HL' or 'HR'

    Returns
    -------
    T_base_toe : 4×4  base→toe (foot_contact end) transform
    T_links    : list of 4×4   base→frame_i for i=1..5 (DH frames; frame 5 = toe)
    """
    dh = DH_HL if side == 'HL' else DH_HR
    T = T_base_leg(side)
    T_links = []
    for i in range(5):
        alpha, a, d, theta_home_deg = dh[i]
        # j1~j4 actuated; j5 fixed
        if i < 4:
            theta = q_urdf[i] + theta_home_deg * DEG
        else:
            theta = theta_home_deg * DEG
        T = T @ dh_transform(alpha, a, d, theta)
        T_links.append(T)
    return T_links[-1], T_links


def foot_pos(q_urdf, side='HL'):
    """toe (foot_contact end) position in base frame."""
    T_toe, _ = fk_leg(q_urdf, side)
    return T_toe[:3, 3]


# ── Foot Jacobian (geometric, 3×4 = linear part only) ───────────────────────
def foot_jacobian(q_urdf, side='HL'):
    """Geometric Jacobian (linear part) of toe wrt 4 actuated joints, in base frame.

    Standard formula for revolute joints:
        J_v_i = z_{i-1} × (p_toe - p_{i-1})
    where z_{i-1} is the axis of joint i (z-axis of frame i-1 after DH convention).
    """
    _, T_links = fk_leg(q_urdf, side)
    T_base = T_base_leg(side)
    frames = [T_base] + T_links   # frames[0] = leg base, frames[k] = frame_k after DH_k

    p_toe = T_links[-1][:3, 3]
    J = np.zeros((3, 4))
    for i in range(4):                  # only actuated joints (1..4)
        T_im1 = frames[i]                # frame i-1 (parent of joint i)
        z_im1 = T_im1[:3, 2]             # joint i axis = z of frame i-1 (DH)
        p_im1 = T_im1[:3, 3]
        J[:, i] = np.cross(z_im1, p_toe - p_im1)
    return J


# ── URDF ↔ robot angle convention helpers ───────────────────────────────────
THETA_HOME_RAD = np.array([d * DEG for (_, _, _, d) in DH_HL[:4]])


def robot_q_from_urdf(q_urdf):
    """q_robot = q_urdf + θ_home  (q_urdf : (4,) or (8,))"""
    q = np.asarray(q_urdf)
    if q.size == 8:
        return np.concatenate([q[:4] + THETA_HOME_RAD, q[4:] + THETA_HOME_RAD])
    return q + THETA_HOME_RAD


def urdf_q_from_robot(q_robot):
    """q_urdf = q_robot - θ_home"""
    q = np.asarray(q_robot)
    if q.size == 8:
        return np.concatenate([q[:4] - THETA_HOME_RAD, q[4:] - THETA_HOME_RAD])
    return q - THETA_HOME_RAD


# ══════════════════════════════════════════════════════════════════════════
# mujoco-based kinematics / dynamics (controller 가 sim 과 분리된 MjModel
# 인스턴스 사용하여 mj_jac / mj_fullM / mj_inverse 직접 호출 — URDF 100% 일치)
# ══════════════════════════════════════════════════════════════════════════
import mujoco as _mj


class BipedMjModel:
    """Controller 측에서 사용하는 별도 MjModel/MjData.
    sim 의 mujoco_node 가 publish 하는 /joint_states + /imu 를 받아서
    이 model 의 qpos/qvel 에 set → mj_forward 한 다음 Jacobian/Mass 계산.
    """

    def __init__(self, mjcf_path: str):
        self.model = _mj.MjModel.from_xml_path(mjcf_path)
        self.data  = _mj.MjData(self.model)
        # foot collision body id (Jacobian 의 contact point)
        self._foot_body_id = {
            'HL': _mj.mj_name2id(self.model, _mj.mjtObj.mjOBJ_BODY, 'HL_foot_link'),
            'HR': _mj.mj_name2id(self.model, _mj.mjtObj.mjOBJ_BODY, 'HR_foot_link'),
        }
        self._foot_geom_id = {
            'HL': _mj.mj_name2id(self.model, _mj.mjtObj.mjOBJ_GEOM, 'HL_foot_collision'),
            'HR': _mj.mj_name2id(self.model, _mj.mjtObj.mjOBJ_GEOM, 'HR_foot_collision'),
        }
        # qpos / qvel slicing
        # qpos = [base_pos(3), base_quat(4), q_legs(8)] = 15
        # qvel = [base_vel(3), base_omega(3), qdot_legs(8)] = 14
        self.nq      = self.model.nq
        self.nv      = self.model.nv
        self.nu      = self.model.nu                    # 8
        self.n_legs  = 2
        self.nj_each = 4

    # ── state set ─────────────────────────────────────────────────────────
    def set_state(self, base_pos, base_quat_wxyz, q_legs,
                  base_vel=None, base_omega=None, qdot_legs=None):
        """qpos / qvel set 후 mj_forward 호출."""
        d = self.data
        d.qpos[0:3] = base_pos
        d.qpos[3:7] = base_quat_wxyz
        d.qpos[7:]  = q_legs
        d.qvel[0:3] = np.zeros(3)   if base_vel   is None else base_vel
        d.qvel[3:6] = np.zeros(3)   if base_omega is None else base_omega
        d.qvel[6:]  = np.zeros(8)   if qdot_legs  is None else qdot_legs
        _mj.mj_forward(self.model, self.data)

    # ── foot world position ───────────────────────────────────────────────
    def foot_world(self, side: str):
        return self.data.geom_xpos[self._foot_geom_id[side]].copy()

    # ── foot Jacobian (3 × nv) in world frame ─────────────────────────────
    def foot_jac(self, side: str):
        """발 끝 (foot_collision geom) 의 linear Jacobian (3 × nv = 3×14).
        Layout: J[:, 0:3] = base linear, J[:, 3:6] = base angular,
                J[:, 6:14] = q_legs (HL 0~3, HR 4~7).
        """
        jacp = np.zeros((3, self.nv))
        jacr = np.zeros((3, self.nv))
        _mj.mj_jacGeom(self.model, self.data, jacp, jacr,
                       self._foot_geom_id[side])
        return jacp

    # ── leg-only Jacobian (3 × 4) ─────────────────────────────────────────
    def foot_jac_leg(self, side: str):
        """발 끝 Jacobian 의 leg joint 부분만 (3×4). WBIC 의 per-leg J_legs."""
        Jfull = self.foot_jac(side)
        if side == 'HL':
            return Jfull[:, 6:10]   # HL: qvel index 6~9
        else:
            return Jfull[:, 10:14]  # HR: qvel index 10~13

    # ── full mass matrix (nv × nv) ────────────────────────────────────────
    def mass_full(self):
        M = np.zeros((self.nv, self.nv))
        _mj.mj_fullM(self.model, M, self.data.qM)
        return M

    # ── per-leg mass + bias (h = C·qdot + g) ──────────────────────────────
    def leg_dynamics(self, side: str):
        """per-leg M_i (4×4), h_i (4) — block-diagonal 근사 (WBIC fork 와 호환).
        block 위치: HL = qvel 6~9, HR = qvel 10~13.
        """
        M = self.mass_full()
        h_full = self.data.qfrc_bias.copy()    # C·qdot + g, dim nv
        if side == 'HL':
            sl = slice(6, 10)
        else:
            sl = slice(10, 14)
        Mi = M[sl, sl]
        hi = h_full[sl]
        return Mi, hi

    # ── body 6-DoF info (WBIC 의 v_dot_des_fb, M_total, I_body 등) ─────────
    def body_state(self):
        d = self.data
        body_pos   = d.qpos[0:3].copy()
        body_quat  = d.qpos[3:7].copy()
        body_vlin  = d.qvel[0:3].copy()
        body_omega = d.qvel[3:6].copy()
        # base mass = total subtree mass at body 1 (= base_link)
        M_total = float(np.sum(self.model.body_mass))
        # body inertia (world frame): subtree_inertia 사용 또는 단순 base inertia
        return dict(pos=body_pos, quat=body_quat, vlin=body_vlin, omega=body_omega,
                    M_total=M_total)
