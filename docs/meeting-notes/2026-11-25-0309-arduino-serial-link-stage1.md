# 회의록: Pi 시간대 정정 · Pi↔Uno 시리얼 링크 1 단계 구현 · 루프 주기 측정과 지연 원인 추적 (보류)

**Date**: 2026-11-25 · **세션**: [03:09]–[04:30] · **Status**: Draft
**작성**: 에이전트 (Claude Code · Opus 5.5, 세션 종료 시 작성) · **검토**: 류시현 [HH:MM — 학생이 채움]
**직전 회의록**: `docs/meeting-notes/2026-11-25-0239-arduino-serial-architecture.md`

> 시각 주의: 세션 시작 때 SessionStart 훅이 주입한 시각은 `2026-11-24 18:09` 이었음. 이 시각은 Pi 의 시간대가 UTC 였던 탓이고, KST 로 바꾸면 **2026-11-25 03:09** 임 (03:20 에 확인, 03:21 에 정정). 이 회의록의 시각은 모두 KST 임

## 진행

### [03:09] 세션 시작 — Pi 에서 처음으로 훅 동작을 확인함, 계획 보고 (P1)
- **Pi 에서도 SessionStart 훅이 동작함**: `session_start_time` 과 `git pull: Already up to date.` 가 주입됨. Pi 에서 확인한 것은 이번이 처음임
- `9ebc0bf..HEAD` 범위의 커밋은 `24f9e69` (직전 종료 커밋) 1 건뿐임. Pi 쪽 새 커밋은 없음
- handoff · 직전 회의록을 읽고 아두이노 관련 확정 · 1 단계 계획 · 가정 · 질문을 정리해 보고함
- 훅 시각 (11-24 18:09) 이 직전 세션 종료 시각 (11-25 02:58) 보다 앞서는 것을 발견함. 「Pi 가 UTC 로 설정되어 있음」 을 가설로 보고함

### [03:20–03:21] Pi 시간대 정정 (P2 · P3)
- 학생은 「host 시간으로 동기화」 를 요청함 (P2). `timedatectl` 로 확인한 상태는 다음과 같았음
  - 시간대 `Etc/UTC`
  - `System clock synchronized: yes` · timesyncd 가 `ntp.ubuntu.com` 과 동기화 중 · 오차 +3.954 ms
  - 즉 시계는 맞고 **시간대만 UTC** 였음
- host 동기화를 하면 시각 출처가 NTP 보다 나빠진다고 설명하고, 시간대만 바꾸자고 제안함. `sudo` 가 필요해 명령만 제시함 (§3-4)
- 학생이 `sudo timedatectl set-timezone Asia/Seoul` 을 실행함. 재확인 (P3) 에서 `Asia/Seoul (KST, +0900)` 와 동기화 `yes` 를 확인함 [03:21]

### [03:23] 1 단계 승인 · 환경 확인 · 링크 구현 (P4)
- 학생이 1 단계 계획을 승인함. Uno 는 Pi USB 에 연결된 상태였음
- 환경 확인 결과
  - Uno R3 는 `/dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_…-if00` → `ttyACM0`
  - `dialout` 그룹 소속 · pyserial 3.5
  - **ROS 2 Jazzy 설치되어 있고 rclpy 를 불러올 수 있음** (질문 「Pi 에 ROS 2 가 설치되어 있는가」 해결)
  - `arduino-cli` 는 없음
- `firmware/serial_link/serial_link.ino` 작성: READY 배너, `M`/`A` 줄 프로토콜 + XOR 체크섬, `crc_err` · `fmt_err` · `wd_trip` 카운터, 50 ms watchdog, LED13 = 트립. `MOTOR_ENABLE 1` 이면 컴파일이 `#error` 로 멈춤
- `src/comm/serial_link.py` 작성: by-id 포트, READY 를 5 s 기다림, 응답을 기다리지 않는 `send` / `poll`, `MOTOR_MAX_DUTY` 로 출력 제한, 실패를 모두 셈
- `tests/test_serial_link.py` 작성: pty 루프백 시험 9 개가 Pi 에서 통과함
  - 시험이 실제로 결함을 잡는지 확인함 (양성 대조): ack 체크섬 검사를 빼면 2 개가 FAIL 함
  - 에이전트가 손으로 계산한 체크섬 기댓값 (0x5D) 이 틀렸던 것을 0x7D 로 바로잡음
