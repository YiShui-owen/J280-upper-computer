# SWM2 Two-Stage Swing Tuning API

## Identity and transport

- Firmware UserCode: `0x53574D32` (SWM2); protocol schema: `0x53575402`.
- Reuse the original J2C3/J2A3 frame and CRC16-CCITT (poly 0x1021, initial 0xFFFF).
- All multibyte integers are little endian. Signed telemetry uses two's complement.
- Requests: magic J2C3, total length u16, UserCode u32, schema u32, command ID u32, opcode u8, payload 0..16 bytes, CRC u16.
- CRC covers every byte before the CRC. Wrong identity/schema/CRC cannot execute an action.
- ACK: J2A3, length44, UserCode u32, schema u32, ID u32, opcode u8, status u8, reason u8, revision u32, readback length u8, padded readback16, CRC u16.
- ACK status 0 means accepted/read; 1 means rejected. Reasons: 0 OK, 1 opcode, 2 length, 3 stale ID, 4 state, 5 range, 6 unknown parameter, 7 status page.

## Ordering and safety

One Host owns the only serial connection and permits one outstanding ordinary request.
Read-only requests accept any ID and do not change the mutating highwater. Use a unique ID for each request, including reads, to reject late ACKs. ID0 may bootstrap STATUS.
Mutating requests require a nonzero ID greater than the last consumed mutating ID. A rejected fresh mutating request consumes its ID too. IDs never wrap; reconnect reads the device highwater first.

No automatic timeout retry and no automatic reconnect motion. Timeouts are indeterminate until a separate status/readback request resolves them. All ordinary requests arriving while the gateway ACK is pending are ignored without action or replay. The Host must not pipeline them.

STOP with empty payload is accepted with any ID, including0. It immediately emits STOP even with an ACK pending. Its ACK waits for the previous ACK transfer; repeated STOPs may coalesce to the newest pending STOP ID. There is no queued RUN in RTL. Host STOP clears any pending or planned RUN and never automatically restarts it.

All parameter writes require stopped, actual PWM=0, no run session, no active swing, no zero capture, and no estop. Invalid values are rejected; there are no silent clamps. Configuration revision increments for each accepted write, including an identical value. A swing RUN latches the complete swing bank once; retries use that session copy. STOP and faults do not erase a valid zero. Clearing F01/F07 is a separate guarded command and does not start motion.

Host recovery sequence: explicit authorization -> STOP -> read actual state -> guarded ACK_FAULT if applicable -> read F=00 and PWM=0 -> separate SWING_RUN -> read real swing/BALANCE/failure states. No unbounded retry loop. Original RTL protection and physical motor limits are unchanged.

## Commands

| Opcode | Name | Payload | Successful readback |
|---|---|---|---|
|00|STOP|empty|empty|
|01|STATUS|page u8|16 bytes below|
|02|SWING_RUN|empty|empty; acceptance is not proof of swing success|
|03|ZERO|empty|empty; read zero state afterwards|
|04|ACK_FAULT|empty|empty; read actual F=00 afterwards|
|05|BALANCE_RUN|empty|empty; original manual balance guard applies|
|70|WRITE|parameter u8, value u32|parameter u8, committed value u32|
|71|READ|parameter u8|parameter u8, current stored value u32|
|72|READ_SWING_CONFIG|empty|packed swing bank16 bytes|

The Host follows each WRITE with a separate READ and compares the actual value. Restoring PID is explicit; cold-start gains are zero. Gain values from earlier runs are not silently applied.

## Nine active two-stage swing parameters

| ID | Field | Default | Accepted values | Unit |
|---|---|---:|---|---|
|00|forward_percent|49|1..90|percent command|
|01|reverse_percent|36|1..90|percent command|
|02|forward_ms|100|1..1000|ms|
|03|qualify_ms|60|1..1000 and <= wait_timeout_ms|ms|
|04|wait_timeout_ms|3000|qualify_ms..10000|ms|
|05|reverse_ms|220|1..1000|ms|
|06|coast_ms|1800|20..10000|ms|
|08|max_attempts|3|1..10|attempt count including first|
|09|retry_step_ms|10|0..50|ms per finite retry|

ID07 is removed: READ and WRITE both reject it as unknown parameter. The old quiet-speed brake setting has no effect in this firmware and is not exposed.

Packed bytes: forward_percent0, reverse_percent1, forward_ms2..3, reverse_ms4..5, qualify_ms6..7, wait_timeout_ms8..9, coast_ms10..11, max_attempts12, retry_step_ms13, reserved zero14..15. Both durations use16 bits throughout the bank, session, counters and readback.

Each active stage ends normally at its own commanded duration. Reverse timing starts when the reverse direction command is issued, including initial deceleration; zero speed, reverse encoder edges and stationary readings do not end it. The original180-count local cutoff, near-top-only transition and requirement for forward movement before the second command are removed. Wrong-direction checking applies only to the forward stage.

