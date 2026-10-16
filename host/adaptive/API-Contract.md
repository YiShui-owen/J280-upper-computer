# SA21 Integration Contract

Target J280 GW2A-LV55PG484C8/I7,50MHz. UserCode53413231, schema53415421. Includes the SG21 gesture/circle contract and original SWM2 stopped-only configuration, replay/CRC/ACK semantics. Use SA21's matching Host; SG21,SWM2 and E68 Hosts are not interchangeable.

## Additional32-bit parameters

|ID|Meaning|Default / values|
|---|---|---|
|30|Gesture enable|0;0/1|
|31|Selected E mode|0off,1control,2shadow|
|32|Independent E integral enable|1;0/1; cannot disable while mode1 selected|
|33|Profile control|0invalidate and clear staged-write mask;1commit control-qualified declaration;2commit shadow-only|
|40..45|Three positive ordered error and three Delta-error nodes|Signed-positive Q20, default0 invalid|
|46..49|Kp_min,Kp_max,Kd_min,Kd_max|Positive ordered unsigned Q24, default0 invalid|

All writes require original stopped/PWMzero/no-session/no-capture/no-estop permission. Staging additionally requires selectedmode0 and invalid profile. All10 words must have been written since invalidation. Commit checks complete write mask and all ordering/ranges before setting valid, and increments profile_revision. Mode1 additionally requires a valid control-qualified profile and independent I enabled. Mode2 requires a valid profile. Profile invalidation returns selection to0. No partial profile can be adopted.

Selection is made while stopped. Effective mode is selectedmode only when actual core mode3/BALANCE and original motor_enable are true; otherwise0. Swing and20ms capture qualification always use original SWM2. There is no live mode/gain-policy switch during balancing. STOP before changing this policy; a subsequent swing applies it only after qualified handoff.

## Readback

- Page4: SG21 sensor/motion observations.
- Page5: selected_mode_u8,effective_mode_u8,profile_flags_u8(valid bit0,qualified bit1,Ienable bit2),last_completed_fault_u8,configured_profile_revision_u32,last_completed_sample_ms_u32,last_completed_E_flags_u32.
- Page6: actual completed Kp_u32,Ki_u32,Kd_u32 inQ24, and the same gain epoch sample_ms_u32, captured atomically.
- Page7: unweighted integral signed96Q20 and its epoch sample_ms_u32. Pages are separate requested snapshots; do not splice pages from different epochs.

Existing E operator rules,49rule table, ROM, gamma, currentKi-times-history integral and true90percent downstream antiwindup are reused. Mode0 is checked against frozen SWM2 balance outputs. Original live STOP/motor/angle protection and E result admission reject on the first edge; only the new worker's internal abort clears on the second edge. No physical protection is delayed.

The SA21 validated sensor Wave command has a local one-clock dispatch register to prevent the sensor error/code decode from propagating into the entire original control clear network. It adds20ns after the sensor event, not to hardware estop or UART STOP. Sensor recognition's official1000ms Wave wait remains unchanged. This boundary does not delay the motor protection once the command is dispatched.

The matching Host imports the existing E profile JSON schema, screens provenance and representability, disables/invalidate first, writes10words with independent READ, then commits. It never automatically enables E or RUN. Synthetic profiles are refused for control qualification. Missing Ku/Tu and physical membership scales remain missing: default mode0/invalid profile is intentional, not an autotuned controller. Load adaptation and stability remain physical acceptance work.
