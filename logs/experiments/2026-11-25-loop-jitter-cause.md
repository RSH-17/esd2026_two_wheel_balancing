# 실험: scout-on 의 몰린 Δt 지연 · write() 정지 원인 분리 (ROS off / on, --diag)

**파일명**: `logs/experiments/2026-11-25-loop-jitter-cause.md` · **선행 실험**: `logs/experiments/2026-11-25-loop-timing-baseline.md` (scout-on VOID) · **회의록**: 이 세션 종료 때 작성함

## 1. 사전등재 (실행 전)

- **배경**: scout-on (04:09) 에서 Δt > 7.5 ms 4 건이 t ≈ 20.15–20.23 s 의 약 80 ms 에 몰렸고, 그 구간에서 `write()` 가 2.2–3.3 ms 씩 반복해 걸림. `work_us` > 3 ms 는 off 35 회 · on 27 회로 양쪽에 있음
- **후보 (하나로 좁히는 것이 목적, §5-2)**
  - (가) ROS 스레드 (DDS · GIL) 가 제어 스레드를 밀어냄
  - (나) ROS 와 무관한 시스템 사건 (같은 Pi 의 Claude Code 세션 · `ondemand` 클록 변화 · USB 처리)
  - (다) 시리얼 `write()` 자체의 정지 (드라이버 · USB 쪽), ROS 유무와 무관
- **비교 대상**: `--ros off` vs `--ros on`, 둘 다 `--diag`
- **정합 축 · 공통 조건**: 선행 실험과 같음 (60 s = 12 000 tick, 명령 0, `--rate 200` · `--imu off` · baud 115200 · `MOTOR_ENABLE 0`, 모터 · IMU 미연결, governor `ondemand`, Claude Code 세션 동시 실행). 순서는 off → on
  - `--diag` 는 tick 마다 `out_waiting` ioctl 2 회와 10 Hz sampler 스레드를 더함 → 양쪽에 같게 들어감. 선행 실험 수치와 직접 비교하지 않음
- **기록하는 것 (`--diag`)**: tick 마다 `t_mono_ns` · `cpu_us` (스레드 CPU 시간) · `write_t0_ns` · `write_cpu_us` · `outq_before/after`. `-events.csv` 에 ROS 콜백 · 로그 flush 의 시작/끝 시각, 10 Hz `cpu0_khz` · `loadavg1`
- **정의**: 「정지 tick」 = `write_us` > 2000 µs 인 tick. 「지연 tick」 = Δt > 7.5 ms 인 tick
- **판정 규칙 (분석 스크립트로 계산, 결과를 본 뒤 바꾸지 않음)**
  - 스크립트: `python3 tools/analyze_jitter.py <off 런> <on 런>` (측정 전에 이 등재와 함께 커밋함)
  - 겹침률 = 정지 tick 의 write 구간 `[write_t0, write_t0 + write_us]` 이 ROS 콜백 (또는 로그 flush) 구간과 겹치는 비율. 구간은 제어 루프가 도는 동안의 것만 셈
  - 우연 기대치 = (해당 스레드 구간의 총 시간 + 정지 tick 의 평균 write 시간 × 구간 수) / 런 전체 시간
  - (가) 지지: on 에서 ROS 콜백 겹침률 ≥ 3 × 우연 기대치, **그리고** 정지 tick 의 `write_cpu_us` / `write_us` 중앙값 < 0.5 (CPU 를 쓰지 못하고 기다림)
  - (다) 지지: off 와 on 의 정지 tick 수가 서로 2 배 이내이고, 어느 스레드와의 겹침률도 3 × 우연 기대치 미만
  - (나) 지지: 정지 tick 중 `cpu0_khz` 변화 앞뒤 50 ms 안에 있는 비율이 50 % 이상이고, 전체 tick 의 같은 비율의 1.5 배 이상. 단 전체 tick 의 비율이 0.5 를 넘으면 「이 계측으로 (나) 판별 불가」 로 보고함
  - 위 규칙 중 둘 이상이 지지되거나 아무것도 지지되지 않으면 「판정 불가」 로 보고함
  - **등재 전 수정 기록**: 3 s 동작 확인 (scratchpad, 비인용) 에서 (나) 의 원래 규칙 (앞뒤 100 ms, 기준선 없음) 이 클록 변화가 초당 약 7 회라 런 전체를 덮어 항상 참이 됨을 발견해 위처럼 고침. 같은 확인에서 READY 대기 중의 ROS 콜백이 우연 기대치에 들어가는 오류도 고침. 둘 다 본 측정 전임
