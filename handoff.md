# Handoff: Pi↔Uno 시리얼 링크 동작 확인 완료 — 다음은 IMU 재연결 → imu_calib.py → `--imu on` baseline

**Last session close**: 2026-11-25 04:33 (Pi, 종료 커밋은 이 파일과 함께 생성됨)
**상태**: ready — 학생 답 2 건 (마감 · ROS 필수 여부) 대기

## 세션 시작의 순서
1. 훅 출력 `session_start_time:` 을 확인함 (노트북 · Pi 모두 동작 확인됨). 기기마다 `timedatectl` 로 시간대가 KST 인지 확인함
2. `git log --oneline 24f9e69..HEAD` 로 커밋을 **전부** 확인함 (이번 세션 12 건 + 종료 커밋)
3. 이 파일을 정독함 → 아래 시퀀스를 계획으로 보고 → 승인 후 착수

## 다음 작업 시퀀스 (단일)
1. 류시현에게 답 2 건을 받음: 11-28 마감 여부, 과목에서 ROS 2 가 필수인지
2. 학생이 MPU-6050 을 Pi I2C (bus 1, 0x68) 에 다시 연결함 → `python3 src/sensing/mpu6050_raw.py` 로 WHO_AM_I 와 raw 값을 확인함
3. `src/sensing/imu_calib.py` 를 작성함: 축 방향 · θ₀ · gyro bias · raw→deg/dps 변환을 한 곳에 둠 (§5-5 · §8-B). 보정값 파일을 커밋함
4. `loop_bench` 의 `theta_deg` · `gyro_dps` 열을 `imu_calib` 로 채움
5. 새 사전등재를 만들어 `--imu on` 으로 ROS off/on baseline 을 측정함 (탐색 1 회 → 확증 3 회). 기준은 `2026-11-25-loop-timing-baseline.md` 와 같게 둠
6. 그 결과로 류시현이 A/B 를 결정함 (A: IMU 는 Pi / B: Uno)

## 핵심 진입점
- 회의록 `docs/meeting-notes/2026-11-25-0309-arduino-serial-link-stage1.md`
- 실험 기록 `logs/experiments/2026-11-25-{loop-timing-baseline,loop-jitter-cause,gil-switch-interval}.md`
- `firmware/serial_link/serial_link.ino` · `src/comm/serial_link.py` · `src/control/loop_bench.py` · `tests/test_serial_link.py`
- 빌드: `~/.local/bin/arduino-cli compile -b arduino:avr:uno firmware/serial_link` (업로드는 `upload -p /dev/serial/by-id/usb-Arduino* …`)

## 확정 (재론 불요)
- MPU-6050 은 bus=1, addr=0x68 (2026-11-24 확인됨). 지금은 **미연결**
- Uno R3 가 PWM 을 맡음 · 엔코더 없음 · USB 연결 · 제어는 순수 Python 스레드, ROS 는 파라미터 · 모니터링만 — 류시현 (11-25 02:42 · 02:56)
- 제어 루프 200 Hz 목표 · Δt 는 실측 — 류시현
- Pi 시간대는 `Asia/Seoul`, 시계는 NTP — 류시현 · 03:21
- 링크 프로토콜 `M,seq,u_l,u_r,*CK` / `A,seq,crc_err,fmt_err,wd_trip,*CK`, ‰ 단위, 115200 baud (가정으로 보고함, 반대 의견 없음)
- 펌웨어 watchdog 50 ms 가 실제로 동작함 (pc2). `MOTOR_ENABLE 1` 은 컴파일 에러로 막혀 있음 — 모터 출력은 별도 계획이 필요함
- RTT 는 tight 모드에서 약 3–7 ms (n=1) → 응답을 기다리는 동기 방식은 쓰지 않음
- baseline 기준 3 「응답이 2 tick 이내」 · 로그는 `logs/runs/` 에 커밋함 · 구동 명령이 없는 측정은 에이전트가 실행함 — 류시현 · 04:04
- 지연 원인 추적은 보류함 (GIL 가설은 기각됨) — 류시현 · 04:29

## 미결 (결정할 사람)
- 11-28 마감 · 과목에서 ROS 2 가 필수인지 — 류시현
- 지연 원인 추적을 언제 재개할지 — 류시현 (권고: IMU 를 연결한 뒤 제어에서 문제가 될 때). 재개 시 첫 실험은 스레드 하나짜리 60 s 측정
- 회의록의 규칙 개정 후보 4 건을 승격할지 — 류시현
- git 전역 `user.name` · `user.email` (Pi 는 저장소 로컬 설정에만 있음), 「`jq -e` 검증 기기」 — 류시현

## 환경 유의
- 임시 계측 `serial_link --trace` · `loop_bench --diag` · `tools/analyze_jitter.py` 는 추적을 재개할 때 쓰려고 **일부러 남겨 둠**. 원인이 확정되면 별도 커밋으로 지움 (§5-3)
- 학생에게 줄 명령은 짧게 함: 긴 명령은 붙여 넣는 중에 줄이 나뉘어 따로 실행된 적이 있음
- `~/.local/bin` 은 다시 로그인하기 전까지 PATH 에 없음. arduino-cli 는 전체 경로로 씀
- `sudo` 명령은 학생이 직접 실행함 (§3-4). Pi 접속 정보는 `.env` 에만 둠
