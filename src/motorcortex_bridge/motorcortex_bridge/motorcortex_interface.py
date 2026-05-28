"""
motorcortex_interface.py
MCX-OS 와의 저수준 통신 전담 클래스
ROS2 의존성 없음 — motion_controller 또는 단독으로 사용 가능

담당:
  - WebSocket(WSS) 연결 / 재연결
  - Engage, JogMode 시퀀스
  - hostInJointPosition2 쓰기
  - axesPositionsActual 구독
  - JumpEvent / HomeEvent / moveLEvent / ForceSEvent / ForceTEvent / GaitEvent / controlMode 구독

  절대 위치 모드 - hostInJointPosition2 4축 동시 제어
  [Machinecontrol] -> [Axescontrol]
  [Joint(ch)] -> [Axes(ch,rad) -> Actuator(rad) -> motor(ticks)]
"""

import motorcortex
import threading
import time
import os

_DEFAULT_CERT = os.path.join(os.path.dirname(__file__), '..', 'config', 'mcx.cert.crt')

# ── MCX 파라미터 경로 ──────────────────────────────────────────────────────────
STATE_CMD_PATH     = 'root/Logic/stateCommand'
STATE_PATH         = 'root/Logic/state'
ENGAGE_CMD         = 2      # GOTO_ENGAGED_E
ENGAGED_STATE      = 4      # ENGAGED_S
ENGAGE_TIMEOUT     = 10.0

JOG_MODE_PATH       = 'root/MachineControl/gotoJogMode'
PAUSE_MODE_PATH     = 'root/MachineControl/gotoPauseMode'
# ── 위치제어경로 ──────────────────────────────────────────────────────────
ADDITIVE_CMD_PATH   = 'root/MachineControl/hostInJointAdditivePosition2'  # additive [rad]
POS_CMD_PATH       = 'root/MachineControl/hostInJointPosition2'              # 절대 위치 [rad] (배열, 6ch) — ch0~3 = 제어축, ch4~5 = 토우/예비 (0 고정)
ACTUAL_PATH        = 'root/AxesControl/axesPositionsActual'   # 부모 경로, value[0~4] 인덱싱 [rad]
VELOCITY_PATH      = 'root/AxesControl/axesVelocitiesActual'  # 부모 경로, value[0~4] 인덱싱 [rad/s]
                                                              # ※ GRID 단위 = rad/s 로 설정 필요
# ── 토크 제어 경로 ────────────────────────────────────────────────────────────
TORQUE_INPUT_PATH       = 'root/AxesControl/axesTorquesInput'          # 토크 입력 (배열, Nm) — 읽기/쓰기
TORQUE_ACTUAL_PATH_FMT  = (                                             # 실제 토크 (스칼라, Nm) — {:02d} = 축 번호 (1-based)
    'root/AxesControl/actuatorControlLoops'
    '/actuatorControlLoop{:02d}/actuatorTorqueActual'
)
# ── 발끝 상태 출력 경로 (UserParameters) ─────────────────────────────────────
FOOT_POS_PATH = 'root/UserParameters/Foot_POS'   # double[3] x,y,z [mm]  힙 원점 기준 FK (m × 1000)
FOOT_GRF_PATH = 'root/UserParameters/Foot_GRF'   # double[3] x,y,z [N]   추정 지면반력

# ── 임피던스/GRF 게인 동기화 (UserParameters, 양방향) ────────────────────────
KP_IMP_PATH   = 'root/UserParameters/kp_imp'    # double[3] Cartesian 강성  [N/m]
KD_IMP_PATH   = 'root/UserParameters/kd_imp'    # double[3] Cartesian 댐핑  [N·s/m]
KF_GRF_PATH   = 'root/UserParameters/kf_grf'    # double[3] GRF 피드백 게인 (무차원)
KP_JOINT_PATH = 'root/UserParameters/kp_joint'  # double[5] Joint 강성     [N·m/rad]  (앞 4축 사용, 5번째 toe 슬롯)
KD_JOINT_PATH = 'root/UserParameters/kd_joint'  # double[5] Joint 댐핑     [N·m·s/rad] (앞 4축 사용)

