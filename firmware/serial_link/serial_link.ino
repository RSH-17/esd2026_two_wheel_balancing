// Pi <-> Uno serial link, stage 1 (no motor output).
//
// Protocol (ASCII, one line each way, '\n' terminated) — must match
// src/comm/serial_link.py:
//   Uno -> Pi at boot : READY,fw=<name>,motor=<0|1>,wd_ms=<int>
//   Pi  -> Uno        : M,<seq>,<u_l>,<u_r>,*<CK>
//   Uno -> Pi         : A,<seq>,<crc_err>,<fmt_err>,<wd_trip>,*<CK>
// seq     : 0..65535, echoed back unchanged
// u_l/u_r : signed duty in per-mille, [-1000, 1000]
// CK      : XOR of every byte before '*', two upper-case hex digits
// crc_err : lines whose checksum did not match (no reply is sent for them)
// fmt_err : lines that were too long or did not parse (no reply)
// wd_trip : times the watchdog fired (no valid command for WATCHDOG_MS)
//
// LED13 on = watchdog tripped, outputs forced to zero (also the state at boot).
// LED13 off = valid commands are arriving.

#define MOTOR_ENABLE 0

#if MOTOR_ENABLE
#error "Motor output is not implemented. Enabling it needs an approved plan (AGENTS.md 3-1, 3-2)."
#endif

const unsigned long BAUD = 115200;   // must equal BAUD in serial_link.py
const unsigned long WATCHDOG_MS = 50;
const char FW_NAME[] = "serial_link-0.1";
const uint8_t LED_PIN = 13;
const long DUTY_LIMIT = 1000;        // protocol range, not the safety limit (that is hw/limits.py)

char line_buf[48];
uint8_t line_len = 0;
bool line_overflow = false;

uint32_t crc_err = 0;
uint32_t fmt_err = 0;
uint32_t wd_trip = 0;

unsigned long last_cmd_ms = 0;
bool tripped = true;                  // safe state until the first valid command

uint8_t xor_bytes(const char *s, uint8_t n) {
  uint8_t ck = 0;
  for (uint8_t i = 0; i < n; i++) ck ^= (uint8_t)s[i];
  return ck;
}

int hex_val(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}

// Parse one signed decimal field ending at ','. Advances *p past the comma.
bool parse_field(char **p, long *out) {
  char *end;
  long v = strtol(*p, &end, 10);
  if (end == *p || *end != ',') return false;
  *out = v;
  *p = end + 1;
  return true;
}

void set_outputs(long u_l, long u_r) {
  // MOTOR_ENABLE 0: nothing is driven. Kept so the call sites already exist.
  (void)u_l;
  (void)u_r;
}

void send_ack(long seq) {
  char out[64];
  int n = snprintf(out, sizeof(out), "A,%ld,%lu,%lu,%lu,", seq,
                   (unsigned long)crc_err, (unsigned long)fmt_err, (unsigned long)wd_trip);
  if (n <= 0 || n >= (int)sizeof(out) - 4) return;
  uint8_t ck = xor_bytes(out, (uint8_t)n);
  snprintf(out + n, sizeof(out) - n, "*%02X\n", ck);
  Serial.print(out);
}

void handle_line() {
  char *star = strchr(line_buf, '*');
  if (star == NULL || (star - line_buf) + 3 != line_len) { fmt_err++; return; }
  int hi = hex_val(star[1]);
  int lo = hex_val(star[2]);
  if (hi < 0 || lo < 0) { fmt_err++; return; }
  uint8_t want = (uint8_t)(hi * 16 + lo);
  if (xor_bytes(line_buf, (uint8_t)(star - line_buf)) != want) { crc_err++; return; }

  *star = '\0';
  if (line_buf[0] != 'M' || line_buf[1] != ',') { fmt_err++; return; }
  char *p = line_buf + 2;
  long seq, u_l, u_r;
  if (!parse_field(&p, &seq) || !parse_field(&p, &u_l) || !parse_field(&p, &u_r) || *p != '\0') {
    fmt_err++;
    return;
  }
  if (seq < 0 || seq > 65535 || u_l < -DUTY_LIMIT || u_l > DUTY_LIMIT ||
      u_r < -DUTY_LIMIT || u_r > DUTY_LIMIT) {
    fmt_err++;
    return;
  }

  last_cmd_ms = millis();
  tripped = false;
  set_outputs(u_l, u_r);
  send_ack(seq);
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);
  set_outputs(0, 0);
  Serial.begin(BAUD);
  Serial.print("READY,fw=");
  Serial.print(FW_NAME);
  Serial.print(",motor=");
  Serial.print(MOTOR_ENABLE);
  Serial.print(",wd_ms=");
  Serial.print(WATCHDOG_MS);
  Serial.print("\n");
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line_buf[line_len] = '\0';
      if (line_overflow) fmt_err++;
      else if (line_len > 0) handle_line();
      line_len = 0;
      line_overflow = false;
    } else if (line_len < sizeof(line_buf) - 1) {
      line_buf[line_len++] = c;
    } else {
      line_overflow = true;
    }
  }

  if (!tripped && millis() - last_cmd_ms > WATCHDOG_MS) {
    tripped = true;
    wd_trip++;
    set_outputs(0, 0);
  }
  digitalWrite(LED_PIN, tripped ? HIGH : LOW);
}
