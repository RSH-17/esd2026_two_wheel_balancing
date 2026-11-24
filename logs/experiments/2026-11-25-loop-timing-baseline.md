# 실험: 200 Hz 제어 스레드 + Uno 시리얼 왕복의 루프 주기 baseline (ROS off / on)

**파일명**: `logs/experiments/2026-11-25-loop-timing-baseline.md` · **회의록**: 이 세션 종료 때 작성함

## 1. 사전등재 (실행 전)

- **질문 / 가설**
  - Q1: Pi 의 순수 Python 제어 스레드가 Uno 시리얼 송수신을 포함해 200 Hz 주기를 유지하는가
  - Q2: 같은 프로세스에 ROS 2 스레드(파라미터 1 개 + 50 Hz status 발행)를 켜면 루프 주기 · 링크 지연이 판정 기준을 벗어나는가
  - 방향 가설은 두지 않음 (ROS 가 Δt 를 늘린다는 주장은 측정 전이므로 쓰지 않음, §4-7)
- **비교 대상**: `--ros off` (baseline) vs `--ros on`
- **정합 축**: 런마다 60 s = 12 000 tick, 명령은 항상 0, 같은 펌웨어(`serial_link-0.1`, `MOTOR_ENABLE 0`) · 같은 포트. 런 순서는 off → on 교대로 해 시간 · 온도 변화가 한쪽에 몰리지 않게 함
- **공통 조건 (명령행 · 상수 하나로 양쪽에 같은 값, 실제값은 `-meta.json` 에 남음)**
  - `--rate 200` · `--duration 60` · `--imu off` · baud 115200 · `ack_timeout` 0.1 s · `MOTOR_MAX_DUTY` 0.6 (명령이 0 이라 clip 없음)
  - CPU governor `ondemand` (변경하지 않음, 실제값을 meta 에 기록), I2C 클록 100 kHz (IMU off 라 미사용)
  - 모터 · 드라이버 · 배터리 미연결, MPU-6050 미연결. Pi 에서는 Claude Code 세션이 함께 돌고 있음 (모든 런 공통)
- **한계 (사전에 명시)**: IMU 가 미연결이라 실부하 중 IMU burst read 가 빠짐. 이 실험만으로 A/B (IMU 를 Pi / Uno) 결정을 내리지 않음. IMU 연결 후 같은 벤치를 `--imu on` 으로 다시 측정함
- **양성 대조 (본 측정 전 각 1 회, 기대 결과)**
  1. `--inject-crc-at 30` → `remote_crc_err` = 1, `lost` = 1
  2. `--pause-at 30 --pause-ms 100` → `remote_wd_trip` = 1, `check_log` VOID (최대 gap ≈ 105 ms)
  3. 정상 런 CSV 의 복사본에서 1 행 삭제 → `check_log` VOID (tick 불연속)
  - 셋 중 하나라도 기대와 다르면 본 측정을 하지 않음
- **로그 위치**: `logs/runs/2026-11-25-loop-timing/<런 이름>{.csv,-acks.csv,-meta.json}` 에 두고 커밋함 — 류시현 · 04:04 결정. 실행은 에이전트가 함 (구동 명령 없음) — 류시현 · 04:04 결정
- **단계**: scout off · on 각 n = 1 → 둘 다 판정 기준 통과면 확증 off · on 각 n = 3 (교대 순서)
- **판정 기준 (런마다 전부 만족해야 「통과」)**
  1. 로그 무결: `python3 tools/check_log.py <run>.csv --rate 200` PASS (샘플 수 ±1 %, 최대 Δt < 7.5 ms, tick 연속)
  2. 링크 무결: `lost` = 0, `bad_ack` = 0, `unknown_seq` = 0, Uno 의 `crc_err` = `fmt_err` = `wd_trip` = 0
  3. 명령 지연: 루프 구간의 모든 ack 가 송신 후 **2 tick 이내**에 보임 (`ack_lag_ticks` 의 최대 키 ≤ 2) — 류시현 · 04:04 결정
  - Q2 판정: on 런이 기준 1–3 을 모두 통과하면 「ROS 스레드 허용」. off / on 의 Δt p99 · max 와 `work_us` p99 는 mean ± sd 로 함께 보고하되 판정에 쓰지 않음
- **중단 기준**: scout 에서 어느 런이라도 기준 1–3 중 하나를 못 넘으면 확증을 돌리지 않고 보고함 (§4-2)
- **참고 (판정에 쓰지 않음)**: 3 s 동작 확인(04:01–04:02, scratchpad, 무효 · 비인용)에서 최대 Δt 가 off 6.8 ms · on 7.2 ms 였음

## 2. 실행 기록

| 런 | 조건 | 시각 | 로그 | 실제 적용값 (meta 에서 읽음) | `check_log.py` |
|---|---|---|---|---|---|

## 3. 결과

| 조건 | n | 지표 (mean ± sd) | baseline 대비 |
|---|---|---|---|

**판정**:
**비고**:

## 4. 다음

-
