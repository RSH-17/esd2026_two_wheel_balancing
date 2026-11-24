# 실험: GIL 전환 간격 (sys.setswitchinterval) 제거 실험 — write() 정지 tick 원인 확인

**파일명**: `logs/experiments/2026-11-25-gil-switch-interval.md` · **선행 실험**: `logs/experiments/2026-11-25-loop-jitter-cause.md` · **회의록**: 이 세션 종료 때 작성함

## 1. 사전등재 (실행 전)

- **가설 (코드 · Python 동작에서 세운 가설, 미측정)**: 제어 스레드가 `write()` 시스템 호출 동안 GIL 을 놓았다가 되찾을 때, 다른 Python 스레드 (로그 · sampler · ROS 콜백) 가 GIL 을 잡고 있으면 최대 switch interval (기본 5 ms) 까지 기다림. 이것이 「정지 tick」 (write 2 ms 초과, 그동안 CPU 비율 약 0.1) 의 원인임
- **변수 (하나)**: `--switch-interval` — 기본 0.005 s vs 0.0005 s. 실제값은 `-meta.json` 의 `applied.switch_interval_s` 로 확인함 (동작 확인 04:21: 0.005 / 0.0005 로 각각 기록됨)
- **비교 대상 (4 런)**: off-5ms · off-0.5ms · on-5ms · on-0.5ms. 순서는 이 순서로 함
- **정합 축 · 공통 조건**: 선행 실험과 같음 (60 s = 12 000 tick, 명령 0, `--rate 200` · `--imu off` · `--diag` · baud 115200 · `MOTOR_ENABLE 0`, 모터 · IMU 미연결, governor `ondemand`, Claude Code 세션 동시 실행)
- **지표**: 정지 tick 수 (`tools/analyze_jitter.py` 의 `stall_ticks`), 지연 tick 수 (Δt > 7.5 ms), Δt max, `check_log` 판정, 정지 tick 의 write CPU 비율 중앙값
- **판정 기준**
  - 가설 **지지**: off 와 on **모두** 정지 tick(0.5 ms) ≤ 0.5 × 정지 tick(5 ms)
  - 가설 **기각**: off 와 on 모두 정지 tick(0.5 ms) ≥ 0.8 × 정지 tick(5 ms)
  - 그 밖은 「판정 불가」
  - `check_log` PASS 여부와 링크 무결 (lost · Uno 카운터 0) 은 함께 보고하되 이 가설 판정에는 쓰지 않음 (선행 baseline 의 판정 기준은 원인 수정 후 별도 등재로 다시 적용함)
- **단계**: 각 n = 1 (원인 확인용 탐색). 결론 · 보고서에 인용하지 않음. 지지되면 0.5 ms 를 쓰는 조건으로 baseline 실험을 n ≥ 3 으로 다시 등재함
- **중단 기준**: off-5ms 와 on-5ms 의 정지 tick 이 둘 다 0 이면 「재현 안 됨」 으로 보고하고 멈춤
- **로그 위치**: `logs/runs/2026-11-25-gil-switch-interval/` 에 커밋함 (류시현 · 04:04 결정과 같음)

## 2. 실행 기록

| 런 | 조건 | 시각 | 로그 | 실제 적용값 (meta 에서 읽음) | `check_log.py` |
|---|---|---|---|---|---|
| off-5ms | ros off | 04:21 | `logs/runs/2026-11-25-gil-switch-interval/off-5ms` | switch_interval 0.005 · fw `serial_link-0.1` · motor 0 · wd 50 ms · imu off · governor ondemand · diag true | VOID (gap 7.7 ms) |
| off-0.5ms | ros off | 04:22 | `…/off-0.5ms` | switch_interval 0.0005 · 나머지 같음 | PASS |
| on-5ms | ros on | 04:23 | `…/on-5ms` | switch_interval 0.005 · `rmw_fastrtps_cpp` | VOID (gap 10.5 ms) |
| on-0.5ms | ros on | 04:25 | `…/on-0.5ms` | switch_interval 0.0005 · `rmw_fastrtps_cpp` | VOID (gap 9.9 ms) |

## 3. 결과

| 런 (n = 1) | 정지 tick | write CPU 비율 중앙값 | 지연 tick | Δt max [ms] | ack_lag 3 | 링크 (ack / lost / Uno 카운터) |
|---|---|---|---|---|---|---|
| off-5ms | 56 | 0.094 | 2 | 7.725 | 0 | 12000 / 0 / 0 |
| off-0.5ms | 72 | 0.110 | 0 | 7.339 | 0 | 12000 / 0 / 0 |
| on-5ms | 172 | 0.119 | 290 | 10.526 | 11 | 12000 / 0 / 0 |
| on-0.5ms | 148 | 0.102 | 5 | 9.873 | 1 | 12000 / 0 / 0 |

**판정**: **가설 기각**. 정지 tick 비 (0.5 ms / 5 ms) 가 off 1.29 · on 0.86 으로 둘 다 기각 기준 (≥ 0.8) 에 해당함. 탐색 결과라 결론에 인용하지 않음
**비고**:
- 전환 간격 0.5 ms 에서도 정지 중 CPU 비율이 약 0.1 로 그대로임 → write() 안의 기다림이 GIL 이 아닌 커널 · USB 시리얼 쪽 또는 OS 스케줄링 쪽일 가능성이 남음 (미측정 가설)
- 스레드 하나뿐인 `serial_link` 확인 실행 (03:48 · 03:56, 각 200 회) 에서도 write() max 2.8 / 2.1 / 1.5 ms 가 있었음 (횟수가 적어 판정 근거로 쓰지 않음)
- **런 간 변동이 매우 큼**: 같은 조건 (on · 5 ms · diag) 의 지연 tick 이 04:16 런 4 · 04:23 런 290. on-0.5ms 의 지연 tick 감소 (290 → 5) 를 전환 간격의 효과로 해석하지 않음
- ROS on 에서 정지 tick 이 많은 경향 (off 56–72 vs on 148–172) 과 ROS 콜백 겹침률 4.4–5.8 배는 이번에도 같음

## 4. 다음

- 원인 추적은 류시현 결정 (04:29) 으로 **보류**함. 남은 후보: (라) 커널 · USB 시리얼 (cdc-acm) 쪽 write() 지연, (마) OS 스케줄링, (나) CPU 클록 변화 (현 계측으로 판별 불가)
- 재개 시 첫 실험: 스레드 하나짜리 프로세스로 60 s (12 000 회) 측정해 정지 tick 수를 off-5ms 와 비교함
- 임시 계측 (`serial_link --trace`, `loop_bench --diag`, `tools/analyze_jitter.py`) 은 재개 때 필요하므로 지우지 않고 남김. 원인 확정 후 별도 커밋으로 제거함 (§5-3)
