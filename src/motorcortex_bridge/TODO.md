# motorcortex_bridge TODO

> 마지막 업데이트: **v1.0.0** (2026-05-28)
> 정책: 모든 commit 에서 본 문서를 함께 갱신 (작업 추가/완료/우선순위 변경 시).

---

## 🚧 진행 중 (Current)

- [ ] **디버깅 (v0.9.x)** — CST + forceTJ 운용 검증
  - opmode=1 → CST 진입 → forceTJ 수동 ON → 모터 강성 (kp_joint) 응답 확인
  - gait/jump 의 CST 동작 검증
  - SW joint safety limit 작동 확인
  - torque_reset 버튼 시나리오 검증

---

## 📋 단기 (운용 가이드 정착 / 다음 단계 준비)

> v1.0.0 완료. MPC_trot 구현 전 운용 검증 단계.

- [ ] **v1.0.0 운용 검증**:
  - forcePF/TF 가 "Dynamic feedforward (tau_dyn 가산)" 으로 작동 확인
  - `/low_cmd` 수신 시 자동 RL_POLICY 진입 확인 (CSP+RL / CST+RL)
  - RL_POLICY timeout (200ms) 시 STANDBY 복귀 확인
  - `torque_reset` 이 `_cmd_tau` 도 클리어 확인
- [ ] **RL 정책 측 메시지 패킷 표준화**:
  - CSP+RL: `JointState(position=qt, effort=tau_offset)`
  - CST+RL: `JointState(position=[], effort=tau_cmd)` (또는 dummy position)
- [ ] **CST+RL 모드 진입 가이드 작성** — opmode=1 + `/low_cmd` publish 시작

---

## 🦿 중기 (MPC_trot 구현)

> `/home/jsh/simulation/gait_sim` 참고.

- [ ] **gait_sim 프로젝트 분석** — MPC step planner / WBIC 등 구조 파악
- [ ] **MPC_trot 이벤트 활성화** (현재 stub)
  - GRID 에 `MPC_trot` 파라미터 등록
  - `_on_mpc_trot` 콜백 구현
- [ ] **MPC controller 모듈** 신설
  - `mpc_controller.py` 별도 클래스 — bridge 내부 또는 외부 노드
  - 상태 입력: `axesPositionsActual`, `axesVelocitiesActual`
  - 출력: tau_cmd (CST 운용)
- [ ] **CST 운용 결정** — 사용자 명시 (MPC = CST)
- [ ] **gait scheduler / step planner** 통합
- [ ] **CoM / IMU 통합** — body state 추정
- [ ] **Phase 2 와 결합** — MPC 가 `q_d, q̇_d, q̈_d` 출력 → bridge 가 inverse dynamics

---

## ⚙️ 중기 (안전 / 인프라)

- [ ] **disableDrive 기반 N_AXES 자동 감지** — 시작 시 1회
  - `DISABLE_DRIVE_PATH = 'root/DriveLogic/disableDrive'`
  - `get_disable_drive()` + `detect_n_axes(arr)`
  - `connect()` 후 `_refresh_constants(n)` 호출
  - default 4, 읽기 실패 시 fallback
- [ ] **opmode 전환 thread 분리** (code review H4)
  - MCX 콜백 스레드의 blocking I/O 문제
  - dedicated 스레드/큐 패턴
- [ ] **atomic state snapshot** (`get_state_snapshot() → (pos, vel, tau)`)
  - 현재 pos/vel/tau 각각 별도 lock → publish 사이클 내 timestamp 어긋남
  - RL observation 정밀도 영향
- [ ] **`_ctrl_state` lock 보호** — read-modify-write race 차단
- [ ] **safety-critical exception 가시화** — silent `except Exception: pass` 제거
  - `_handle_limit_violation`, `_disable_mode_*`, mode 전환 경로

---

## 🚀 장기 (1kHz 전환 + Phase 2)

> 운용 안정화 후 진행.

- [ ] **Encoder 17-bit → 20-bit 업그레이드** (hw)
- [ ] **Control loop 500Hz → 1kHz** 전환
  - WSL2 → bare-metal RT Linux 마이그레이션 검토
  - Motorcortex drive cycle 매칭
