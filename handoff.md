# Handoff: 규칙 파일 확정 — 다음은 Pi 환경과 첫 IMU 로그

**Last session close**: 2026-11-24 11:53 (commit `d1f4601` 기준, 종료 커밋은 이 파일과 함께 생성됨)
**상태**: ready

## 세션 시작의 순서
1. `git pull` → `git log --oneline d1f4601..HEAD` 로 지난 세션 이후 커밋을 **전부** 확인 (노트북 · Pi 양쪽 커밋 포함)
2. 이 파일 정독 → 「다음 작업 시퀀스」 를 계획으로 보고 → 학생 승인 후 착수
3. 첫 턴에서 `date +"%Y-%m-%d %H:%M"` 을 읽어 세션 시작 시각을 남김
   (지난 세션에서 P1 · P2 의 입력 시각이 실측되지 않아 영구 미기록으로 남았음)

## 다음 작업 시퀀스 (단일)
1. 미결 두 건을 결정받아 반영함 — ① 커밋 trailer 사용 여부 (§7-3) ② §8-B 의 「Pi 3 B+」 문장 (§0 은 Pi 4 Model B).
   결정한 내용을 `AGENTS.md` §9 에 한 행씩 추가하고 단독 `rules:` 커밋으로 push 함
2. Pi 환경을 구성함 — Ubuntu 24.04 LTS 64-bit 설치 · SSH 접속 · 사용자 그룹 (`gpio` `i2c` `video`) 확인 ·
   저장소 clone. `sudo` 가 필요한 시스템 설정은 학생이 직접 실행함 (§3-4)
3. MPU-6050 을 I2C 로 읽어 `logs/` 에 CSV 로 저장하고 `python3 tools/check_log.py <로그> --rate <Hz>` 를 통과시킴.
   로그 필드는 §8-B 의 최소 집합을 따르고, 이 단계에서는 모터를 돌리지 않음 (센서 읽기만)

## 핵심 진입점
- `AGENTS.md` — 규칙 원본 (§9 개정 이력 r0 · r1 기입 완료)
- `docs/meeting-notes/2026-11-24-1151-rules-revision-history.md` — 직전 회의록
- `docs/meeting-notes/TEMPLATE.md` · `logs/experiments/TEMPLATE.md` — 기록 틀
- `tools/check_log.py` — 로그 무결성 검사 (§4-5)

## 확정 (재론 불요)
- `AGENTS.md` §0 프로젝트 개요 · §8-B 주제별 규칙 — 류시현 · 2026-11-23 · 커밋 `4098cc9` · `a456090`
- §9 개정 이력 r0 (2026-10-05 착수) · r1 (2026-11-23 지시) — 류시현 · 2026-11-24 ·
  `docs/meeting-notes/2026-11-24-1151-rules-revision-history.md`
- Claude Code 가 `CLAUDE.md` → `@AGENTS.md` 로 규칙 전문을 읽음을 확인함 (README 「규칙 적재 확인」 양성 대조) —
  2026-11-23 · 같은 회의록
- 커밋 메시지 언어는 영어 (§6-7 에 규정되어 있음 — 재론 불요)

## 미결 (결정할 사람)
- 커밋 trailer (`Assisted-by:` 또는 `Co-Authored-By:`) 사용 여부 — 학생.
  지난 세션 커밋 `d1f4601` 에는 `Co-Authored-By: Claude Opus 5` 가 붙어 있음 (에이전트 가정, 사후 확인 필요)
- §8-B 「Pi 3 B+ 는 특히 그렇습니다」 문장 정정 — 학생
- §1-1 에 「세션 시작 시각 실측」 단계를 넣을지 (규칙 개정 후보) — 학생

## 환경 유의
- Pi 접속 정보 (IP · 계정) 는 `.env` 에만 둠. 커밋하지 않음
- 노트북 · Pi 양쪽에서 커밋하므로 기기를 옮기기 전에 반드시 push 함 (§7-1)
