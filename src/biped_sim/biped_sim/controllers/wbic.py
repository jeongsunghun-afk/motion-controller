"""biped_sim.controllers.wbic — biped (2-leg) WBIC QP fork.

gait_sim.controllers.wbic.wbic_qp_full (4-contact quadruped, 58-dim) 의
biped 용 단순화. n_legs=2, nj_per_leg=[4,4], WBIC QP **28-dim**:

    x = [ Δv̇_fb (6); Δq̈ (8); Δτ (8); Δλ (6) ]

비용:
    w_fb·‖Δv̇_fb‖² + w_ddq·‖Δq̈‖² + w_tau·‖Δτ‖² + w_lam·‖Δλ‖²

등식 (6 + 8 = 14):
    body 6-DoF (6):
        M_fb·(v̇_fb_des + Δv̇_fb) = F_des(λ_des) + ΔF(Δλ)
        F_des: linear = Σ λ_des + M·g
               angular = Σ r_i × λ_des_i − ω×(I·ω),  r_i = foot_i − CoM
    per-leg dyn (8):
        M_i·Δq̈_i − Δτ_i − Jᵀ_i·Δλ_i = r_i
        r_i = tau_ff_i + Jᵀ_i·λ_des_i − M_i·ddq_des_i − h_i

부등 / 경계:
    torque limit: τ_min ≤ tau_ff + Δτ ≤ τ_max
    stance: λ_z + Δλ_z ≥ lamz_min
            |λ_x,y + Δλ_x,y| ≤ μ(λ_z + Δλ_z)    (4-pyramid)
    swing : Δλ = -λ_des  (λ=0 고정)
"""
import numpy as np
import qpsolvers


# joint torque limit — max torque (URDF rated × 3)
#   [hip_roll, hip_pitch, knee, ankle]
# hip_roll 만 임시로 200Nm (geometry 문제로 standing 시 큰 부담; user 확인 후)
JOINT_TORQUE_LIMIT_BIPED = np.array([200.0, 84.0, 126.0, 168.0])
G_ACC = 9.81
DEFAULT_QP_SOLVER = 'quadprog'


def _skew(v):
    return np.array([[0.0, -v[2],  v[1]],
                     [v[2],  0.0, -v[0]],
                     [-v[1], v[0], 0.0]])