- 계획과 달리 한 것 (가정으로 보고함): 응답에 `fmt_err` 와 `*CK` 를 추가함, 명령 단위를 ‰ 정수로 정함, 보드레이트 115200

### [03:34–03:38] arduino-cli 설치 · 컴파일 (P5)
- v1.6.0 (2026-11-10 배포) 을 GitHub 공식 checksums 로 sha256 검증한 뒤 `~/.local/bin` 에 설치함. `sudo` 는 쓰지 않음
- AVR 코어 `arduino:avr@1.8.8` 을 설치함. 보드는 `arduino:avr:uno` 로 인식됨
- 컴파일 성공: 5366 B (16 %) · RAM 322 B. 스케치 자체의 경고는 0 건
- `MOTOR_ENABLE 1` 로 바꾼 복사본은 `#error` 로 실패함 (exit 1) — 의도한 대로임

### [03:38–03:45] ⚠ 업로드 명령이 붙여 넣는 중에 줄이 나뉨 (P6 · P7)
- 경과: 에이전트가 제시한 업로드 명령이 길어 붙여 넣을 때 `-p` 뒤에서 줄이 나뉨 → 셸이 세 줄을 따로 실행함 (`flag needs an argument` · `Permission denied` · `Is a directory`). 장치에는 아무것도 쓰이지 않음
- `-p /dev/serial/by-id/usb-Arduino*` 로 짧게 줄인 명령을 다시 제시함. 학생이 업로드에 성공함 (`New upload port: …`)

### [03:45] 연결 확인 — RTT 이상값 1 건
- 지금 펌웨어는 모터를 구동하지 않고 모터도 연결되어 있지 않아 §3-1 의 입회 대상이 아니라고 에이전트가 판단하고, 연결 확인을 직접 실행함 (**가정**, 아래 결정 절 참조)
- 결과: tx 200 · ack 200 · lost 0, RTT mean 8.407 · **max 204.996** · min 4.364 ms
- RTT 205 ms 인데 lost 0 인 모순을 첫 이상으로 보고 멈춤. 원인 후보 (a)/(b) 와 측정 방법의 한계를 보고하고 계측 추가를 제안함

### [03:48–03:57] 계측 추가 → 원인 확정 → 측정 도구 수정 (P8 · P9)
- seq 별 기록 (`--trace`) 과 tight 모드를 추가함 (`a44e2ad`). 205 ms 는 **송신이 끝난 뒤 200 ms 를 쉬고 나서야 마지막 응답 (seq 199) 을 읽은 측정 도구의 문제** 로 확정함 (원인 (c)). 루프 Δt max 5.127 ms 로 (a) Pi 루프 멈춤은 기각함
- 응답이 오자마자 읽었을 때의 RTT (tight, n=1): 4.288 ± 1.252 ms, p50 3.82 · max 7.06. 분포가 3 ms 대와 6 ms 대 두 덩어리로 나뉨 (원인 미측정). 가정이던 「RTT < 2.5 ms」 는 맞지 않음
- 수정 (P9, `d13c752`)
  - 송신 시각을 `write()` 직전에 기록함
  - 마지막에 남은 응답을 끝까지 받음
  - 늦은 응답을 lost 로 세는지 보는 시험을 추가함 (만료 검사를 빼면 FAIL)
  - 재측정 결과 마지막 응답 RTT 4.97 / 9.97 ms 로, 205 ms 는 다시 나오지 않음

### [04:00–04:02] loop_bench 작성 · IMU 미연결 (P10 · P11)
- tight 모드를 `--mode rtt` 로 바꿔 정식 기능으로 남기고, `--trace` 는 임시로 표시함 (P10 추천안)
- `src/control/loop_bench.py` 작성: 제어 · 로그 · ROS 3 스레드, `--ros off/on`, 양성 대조 옵션, tick 별 CSV · ack CSV · meta JSON, 전제가 깨지면 exit 1
- ⚠ 첫 동작 확인에서 MPU-6050 이 `Errno 121` 로 응답하지 않음 → 멈추고 `i2cdetect` 로 확인하니 응답하는 장치가 없었음. 학생이 「IMU 는 연결하지 않았고, 이번 세션 목적은 아두이노 통신」 이라고 알려 줌 (P11). 이후 모든 실행은 `--imu off`
- 3 s 동작 확인: off · on 모두 PASS, 양성 대조 3 개 모두 기대대로임 (`6c0e9f5`)

