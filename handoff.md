# Handoff: Pi↔Uno 시리얼 구조 결정 — 다음은 1 단계(시리얼 링크 + 실부하 Δt 측정) 승인 → 구현

**Last session close**: 2026-11-25 02:58 (종료 커밋은 이 파일과 함께 생성됨)
**상태**: ready — 1 단계 계획 보고 완료, **승인 대기**

## 세션 시작의 순서
1. SessionStart 훅 출력(`session_start_time:`)이 컨텍스트에 있는지 확인함. 노트북에서는 동작을 확인함. Pi 에서는 처음이므로 결과를 회의록에 적음
2. `git log --oneline 9ebc0bf..HEAD` 로 커밋을 **전부** 확인 (노트북 · Pi 양쪽)
3. 이 파일 정독 → 아래 시퀀스를 계획으로 보고 → 승인 후 착수

## 다음 작업 시퀀스 (단일)
1. 학생에게 1 단계 계획 승인과 답 3 건을 받음: 업로드 방법(권고 Pi `arduino-cli`), Pi 의 ROS 2 Jazzy 설치 여부, RTT 판정 기준(2.5 ms 는 가정)
2. 모터 · 드라이버는 **미연결**. 펌웨어는 `MOTOR_ENABLE 0` 으로 빌드. 작성 대상:
   - `firmware/serial_link/serial_link.ino`: READY, `M,seq,u_l,u_r,*CK` 파싱 → `A,seq,crc_err,wd_trip` 응답, 50 ms watchdog, LED13 표시
   - `src/comm/serial_link.py`: by-id 포트, READY 대기 5 s, 순번 · XOR 체크섬, 실패 집계
3. pty 루프백 단위 시험을 노트북에서 통과시킴
4. `src/control/loop_bench.py` 작성: 제어 · 로그 · ROS 3 스레드, `--ros off/on`. 사전등재 `logs/experiments/2026-11-2x-loop-timing-baseline.md` 를 먼저 커밋
5. 학생이 Pi 에서 실행 — 양성 대조 3 개(체크섬 오류 주입 · 송신 100 ms 정지 · CSV 행 삭제) → 본 측정 60 s, 탐색 n=1 → 확증 n=3 → 수치 표로 보고
6. 류시현이 A/B 결정 (A: IMU 는 Pi 유지 / B: IMU 를 Uno 로). 마감 11-28 은 **가정**임. 그 뒤 `imu_calib.py` → CSV 로깅으로 복귀

## 핵심 진입점
- `docs/meeting-notes/2026-11-25-0239-arduino-serial-architecture.md` — 직전 회의록 (1 단계 계획 원문)
- `src/sensing/mpu6050_raw.py` · `hw/limits.py` · `tools/check_log.py`
- `AGENTS.md` §3-1 (구동 입회) · §4 · §5-4 (전제 검사) · §8-B

## 확정 (재론 불요)
- MPU-6050, bus=1, addr=0x68, WHO_AM_I 응답 확인됨. i2cdetect 실패 원인은 GND 불량 (2026-11-24 10:10 확인)
- 커밋 trailer 미사용 · §8-B 「Pi 3 B+」 문장 유지 — 류시현 (§9 r2)
- 제어 루프는 **200 Hz 목표**, Δt 실측 필수 — 류시현
- SessionStart 훅(r3, r4 jq 제거) — 노트북에서 동작 확인 (2026-11-25 02:39)
- **아두이노 = Uno R3, 모터 PWM 담당, 엔코더 없음** — 류시현 · 2026-11-25 02:42 경
- **제어 루프는 순수 Python 스레드에서 돌림. ROS 2 는 같은 프로세스의 별도 스레드에서 파라미터 · 모니터링만 맡음. 로그는 별도 스레드에서 CSV 로 씀** — 류시현 · 2026-11-25 02:56
- Pi↔Uno 연결은 USB 케이블 (GPIO UART 를 쓰려면 5 V→3.3 V 레벨 시프터 필수)

## 미결 (결정할 사람)
- 1 단계 계획 승인 · 업로드 방법 · RTT 기준 · 11-28 마감 — 류시현
- 과목에서 ROS 2 사용이 필수인지 — 류시현
- git 전역 `user.name` · `user.email` 설정 (지금은 매번 `git -c` 로 지정) — 류시현
- 11-24 기록의 「`jq -e` 검증」 을 한 기기 — 류시현

## 환경 유의
- Pi 접속 정보는 `.env` 에만 둠, 커밋하지 않음
- `sudo` 명령(`usermod -aG dialout` 등)은 학생이 직접 실행 (§3-4)
- 엔코더가 없으므로 위치 drift 는 외부 측정(바닥 표시)이 필요하고, 속도 루프는 구성할 수 없음
