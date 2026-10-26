"""Offline task orchestration: fake native tools and fake Host, never devices."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import threading
import types
import unittest

from fd2_telemetry import IDENTITIES

if importlib.util.find_spec('firmware_service'):
    from firmware_service import FirmwareService, FirmwareError
else:
    FirmwareService = FirmwareError = None


def live(variant=1, session='old'):
    uid, schema, wire = IDENTITIES[variant]
    return dict(protocol='FD2', variant=variant, user_code=uid, schema=schema,
                wire_version=wire, session=session, connected=True, synced=True,
                status_age_s=0, control_age_s=0, replay={'active': False},
                automation={'supported': True, 'busy': False},
                transport={'usb_connected': True},
                host={'latest': dict(firmware_id=int(uid, 16), schema=int(schema, 16),
                                     wire_version=wire, variant=variant),
                      'error': '', 'log_error': ''})


class FakeHost:
    def __init__(self):
        self.current = live()
        self.calls = []
        self.error = None
        self.next_variant = None
        self.same_session = False

    def snapshot(self):
        return copy.deepcopy(self.current)

    def prepare(self, request_id):
        self.calls.append('prepare')
        if self.error:
            raise RuntimeError(self.error)
        return dict(prepared=True, token='private-token', session='old',
                    job_id=request_id, connection=dict(port='COM8', mode='USB'))

    def close(self, prepared):
        self.calls.append('close')

    def reconnect(self, target, connection, request_id, previous_session=None):
        self.calls.append(('reconnect', target, connection['port']))
        return live(self.next_variant or int(target[1:]),
                    'old' if self.same_session else 'new')

    def complete(self):
        self.calls.append('complete')


class FakeProgrammer:
    def __init__(self):
        self.calls = []
        self.error = None
        self.gate = None
        self.entered = threading.Event()

    def probe(self):
        self.calls.append('probe')
        return {'version': 'EXPLICIT_OFFLINE_FIXTURE'}

    def scan_cables(self):
        self.calls.append('scan_cables')
        return [dict(cable_index=1, channel=0, location=123, uid='fixture')]

    def scan_device(self, cable):
        self.calls.append('scan_device')
        return {'device': 'GW2A-55C'}

    def program(self, variant, cable, emit=None):
        self.calls.append(('program', variant))
        self.entered.set()
        if self.gate:
            if not self.gate.wait(3):
                raise TimeoutError('offline fixture gate')
        if self.error:
            raise self.error
        if emit:
            emit('EXPLICIT_OFFLINE_FIXTURE: SRAM verified')
        return {'verified': True, 'log': ['EXPLICIT_OFFLINE_FIXTURE: verified']}


class FirmwareServiceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(FirmwareService, '缺少SRAM任务调度器')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.exe = self.root / 'with spaces 中文' / 'programmer_cli.exe'
        self.exe.parent.mkdir()
        self.exe.write_text('EXPLICIT OFFLINE TEST; never executed')
        self.host, self.tool = FakeHost(), FakeProgrammer()
        self.saved, self.parked = [], []
        self.tools = types.SimpleNamespace(
            discover_programmers=lambda: [str(self.exe)],
            resolve_programmer=lambda value: self.exe,
            validate_cable=lambda value: dict(value),
            load_firmware=lambda variant: {'variant': variant, 'path': self.root / 'fixture.fs'},
            GowinProgrammer=lambda exe: self.tool,
        )
        self.replaying = False
        self.service = self.make_service()
        self.service.save_config(dict(programmer_path=str(self.exe),
                                     cable=dict(cable_index=1, channel=0, location=123, uid='fixture'),
                                     usb_port='COM8'))

    def make_service(self):
        return FirmwareService(self.root / 'state', tools=self.tools,
                               host_factory=lambda: self.host,
                               commit_variant=self.saved.append,
                               car_quiesce=lambda: self.parked.append(True),
                               is_replay=lambda: self.replaying)

    def run_job(self, **changes):
        body = dict(request_id='one', target='V5', motor_isolated=False) | changes
        self.service.start(**body)
        self.assertTrue(self.service.wait_idle(4), '离线任务未结束')
        return self.service.result(body['request_id'])

    def test_config_reads_and_saves_do_not_access_any_device(self):
        config = self.service.config()
        self.assertTrue(config['configured'])
        self.assertEqual(config['usb_port'], 'COM8')
        self.assertEqual(self.tool.calls, [])
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.service.status()['busy'], False)

    def test_success_requires_handoff_then_single_sram_then_real_new_identity(self):
        result = self.run_job()
        self.assertEqual(result['state'], 'succeeded')
        self.assertEqual(self.host.calls, ['prepare', 'close', ('reconnect', 'V5', 'COM8'), 'complete'])
        self.assertEqual(self.tool.calls.count(('program', 'V5')), 1)
        self.assertEqual(self.saved, ['V5'])
        self.assertEqual(len(self.parked), 1)
        self.assertNotIn('private-token', str(result))

    def test_same_request_id_is_once_only_and_conflicting_target_rejected(self):
        first = self.run_job()
        again = self.service.start(request_id='one', target='V5', motor_isolated=False)
        self.assertEqual(again['request_id'], first['request_id'])
        self.assertEqual(self.tool.calls.count(('program', 'V5')), 1)
        with self.assertRaises(FirmwareError):
            self.service.start(request_id='one', target='V4', motor_isolated=False)

    def test_busy_rejects_second_job_config_and_motion_but_stop_is_available(self):
        self.tool.gate = threading.Event()
        self.service.start(request_id='one', target='V5', motor_isolated=False)
        self.assertTrue(self.tool.entered.wait(2))
        try:
            self.assertTrue(self.service.status()['busy'])
            with self.assertRaises(FirmwareError):
                self.service.start(request_id='two', target='V4', motor_isolated=False)
            with self.assertRaises(FirmwareError):
                self.service.run_control('balance', lambda: True)
            self.assertTrue(self.service.run_control('stop', lambda: True))
            with self.assertRaises(FirmwareError):
                self.service.save_config(self.service.config())
        finally:
            self.tool.gate.set()
            self.assertTrue(self.service.wait_idle(4))

    def test_replay_never_scans_or_programs_even_with_isolation_confirmation(self):
        self.replaying = True
        with self.assertRaises(FirmwareError):
            self.service.start(request_id='one', target='V5', motor_isolated=True)
        with self.assertRaises(FirmwareError):
            self.service.scan(str(self.exe))
        self.assertEqual(self.tool.calls, [])

    def test_replay_discovered_from_actual_host_fails_before_stop_or_program(self):
        self.host.current['replay']['active'] = True
        result = self.run_job(motor_isolated=True)
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(self.host.calls, [])
        self.assertNotIn(('program', 'V5'), self.tool.calls)

    def test_stale_connected_host_cannot_be_bypassed_by_isolation_checkbox(self):
        self.host.current['status_age_s'] = 2
        result = self.run_job(motor_isolated=True)
        self.assertEqual(result['state'], 'failed')
        self.assertNotIn('prepare', self.host.calls)
        self.assertNotIn(('program', 'V5'), self.tool.calls)

    def test_no_host_requires_explicit_per_job_motor_isolation(self):
        self.host.current = None
        result = self.run_job()
        self.assertEqual(result['state'], 'failed')
        self.assertNotIn(('program', 'V5'), self.tool.calls)
        isolated = self.run_job(request_id='two', motor_isolated=True)
        self.assertEqual(isolated['state'], 'succeeded')
        self.assertEqual(self.host.calls, [('reconnect', 'V5', 'COM8'), 'complete'])

    def test_prepare_failure_cannot_reach_any_jtag_device_operation(self):
        self.host.error = 'STOP has no fresh zero output'
        result = self.run_job()
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(self.host.calls, ['prepare'])
        self.assertNotIn('scan_device', self.tool.calls)
        self.assertNotIn(('program', 'V5'), self.tool.calls)

    def test_cli_failure_is_not_retried_and_does_not_start_host(self):
        self.tool.error = RuntimeError('verify failed')
        result = self.run_job()
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(self.tool.calls.count(('program', 'V5')), 1)
        self.assertEqual(self.host.calls, ['prepare', 'close'])
        self.assertEqual(self.saved, [])

    def test_cli_timeout_remains_indeterminate_without_retry(self):
        self.tool.error = TimeoutError('write outcome unknown')
        result = self.run_job()
        self.assertEqual(result['state'], 'indeterminate')
        self.assertEqual(self.tool.calls.count(('program', 'V5')), 1)
        self.assertEqual(self.saved, [])

    def test_wrong_or_old_host_identity_cannot_mark_download_complete(self):
        self.host.next_variant = 4
        result = self.run_job()
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(self.saved, [])
        self.assertNotIn('complete', self.host.calls)
        self.host.next_variant = None
        self.host.same_session = True
        second = self.run_job(request_id='two')
        self.assertEqual(second['state'], 'failed')
        self.assertEqual(self.saved, [])

    def test_restarted_service_preserves_once_only_result(self):
        self.run_job()
        restarted = self.make_service()
        self.assertEqual(restarted.result('one')['state'], 'succeeded')
        restarted.start(request_id='one', target='V5', motor_isolated=False)
        self.assertEqual(self.tool.calls.count(('program', 'V5')), 1)

    def test_safe_api_id_with_colon_is_audited_without_windows_stream_filename(self):
        result = self.run_job(request_id='fixture:one.01')
        self.assertEqual(result['state'], 'succeeded')
        restored = self.make_service()
        self.assertEqual(restored.result('fixture:one.01')['state'], 'succeeded')
        self.assertTrue(all(':' not in file.name for file in (self.root/'state/jobs').iterdir()))

    def test_interrupted_journal_becomes_unknown_and_is_never_automatically_repeated(self):
        self.run_job()
        job = dict(self.service._jobs['one'], state='running', phase='programming')
        self.service._persist(job)
        restored = self.make_service()
        self.assertEqual(restored.result('one')['state'], 'indeterminate')
        restored.start(request_id='one', target='V5', motor_isolated=False)
        self.assertEqual(self.tool.calls.count(('program', 'V5')), 1)

    def test_actual_replay_host_prevents_cable_scan_before_native_process(self):
        self.host.current['replay']['active'] = True
        with self.assertRaises(FirmwareError):
            self.service.scan(str(self.exe))
        self.assertEqual(self.tool.calls, [])


if __name__ == '__main__':
    unittest.main()