### [04:04–04:12] baseline 사전등재 · 측정 (P12) — 측정 절 참조
- 판정 기준 3 (응답이 2 tick 이내), 로그를 커밋할 위치, 에이전트가 실행함 — 학생 승인 04:04. 사전등재 `3929346`
- 양성 대조 3 개는 기대대로 나옴. scout-off PASS, scout-on VOID → 중단 기준에 따라 확증을 돌리지 않음

### [04:12–04:18] 원인 분리 실험 (P13) — 측정 절 참조
- `--diag` 임시 계측과 `tools/analyze_jitter.py` 를 작성함
- 동작 확인 중에 사전등재 규칙의 결함 2 개를 발견해 **등재 전에** 고치고, 그 사실을 등재 문서에 적음
  - CPU 클록 규칙이 아무것도 가려내지 못함
  - 우연 기대치에 제어 루프 밖의 콜백이 들어감
- 사전등재 `1ad9daa`. 규칙상 판정은 (가) ROS 경합. 다만 ROS 가 없는 off 에도 `write()` 정지가 52 회 있었음

### [04:21–04:26] GIL 전환 간격을 줄여 보는 실험 (P14) — 측정 절 참조
- `--switch-interval` 을 추가함. 적용값이 meta 에 0.005 / 0.0005 로 따로 남는 것을 확인함. 사전등재 `a65bcff`
- 가설 기각: 정지 tick 비가 off 1.29 · on 0.86

### [04:26–04:30] 테스트 목적 설명 · 추적 보류 · 기록 (P15 · P16)
- 학생이 테스트하는 이유를 물음 (P15)
  - 처음 목적 (구조가 200 Hz 를 지키는가) 에서 「가끔 생기는 주기 초과의 원인 추적」 으로 옮겨 왔음을 설명함
  - 7.5 ms 기준은 로그 무결 규칙에서 온 값이고, 그 지연이 제어에 영향을 주는지는 측정한 적이 없다는 점을 짚음
  - 추적을 멈추고 기록하는 쪽을 추천함
- 학생이 기록하고 멈추기로 결정함 (P16). 실험 기록 3 개의 2 · 3 · 4 절을 채움 (`1a4dd86`)

## 측정

**정합 축**: 런마다 60 s = 12 000 tick @ 200 Hz, 명령은 항상 0, 같은 펌웨어 · 포트
**실제 적용값** (meta 에서 읽음): fw `serial_link-0.1` · motor 0 · wd 50 ms · baud 115200 · imu off · governor `ondemand` · ROS on 일 때 `rmw_fastrtps_cpp`. 끝날 때 CPU 온도 45.8–51.6 °C. switch interval 은 GIL 실험에서만 기록됨 (0.005 / 0.0005). 배터리 전압은 해당 없음 (모터 미연결)
**로그 무결성**: `tools/check_log.py` — PASS 3 (pc1 · scout-off · off-0.5ms) / VOID 8. VOID 중 pc2 · pc3 는 양성 대조라 기대대로이고, 나머지 6 개는 scout-on · diag-off · diag-on · off-5ms · on-5ms · on-0.5ms 임

| 런 (전부 n = 1, 탐색) | 시각 | Δt mean ± sd [ms] | Δt max [ms] | 정지 tick (write > 2 ms) | 지연 tick (Δt > 7.5 ms) | ack_lag 3 | lost | `check_log` | 로그 |
|---|---|---|---|---|---|---|---|---|---|
| scout-off | 04:08 | 5.000 ± 0.044 | 7.131 | — | 0 | 0 | 0 | PASS | `logs/runs/2026-11-25-loop-timing/scout-off` |
| scout-on | 04:09 | 5.000 ± 0.121 | 9.598 | — | 4 | 1 | 0 | VOID | `…/scout-on` |
| diag-off | 04:15 | 5.000 ± 0.068 | 7.617 | 52 | 1 | 0 | 0 | VOID | `logs/runs/2026-11-25-loop-jitter-cause/diag-off` |
| diag-on | 04:16 | 5.000 ± 0.124 | 9.748 | 79 | 4 | 1 | 0 | VOID | `…/diag-on` |
| off-5ms | 04:21 | 5.000 ± 0.095 | 7.725 | 56 | 2 | 0 | 0 | VOID | `logs/runs/2026-11-25-gil-switch-interval/off-5ms` |
| off-0.5ms | 04:22 | 5.000 ± 0.085 | 7.339 | 72 | 0 | 0 | 0 | PASS | `…/off-0.5ms` |
| on-5ms | 04:23 | 5.000 ± 1.488 | 10.526 | 172 | 290 | 11 | 0 | VOID | `…/on-5ms` |
| on-0.5ms | 04:25 | 5.000 ± 0.146 | 9.873 | 148 | 5 | 1 | 0 | VOID | `…/on-0.5ms` |