- [ ] **Phase 2 통합** — `M(q)·q̈_d` feedforward (forcePF/TF 모듈 내 확장)
  - `q̈_d` 추정: trajectory analytical derivative 또는 backward diff + LPF
  - `compute_inertia_matrix` 헬퍼 이미 존재
  - `K_INERTIA` 게인 (0.0 default 비활성, 1.0 = 완전 feedforward)
- [ ] **q̇_d term 추가** — full PD `kd·(q̇_d − q̇_a)` (현재 `−kd·q̇_a` 만)
  - 1kHz + 20-bit 시 효용 증가
- [ ] **`K_GRAVITY` 옵션** (선택) — 중력 보상 부분 적용 / OFF
  - 또는 forcePF/TF 토글이 사실상 이 역할 (v1.0.0 후 자연 해결)

---

## 🐛 디버깅 / 검증 펜딩

- [ ] **`axesVelocitiesActual` 단위 확인** — rad/s 인지 검증 (1초에 90° 회전 시 raw=1.5~1.6 확인)
- [ ] **`forceTC` 진입 가드** — GRF 추정 분산이 큰 경우 자동 차단
- [ ] **`kd_joint` 자동 critical damping** — `kd = 2·√(kp·I_eff)` 자동 계산 옵션
- [ ] **SW velocity limit** — PVA velocity limit 미러, 한계 초과 시 safety stop

---

## ✅ 완료 (Done)

### v1.0.0 (2026-05-28)
- **토크 식 모듈화 재설계** — 6개 force* 토글 의미 정합:
  - **forcePF / forceTF**: Dynamic feedforward (`tau_dyn` 가산) — 이전 외부 `_cmd_tau` 채널 의미 제거
  - **forcePI / forceTJ**: Impedance (Cartesian / Joint) — 기존 의미 유지
  - **forcePC / forceTC**: GRF FF+FB — 기존 의미 유지
- **`tau_dyn` always-on 제거** → forcePF/TF active 시에만 가산 (kinesthetic teaching 자연 지원)
- **RL_POLICY auto-entry** — `/low_cmd` 수신 자체가 진입 시그널 (별도 forceRL 토글 없음)
  - 진입 시 다른 force* 자동 비활성 (GRID sync)
  - mode-aware 토크 처리:
    - CSP+RL: Hermite 위치 + `cmd_tau` (tau_offset feedforward)
    - CST+RL: `set_target_torques(cmd_tau)` only (raw passthrough)
  - `RL_CMD_TIMEOUT = 200ms` → publisher dropout 시 자동 STANDBY 복귀
- **`_cmd_tau` 의미 정합** — motorcortex `axesTorquesInput == target torque offset`:
  - CSP+RL: drive 위치 PID 위의 feedforward (tau_offset)
  - CST+RL: drive base ≈ 0 → 사실상 absolute torque
- **`set_command` 시그니처** — `q=None` 분기 (CST+RL 의 effort 만 수신 시나리오)
- **`_on_low_cmd` 가드 완화** — position 부족해도 effort 만 처리 가능
- **`torque_reset` 보강** — `_cmd_tau` 도 함께 클리어 (RL 잔여 명령 차단)
- **docstring 전면 갱신** — control_loop 도패 + 토글 의미

### v0.9.3 (2026-05-28, `cb90a58`)
- Joint impedance default 절반으로 하향: `KP_JOINT = [25, 50, 50, 25, 10]`, `KD_JOINT = [1.5, 2.5, 1.5, 0.5, 0.25]`
- 사유: v0.9.2 의 medium-low 영역이 운용에서 너무 강함 → very-compliant ~ compliant 경계로 조정

### v0.9.2 (2026-05-28, `4be746d`)
- Joint impedance default 상향: `KP_JOINT = [50, 100, 100, 50, 20]`, `KD_JOINT = [3, 5, 3, 1, 0.5]`
- compliant (10~30) → medium-low (50~100) 진입, critical damping × 0.75 매칭

### v0.9.1 (2026-05-28, `bc13bc7`)
- CST 진입 시 forceTJ 자동 활성화 제거 — 사용자 수동 운용 (강성 테스트 위해)

### v0.9.0 (2026-05-28, `4743fc9`)
- forcePI mirror 패턴 통일 (다른 5 force* 와 일관)
- ~~CST 진입 시 forceTJ 자동 활성화~~ (v0.9.1 에서 revert)
- `set_force_tj_event()` 메서드 추가 (interface)

