# SG21 Integration Contract

Target J280 GW2A-LV55PG484C8/I7,50MHz. UserCode53473231, schema53475421. Existing J2C3/J2A3 framing, CRC, stopped-only writes, ID replay protection, independent ACK/readback and SWM2 parameters remain as in [the frozen SWM2 API](../baseline/SWM2/API-Contract.md). Use this image's matching Host only.

Parameter30 is gesture_enable, default0, accepted0/1 while stopped. A valid, ready, error-free U127 event may request motion only when enabled. Right(code1) starts the existing SWM2 session when ZERO is valid, angleP is nonzero and all existing swing-start conditions hold. CW(code7)/CCW(code8) request+1/-1turn only in BALANCE with the motor permitted and no active/busy circle. Each trajectory duration is200 accepted10ms samples:2seconds from its k0 reference to k200. The reused quintic trajectory accelerates and decelerates; this is not constant instantaneous speed. No busy motion is queued. Left(code2) cancels the reference at its current held target. Wave(code9) invokes the original STOP path. Other event codes have no motion mapping.

Sensor recognition/timing,219writes, checkedID7620, STOP-before-read and raw event encoding are copied from the adopted U127 image. The sensor's official Wave pre-output wait remains1000ms; physical estop and UART STOP remain independent of sensor timing. No OLED is included.

Status page4 is observer-only: first8bytes are ID0,ID1,raw43,raw44,error,packed(code<<3),error_count_u16; next8bytes are flags(active,busy,accepted,rejected bits0..3; command_status bits4..7),3zero bytes,sequence_u32. This page does not expose sensor.ready and must not be interpreted as an independent initialization-complete certificate. Actual command admission uses the driver's real ready/error signals.

Cold PID remainszero and gestures disabled. No gain/zero/profile is restored automatically. SWM2 phase timing measures the command, not instantaneous actual PWM. All baseline protection and physical motor mapping are retained. Motion, mounted direction and closed-loop performance require real hardware verification.

The reused HOLD adapter rejects a new circle from a fractional held count after an intermediate cancellation. After Left cancellation, use STOP and a new swing/balance session before starting another circle. Completed circles have integer endpoints and support repeated opposite commands without restarting.