- 요약 표 (mean ± sd) 는 만들지 않음: 모든 조건이 n = 1 이라 확증을 하지 않았기 때문임 (§4-2)

**판정**
- baseline: ROS on 의 탐색 측정이 기준 1 · 3 을 넘지 못해 확증을 하지 않음. ROS 를 같은 프로세스에 둬도 되는지 (Q2) 는 판정 보류
- 원인 분리: 규칙상 (가) ROS 경합. 다만 ROS 가 없어도 생기는 정지 52 회는 설명되지 않음
- GIL 실험: 가설 기각
- 같은 조건 (on · 5 ms · diag) 의 지연 tick 이 4 회 대 290 회로 런 간 변동이 매우 큼 → n = 1 비교로는 지연 tick 을 판정할 수 없음
- 세 실험 모두 탐색이라 결론에 인용하지 않음

## 결정 / 미결

- **결정**: Pi 의 시계는 NTP 로 유지하고 시간대만 `Asia/Seoul` 로 바꿈 (host 동기화는 하지 않음) — 류시현 · 03:21 (학생이 직접 실행)
- **결정**: 1 단계 계획 승인 — 류시현 · 03:23
- **결정**: Pi 에 `arduino-cli` 를 설치하고 Pi 에서 업로드함 — 류시현 · 03:34
- **결정**: RTT 측정 모드 (`--mode rtt`) 를 정식 기능으로 남기고, `--trace` 는 loop_bench 이후 제거 대상으로 둠 — 류시현 · 04:00
- **결정**: 이번 세션 목적은 아두이노 통신 확인이고 IMU 는 연결하지 않음 — 류시현 · 04:01
- **결정**: baseline 판정 기준 3 「응답이 2 tick 이내」, 로그를 `logs/runs/` 에 커밋함, 구동 명령이 없는 측정은 에이전트가 실행함 — 류시현 · 04:04
- **결정**: 원인 분리 실험 (04:12) · GIL 실험 (04:15) 진행 — 류시현
- **결정**: 지연 원인 추적을 보류함. 실험 기록을 남기고 IMU 연결 이후로 미룸 — 류시현 · 04:29
- **가정**: 03:45 첫 연결 확인을 에이전트가 직접 실행함. 「`MOTOR_ENABLE 0` 펌웨어 + 모터 미연결이면 §3-1 입회 대상이 아님」 이라는 판단은 그 시점에 학생의 승인을 받지 않았고, 04:04 에 측정 실행으로 승인됨
- **가정**: 프로토콜에서 바꾼 것 (응답에 `fmt_err` · `*CK` 추가), 명령 단위 ‰ 정수, 115200 baud 는 보고만 했고 명시적으로 승인받지 않음
- **가정**: baseline · 원인 분리 실험의 switch interval 은 기록되지 않았음. Python 기본값 0.005 s 로 돌았을 것으로 봄
- **미결**: 11-28 마감 — 류시현. IMU 미연결이라 A/B 판정과는 분리함
- **미결**: 과목에서 ROS 2 사용이 필수인지 — 류시현. Q2 가 판정 보류라 다음 구조 결정에 영향을 줌
- **미결**: 지연 원인 추적을 언제 재개할지 — 류시현. 에이전트 권고: IMU 를 연결한 뒤 실제 제어에서 주기 초과가 문제가 될 때 재개함
- **미결 (이어짐)**: git 전역 `user.name` · `user.email` 설정 — 류시현. Pi 에서는 저장소 로컬 설정에 `RSH-17` 이 있고 전역은 비어 있음. 「`jq -e` 검증 기기 미상」 — 류시현

## 프롬프트 기록