- **단계**: 각 n = 1 (원인 분리용 탐색). 결론 · 보고서에 인용하지 않음. 원인이 하나로 좁혀지면 고친 뒤 선행 실험의 판정 기준으로 다시 등재함
- **중단 기준**: 두 런 모두 정지 tick 이 0 이면 「재현 안 됨」 으로 보고하고 멈춤
- **로그 위치**: `logs/runs/2026-11-25-loop-jitter-cause/` 에 커밋함 (선행 실험과 같은 결정 — 류시현 · 04:04)

## 2. 실행 기록

| 런 | 조건 | 시각 | 로그 | 실제 적용값 (meta 에서 읽음) | `check_log.py` |
|---|---|---|---|---|---|
| diag-off | ros off · `--diag` | 04:15 | `logs/runs/2026-11-25-loop-jitter-cause/diag-off` | fw `serial_link-0.1` · motor 0 · wd 50 ms · imu off · governor ondemand · diag true | VOID (gap 7.6 ms) |
| diag-on | ros on · `--diag` | 04:16 | `…/diag-on` | 위와 같음 + `rmw_fastrtps_cpp` | VOID (gap 9.7 ms) |

- switch interval 은 이 실험 당시 meta 에 기록하지 않았음 (필드 추가 전)

## 3. 결과

`python3 tools/analyze_jitter.py diag-off diag-on` 출력 (n = 1 씩):

| 지표 | diag-off | diag-on |
|---|---|---|
| Δt mean ± sd · p99 · max [ms] | 5.000 ± 0.068 · 5.082 · 7.617 | 5.000 ± 0.124 · 5.092 · 9.748 |
| 정지 tick (write > 2 ms) | 52 | 79 |
| 지연 tick (Δt > 7.5 ms) | 1 | 4 |
| 정지 tick 의 write CPU 비율 중앙값 | 0.098 | 0.113 |
| outq_before > 0 인 tick | 0 | 0 |
| ROS 콜백 겹침률 (우연 기대치, 배수) | — | 0.570 (0.152, 3.74 배) |
| 로그 flush 겹침률 | 0 / 52 | 0 / 79 |
| cpu0 클록 변화 · 변화 ±50 ms 가 덮는 tick 비율 | 306 회 · 0.510 | 410 회 · 0.683 |
| 링크 (ack / lost / Uno 카운터) | 12000 / 0 / 0 | 12000 / 0 / 0 |

**판정**: 등재 규칙상 **(가) ROS 경합 지지** (겹침률 3.74 배 ≥ 3, CPU 비율 0.113 < 0.5). (다) 지지 안 됨, (나) 이 계측으로 판별 불가. 탐색 결과라 결론에 인용하지 않음
**비고**:
- ROS 가 없는 diag-off 에도 정지 tick 이 52 개 있었고, 어느 기록된 스레드 구간과도 겹치지 않음 → ROS 는 정지를 늘리는 요인일 수 있으나 유일한 원인으로 설명되지 않음
- 양쪽 모두 정지 중 CPU 비율이 약 0.1 이고 OS 출력 큐는 비어 있었음 → 제어 스레드가 write() 안에서 「기다림」. 이를 근거로 GIL 전환 간격 가설을 세워 다음 실험으로 검사함
- diag-off 도 VOID 가 되어 선행 scout-off (PASS) 와 다름. `--diag` 부하 탓인지 런 간 변동인지 구분하지 못함

## 4. 다음

- `2026-11-25-gil-switch-interval.md` 로 이어짐 (GIL 가설 제거 실험)