Timing exceptions remain explicit: STOP, estop, invalid/lost zero, original global protections, and the original fully qualified capture window. Merely being near the top is insufficient. A complete instantaneous capture window immediately removes output and enters COAST as in SWM1, then requires20 consecutive valid samples before asserting handoff. If interrupted, the candidate remains in finite COAST and can retry; candidate is never reported as successful BALANCE. Only actual core mode3 establishes that PID balancing was entered.

Retry adaptation changes only the session's forward duration, using17-bit arithmetic and saturation1..1000 ms. Reverse duration stays independently fixed for the session. The full bank is latched once on explicit RUN; subsequent bank changes cannot affect a running session. Defaults remain49%/100ms forward and36%/220ms reverse, but SWM2 intentionally changes the old stop-at-zero behavior.

The original motor driver90% cap, rise ramp, reversal blanking and all global protection sources are unchanged. Actual applied PWM is separately reported. Stage duration measures command time, not a guarantee that physical PWM instantly reaches the requested value. The20ms handoff qualification and original angle/speed protection thresholds remain fixed.

## Existing PID and filter bank

| ID | Field | Default | Range |
|---|---|---:|---|
|20|AKP|0|0..65535|
|21|AKD|0|0..65535|
|22|AKI|0|0..65535|
|23|PKP|0|0..65535|
|24|PKD|0|0..65535|
|25|PKI|0|0..65535|
|26|KI enable|0|0..1|
|27|encoder mode|1|0..1|
|28|angle D filter Q12|757|0..4096|
|29|angle averaging window|4|1..8|
|2A|position D gamma Q31|578949194|1..0x80000000|

These are retained configuration points, not a changed PID/filter algorithm. Fixed original integration values: lab strength Q8=256, position D filter enabled, control mode1, angle output limit90, position output limit0, control period100. Native controller gains/filters and 1 ms/10 ms scheduling remain unchanged.

## Atomic status pages

Each ACK captures one current snapshot. Separate pages need not share the same sample time.

Core mode enumeration: 0 SAFE_IDLE, 1 ZERO_CAPTURED, 2 ARMED, 3 BALANCE, 4 FAULT_STOP. Only mode3 confirms balancing; mode2 does not.
Swing state enumeration: 0 IDLE, 10 QUALIFY, 11 FORWARD_DRIVE, 13 REVERSE_DRIVE, 40 COAST, 70 RETRY_WAIT, 90 FAILED. Retry count counts retries after the first attempt.

Page0:
- byte0 mode, byte1 fault, byte2 flags, byte3 swing state.
- byte4..5 signed actual PWM, byte6 retry count, byte7 reserved0.
- byte8..11 last mutating ID, byte12..15 configuration revision.
- flags: bit0 zero_valid,1 run_session,2 swing_active,3 swing_fail,4 zero_capture_active,5 estop,6 stopped_config_allowed,7 PWM zero.

Page1: timestamp_ms u32, alpha Q20 i32, alpha_dot Q20 i32, theta_dot Q20 i32.

Page2: timestamp_ms u32, encoder_count i32, PWM i16, mode u8, fault u8, flags u8, swing state u8, retry count u8, reserved0.

Page3 (phase diagnostics; no history RAM):
- byte0 swing state; byte1 last phase-end reason.
- byte2..3 phase_elapsed_ms u16: elapsed command-stage time, reset at each stage transition.
- byte4..5 effective_forward_ms u16: actual session/retry forward duration.
- byte6..7 session_reverse_ms u16: independent session reverse duration.
- byte8..11 timestamp_ms u32; byte12 retry count; byte13 handoff_hold_ms.
- byte14 flags: bit0 swing active, bit1 capture candidate, bit2 handoff confirmed, bit3 failed; upper bits zero. byte15 reserved0.
- Candidate flag is active && state40 && hold>0 && !handoff. A handoff-confirmed flag reports the controller request, not proof that PID entered BALANCE.

Phase-end reasons: 0 NONE/new stage, 1 FORWARD_TIMER, 2 REVERSE_TIMER, 3 CAPTURE_CANDIDATE, 4 HANDOFF_CONFIRMED, 5 STOP, 6 ZERO_LOST, 7 ESTOP, 8 WRONG_FORWARD_DIRECTION, 9 RETRY_SCHEDULED, 10 QUALIFY_TIMEOUT, 11 ATTEMPTS_EXHAUSTED, 12 INVALID_CONFIG. The field records the most recent phase event; state and flags describe the current state. A top-level global fault cancels RUN through the existing STOP path, so its true fault cause is read from page0 F, not inferred from this local reason.

The Host must label measured/derived values accurately and use FPGA timestamps. Polling waveforms does not promise 1 ms serial sampling. This version has no historical sample buffer.
