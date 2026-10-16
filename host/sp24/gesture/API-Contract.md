# SP24 Integration Contract

Target J280 GW2A-LV55PG484C8/I7, 50MHz. UserCode `0x53503234`, schema `0x53505424`. Use this image's matching SP24 Host only. Original SWM2 framing, CRC, stopped-only writes, ID replay protection, independent ACK/readback and swing parameters are retained. The complete Host parameter inventory is [tune_parameters.py](host/tune_parameters.py); actual board wiring is [J280_WIRING_CN.md](../J280_WIRING_CN.md).

All integers are little-endian. A `J2C3` command contains total length u16, UserCode u32, schema u32, command ID u32, opcode u8, up to16 payload bytes and CRC16-CCITT u16 (initial `0xFFFF`, polynomial `0x1021`). Total command size is21 plus payload length. The `J2A3` ACK is44 bytes: header/identity/ID/opcode, status u8, reason u8, revision u32, readback length u8,16-byte readback area and CRC. Nonzero ACK status is rejection; a write ACK alone never establishes the parameter's actual readback.

Opcodes are `0x00 STOP`, `0x01 STATUS(page:u8)`, `0x02 SWING_RUN`, `0x03 ZERO`, `0x04 ACK_FAULT`, `0x05 BALANCE_RUN`, `0x70 WRITE(parameter:u8,value:u32)`, `0x71 READ(parameter:u8)`, and `0x72 READ_SWING_CONFIG`. Mutation IDs must advance; STOP retains priority, including ID0. Every configuration write requires stopped/PWM0, no active run session, no swing, no zero capture and no estop; existing fault guards remain. The Host independently reads back each write with opcode0x71 and checks the matching parameter, value and revision. It never automatically retries or replays motion after a timeout or reconnect.

| Parameter | Name | Default | Accepted values | Meaning |
|---|---|---|---|---|
| `0x30` | `gesture_enable` |0|0/1|Enable valid U127 motion events.|
| `0x34` | `move_degrees` |50|Integer1..360|Relative angular step per balanced Left/Right start.|
| `0x35` | `left_negative` |1|0/1|1 maps Left to negative encoder counts;0 reverses the Left/Right mapping.|

A valid, ready, error-free U127 event may request motion only when gesture control is enabled. Up(code3) while stopped starts the existing SWM2 session when ZERO is valid, angleP is nonzero and all existing swing-start conditions hold. In actual BALANCE with the motor permitted and no active/busy trajectory, Left(code2) or Right(code1) starts a finite move from the current held position reference by the configured relative angle. This is not an absolute homing command. There are1080 encoder counts/revolution, so each degree is3 counts. The configured step and direction are latched for the accepted command.

During a Left-started move, Right cancels the reference immediately at its last committed target and leaves the balance controller active; Left during a Right-started move behaves symmetrically. That cancellation event never also starts the reverse move. Another later gesture can start a new move. A repeated same-direction event during motion is ignored and no busy motion is queued. Cancellation freezes the commanded position reference; it is not a promise of an instantaneous mechanical stop or a smooth braking trajectory.

CW(code7)/CCW(code8) still request+1/-1turn only in BALANCE with the motor permitted and no active/busy trajectory. All trajectories use200 intervals of10ms:2seconds from k0 to k200. The reused quintic trajectory accelerates and decelerates; it is not constant instantaneous speed. Left cancels a CW-started circle and Right cancels a CCW-started circle. Wave(code9) invokes the original global STOP path after the swing-discard gate; Down/Near/Far and combination event codes have no motor mapping. Right does not start swing.

Sensor recognition/timing,219writes, checkedID7620, STOP-before-read and raw event encoding are copied from the adopted U127 image. The sensor's official Wave pre-output wait remains1000ms; physical estop and UART STOP remain independent of sensor timing. No OLED is included.

