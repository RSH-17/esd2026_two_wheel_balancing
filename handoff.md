# Handoff: SessionStart 훅 jq 의존 제거 (r4) — 다음은 훅 발화 확인 → imu_calib.py + CSV 로깅

**Last session close**: 2026-11-25 02:37 (종료 커밋은 이 파일과 함께 생성됨)
**상태**: ready

## 세션 시작의 순서
1. `git pull` → `git log --oneline 0eb06ee..HEAD` 로 지난 세션 이후 커밋을 **전부** 확인 (노트북 · Pi 양쪽 커밋 포함)
2. 이 파일 정독 → 「다음 작업 시퀀스」를 계획으로 보고 → 학생 승인 후 착수
3. **SessionStart 훅 (r4, jq 제거)** 이 컨텍스트에 `session_start_time:` 을 넣었는지 첫 턴에서 확인함.
   없으면 `/hooks` 로 확인하고, 직접 `date` · `git pull` 을 실행한 뒤 훅 명령을 손으로 재현해 원인을 보고함

## 다음 작업 시퀀스 (단일, 2026-11-24 10:08 handoff 에서 이어짐 — 아직 착수 안 함)
0. 훅 발화 확인 (위 3번) — 결과를 회의록에 적음
1. `src/sensing/imu_calib.py` 작성: `src/sensing/mpu6050_raw.py` 의 raw 값을 물리단위로 변환
   (가속도 ±2g → LSB/16384, 각속도 ±250°/s → LSB/131, 온도 raw/340+36.53), 자이로 bias 는 정지 상태
   n 샘플 평균으로 추정해 보정값 파일로 커밋, 장착 오프셋 θ₀ 측정 방법 포함
2. CSV 파일 로깅 추가 — 제어 루프는 **200Hz 목표**로 구현하고 평균·최대 Δt 를 실측해 로그에 남김
   (로그 필드는 §8-B 최소 집합: `t, tick, theta_deg, gyro_dps, wheel_l, wheel_r, u_l, u_r, vbat, i2c_err`,
   아직 모터·엔코더가 없으니 해당 칸은 빈 값으로 두고 어떤 칸이 비었는지 로그에 명시) →
   `python3 tools/check_log.py <로그> --rate <Hz>` 통과 확인
3. 미결 2 건 (아래) 을 학생이 결정

## 핵심 진입점
- `AGENTS.md` §1-1 (SessionStart 훅 강제) · §5-5 · §8-B · §9 r3 · r4 (훅 jq 제거)
- `.claude/settings.json` — SessionStart 훅 설정 (date + git pull, 일반 stdout, jq 없음)
- `docs/meeting-notes/2026-11-25-0229-hook-jq-fix.md` — 직전 회의록
- `src/sensing/mpu6050_raw.py` — raw 읽기 (WHO_AM_I 확인, ACC/GYRO 레이블 출력)
- `tools/check_log.py` — 로그 무결성 검사 (§4-5)

## 확정 (재론 불요)
- MPU-6050, bus=1, addr=0x68, WHO_AM_I 응답 확인됨 — raw 통신 정상
- `i2cdetect -y 1` 이 0x68 을 못 찾은 원인은 **GND 연결 불량** (학생 확인, 10-11-24 10:10)
- 커밋 trailer(`Assisted-by`) **미사용** — 류시현 (`AGENTS.md` §9 r2)
- §8-B 「Pi 3 B+」 문장 **정정하지 않음** — 류시현 (`AGENTS.md` §9 r2)
- CLI 디버그 출력(10Hz)은 유지, **제어 루프는 200Hz 목표** — 류시현, Δt 실측 필수
- **§1-1 세션 시작 시각 실측·git pull 은 SessionStart 훅으로 강제함** — 류시현 · 10:24 (`AGENTS.md` §9 r3,
  지시만으로는 4 연속 재발했기 때문)
- **훅에서 jq 의존 제거, 일반 stdout + `exit 0`** — 류시현 · 2026-11-25 (`AGENTS.md` §9 r4, 노트북 jq 미설치로 exit 127 이 계기)

## 미결 (결정할 사람)
- r4 훅이 새 세션에서 실제로 컨텍스트에 주입되는지 — 다음 세션 첫 턴에서 에이전트가 확인하고, 실패 시 대응은 학생이 결정
- 11-24 기록의 「`jq -e` 로 검증함」 과 노트북의 jq 부재가 어긋남 (검증 기기 미상) — 학생이 확인
- git `user.name` · `user.email` 이 미설정이라 커밋 때마다 `git -c` 로 지정 중 — 학생이 `git config --global` 로 설정
- 아두이노 연결 여부·방식 — 학생. 에이전트 권고: `pyserial`

## 환경 유의
- Pi 접속 정보는 `.env` 에만 둠, 커밋하지 않음
- `sudo` 가 필요한 명령(패키지 설치 등)은 비대화형 Bash 에서 비밀번호 입력이 불가함 — 학생이 직접 실행 (§3-4)
