# Handoff: lgpio·smbus2 설치 완료 — 다음은 I2C 통신 확인과 IMU 로그

**Last session close**: 2026-11-24 09:41 (종료 커밋은 이 파일과 함께 생성됨)
**상태**: ready

## 세션 시작의 순서
1. `git pull` → `git log --oneline 221777f..HEAD` 로 지난 세션 이후 커밋을 **전부** 확인 (노트북 · Pi 양쪽 커밋 포함)
2. 이 파일 정독 → 「다음 작업 시퀀스」를 계획으로 보고 → 학생 승인 후 착수
3. 첫 턴에서 `date +"%Y-%m-%d %H:%M"` 을 읽어 세션 시작 시각을 남김
   (2 연속 세션에서 이 단계가 누락되어 P1 들의 입력 시각이 영구 미기록으로 남았음)

## 다음 작업 시퀀스 (단일)
1. `i2cdetect -y 1` 로 MPU-6050 버스 스캔 (`0x68`/`0x69` 응답 확인) → `WHO_AM_I` (레지스터 0x75) 읽기로 실제
   통신을 확인함. 이 단계에서 모터는 돌리지 않음
2. 통신이 확인되면 MPU-6050 을 `smbus2` 로 읽어 `logs/` 에 CSV 로 저장하고
   `python3 tools/check_log.py <로그> --rate <Hz>` 를 통과시킴. 로그 필드는 §8-B 최소 집합
   (`t, tick, theta_deg, gyro_dps, wheel_l, wheel_r, u_l, u_r, vbat, i2c_err`) 을 따르고, 보정 코드는
   `src/sensing/imu_calib.py` 한 곳에 둠
3. 미결 4 건 (커밋 trailer 사용 여부, §8-B 「Pi 3 B+」 문장, §1-1 시작 시각 실측 규칙, 아두이노 연결 방식) 을
   결정받아 반영하고 §9 에 기록함

## 핵심 진입점
- `AGENTS.md` §3-4 (sudo 최소화) · §8-B (이륜 로봇 주제별 규칙)
- `docs/meeting-notes/2026-11-24-0941-lgpio-smbus2-setup.md` — 직전 회의록
- `hw/limits.py` — 액추에이터 한계값 (모터 코드 작성 시 참조)
- `tools/check_log.py` — 로그 무결성 검사 (§4-5)

## 확정 (재론 불요)
- GPIO 라이브러리 `lgpio`, I2C 라이브러리 `smbus2` 채택 — 류시현 · 2026-11-24
- `python3-lgpio` · `python3-smbus2` · `i2c-tools` 설치 완료 (Pi, Ubuntu 24.04.5, aarch64) — `dpkg -l` 로 확인
- 사용자 `ryu` 는 이미 `gpio` `i2c` `spi` 그룹에 속해 있어 추가 그룹 설정 불필요 — `groups` 로 확인
- 아두이노 연결은 지금 다루지 않음 (방식은 미결, 아래)

## 미결 (결정할 사람)
- 커밋 trailer 사용 여부 — 학생 (이전 세션부터 이어짐)
- §8-B 「Pi 3 B+」 문장 정정 — 학생 (이전 세션부터 이어짐)
- §1-1 세션 시작 시각 실측 단계 추가 여부 — 학생 (2 연속 세션 재발)
- 아두이노 연결 여부·방식 — 학생. 에이전트 권고: `pyserial` (단순, 200 Hz 루프 오버헤드가 적음). micro-ROS 는 대안

## 환경 유의
- Pi 접속 정보는 `.env` 에만 둠, 커밋하지 않음
- `sudo` 가 필요한 명령(패키지 설치 등)은 비대화형 Bash 에서 비밀번호 입력이 불가함 — 학생이 자신의 터미널에서
  직접 실행함 (§3-4)