def wbic_qp_full_biped(
    M_legs,            # list[np.ndarray (4,4)] × 2  per-leg mass matrix
    h_legs,            # list[np.ndarray (4,)] × 2   per-leg bias (C+g)
    ddq_des_legs,      # list[np.ndarray (4,)] × 2   per-leg desired joint accel
    tau_ff_legs,       # list[np.ndarray (4,)] × 2
    lam_des_all,       # np.ndarray (2, 3)           per-leg desired GRF
    J_legs,            # list[np.ndarray (3,4)] × 2  per-leg foot Jacobian (joint-only)
    contact_mask,      # list[bool] × 2              [HL_stance, HR_stance]
    foot_world_all,    # np.ndarray (2, 3)           world-frame foot positions
    body_pos,          # np.ndarray (3,)             body CoM world
    v_dot_des_fb,      # np.ndarray (6,)             desired base accel [lin(3), ang(3)]
    M_total,           # float                       total mass (≈ 7.5 kg)
    I_body,            # np.ndarray (3,3)            body inertia world frame
    omega_world,       # np.ndarray (3,)             body angular vel world
    w_fb=1.0,
    w_ddq=1.0,
    w_tau=1e-3,
    w_lam=1e-3,
    lamz_min=1.0,
    mu=0.6,
    qp_solver=DEFAULT_QP_SOLVER,
):
    """biped WBIC QP — 28-dim."""
    n_legs   = 2
    nj_each  = 4
    nj_total = nj_each * n_legs            # 8

    n_fb  = 6
    n_ddq = nj_total
    n_tau = nj_total
    n_lam = 3 * n_legs                     # 6
    n_v   = n_fb + n_ddq + n_tau + n_lam   # 28

    sl_fb  = slice(0, n_fb)
    sl_ddq = slice(n_fb,          n_fb + n_ddq)
    sl_tau = slice(n_fb + n_ddq,  n_fb + n_ddq + n_tau)
    sl_lam = slice(n_fb + n_ddq + n_tau, n_v)
    leg_off_ddq = [nj_each * i for i in range(n_legs)]
    leg_off_lam = [3 * i for i in range(n_legs)]

    # ── 비용 ────────────────────────────────────────────────────────
    P = np.zeros((n_v, n_v))
    P[sl_fb,  sl_fb]  = w_fb  * np.eye(n_fb)
    P[sl_ddq, sl_ddq] = w_ddq * np.eye(n_ddq)
    P[sl_tau, sl_tau] = w_tau * np.eye(n_tau)
    P[sl_lam, sl_lam] = w_lam * np.eye(n_lam)
    qv = np.zeros(n_v)

    # ── 등식 1: body 6-DoF (6) ──────────────────────────────────────
    M_fb = np.zeros((6, 6))
    M_fb[:3, :3] = M_total * np.eye(3)
    M_fb[3:, 3:] = I_body

    F_lin_des = np.sum(lam_des_all, axis=0) + np.array([0.0, 0.0, -M_total * G_ACC])
    F_ang_des = -np.cross(omega_world, I_body @ omega_world)
    for i in range(n_legs):
        r_i = foot_world_all[i] - body_pos
        F_ang_des += np.cross(r_i, lam_des_all[i])
    F_des = np.concatenate([F_lin_des, F_ang_des])
    rhs_fb = M_fb @ v_dot_des_fb - F_des

    A_eq_fb = np.zeros((6, n_v))
    A_eq_fb[:, sl_fb] = M_fb
    for i in range(n_legs):
        r_i = foot_world_all[i] - body_pos
        col = sl_lam.start + leg_off_lam[i]
        A_eq_fb[:3, col:col+3] += -np.eye(3)
        A_eq_fb[3:, col:col+3] += -_skew(r_i)
    b_eq_fb = -rhs_fb

    # ── 등식 2: per-leg dyn (8) ─────────────────────────────────────
    A_eq_legs = []
    b_eq_legs = []
    residual_legs = np.zeros(n_legs)
    for i in range(n_legs):
        Mi = M_legs[i]; hi = h_legs[i]; Ji = J_legs[i]
        ddq_i = ddq_des_legs[i]; tau_i = tau_ff_legs[i]; lam_i = lam_des_all[i]
        r_i_res = tau_i + Ji.T @ lam_i - Mi @ ddq_i - hi

        Ai = np.zeros((nj_each, n_v))
        s_ddq = sl_ddq.start + leg_off_ddq[i]
        s_tau = sl_tau.start + leg_off_ddq[i]
        s_lam = sl_lam.start + leg_off_lam[i]
        Ai[:, s_ddq : s_ddq + nj_each] = Mi
        Ai[:, s_tau : s_tau + nj_each] = -np.eye(nj_each)
        Ai[:, s_lam : s_lam + 3]       = -Ji.T
        A_eq_legs.append(Ai); b_eq_legs.append(r_i_res)
        residual_legs[i] = float(np.linalg.norm(r_i_res))

    A_eq = np.vstack([A_eq_fb] + A_eq_legs)
    b_eq = np.concatenate([b_eq_fb] + b_eq_legs)

    # ── bounds (torque limit + λ_z) ─────────────────────────────────
    lb = np.full(n_v, -1e8); ub = np.full(n_v, 1e8)
    for i in range(n_legs):
        s_off = sl_tau.start + leg_off_ddq[i]
        lb[s_off : s_off + nj_each] = -JOINT_TORQUE_LIMIT_BIPED - tau_ff_legs[i]
        ub[s_off : s_off + nj_each] =  JOINT_TORQUE_LIMIT_BIPED - tau_ff_legs[i]

    # ── 부등식: 마찰 추 4-pyramid (stance) + swing 고정 ───────────────
    G_rows = []; h_rows = []
    for i in range(n_legs):
        l_off = sl_lam.start + leg_off_lam[i]
        if contact_mask[i]:
            lb[l_off + 2] = max(lb[l_off + 2], lamz_min - lam_des_all[i, 2])
            for sgn_x, sgn_y in [(+1, 0), (-1, 0), (0, +1), (0, -1)]:
                row = np.zeros(n_v)
                row[l_off + 0] = sgn_x
                row[l_off + 1] = sgn_y
                row[l_off + 2] = -mu
                rhs = mu * lam_des_all[i, 2] - sgn_x * lam_des_all[i, 0] - sgn_y * lam_des_all[i, 1]
                G_rows.append(row); h_rows.append(rhs)
        else:
            for k in range(3):
                lb[l_off + k] = -lam_des_all[i, k]
                ub[l_off + k] = -lam_des_all[i, k]

    G_ineq = np.vstack(G_rows) if G_rows else None
    h_ineq = np.array(h_rows)  if h_rows else None

    try:
        sol = qpsolvers.solve_qp(P, qv, G_ineq, h_ineq, A_eq, b_eq, lb, ub, solver=qp_solver)
    except Exception:
        sol = None

    if sol is None:
        return None
    return {
        'd_v_fb':     sol[sl_fb],
        'd_ddq_legs': [sol[sl_ddq.start + leg_off_ddq[i] : sl_ddq.start + leg_off_ddq[i] + nj_each]
                       for i in range(n_legs)],
        'd_tau_legs': [sol[sl_tau.start + leg_off_ddq[i] : sl_tau.start + leg_off_ddq[i] + nj_each]
                       for i in range(n_legs)],
        'd_lam_legs': [sol[sl_lam.start + leg_off_lam[i] : sl_lam.start + leg_off_lam[i] + 3]
                       for i in range(n_legs)],
        'residual_legs': residual_legs,
        'residual_fb':   float(np.linalg.norm(rhs_fb)),
    }
