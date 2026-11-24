# AI 사용 기록

이 파일은 **필수**입니다 (`AGENTS.md` §6-3). 에이전트와 일한 세션마다 한 줄을 추가합니다. 보고서의 「AI 사용 고지」 는 이 표에서 만듭니다.
세션 종료 절차 (`/session-close`) 에서 에이전트가 초안을 추가하고, 학생이 「검토한 범위」 를 직접 고칩니다. 항목은 「~함」 체로 적습니다.

- **한 일**: 에이전트가 만든 것 · 고친 것 · 조사한 것 (파일 이름이나 커밋으로)
- **학생이 검토한 범위**: 직접 읽고 확인한 부분. 「전부 검토」 처럼 쓰지 말고 무엇을 어떻게 확인했는지 적습니다
  (예: 「`ctrl/pid.py` 를 읽고 시뮬레이터 계단응답으로 확인함」, 「표 2 의 수치를 로그와 대조함」)
- 에이전트가 틀린 것을 학생이 잡았다면 그것도 적습니다 — 그 기록이 다음 규칙 개정의 근거가 됩니다

| 날짜 | 도구 · 모델 | 한 일 | 학생이 검토한 범위 | 회의록 |
|---|---|---|---|---|
| YYYY-MM-DD | <예: Kiro · Auto> | <예: `tools/plot.py` 작성함> | <예: 출력 그림을 로그와 대조함> | `docs/meeting-notes/<파일>` |
| 2026-11-24 | Claude Code · Opus 5 | `AGENTS.md` 전문을 읽고 절별로 설명함, §9 개정 이력 r0 · r1 행을 `git log` 실측 날짜로 채움 (`d1f4601`), 세션 기록 3 건 작성함 | `<학생이 채움 — §6-3>` | `docs/meeting-notes/2026-11-24-1151-rules-revision-history.md` |
| 2026-11-24 | Claude Code · Sonnet 5 | GPIO/I2C 라이브러리(`lgpio`, `smbus2`) 선정 근거와 장단점을 정리함, 설치 전 호스트 상태(`uname` · `groups` · `apt-cache policy`)를 점검함, 패키지명 오류(`python-smbus3` → `python3-smbus2`)를 정정함, 설치 완료를 `dpkg -l` 로 확인함, I2C 통신 확인 절차(`i2cdetect` · `WHO_AM_I`)를 제시함 | `<학생이 채움 — §6-3>` | `docs/meeting-notes/2026-11-24-0941-lgpio-smbus2-setup.md` |
| 2026-11-24 | Claude Code · Sonnet 5 | `src/sensing/mpu6050_raw.py` 작성함(`af7f54e`), WHO_AM_I·raw 값을 직접 실행해 검증함, 가독성 요청에 따라 ACC/GYRO 레이블 출력으로 수정함(`cd9b8e0`), raw LSB 단위를 설명함. 세션 시작 시각 실측(§1-1)을 또 누락함(3 연속) | `<학생이 채움 — §6-3>` | `docs/meeting-notes/2026-11-24-0946-imu-raw-read.md` |
| 2026-11-24 | Claude Code · Sonnet 5 | i2cdetect 미응답 원인을 「quick-write probe 비호환」으로 잘못 추정했던 것을 학생 피드백(GND 연결 불량)으로 정정함(`e5b3cb3`), 미결 5 건을 추천 우선으로 설명함, 학생이 결정한 trailer 미사용·§8-B 문장 유지를 `AGENTS.md` §9 r2 에 기록함(`f42795e`), CLI/제어 루프 주기 결정을 handoff 에 반영함(`273cc08`). 세션 시작 시각 실측(§1-1)을 또 누락함(4 연속) | `<학생이 채움 — §6-3>` | `docs/meeting-notes/2026-11-24-1006-decisions-and-correction.md` |
| 2026-11-24 | Claude Code · Sonnet 5 | 세션 시작 시각 실측을 처음 턴에서 성공함(4 연속 재발 종료), §1-1 미결 상세 설명함, 학생 제안으로 `.claude/settings.json` 에 SessionStart 훅(`date`+`git pull` 자동 실행·주입) 을 `update-config` 스킬로 추가하고 pipe-test·`jq -e`·디코딩 실행으로 검증함, `AGENTS.md` §1-1 문구와 §9 r3 를 갱신함(`37ee535`) | `<학생이 채움 — §6-3>` | `docs/meeting-notes/2026-11-24-1020-session-start-hook.md` |
