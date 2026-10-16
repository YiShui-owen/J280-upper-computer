# SP24 Integration Specification

## Scope and acceptance

1. Preserve exact SP22 motion and safety baseline; change stopped swing gesture Right1 to Up3. Block sensor actions throughout all SWM2phases and handoff boundary, with fresh post-ready events only; independentSTOP/estop/fault unchanged.
2. Reproduce and diagnose natural automatic handoff path using real core/swingstates,20qualified1ms capture samples and no force ofmode/handoff/deadman/initialized. Exercise Up and UARTSWING_RUN entry, left/rightposition/cancel/restart/circles, allphasefalsegesturediscard, handoff before/on/after boundary and manualcontrast.
3. Integrate exact SA21 paperE arithmetic/ROM/positionPID into latestSP22 core. Eoff matches latestSP22; shadowdoesnotdrive; actualadoptiononlyBALANCE+originalmotorpermit. Preserve 0x31..33,40..49 plusSP22 0x34/35. Independentintegral with originalAW/STOPstate semantics and targetD acknowledged.
4. New event telemetry records realready/error, independent eventcounter, boardeventms, accepted/rejectedaction and reason, realsession/handoff/motionready. Pollsequenceis separate. Compactversionedreadonlypages, retained snapshot (no stale eventredisplay asnew).
5. MatchingHost has clearChineseevent/action/reason labels, one serialowner,CRC,STOPpriority, stopped-onlywrites,independentreadback,noautomaticRUN/ZERO/PT/retry. Allow coldzero ordinary READ onlyforunconfiguredEwords; keepwrite/verify/inputpositiveconstraints.
6. Publish independentnumeric traditionalpositionPID and Eengineeringpresets with actualRTLunits/Qformats,evidencegrades,risks and rollback; no fabricatedKu/Tu/modelquality/measuredcontrolqualification. FieldrecordedSWM2settings importedexplicitly. DefaultEoff andprofileinvalid.
7. Complete source-bound RTL/regressions/Hosttests before visible50MHzSYNtiminggate and full serialPnR; new UID53503234/schema53505424; setup0/hold0; fullsource/Host/presets/nativehashes/recoveryZIP. Physicalswing/settling/loadperformance remainsunacceptedwithoutboard.

## Implementation constraints

Surgicalglue reuse, no replacementrecognition/controlalgorithm or wide logging. Missing local karpathy-guidelines/ponytail skill files: apply their requested explicitassumptions/minimalreuse/focusedverificationprinciples directly. No writes outside this successor except finalworkspaceMEMORYentry and uniquely scoped native/ModelSim scratch.


## Owner update: dual-loop tuning scope

The new attachment reviewed during native routing expands tuning scope and physicalacceptance, not FPGAfunctionrequirements. Angle900/870/90 is a suppliedbaseline, not optimal or locked. Both loops and E must be iterated; no needtochangecurrentHDL orcancelroute. Add explicitangle-only minimalcandidate presets and stageddual-loop matching/rollback, preservingknownouterwhiletestingangle. Primaryphysicaltarget: actualrodsteadyoscillation atmostonefifth ofbaseline, thenlonghold, thenrepeatedbidirectionalarmsettlingwithdisturbancerecovery. No adequateplant/highrateactualREF/angle/PWMrecord exists locally; phasecauses/optima and targetachievementremainunverified. Data/profile/Hostpresetinventory updates donot requireFPGArecompile.

## Current telemetry delta

Telemetry-Spec.md is authoritative for the100Hz synchronizedstream, nativeprecisionlogging, plotting andtheir acceptance. The sectionsabove retain theacceptedcontrolbaseline. PriorSP23nativeacceptance doesnotapply toSP24; a freshsource-bound fullroute isrequired.