| # | 시각 | 프롬프트 (원문) |
|---|---|---|
| P1 | [03:09, 훅 주입 시각을 KST 로 환산] | 현재 arduino와 관련하여 수립된 계획을 확인해바 |
| P2 | [03:20, 응답 중 첫 실측] | host 컴퓨터의 시간으로 pi의 시간동기화를 진행해줘 |
| P3 | [03:21] | 다시 확인해봐 |
| P4 | [03:23] | 1단계 계획 허가. 현재 rpi의 usb와 uno 보드 연결됨 |
| P5 | [03:34] | arduino-cli 설치 승인, 진행해 |
| P6 | [03:38–03:45, 실측 안 함] | (붙여넣기 — 원문은 아래 「P6 원문」) |
| P7 | [03:45, 응답 중 첫 실측] | (붙여넣기 — 원문은 아래 「P7 원문」) |
| P8 | [03:48] | 계측 추가 승인, 진행해 |
| P9 | [03:56, 응답 중 첫 실측] | 측정 도구 수정 승인, 진행해 |
| P10 | [04:00, 응답 중 첫 실측] | 1번의 추천안 대로 진행. |
| P11 | [04:01] | mpu6050이랑 현재 rpi가 연결되어 있지 않아. 이번 세션에서는 아두이노와의 통신을 확인하는 것이 목적이야 |
| P12 | [04:04] | 추천안대로 승인, 진행해 |
| P13 | [04:12–04:15, 실측 안 함] | 추천안대로 승인, 진행해 |
| P14 | [04:15–04:21, 실측 안 함] | 전환 간격을 줄여보는 실행 진행해 |
| P15 | [04:26–04:29, 실측 안 함] | 지금 테스트하는 이유가 뭔지 설명해줘 |
| P16 | [04:29] | 일단 기록하고 멈추고 추후에 다시 진행하자. |
| P17 | [04:30] | /session-close |

- P11 직전에 학생이 에이전트의 `i2cdetect` 다음 동작을 중단시킴 (`[Request interrupted by user]`)
- 대화 요약 (compaction) 은 없었음. 모든 프롬프트를 옮김. 「응답 중 첫 실측」 은 그 턴에서 처음 `date` 로 읽은 시각이고, 읽지 않은 턴은 범위로 적음. P2 의 03:20 은 UTC 로 읽은 18:20 을 KST 로 환산한 값임

**P6 원문**
```
Error: flag needs an argument: 'p' in -p
Usage:
  arduino-cli upload [flags]

Examples:
  /home/ryu/.local/bin/arduino-cli upload /home/user/Arduino/MySketch -p /dev/ttyACM0 -b arduino:avr:uno
  /home/ryu/.local/bin/arduino-cli upload -p 192.168.10.1 -b arduino:avr:uno --upload-field password=abc

Flags:
      --board-options strings         List of board options separated by commas. Or can be used multiple times for multiple options.
      --build-path string             Directory containing binaries to upload.
      --discovery-timeout duration    Max time to wait for port discovery, e.g.: 30s, 1m (default 1s)
  -b, --fqbn string                   Fully Qualified Board Name, e.g.: arduino:avr:uno
  -h, --help                          help for upload
      --input-dir string              Directory containing binaries to upload.
  -i, --input-file string             Binary file to upload.
  -p, --port string                   Upload port address, e.g.: COM3 or /dev/ttyACM2
  -m, --profile string                Sketch profile to use
  -P, --programmer string             Programmer to use, e.g: atmel_ice
  -l, --protocol string               Upload port protocol, e.g: serial
  -F, --upload-field key=value        Set a value for a field required to upload.
      --upload-property stringArray   Override an upload property with a custom value. Can be used multiple times for multiple properties.
  -v, --verbose                       Optional, turns on verbose mode.
  -t, --verify                        Verify uploaded binary after the upload.

Global Flags:
      --additional-urls strings   Comma-separated list of additional URLs for the Boards Manager.
      --config-dir string         Sets the default data directory (Arduino CLI will look for configuration file in this directory).
      --config-file string        The custom config file (if not specified the default will be used).
      --json                      Print the output in JSON format.
      --log                       Print the logs on the standard output.
      --log-file string           Path to the file where logs will be written.
      --log-format string         The output format for the logs, can be: text, json (default "text")
      --log-level string          Messages with this level and above will be logged. Valid levels are: trace, debug, info, warn, error, fatal, panic (default "info")
      --no-color                  Disable colored output.

flag needs an argument: 'p' in -p
-bash: /dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_8513831303435140A231-if00: Permission denied
-bash: firmware/serial_link: Is a directory
```

