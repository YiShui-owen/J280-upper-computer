import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

try:
    import gowin_programmer as gp
except ImportError:
    gp = None


CABLE = {'cable_index': 1, 'channel': 0, 'location': 99091, 'uid': 'GW20LCRZ'}
CABLE_TEXT = 'Gowin USB Cable(FT2CH)/0/99091/GW20LCRZ (USB location:99091) (SN: GW20LCRZ)\n'
TARGET_TEXT = 'Target Cable: Gowin USB Cable(FT2CH)/0/99091/GW20LCRZ@2.5MHz\n'
DEVICE_TEXT = TARGET_TEXT + 'Device Info:\nFamily: GW2A\nName: GW2A-55C\nID: 0x01234567\n1 device(s) found!\n'
HELP_TEXT = 'GOWIN Programmer Version V1.9.12.03\nGW2A-55C\n4: SRAM Program and Verify\n--cable-index --channel --location --uid --scan --scan-cables --fsFile --run\n'
SUCCESS_TEXT = 'SRAM Program and Verify\nProgram successful\nVerify successful\n'
OBSERVED_CABLE = {'cable_index': 0, 'channel': 0, 'location': 20, 'uid': None}
OBSERVED_CABLE_TEXT = 'Gowin USB Cable(GWU2X)/0/20/null (USB location:20)\n'
OBSERVED_SCAN_TEXT = (' Scanning!\n'
                      ' Target Cable: Gowin USB Cable(GWU2X)/0/20/null@1.33 MHz\n'
                      'Device Info:\n'
                      ' \tFamily: GW2AN  \n'
                      '\tName: GW2A-55C GW2AN-55C  (One of them)  \n'
                      '\tID: 0x0000281B  \n'
                      ' 1 device(s) found!\n'
                      ' Cost 0.58 second(s)\n')


class ProgrammerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(gp, '需要实现固定SRAM工具适配器')
        self.tmp = tempfile.TemporaryDirectory(prefix='高云 工具 ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.exe = self.root / 'Gowin_V1.9.12.03_x64' / 'Programmer' / 'bin' / 'programmer_cli.exe'
        self.exe.parent.mkdir(parents=True)
        self.exe.write_bytes(b'offline executable fixture; never execute')
        self.calls = []

    def runner(self, stdout='', code=0, stderr='', error=None):
        def run(argv, **kwargs):
            self.calls.append((argv, kwargs))
            if error:
                raise error
            if '--scan-cables' in argv:
                output = CABLE_TEXT
            elif '--scan' in argv:
                output = DEVICE_TEXT
            else:
                output = stdout
            return subprocess.CompletedProcess(argv, code, output, stderr)
        return run

    def test_resolve_executable_bin_programmer_and_install_root_with_unicode_spaces(self):
        for value in (self.exe, self.exe.parent, self.exe.parent.parent, self.exe.parents[2]):
            self.assertEqual(gp.resolve_programmer(str(value)), self.exe.resolve())
        for value in ('', str(self.exe) + ' --run 5', '"' + str(self.exe) + '"', str(self.root / 'x.exe')):
            with self.subTest(value=value), self.assertRaises(gp.ProgrammerError):
                gp.resolve_programmer(value)

    def test_discovery_only_filesystem_and_newest_version_first(self):
        older = self.root / 'Gowin_V1.9.9_x64' / 'Programmer' / 'bin' / 'programmer_cli.exe'
        older.parent.mkdir(parents=True)
        older.write_bytes(b'fixture')
        with patch.object(gp, '_discovery_roots', return_value=[self.root]), patch.object(gp.subprocess, 'Popen', side_effect=AssertionError('不得启动进程')):
            self.assertEqual(gp.discover_programmers(), [str(self.exe.resolve()), str(older.resolve())])

    def test_cable_requires_explicit_supported_type_and_strict_scalars(self):
        self.assertEqual(gp.validate_cable({'cable_index': 1}), {'cable_index': 1, 'channel': 0, 'location': None, 'uid': None})
        self.assertEqual(gp.validate_cable(dict(CABLE, label='offline fixture')), CABLE)
        for value in ({}, {'cable_index': True}, {'cable_index': 2}, dict(CABLE, channel='0'), dict(CABLE, channel=-1), dict(CABLE, location=True), dict(CABLE, uid='x --run 5'), dict(CABLE, args=['--run', '5'])):
            with self.subTest(value=value), self.assertRaises(gp.ProgrammerError):
                gp.validate_cable(value)

    def test_manifest_imports_exact_five_original_bitstreams(self):
        manifest = json.loads((gp.PROJECT_ROOT / 'firmware' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(set(manifest['firmwares']), {'V1', 'V2', 'V3', 'V4', 'V5'})
        for variant in manifest['firmwares']:
            item = gp.load_firmware(variant)
            self.assertEqual(item['size'], 18588969)
            self.assertEqual(item['device'], 'GW2A-55C')
            self.assertEqual(hashlib.sha256(item['path'].read_bytes()).hexdigest(), item['sha256'])
            self.assertRegex(manifest['firmwares'][variant]['source_archive_sha256'], r'^[a-f0-9]{64}$')
        with self.assertRaises(gp.ProgrammerError):
            gp.load_firmware('v1')

    def test_changed_bitstream_and_changed_manifest_rejected(self):
        folder = self.root / 'firmware' / 'V1'
        folder.mkdir(parents=True)
        (folder / 'J280_V1.fs').write_bytes(b'tampered')
        original = json.loads((gp.PROJECT_ROOT / 'firmware' / 'manifest.json').read_text(encoding='utf-8'))
        (self.root / 'firmware' / 'manifest.json').write_text(json.dumps(original), encoding='utf-8')
        with self.assertRaises(gp.ProgrammerError):
            gp.load_firmware('V1', self.root)
        original['firmwares']['V1']['sha256'] = hashlib.sha256(b'tampered').hexdigest()
        original['firmwares']['V1']['size'] = len(b'tampered')
        (self.root / 'firmware' / 'manifest.json').write_text(json.dumps(original), encoding='utf-8')
        with self.assertRaises(gp.ProgrammerError):
            gp.load_firmware('V1', self.root)

    def test_probe_only_runs_help_and_requires_exact_operation_four(self):
        tool = gp.GowinProgrammer(self.exe, runner=self.runner(HELP_TEXT))
        self.assertTrue(tool.probe()['supported'])
        self.assertEqual(self.calls[0][0], [str(self.exe), '--help'])
        for text in ('GW2A-55C\nSRAM Program', HELP_TEXT.replace('4:', '5:'), HELP_TEXT.replace('GW2A-55C', 'GW2A-55')):
            with self.subTest(text=text), self.assertRaises(gp.ProgrammerError):
                gp.GowinProgrammer(self.exe, runner=self.runner(text)).probe()

    def test_help_accepts_official_semicolon_operation_list(self):
        self.assertTrue(gp.GowinProgrammer(self.exe, runner=self.runner(HELP_TEXT.replace('4: SRAM Program and Verify', '4: SRAM Program and Verify;'))).probe()['supported'])

    def test_official_cli_scan_prefix_timing_and_null_uid(self):
        for output, uid in [('Cable found: ' + CABLE_TEXT + 'Cost 0.05 second(s)\n', CABLE['uid']), ('Cable found: Gowin USB Cable(FT2CH)/0/99091/null (USB location:99091)\nCost 0.05 second(s)\n', None)]:
            with self.subTest(output=output):
                result = gp.GowinProgrammer(self.exe, runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, output, '')).scan_cables()
                self.assertEqual(result[0]['uid'], uid)

    def test_official_scan_device_blocks_need_exact_name_count_and_cable(self):
        output = 'Scanning!\nTarget Cable: Gowin USB Cable(FT2CH)/0/99091/GW20LCRZ@2.5MHz\nDevice Info:\n Family: GW2A\n Name: GW2A-55C\n ID: 0x01234567\n1 device(s) found!\nCost 0.08 second(s)\n'
        tool = lambda text: gp.GowinProgrammer(self.exe, runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, text, ''))
        self.assertEqual(tool(output).scan_device(CABLE)['device'], 'GW2A-55C')
        for invalid in (output.replace('1 device(s)', '2 device(s)'), output.replace('Name: GW2A-55C', 'Name: GW2A-55C GW2AR-55C (One of them)'), output.replace('/GW20LCRZ@', '/WRONG@'), output.replace(' ID: 0x01234567\n', ''), output + 'Device Info:\n Name: UNKNOWN\n'):
            with self.subTest(invalid=invalid), self.assertRaises(gp.ProgrammerError):
                tool(invalid).scan_device(CABLE)

    def test_same_uid_on_multiple_channels_cannot_ignore_channel(self):
        output = CABLE_TEXT + CABLE_TEXT.replace('/0/99091/', '/1/99092/').replace('location:99091', 'location:99092')
        def runner(argv, **kwargs):
            self.calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, output if '--scan-cables' in argv else DEVICE_TEXT, '')
        with self.assertRaises(gp.ProgrammerError):
            gp.GowinProgrammer(self.exe, runner=runner).program('V1', CABLE)
        self.assertFalse(any('--run' in argv for argv in self.calls))

    def test_scan_accepts_spaced_frequency_without_relaxing_cable_identity(self):
        # An exact-name offline fixture isolates cable formatting from the
        # observed scan's separate, still-blocking device-model ambiguity.
        output = OBSERVED_SCAN_TEXT.replace('GW2A-55C GW2AN-55C  (One of them)', 'GW2A-55C')
        tool = gp.GowinProgrammer(self.exe, runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, output, ''))
        self.assertEqual(tool.scan_device(OBSERVED_CABLE)['device'], 'GW2A-55C')
        for changes in ({'location': 21}, {'channel': 1}, {'cable_index': 1}, {'uid': 'OTHER'}):
            with self.subTest(changes=changes), self.assertRaises(gp.ProgrammerError):
                tool.scan_device(dict(OBSERVED_CABLE, **changes))

    def test_observed_ambiguous_chip_scan_reports_model_ambiguity_without_write(self):
        def runner(argv, **kwargs):
            self.calls.append(argv)
            output = OBSERVED_CABLE_TEXT if '--scan-cables' in argv else OBSERVED_SCAN_TEXT
            return subprocess.CompletedProcess(argv, 0, output, '')
        with self.assertRaisesRegex(gp.ProgrammerError, '型号不唯一.*芯片丝印') as raised:
            gp.GowinProgrammer(self.exe, runner=runner).program('V5', OBSERVED_CABLE)
        self.assertFalse(raised.exception.indeterminate)
        self.assertFalse(any('--run' in argv for argv in self.calls))

    def test_program_accepts_matching_target_cable_with_spaced_frequency(self):
        output = TARGET_TEXT.replace('2.5MHz', '2.5 MHz') + SUCCESS_TEXT
        result = gp.GowinProgrammer(self.exe, runner=self.runner(output)).program('V5', CABLE)
        self.assertTrue(result['verified'])
        self.assertEqual(sum('--run' in argv for argv, _ in self.calls), 1)

    def test_timeout_kills_only_spawned_process_once_without_shell(self):
        process = Mock(stdout=io.BytesIO(b'partial log\n'), returncode=-1)
        process.wait.side_effect = [subprocess.TimeoutExpired(['fixture'], 1), -1]
        with patch.object(gp.subprocess, 'Popen', return_value=process) as popen:
            with self.assertRaises(subprocess.TimeoutExpired):
                gp._run_process(['fixture'], cwd=str(self.root), timeout=1, shell=False, creationflags=0)
        process.kill.assert_called_once()
        popen.assert_called_once()
        self.assertIs(popen.call_args.kwargs['shell'], False)

    def test_only_write_timeout_is_indeterminate_and_does_not_retry(self):
        def run(argv, **kwargs):
            self.calls.append(argv)
            if '--run' in argv:
                raise subprocess.TimeoutExpired(argv, 180, output=b'partial write log')
            return subprocess.CompletedProcess(argv, 0, CABLE_TEXT if '--scan-cables' in argv else DEVICE_TEXT, '')
        with self.assertRaises(gp.ProgrammerError) as result:
            gp.GowinProgrammer(self.exe, runner=run).program('V1', CABLE)
        self.assertTrue(result.exception.indeterminate)
        self.assertIn('partial write log', result.exception.log)
        self.assertEqual(sum('--run' in argv for argv in self.calls), 1)

    def test_program_unknown_success_is_indeterminate(self):
        with self.assertRaises(gp.ProgrammerError) as result:
            gp.GowinProgrammer(self.exe, runner=self.runner('Finished.')).program('V1', CABLE)
        self.assertTrue(result.exception.indeterminate)

    def test_program_rejects_error_text_and_wrong_operation_despite_success_lines(self):
        for output in (SUCCESS_TEXT + 'FAIL: JTAG disconnected', SUCCESS_TEXT + 'Unable to verify device', SUCCESS_TEXT + 'Operation "embFlash Erase,Program,Verify" for device#1...', SUCCESS_TEXT + 'Target Device: GW2A-18C(0x01234567)', SUCCESS_TEXT + 'Target Cable: Gowin USB Cable(FT2CH)/0/99091/OTHER@2.5MHz'):
            with self.subTest(output=output), self.assertRaises(gp.ProgrammerError):
                gp.GowinProgrammer(self.exe, runner=self.runner(output)).program('V1', CABLE)

    def test_scan_device_requires_explicit_physical_identity(self):
        with self.assertRaises(gp.ProgrammerError):
            gp.GowinProgrammer(self.exe, runner=self.runner()).scan_device({'cable_index': 1})
        self.assertEqual(self.calls, [])

    def test_scan_device_every_format_requires_matching_target_and_exact_single_count(self):
        for output in ('Device 0: GW2A-55C\n', 'Device 0: GW2A-55C\n2 device(s) found!\n', 'Device 0: GW2A-55C\n1 device(s) found!\n', TARGET_TEXT + 'Device 0: GW2A-55C\n', TARGET_TEXT + 'Device 0: GW2A-55C\n2 device(s) found!\n'):
            with self.subTest(output=output):
                tool = gp.GowinProgrammer(self.exe, runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, output, ''))
                with self.assertRaises(gp.ProgrammerError) as raised:
                    tool.scan_device(CABLE)
                self.assertFalse(raised.exception.indeterminate)

    def test_ambiguous_scan_summary_never_starts_write(self):
        for device_output in ('Device 0: GW2A-55C\n', 'Device 0: GW2A-55C\n2 device(s) found!\n'):
            calls = []
            def runner(argv, **kwargs):
                calls.append(argv)
                output = CABLE_TEXT if '--scan-cables' in argv else device_output if '--scan' in argv else SUCCESS_TEXT
                return subprocess.CompletedProcess(argv, 0, output, '')
            with self.subTest(device_output=device_output), self.assertRaises(gp.ProgrammerError):
                gp.GowinProgrammer(self.exe, runner=runner).program('V1', CABLE)
            self.assertFalse(any('--run' in argv for argv in calls))

    def test_outputs_and_error_logs_are_bounded(self):
        with self.assertRaises(gp.ProgrammerError) as result:
            gp.GowinProgrammer(self.exe, runner=self.runner('x' * (gp.MAX_OUTPUT_BYTES + 1))).probe()
        self.assertLessEqual(len(result.exception.log), gp.MAX_LOG_LINES)
        self.assertTrue(all(len(line) <= gp.MAX_LINE_LENGTH for line in result.exception.log))

    def test_explicit_no_cables_is_empty_but_unknown_banner_is_failure(self):
        for output in ('No cables found.\nCost 0.05 second(s)', 'Cost 0.05 second(s)'):
            tool = gp.GowinProgrammer(self.exe, runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, output, ''))
            if output.startswith('No cables'):
                self.assertEqual(tool.scan_cables(), [])
            else:
                with self.assertRaises(gp.ProgrammerError):
                    tool.scan_cables()

    def test_scan_cables_parses_documented_identity_and_rejects_ambiguous_output(self):
        cables = gp.GowinProgrammer(self.exe, runner=self.runner()).scan_cables()
        self.assertEqual({k: cables[0][k] for k in CABLE}, CABLE)
        self.assertTrue(cables[0]['label'])
        for output in ('', 'USB cable connected', CABLE_TEXT + 'unrecognized cable: xyz', CABLE_TEXT + CABLE_TEXT):
            with self.subTest(output=output), self.assertRaises(gp.ProgrammerError):
                gp.GowinProgrammer(self.exe, runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, output, '')).scan_cables()

    def test_scan_device_rejects_wrong_multiple_and_unknown_devices(self):
        tool = gp.GowinProgrammer(self.exe, runner=self.runner())
        self.assertEqual(tool.scan_device(CABLE)['device'], 'GW2A-55C')
        for output in ('', 'GW2A-55C', 'Device 0: GW2A-55\n', DEVICE_TEXT + 'Device 1: GW2A-55C\n', DEVICE_TEXT + 'Device 1: UNKNOWN\n'):
            with self.subTest(output=output), self.assertRaises(gp.ProgrammerError):
                gp.GowinProgrammer(self.exe, runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, output, '')).scan_device(CABLE)

    def test_program_only_fixed_operation_four_with_verified_output(self):
        emitted = []
        result = gp.GowinProgrammer(self.exe, runner=self.runner(SUCCESS_TEXT)).program('V1', CABLE, emitted.append)
        self.assertTrue(result['verified'])
        self.assertTrue(result['log'])
        self.assertTrue(emitted)
        writes = [item for item in self.calls if '--run' in item[0]]
        self.assertEqual(len(writes), 1)
        argv, kwargs = writes[0]
        self.assertEqual(argv[argv.index('--run') + 1], '4')
        self.assertEqual(argv[argv.index('--device') + 1], 'GW2A-55C')
        self.assertEqual(argv[argv.index('--cable-index') + 1], '1')
        self.assertIn('--fsFile', argv)
        self.assertIs(kwargs['shell'], False)
        self.assertEqual(Path(kwargs['cwd']), self.exe.parent)
        self.assertGreater(kwargs['timeout'], 0)
        if os.name == 'nt':
            self.assertTrue(kwargs['creationflags'] & subprocess.CREATE_NO_WINDOW)

    def test_explicit_program_finished_and_verify_success_are_both_required(self):
        output = 'Operation "SRAM Program and Verify" for device#1...\nProgram Finished!\nVerify Success\nFinished.\n'
        self.assertTrue(gp.GowinProgrammer(self.exe, runner=self.runner(output)).program('V1', CABLE)['verified'])
        for incomplete in (output.replace('Verify Success\n', ''), output.replace('Program Finished!\n', '')):
            with self.assertRaises(gp.ProgrammerError):
                gp.GowinProgrammer(self.exe, runner=self.runner(incomplete)).program('V1', CABLE)

    def test_program_does_not_accept_generic_success_nonzero_errors_or_timeout(self):
        for output, code, stderr in [('success', 0, ''), ('SRAM Program and Verify\n', 0, ''), (SUCCESS_TEXT, 1, ''), (SUCCESS_TEXT, 0, 'Error: cable lost'), (SUCCESS_TEXT + 'ERROR: mismatch', 0, ''), ('SRAM Program and Verify failed\nVerify successful', 0, '')]:
            with self.subTest(output=output, code=code), self.assertRaises(gp.ProgrammerError):
                gp.GowinProgrammer(self.exe, runner=self.runner(output, code, stderr)).program('V1', CABLE)
        self.calls.clear()
        timeout = subprocess.TimeoutExpired([str(self.exe)], 1)
        with self.assertRaises(gp.ProgrammerError):
            gp.GowinProgrammer(self.exe, runner=self.runner(error=timeout)).program('V1', CABLE)
        self.assertEqual(len(self.calls), 1)

    def test_program_rejects_unmatched_cable_before_any_write(self):
        with self.assertRaises(gp.ProgrammerError):
            gp.GowinProgrammer(self.exe, runner=self.runner(SUCCESS_TEXT)).program('V1', dict(CABLE, uid='OTHER'))
        self.assertFalse(any('--run' in argv for argv, kw in self.calls))

    def test_success_lines_cannot_hide_skipped_lost_or_unknown_output(self):
        for tail in ('Verification skipped: JTAG connection lost',
                     'Unrecognized vendor status: 999', 'Verify not performed'):
            with self.subTest(tail=tail):
                with self.assertRaises(gp.ProgrammerError) as context:
                    gp.GowinProgrammer(self.exe, runner=self.runner(SUCCESS_TEXT + tail + '\n')).program('V1', CABLE)
                self.assertTrue(context.exception.indeterminate)


if __name__ == '__main__':
    unittest.main()
