# SP24 Precise Telemetry Specification

## Goal and boundaries

Preserve frozen SP23 control/gesture/E/STOP behavior. Replace low-rate asynchronous waveform polling with synchronized native precision telemetry. No hardware programming, serial enumeration or motor actions. J280 GW2A-LV55PG484C8/I7, original50MHz/20ns clock and115200/8N1 serial stay unchanged. UID0x53503234/schema0x53505424. No new filtering/interpolation/control decisions.

## Contract

J2T4 frame: magic4, total_length u16LE=80, UID u32LE, schema u32LE, payload64, CRC16CCITT-FALSE u16LE acrossfirst78bytes. Existing J2C3/J2A3 commands retain format, newidentity. Payload offsets:0sequence u32;4sample_ms u32;8capture_ms u32;12alpha_q20 i32;16alpha_rate_q20 i32;20theta_rate_q20 i32;24encoder_count i64;32target_count_q32 i96;44reference_rad_q20 i64;52actual_pwm_q15 i16;54flags u8;55fault u8;56angle_revision u32;60position_revision u32. Flags:mode bits0..2,PIDvalid3,velocityvalid4,motor5,ZEROvalid6,saturation7. Numericframefields use the existing committed core epoch. PWM/mode/protection are explicitly live snapshots atcapture_ms, not mislabeled same-PID-epoch data. Exactrawinteger columns remain authoritative. Physical ADC/encoder resolution does not increase.

Captureevery10 existing1ms diagnostic pulses, only bounded snapshot/active buffers; no backpressure tocontrol. Sequence advances forscheduledcaptures, replacement underbackpressure is visible as sequence gaps. ACK priority onlybetweenwholeframes and UART physicalidle; originalSTOP executes independently firstedge. Nominalwave100Hz,80*100*10=80000baud,69.45percent of115200 beforeACK. No newfull420byteobservability chain.

## Host and logs

Parse fragmented/mixed/corruptACK/telemetry streams strictly, allCRC/identity/size gates. Preserve rawbytes, fullintegerCSV includingi96Q32, boardandhosttimes, actualrevisions, gaps/CRC/stale/reset statistics. Log existingreadonlyE/gesturepages too. Batch writes, flushatboundedintervalandclose; no perframeflushblockingUI. One serialowner andSTOPpriority stay. Renderapproximately30FPS withsharedboardtimeaxis, target/measuredarm andreference/angle, visibleaxes/timeunits/currentvalues/age/observedrate/gaps. Pixelminmaxreductionpreservesextrema; no fabricatedsmoothing, no lineacrossgaps. Verticalminimumsreflectnumeric/measurementquantizationratherthan1degreepadding. Recordingretainsallvalidsamples independentofdisplayreduction.

## Tasks and acceptance

1. Reuse existingwholeframearbiter unchanged; addsmallserializer andtopread-onlywiring. Source-bound Verilog test transmitsactualUART, checks100Hzintervals/rawsignedboundaries/CRC/ACKarbitration/sequencegaps/reset/STOPindependence; proveobservedframeiscommittedbeforecapture.
2. Host decoder/logger/plot implementation andtests coverfragmentation/corruption/restart/timewrap/fullrawprecision/knownsineandnarrowspike/gapmarks/throughput100HzplusACK/noautohardware.
3. RetaincompleteSP23controlregressions andHostguardtests. NewUIgeometry/actualrenderproofwhereavailable. FreshvisibleSYNgate thenfull50MHznativeroute, setup0/hold0.
4. Rebindallproofs/acceptedFS/Host/presets/recovery, packageandcleanextractvalidation. MeasuredUSB/physicalend-to-endlatency remainspendingwithoutboard; reportsoftware/nativebounds honestly.