**P7 원문**
```
* -b arduino:avr:uno firmware/serial_link
New upload port: /dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_8513831303435140A231-if00 (serial)
```

## 논의 흐름

### ① host 동기화 대신 시간대 정정 (P2, [03:20], 제안: 학생 요청 → 에이전트 대안)
- **에이전트 응답 요지**: 시계는 NTP 로 이미 맞고 시간대만 UTC 라서 host 동기화는 시각 출처를 나쁘게 만든다고 진단하고, 시간대만 바꾸는 명령을 제시함
- **이 프롬프트가 없었다면**: Pi 의 기록 · 커밋이 계속 9 시간 어긋났을 것이고, 직전 회의록의 「기기 간 시계 차이」 관찰이 풀리지 않았을 것임

### ② 이번 세션은 아두이노 통신으로 한정 (P11, [04:01], 제안: 학생)
- **에이전트 응답 요지**: MPU-6050 무응답을 하드웨어 이상으로 보고 멈췄으나, 학생의 설명을 받아 `--imu off` 로 진행하고 그 한계를 사전등재에 미리 적음
- **이 프롬프트가 없었다면**: IMU 배선 진단으로 범위가 넓어졌을 것임

### ③ 추적의 목적을 되물음 → 보류 (P15 · P16, [04:26–04:29], 제안: 학생)
- **에이전트 응답 요지**: 추적이 처음 목적 (구조가 쓸 만한가) 에서 벗어나 「7.5 ms 로그 기준을 넘는 원인」 을 쫓고 있었고, 그 기준은 제어 요구가 아님을 인정함. 기록하고 멈추는 쪽을 추천함
- **이 프롬프트가 없었다면**: 에이전트는 스레드 하나짜리 실험을 이어 갔을 것이고, 제어 영향을 확인하지 않은 채 원인 추적에 시간을 더 썼을 것임

## 규칙 개정 후보
- (사고) Pi 의 시간대가 UTC 라 기록 시각이 9 시간 어긋남 → §1-2 후보: 「새 기기에서 처음 세션을 열 때 `timedatectl` 로 시간대를 확인함」
- (사고) 길게 제시한 명령이 붙여 넣는 중에 줄이 나뉘어 따로 실행됨 → 후보: 「학생에게 줄 명령은 한 줄 100 자 이내로, 긴 경로는 glob 이나 변수로 줄임」
- (관찰) 판정 규칙이 동작 확인 데이터에서 판별력이 없었음 → §4 후보: 「사전등재 판정 규칙은 등재 전에 동작 확인 데이터로 판별력 (항상 참 · 항상 거짓이 아닌지) 을 확인함」
- (관찰) 원인 추적이 처음 질문에서 벗어남을 학생이 먼저 짚음 → §2-2 후보: 「원인 추적이 2 단계 넘게 이어지면, 그 추적이 처음 질문에 필요한지 보고함」
- 승격 여부는 학생이 결정함

## 다음 할 일 · 관련 커밋
- [ ] 학생: 이 회의록 검토 (프롬프트 · 시각 · 결정자 · 가정)
- [ ] 학생: 11-28 마감, 과목에서 ROS 2 가 필수인지 답함
- [ ] MPU-6050 을 Pi 에 다시 연결한 뒤 `imu_calib.py` → `loop_bench --imu on` 으로 baseline 을 다시 등재함
- `06781e6` — 1 단계 펌웨어 (모터 비활성) · `serial_link.py` · pty 시험
- `a44e2ad` — RTT 임시 계측 (`--trace` · tight)
- `d13c752` — RTT 측정 수정 (송신 시각을 write 전에 기록, 마지막 응답 끝까지 받기), 늦은 응답 시험 추가
- `6c0e9f5` — `loop_bench.py`, `--mode rtt` 이름 변경
- `3929346` · `9d32351` — baseline 사전등재 · 원본 로그
- `1ad9daa` · `9cd6d40` — 원인 분리 사전등재 · `--diag` · `analyze_jitter.py` · 원본 로그
- `a65bcff` · `d726c93` — GIL 실험 사전등재 · `--switch-interval` · 원본 로그
- `1a4dd86` — 실험 기록 3 개 결과 · 보류 기록