Status page4 is observer-only: first8bytes are ID0,ID1,raw43,raw44,error,packed(code<<3),error_count_u16; next8bytes are flags(active,busy,accepted,rejected bits0..3; command_status bits4..7),3zero bytes,sequence_u32. This page does not expose sensor.ready and must not be interpreted as an independent initialization-complete certificate. Actual command admission uses the driver's real ready/error signals.

Cold PID remainszero and gestures disabled. No gain/zero/profile is restored automatically. SWM2 phase timing measures the command, not instantaneous actual PWM. All baseline protection and physical motor mapping are retained. Motion, mounted direction and closed-loop performance require real hardware verification.

The SP22 HOLD adapter preserves the full fractional count-Q32 reference across cancellation and subsequent commands. A new move or circle can start from that held reference without STOP/re-entering BALANCE. Endpoint/completion telemetry describes the commanded trajectory; physical arrival, mounted direction and closed-loop settling require hardware verification.

## Swing discard and actual handoff

From acceptance of UART SWING_RUN or Up-swing through all SWM2 phases and actual automatic BALANCE/HOLD readiness, every sensor action including Wave is discarded. Driver polling and event observability continue. An ignored event is never queued for post-handoff execution. A fresh sensor event after actual mode3, original motor permission and initialized HOLD may request positioning/circle/cancel. Physical estop, UART STOP, ZERO and faults retain independent original priority. Sensor Wave is not an emergency stop.

## Adaptive configuration

SA21 paperE source, ROM and arithmetic are reused. Parameters0x31(mode0off/1actual/2shadow),0x32(independentI) and0x33(profile0invalid/1qualified/2shadow) coexist with0x34/35. Parameters0x40..45 are three positive ordered error and delta knots each in Q20 radians or radians/sample;0x46..49 are positive ordered Kp/Kd bounds in Q24. All writes remain STOP-only. Invalidate selects mode0 and clears the10-word completion mask; positive staging writes and complete ordered validation precede atomic commit. Actual mode1 requires a valid, control-qualified profile and independentI enabled. Boot is off/invalid; effective mode is0 unless actual BALANCE and motor permitted. Ordinary opcode0x71 may read cold-zero unconfigured E words; WRITE/verify/import positivity constraints remain strict.

Page5 LE`<BBBBIII>` is selected/effective/profile_flags/last_fault/profile_revision/sample_ms/sample_flags. Page6 LE`<IIII>` is held coherent Kp/Ki/Kd Q24 plus sample_ms. Page7 is signed96-bit integral sum Q20 then sample_ms u32. Separate pages can represent separate completed epochs.

## Compact gesture event and current runtime

Page8 LE`<IIBBBBI>`: event_count u32, board_event_ms u32, code u8, action u8, reason u8, event_flags u8, event_id u32. The retained event is updated by actual sensor events; a pending planner result may update its reason without incrementing the event counter. Reading this page or observing a sensor poll sequence does not create a new event. The Host never labels the first retained snapshot after reconnect as a newly received gesture.

Actions:0none,1UpSwing,2position,3circle,4cancel,5WaveSTOP. Reasons:0none,1disabled,2not-ready/error,3swing-discard,4not-actual-handoff,5HOLD-not-ready,6busy/no-queue,7accepted,8cancelled,9protection-or-admission,10unmapped,11planner-rejected,12awaiting-planner.

Page9 LE`<IIHBBBBBB>`: sensor_poll_sequence u32, current_board_ms u32, error_count u16, current_error u8, flags u8, swing_state u8, actual_mode u8, rotation_status u8, runtime u8. Flags bits0..7 are sensor_ready,gesture_enabled,swing_blocked,fresh_balance_ready,motor_permission,zero_valid,estop,fault. Runtime bits0..7 are swing_active,handoff_request,auto_session_armed,manual_run_latch,balance_deadman,HOLD_initialized,rotation_active,rotation_busy. Event flags capture the same current flag meaning at event acceptance; runtime page is current and must not be spliced into a past event as if atomic. Host polling interleaves8/9 three times per full telemetry schedule; serial scheduling and device response determine observation latency.