### v0.8.2 (2026-05-28, `ecf7db2`)
- N_AXES 토글만으로 4↔5축 자동 정합
- `_Q_HOME_DEG_FULL[:N_AXES]` 등 마스터 슬라이스 패턴
- 동역학 함수가 `len(_DH)=4` 까지만 계산 (IndexError 차단)

### v0.8.1 (2026-05-28, `5e4ba5f`)
- `torque_reset` 버튼 — EMG 복귀용 비상 정지

### v0.8.0 (2026-05-28, `b5803a3`)
- N_AXES = 5 — 5축 (toe) 임피던스 활성화 (forceTJ 테스트용)

### v0.7.9 (2026-05-28, `e20ef95`)
- 코드리뷰 핫픽스: first-cycle damping spike, set_command 가드, _on_idle_mode actual sync, _on_force_tf_stop TC cascade, _ctrl_ready dead line 제거

### v0.7.8 (2026-05-28, `a6139bd`)
- idle state 통합 — `FORCE_PF/PI/TJ_IDLE` 3개 → `CSP_IDLE` / `CST_IDLE` 2개 (옵션 B)
- EXEC_TRAJ 종료 시 force* 활성이면 idle 직행 (STANDBY 윈도우 제거)
- forcePF 의미 정합 — `ff_active = pf or tf` 대칭 게이트

### v0.7.7 (2026-05-28, `afa7bcb`)
- `axesVelocitiesActual` 드라이브 측 velocity 구독 (rad/s) — backward diff 노이즈 회피
- `joint_state_bridge` 의 `/joint_states` `/low_state` velocity/effort 실측값

### v0.7.6 (2026-05-28, `1966c99`)
- SW joint position safety limit — CST runaway 차단
- `_check_joint_safety_limit` + `_handle_limit_violation`

### v0.7.5 이전 — 내부 변수명 통일 (forcePI/PF/PC/TJ — GRID 와 일치), GRID 게인 동기화 (push), opmode CSP↔CST 전환, forceTJ/TF/TC FF channels, EXEC_TRAJ 명시 플래그 게이팅, MPC_trot/MPC_stairs/NMPC_trot stub, foot state publish, GRF FF+FB 통합 수식, jump 궤적, home (POS/ADDITIVE), moveL, gait Bezier, forceT GRF 추정 등

---

## 📐 펜딩 결정 / 검토 사항

- [ ] **GRID 게인 sync `frq_divider`** — 현재 10 (~ 400Hz). 운용 부하 확인 후 조정 (50 = 80Hz 또는 100 = 40Hz)
- [ ] **`_disable_mode_a / b` 가 forceRL 도 해제할지** — v1.0.0 재설계 시 결정
- [ ] **MPC_trot 위치** — bridge 내부 vs 별도 ROS2 노드 — gait_sim 분석 후

---

## 📝 운용 메모

### GRID 측 필수 확인사항
- `axesVelocitiesActual` 단위가 rad/s 인지
- `kp_joint / kd_joint` 가 `double[5]` 으로 등록되어 있는지
- `torque_reset` 이벤트 (`root/UserParameters/torque_reset`) 가 GRID 에 등록되어 있는지

### home / torque_reset 운용 가이드 (수동 운용 — 자동 전환 없음)
| 모드 | 의도 | 사용 명령 |
|---|---|---|
| **CSP** | 자세 복귀 [0,0,0,0,0] | `home` 직접 |
| **CSP** | feedforward 토크 정리 (위치 유지) | `torque_reset` |
| **CST** | 자세 복귀 [0,0,0,0,0] | **opmode=0 (CSP 전환) → home 누름** (수동) |
| **CST** | 비상 정지 / 토크 클리어 | `torque_reset` |

→ CST drive 는 위치 PID 가 없어 `home` 단독으로 자세 복귀 불가. 사용자가 CSP 로 먼저 전환.
→ `home` 콜백은 모든 force* OFF 시키므로 CST 에서 누르면 사실상 `torque_reset` 과 동일.

### 토크 식 매핑 (v1.0.0 후)
```
tau_cmd = kp · (q_d − q_a) + kd · (q̇_d − q̇_a)    ← impedance      (forcePI/forceTJ)
        + tau_dyn                                  ← 중력 보상      (forcePF/forceTF)
        + tau_GRF                                  ← 접지력         (forcePC/forceTC)
        + tau_raw                                  ← RL/MPC raw    (forceRL)
```
