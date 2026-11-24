"""MPU-6050 raw register reads over I2C (AGENTS.md section 8-B).

Returns raw int16 register values only — no bias removal, no scale to
deg/s or g, no theta0 offset. Those conversions belong in
src/sensing/imu_calib.py once this module's read is confirmed working
(AGENTS.md section 5-5: raw -> physical conversion lives in one place).
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass

from smbus2 import SMBus

I2C_BUS = 1
MPU6050_ADDR = 0x68  # AD0 pin tied low; 0x69 if AD0 is tied high

REG_PWR_MGMT_1 = 0x6B
REG_WHO_AM_I = 0x75
REG_ACCEL_XOUT_H = 0x3B
REG_TEMP_OUT_H = 0x41
REG_GYRO_XOUT_H = 0x43

WHO_AM_I_EXPECTED = 0x68  # MPU-6050 reports this regardless of AD0 level


@dataclass
class RawSample:
    ax: int
    ay: int
    az: int
    temp: int
    gx: int
    gy: int
    gz: int


def _read_word(bus: SMBus, addr: int, reg_high: int) -> int:
    data = bus.read_i2c_block_data(addr, reg_high, 2)
    (value,) = struct.unpack(">h", bytes(data))
    return value


def wake_up(bus: SMBus, addr: int = MPU6050_ADDR) -> None:
    """Clear the sleep bit (register powers on in sleep mode)."""
    bus.write_byte_data(addr, REG_PWR_MGMT_1, 0x00)


def check_who_am_i(bus: SMBus, addr: int = MPU6050_ADDR) -> int:
    """Return the WHO_AM_I register value. Caller compares to WHO_AM_I_EXPECTED."""
    return bus.read_byte_data(addr, REG_WHO_AM_I)


def read_raw(bus: SMBus, addr: int = MPU6050_ADDR) -> RawSample:
    """Read accel/temp/gyro as one 14-byte burst (registers 0x3B-0x48)."""
    data = bus.read_i2c_block_data(addr, REG_ACCEL_XOUT_H, 14)
    ax, ay, az, temp, gx, gy, gz = struct.unpack(">7h", bytes(data))
    return RawSample(ax=ax, ay=ay, az=az, temp=temp, gx=gx, gy=gy, gz=gz)


def main() -> None:
    period_s = 0.1
    i2c_err = 0

    with SMBus(I2C_BUS) as bus:
        who = check_who_am_i(bus)
        if who != WHO_AM_I_EXPECTED:
            print(
                f"WHO_AM_I mismatch: got 0x{who:02X}, expected 0x{WHO_AM_I_EXPECTED:02X} "
                f"(addr=0x{MPU6050_ADDR:02X}, bus={I2C_BUS})"
            )
        wake_up(bus)

        print("t,ax,ay,az,temp,gx,gy,gz,i2c_err")
        t0 = time.monotonic()
        try:
            while True:
                t = time.monotonic() - t0
                try:
                    s = read_raw(bus)
                    print(f"{t:.3f},{s.ax},{s.ay},{s.az},{s.temp},{s.gx},{s.gy},{s.gz},{i2c_err}")
                except OSError:
                    i2c_err += 1
                    print(f"{t:.3f},READ_ERROR,,,,,,,{i2c_err}")
                time.sleep(period_s)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