## Explicit presets

Six bundled parameter JSONs have SP24 identity and a fixed/swing-preset schema. `apply-preset` requires a fresh stopped/PWM0 state, validates every editable integer and read-only encoder/gamma prerequisite, then reuses one-flight WRITE plus independent READ for each field. STOP, timeout or rejection cancels remaining work without replay; completed writes remain reported. It never runs ZERO/RUN/PT or commits/enables Eactual. The baseline112/0/48, damping112/0/56 and slowI112/2/48 choices are individually labeled by evidence. AngleD80 (900/870/80) and angleI780 (900/780/90) each change only one angle gain from the supplied field baseline, retaining position112/0/48 and Eoff; they are separate unvalidated engineering candidates, never automatically combined. All original six angle/position gains remain explicitly STOP-editable. Holding angle gains during a position comparison is an experimental control, not a permanent restriction. Field swing70%230ms/70%230ms/max1 is separate and explicit. The E engineering JSON uses the existing load-profile path with control=False, remains mode0 after upload, and cannot qualify actual control. A later explicit STOP-only mode2 selection is required for shadow.

## SP24 synchronized waveform stream

The80byte J2T4 packet is independent of request/ACK traffic and appears nominally100times/second. Header14bytes:magicJ2T4,total_length u16LE=80,UID0x53503234 u32LE,schema0x53505424 u32LE. CRC16CCITT-FALSE(initialFFFF,polynomial1021) acrossfirst78bytes, little-endian trailing2bytes. No command or setting is implied by receiving telemetry. Frame-boundaryACKpriority preserves completepackets andphysicalUARTidle; UARTSTOP executes independently before itsACK is sent. Raw80byteframes consume8000byte/s of11520byte/s nominal115200/8N1 capacity. Host/USB latency is not certified without hardware.

| Payload byte | Field | Representation |
|---|---|---|
|0|sequence|u32; advances every scheduledcapture, replacement visibleasgaps|
|4|sample_ms|u32; existingcommittedmeasurement/PIDepoch|
|8|capture_ms|u32; snapshot time foractualPWM/protectionflags|
|12|alpha_q20|i32 radiansQ20|
|16|alpha_rate_q20|i32 radians/secondQ20|
|20|theta_rate_q20|i32 radians/secondQ20|
|24|encoder_count|i64 unwrappedcount|
|32|target_count_q32|i96 countQ32; allbits retained|
|44|reference_rad_q20|i64 inner-angle REF radiansQ20|
|52|actual_pwm_q15|i16 signedactualdriverduty|
|54|flags|u8 modebits0..2,PIDvalid3,velocityvalid4,motor5,ZEROvalid6,saturation7|
|55|fault|u8 livecapturefault|
|56|angle_revision|u32 appliedanglePIDrevision|
|60|position_revision|u32 appliedpositionPIDrevision|

Offsets are relative to the64bytepayload, not thewholepacket. Samplevalues come fromexistingcommittedframe registers; actualPWM/status areliveatcapture_ms andmustnotbemisrepresentedassamePIDepoch. Freshness isverifiedfrombothboardtimestamps andreceiverarrival; a repeatedepoch isnotnewmeasurement. The flags describevalidity, notphysicalstability. Encoder1080counts/turn remains3counts/degree; targetQ32 ispositionreferenceprecision, notadditionalencoderresolution. Q20numericLSB isnotADCaccuracy. NewHostrecordsfullsignedintegers, derivedphysicalunits, revisions andgap/CRC/resetstatistics; renderdecimationneverdiscardsrawrecordedsamples. Originalreadonlypages1..9andparameterACKcontracts remainavailable; page1/2snapshots mustnotbesplicedintonewcoherentframes.