# ── 이벤트 경로 (GRID UserParameters) ──────────────────────────────────────────
JUMP_EVENT_PATH          = 'root/UserParameters/jump'
HOME_EVENT_PATH          = 'root/UserParameters/home'
HOME_ADDITIVE_EVENT_PATH = 'root/UserParameters/homeAdditive'
MOVE_L_EVENT_PATH        = 'root/UserParameters/moveL'
FORCE_PI_EVENT_PATH       = 'root/UserParameters/forcePI'   # CSP Cartesian Impedance
FORCE_PF_EVENT_PATH       = 'root/UserParameters/forcePF'   # CSP τ_ff (외부 channel)
FORCE_PC_EVENT_PATH       = 'root/UserParameters/forcePC'   # CSP GRF FF+FB
FORCE_TJ_EVENT_PATH       = 'root/UserParameters/forceTJ'  # CST Joint Impedance
FORCE_TF_EVENT_PATH      = 'root/UserParameters/forceTF' # CST τ_ff toggle
FORCE_TC_EVENT_PATH      = 'root/UserParameters/forceTC' # CST GRF FF+FB toggle

RESET_GAIN_EVENT_PATH    = 'root/UserParameters/reset'
TORQUE_RESET_EVENT_PATH  = 'root/UserParameters/torque_reset'   # EMG 복귀: 모든 force 토글 OFF + tau=0 + STANDBY

DRIVE_MODE_PATH = 'root/DriveLogic/driveMode'   # int[6] — CIA402 Mode of Operation (8=CSP, 10=CST)
OPMODE_PATH     = 'root/UserParameters/opmode'  # int   — 0=CSP, 1=CST (단일 토글, level+에지)
GAIT_EVENT_PATH          = 'root/UserParameters/gait'
SITTING_EVENT_PATH       = 'root/UserParameters/Sitting'
STANDING_EVENT_PATH      = 'root/UserParameters/Standing'
RL_TROT_EVENT_PATH       = 'root/UserParameters/RL_trot'
FALL_RECOVERY_EVENT_PATH = 'root/UserParameters/Fall recovery'
# ── MPC / NMPC 모드 이벤트 (stub — 구현 TODO) ──────────────────────────────────
MPC_TROT_EVENT_PATH      = 'root/UserParameters/MPC_trot'
MPC_STAIRS_EVENT_PATH    = 'root/UserParameters/MPC_stairs'
NMPC_TROT_EVENT_PATH     = 'root/UserParameters/NMPC_trot'

# ── 조인트 매핑: (ROS joint name, ch index) ───────────────────────────────────
#   ch0 = HL_joint2_thigh_r
#   ch1 = HL_joint3_thigh_p
#   ch2 = HL_joint4_knee_p
#   ch3 = HL_joint5_ankle_p
#   ch4 = HL_joint6_toe_p    (read-only)

N_AXES = 4   # 제어축 수 (toe 제외)
NUM_CH = 6   # hostInJointPosition2 전체 채널 수

JOINT_LOOP_MAP = [
    ('HL_joint2_thigh_r', '00'),
    ('HL_joint3_thigh_p', '01'),
    ('HL_joint4_knee_p',  '02'),
    ('HL_joint5_ankle_p', '03'),
    ('HL_joint6_toe_p',   '04'),
]

class MotorcortexInterface:
    """
    MCX-OS 통신 래퍼.
    connect() 후 engage() → set_jog_mode() → subscribe_positions() 순서로 초기화.
    """

    def __init__(self, url: str, cert: str, login: str, password: str):
        self._url      = url
        self._cert     = cert or _DEFAULT_CERT
        self._login    = login
        self._password = password

        self._req  = None
        self._sub  = None
        self._subs = []

        self._lock            = threading.Lock()
        self._actual_pos_rad  = [0.0] * len(JOINT_LOOP_MAP)
        self._actual_vel_rps  = [0.0] * len(JOINT_LOOP_MAP)   # axesVelocitiesActual [rad/s]
        self._last_target_rad = [0.0] * N_AXES
        self._actual_torque   = [0.0] * N_AXES   # actuatorTorqueActual (Nm)
        self._base_pos        = [0.0] * N_AXES   # JogMode 진입 시점 절대 위치 (additive 기준)

    # ── 연결 ─────────────────────────────────────────────────────────────────
    def connect(self, timeout_ms: int = 5000) -> bool:
        parameter_tree    = motorcortex.ParameterTree()
        motorcortex_types = motorcortex.MessageTypes()
        self._req, self._sub = motorcortex.connect(
            self._url,
            motorcortex_types,
            parameter_tree,
            certificate=self._cert,
            timeout_ms=timeout_ms,
            login=self._login,
            password=self._password,
            reconnect=False,
        )
        return True

    def disconnect(self):
        for sub in self._subs:
            try:
                sub.unsubscribe()
            except Exception:
                pass
        self._subs.clear()
        self._req = None
        self._sub = None

    @property
    def is_connected(self) -> bool:
        return self._req is not None

    # ── Engage / JogMode ──────────────────────────────────────────────────────
    def engage(self, timeout: float = ENGAGE_TIMEOUT) -> bool:
        """Engage 상태 진입. 이미 Engaged면 즉시 True 반환."""
        result = self._req.getParameter(STATE_PATH).get()
        if result and result.value and result.value[0] == ENGAGED_STATE:
            return True

        self._req.setParameter(STATE_CMD_PATH, [ENGAGE_CMD]).get()
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self._req.getParameter(STATE_PATH).get()
            if result and result.value and result.value[0] == ENGAGED_STATE:
                return True
            time.sleep(0.1)
        return False

    def set_jog_mode(self):
        """JogMode 활성, PauseMode 해제."""
        self._req.setParameter('root/MachineControl/gotoJogMode',  True).get()
        self._req.setParameter('root/MachineControl/gotoPauseMode', False).get()

    # ── 위치 명령 ─────────────────────────────────────────────────────────────
    def set_target_positions(self, positions_rad: list, blocking: bool = False):
        """
        hostInJointPosition2 에 6ch 배열로 목표 위치 명령 전송.
        positions_rad: N_AXES 길이의 절대 위치 리스트 [rad]
        """
        cmd = list(positions_rad[:N_AXES]) + [0.0] * (NUM_CH - N_AXES)
        future = self._req.setParameter(POS_CMD_PATH, cmd)
        with self._lock:
            self._last_target_rad = list(positions_rad[:N_AXES])
        if blocking:
            future.get()

    def set_base_pos(self, positions_rad: list):
        """
        JogMode 진입 시점 절대 위치를 base_pos로 저장.
        set_additive_positions()의 기준점이 됨.
        초기화 시 get_actual_positions_snapshot() 결과를 전달.
        """
        with self._lock:
            self._base_pos = list(positions_rad[:N_AXES])

    def set_additive_positions(self, target_abs: list, blocking: bool = False):
        """
        hostInJointAdditivePosition2에 additive 명령 전송.
        additive[i] = target_abs[i] - base_pos[i]

        target_abs : 목표 절대 위치 [rad]  (N_AXES,)
        """
        with self._lock:
            base = list(self._base_pos)
        additive = [target_abs[i] - base[i] for i in range(N_AXES)]
        cmd      = additive + [0.0] * (NUM_CH - N_AXES)
        future   = self._req.setParameter(ADDITIVE_CMD_PATH, cmd)
        with self._lock:
            self._last_target_rad = list(target_abs[:N_AXES])
        if blocking:
            future.get()

    def reset_additive(self, blocking: bool = False):
        """hostInJointAdditivePosition2 에 0 배열 전송 — additive 초기화."""
        cmd    = [0.0] * NUM_CH
        future = self._req.setParameter(ADDITIVE_CMD_PATH, cmd)
        if blocking:
            future.get()

    def get_actual_positions_snapshot(self) -> list:
        """현재 실제 위치 읽기 [rad] — 초기값 설정용 1회성 폴링."""
        try:
            result = self._req.getParameter(ACTUAL_PATH).get()
            if result and result.value:
                return [float(result.value[i]) for i in range(N_AXES)]
        except Exception:
            pass
        return [0.0] * N_AXES

    def get_target_positions(self) -> list:
        """현재 목표 위치 [rad] 읽기 — 캐시 반환."""
        with self._lock:
            return list(self._last_target_rad)

    # ── 토크 명령 ─────────────────────────────────────────────────────────────
    def set_target_torques(self, torques_nm: list, blocking: bool = False):
        """
        axesTorquesInput 에 배열로 토크 오프셋 전송 (Nm).
        torques_nm : N_AXES 길이의 토크 리스트 [Nm]
        """
        cmd = [float(t) for t in torques_nm[:N_AXES]] + [0.0] * (NUM_CH - N_AXES)
        future = self._req.setParameter(TORQUE_INPUT_PATH, cmd)
        if blocking:
            future.get()

    def set_pos_and_torque(self, positions_rad: list, torques_nm: list, blocking: bool = False):
        """position + torque를 단일 setParameterList로 원자적 전송."""
        pos_cmd = list(positions_rad[:N_AXES]) + [0.0] * (NUM_CH - N_AXES)
        tau_cmd = [float(t) for t in torques_nm[:N_AXES]] + [0.0] * (NUM_CH - N_AXES)
        with self._lock:
            self._last_target_rad = list(positions_rad[:N_AXES])
        future = self._req.setParameterList([
            {'path': POS_CMD_PATH,      'value': pos_cmd},
            {'path': TORQUE_INPUT_PATH, 'value': tau_cmd},
        ])
        if blocking:
            future.get()

    # ── 임피던스/GRF 게인 동기화 ──────────────────────────────────────────
    def set_impedance_gains(self, kp_imp, kd_imp, kf_grf,
                            kp_joint, kd_joint, blocking: bool = False):
        """5개 임피던스 게인을 GRID UserParameters 에 송신 (startup 초기값).

        kp_imp   : (3,) [N/m]      Cartesian 강성
        kd_imp   : (3,) [N·s/m]    Cartesian 댐핑
        kf_grf   : (3,)            GRF 피드백 게인 (무차원)
        kp_joint : (4,) [N·m/rad]  Joint 강성  — 5-elem 으로 padding (5번째=0)
        kd_joint : (4,) [N·m·s/rad] Joint 댐핑 — 5-elem 으로 padding
        """
        kp  = [float(v) for v in kp_imp[:3]]
        kd  = [float(v) for v in kd_imp[:3]]
        kf  = [float(v) for v in kf_grf[:3]]
        # GRID kp_joint/kd_joint = double[5] — N_AXES=5 면 그대로 매핑 (5번째=toe)
        kpj = [float(v) for v in kp_joint[:N_AXES]]
        kdj = [float(v) for v in kd_joint[:N_AXES]]
        # GRID 가 5-elem 인데 N_AXES < 5 면 부족분 0 패딩
        while len(kpj) < 5: kpj.append(0.0)
        while len(kdj) < 5: kdj.append(0.0)
        future = self._req.setParameterList([
            {'path': KP_IMP_PATH,   'value': kp},
            {'path': KD_IMP_PATH,   'value': kd},
            {'path': KF_GRF_PATH,   'value': kf},
            {'path': KP_JOINT_PATH, 'value': kpj},
            {'path': KD_JOINT_PATH, 'value': kdj},
        ])
        if blocking:
            future.get()

    def subscribe_impedance_gains(self, callback: callable):
        """GRID 5개 게인 변경 구독 (10 cycle = 100Hz delivery).

        callback(kp_imp, kd_imp, kf_grf, kp_joint, kd_joint)
          - kp_imp/kd_imp/kf_grf : list[float] 길이 3 또는 None
          - kp_joint/kd_joint    : list[float] 길이 4 (5번째 toe 슬롯 잘라냄) 또는 None
        """
        sub = self._sub.subscribe(
            [KP_IMP_PATH, KD_IMP_PATH, KF_GRF_PATH, KP_JOINT_PATH, KD_JOINT_PATH],
            'imp_gain_group',
            frq_divider=10,
        )

        def _cb(msg):
            if not msg or len(msg) < 5:
                return
            kp   = [float(v) for v in msg[0].value[:3]] if msg[0].value else None
            kd   = [float(v) for v in msg[1].value[:3]] if msg[1].value else None
            kf   = [float(v) for v in msg[2].value[:3]] if msg[2].value else None
            kpj  = [float(v) for v in msg[3].value[:N_AXES]] if msg[3].value else None
            kdj  = [float(v) for v in msg[4].value[:N_AXES]] if msg[4].value else None
            callback(kp, kd, kf, kpj, kdj)

        sub.notify(_cb)
        self._subs.append(sub)

    # ── 발끝 상태 출력 ─────────────────────────────────────────────────────
    def set_foot_state(self, pos_xyz, grf_xyz, blocking: bool = False):
        """발끝 위치(Foot_POS) + 추정 반력(Foot_GRF) 원자적 동시 쓰기.

        pos_xyz : (3,) [mm] 힙 원점 기준 발끝 좌표 (m × 1000 — 호출측 책임)
        grf_xyz : (3,) [N]  추정 지면반력 (compute_grf 출력)
        """
        pos = [float(p) for p in pos_xyz[:3]]
        grf = [float(f) for f in grf_xyz[:3]]
        future = self._req.setParameterList([
            {'path': FOOT_POS_PATH, 'value': pos},
            {'path': FOOT_GRF_PATH, 'value': grf},
        ])
        if blocking:
            future.get()

    # ── 구독 ─────────────────────────────────────────────────────────────────
    def subscribe_positions(self):
        """axesPositionsActual 부모 경로 구독, value[0~4] 인덱싱."""
        sub_pos = self._sub.subscribe([ACTUAL_PATH], 'pos_group', frq_divider=1)

        def _cb_pos(msg):
            if msg and msg[0].value:
                with self._lock:
                    for i in range(len(JOINT_LOOP_MAP)):
                        self._actual_pos_rad[i] = float(msg[0].value[i])

        sub_pos.notify(_cb_pos)
        self._subs.append(sub_pos)

    def subscribe_velocities(self):
        """axesVelocitiesActual 부모 경로 구독 [rad/s], value[0~4] 인덱싱.

        드라이브 내부 필터링된 motor velocity — backward difference 보다
        양자화 노이즈가 훨씬 적어 임피던스 PD 의 kd·dq_a 항 안정화.
        ※ GRID 측 단위 = rad/s 로 설정되어 있어야 함.
        """
        sub_vel = self._sub.subscribe([VELOCITY_PATH], 'vel_group', frq_divider=1)

        def _cb_vel(msg):
            if msg and msg[0].value:
                with self._lock:
                    for i in range(len(JOINT_LOOP_MAP)):
                        self._actual_vel_rps[i] = float(msg[0].value[i])

        sub_vel.notify(_cb_vel)
        self._subs.append(sub_vel)

    # ── 이벤트 구독 헬퍼 ──────────────────────────────────────────────────────────
    def _subscribe_event(self, path: str, group: str, callback: callable):
        """value[0] == 1 일 때만 callback 호출하는 범용 이벤트 구독."""
        sub = self._sub.subscribe([path], group, frq_divider=1)

        def _cb(msg):
            if msg and msg[0].value and int(msg[0].value[0]) == 1:
                callback()

        sub.notify(_cb)
        self._subs.append(sub)

    def _subscribe_level_event(self, path: str, group: str,
                               on_high: callable, on_low: callable = None):
        """value=1 → on_high, value=0 → on_low. 에지 감지: 이전과 동일 시 무시."""
        sub = self._sub.subscribe([path], group, frq_divider=1)
        _prev = [None]

        def _cb(msg):
            if not msg or not msg[0].value:
                return
            val = int(msg[0].value[0])
            if val == _prev[0]:
                return
            _prev[0] = val
            if val == 1:
                on_high()
            elif val == 0 and on_low:
                on_low()

        sub.notify(_cb)
        self._subs.append(sub)

    def _reset_event(self, path: str):
        """
        이벤트 파라미터를 0으로 리셋 (fire-and-forget).
        호출 후 caller가 time.sleep(0.05)로 MCX 버퍼 콜백을 드레인해야 함.
        ※ 콜백 스레드에서 action 이벤트 리셋 금지 (재트리거 방지 설계)
        """
        self._req.setParameter(path, [0])

    # ── 이벤트 구독 / 리셋 ────────────────────────────────────────────────────────
    def subscribe_jump_event(self, cb: callable):
        self._subscribe_event(JUMP_EVENT_PATH, 'jump_group', cb)

    def reset_jump_event(self):
        self._reset_event(JUMP_EVENT_PATH)

    def subscribe_home_event(self, cb: callable):
        self._subscribe_event(HOME_EVENT_PATH, 'home_group', cb)

    def reset_home_event(self):
        self._reset_event(HOME_EVENT_PATH)

    def subscribe_home_additive_event(self, cb: callable):
        self._subscribe_event(HOME_ADDITIVE_EVENT_PATH, 'home_additive_group', cb)

    def reset_home_additive_event(self):
        self._reset_event(HOME_ADDITIVE_EVENT_PATH)

    def subscribe_movel_event(self, cb: callable):
        self._subscribe_event(MOVE_L_EVENT_PATH, 'movel_group', cb)

    def reset_movel_event(self):
        self._reset_event(MOVE_L_EVENT_PATH)

    def subscribe_force_pi_event(self, cb: callable):
        """forceS 토글 — 0→1 에지에서만 cb 발화.

        pulse subscribe 시 GRID 버튼이 latched(1 유지)면 reset 0 직후 GRID가
        다시 1로 끌어올려 콜백이 반복 발화 → 토글이 무한히 ON/OFF 되는 문제 회피.
        forceT 와 동일한 level+에지 패턴 사용.
        """
        self._subscribe_level_event(FORCE_PI_EVENT_PATH, 'forces_group', cb, None)

    def reset_force_pi_event(self):
        self._reset_event(FORCE_PI_EVENT_PATH)

    def subscribe_force_pf_event(self, on_start: callable, on_stop: callable = None):
        """forceT 레벨 구독: value=1 → on_start, value=0 → on_stop."""
        self._subscribe_level_event(FORCE_PF_EVENT_PATH, 'forcet_group', on_start, on_stop)

    def reset_force_pf_event(self):
        self._reset_event(FORCE_PF_EVENT_PATH)

    def subscribe_force_pc_event(self, on_start: callable, on_stop: callable = None):
        """forceF 레벨 구독: value=1 → on_start (GRF 피드백 ON), value=0 → on_stop."""
        self._subscribe_level_event(FORCE_PC_EVENT_PATH, 'forcef_group', on_start, on_stop)

    def reset_force_pc_event(self):
        self._reset_event(FORCE_PC_EVENT_PATH)

    def subscribe_force_tj_event(self, on_start: callable, on_stop: callable = None):
        """forceJ 레벨 구독: value=1 → on_start (Joint impedance ON), value=0 → on_stop."""
        self._subscribe_level_event(FORCE_TJ_EVENT_PATH, 'forcej_group', on_start, on_stop)

    def reset_force_tj_event(self):
        self._reset_event(FORCE_TJ_EVENT_PATH)

    def subscribe_force_tf_event(self, on_start: callable, on_stop: callable = None):
        """forceTF (CST τ_ff toggle) — level+에지."""
        self._subscribe_level_event(FORCE_TF_EVENT_PATH, 'forcetf_group', on_start, on_stop)

    def reset_force_tf_event(self):
        self._reset_event(FORCE_TF_EVENT_PATH)

    def subscribe_force_tc_event(self, on_start: callable, on_stop: callable = None):
        """forceTC (CST GRF FF+FB toggle) — level+에지."""
        self._subscribe_level_event(FORCE_TC_EVENT_PATH, 'forcetc_group', on_start, on_stop)

    def reset_force_tc_event(self):
        self._reset_event(FORCE_TC_EVENT_PATH)

    def subscribe_reset_gain_event(self, cb: callable):
        self._subscribe_level_event(RESET_GAIN_EVENT_PATH, 'reset_gain_group', cb, None)

    def reset_reset_gain_event(self):
        self._reset_event(RESET_GAIN_EVENT_PATH)

    def subscribe_torque_reset_event(self, cb: callable):
        """torque_reset 버튼 — 0→1 에지에서 cb 발화. 사용자 명시적 비상 정지용."""
        self._subscribe_level_event(TORQUE_RESET_EVENT_PATH, 'torque_reset_group', cb, None)

    def reset_torque_reset_event(self):
        self._reset_event(TORQUE_RESET_EVENT_PATH)

    def set_drive_mode(self, modes: list, blocking: bool = True):
        """root/DriveLogic/driveMode 에 6채널 모드 송신. 8=CSP, 10=CST."""
        cmd = [int(m) for m in modes[:6]] + [0] * max(0, 6 - len(modes))
        future = self._req.setParameter(DRIVE_MODE_PATH, cmd[:6])
        if blocking:
            future.get()

    def get_drive_mode(self):
        """현재 drive mode 읽기. 반환: list[int] 길이 6 또는 None (실패)."""
        try:
            result = self._req.getParameter(DRIVE_MODE_PATH).get()
            if result and result.value:
                return [int(v) for v in result.value]
        except Exception:
            pass
        return None

    def subscribe_opmode_event(self, on_cst: callable, on_csp: callable):
        """opmode: 0=CSP, 1=CST. 0→1 에지에서 on_cst, 1→0 에지에서 on_csp 발화.
        startup 시 첫 delivery 에서도 현재 값에 맞춰 한 번 fire."""
        self._subscribe_level_event(OPMODE_PATH, 'opmode_group', on_cst, on_csp)

    def subscribe_gait_event(self, cb: callable):
        self._subscribe_event(GAIT_EVENT_PATH, 'gait_group', cb)

    def reset_gait_event(self):
        self._reset_event(GAIT_EVENT_PATH)

    # ── 자세/모드 이벤트 구독 / 리셋 ────────────────────────────────────────────
    def subscribe_sitting_event(self, cb: callable):
        self._subscribe_event(SITTING_EVENT_PATH, 'sitting_group', cb)

    def reset_sitting_event(self):
        self._reset_event(SITTING_EVENT_PATH)

    def subscribe_standing_event(self, cb: callable):
        self._subscribe_event(STANDING_EVENT_PATH, 'standing_group', cb)

    def reset_standing_event(self):
        self._reset_event(STANDING_EVENT_PATH)

    def subscribe_rl_trot_event(self, cb: callable):
        self._subscribe_event(RL_TROT_EVENT_PATH, 'rl_trot_group', cb)

    def reset_rl_trot_event(self):
        self._reset_event(RL_TROT_EVENT_PATH)

    def subscribe_fall_recovery_event(self, cb: callable):
        self._subscribe_event(FALL_RECOVERY_EVENT_PATH, 'fall_recovery_group', cb)

    def reset_fall_recovery_event(self):
        self._reset_event(FALL_RECOVERY_EVENT_PATH)

    # ── MPC / NMPC 모드 이벤트 구독 / 리셋 (stub — 구현 TODO) ──────────────────
    def subscribe_mpc_trot_event(self, cb: callable):
        self._subscribe_event(MPC_TROT_EVENT_PATH, 'mpc_trot_group', cb)

    def reset_mpc_trot_event(self):
        self._reset_event(MPC_TROT_EVENT_PATH)

    def subscribe_mpc_stairs_event(self, cb: callable):
        self._subscribe_event(MPC_STAIRS_EVENT_PATH, 'mpc_stairs_group', cb)

    def reset_mpc_stairs_event(self):
        self._reset_event(MPC_STAIRS_EVENT_PATH)

    def subscribe_nmpc_trot_event(self, cb: callable):
        self._subscribe_event(NMPC_TROT_EVENT_PATH, 'nmpc_trot_group', cb)

    def reset_nmpc_trot_event(self):
        self._reset_event(NMPC_TROT_EVENT_PATH)

    # ── JogMode / PauseMode 동시 0 구독 ──────────────────────────────────────
    def subscribe_idle_mode(self, on_idle: callable, on_busy: callable = None):
        """
        JogMode/PauseMode 상태 전환 에지 콜백.
          on_idle : non-idle → idle (둘 다 0) 전환 시 1회 호출
          on_busy : idle → non-idle (어느 하나라도 non-0) 전환 시 1회 호출
        """
        sub = self._sub.subscribe(
            [JOG_MODE_PATH, PAUSE_MODE_PATH], 'idle_mode_group', frq_divider=1
        )
        self._jog_val   = None
        self._pause_val = None
        self._was_idle  = False

        def _cb(msg):
            if not msg or len(msg) < 2:
                return
            if msg[0].value:
                self._jog_val   = int(msg[0].value[0])
            if msg[1].value:
                self._pause_val = int(msg[1].value[0])
            if self._jog_val is None or self._pause_val is None:
                return
            is_idle = (self._jog_val == 0 and self._pause_val == 0)
            if is_idle and not self._was_idle:
                on_idle()
            elif not is_idle and self._was_idle and on_busy:
                on_busy()
            self._was_idle = is_idle

        sub.notify(_cb)
        self._subs.append(sub)

    # ── 토크 센싱 구독 ───────────────────────────────────────────────────────
    def subscribe_torque_actual(self):
        """
        actuatorTorqueActual 채널별 구독 (ch0~N_AXES-1).
        경로: actuatorControlLoop{01~04}/actuatorTorqueActual
        """
        paths = [TORQUE_ACTUAL_PATH_FMT.format(i + 1) for i in range(N_AXES)]
        sub   = self._sub.subscribe(paths, 'torque_actual_group', frq_divider=1)

        def _cb(msg):
            if msg:
                with self._lock:
                    for i, m in enumerate(msg[:N_AXES]):
                        if m and m.value:
                            self._actual_torque[i] = float(m.value[0])

        sub.notify(_cb)
        self._subs.append(sub)

    # ── 상태 읽기 ─────────────────────────────────────────────────────────────
    @property
    def actual_positions(self) -> list:
        with self._lock:
            return list(self._actual_pos_rad)

    @property
    def actual_velocities(self) -> list:
        """드라이브 측 측정 관절 속도 [rad/s] (필터링됨, len=len(JOINT_LOOP_MAP))."""
        with self._lock:
            return list(self._actual_vel_rps)

    @property
    def actual_torque(self) -> list:
        with self._lock:
            return list(self._actual_torque)

