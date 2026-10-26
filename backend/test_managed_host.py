"""Process/HTTP transition tests with fake subprocesses and loopback clients."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from host_bridge import BridgeError
from test_firmware_service import live

if importlib.util.find_spec('managed_host'):
    from managed_host import ManagedHostGateway
else:
    ManagedHostGateway = None


class FakeClient:
    def __init__(self):
        self.current = live(5, 'new')
        self.current['automation'] = dict(supported=True, busy=True, launch_job_id='job')
        self.calls = []
        self.offline = False

    def status(self):
        if self.offline:
            raise BridgeError('fixture refused')
        return self.current

    def exchange(self, path, body):
        self.calls.append((path, body))
        if path == '/automation/complete':
            self.current['automation']['busy'] = False
        return {'ok': True}


class FakeProcess:
    def __init__(self):
        self.closed = False

    def poll(self):
        return 0 if self.closed else None

    def terminate(self):
        self.closed = True

    def wait(self, timeout=5):
        return 0


class ManagedHostTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(ManagedHostGateway, '缺少受控Host启动器')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'host/fd2/upstream/runtime').mkdir(parents=True)
        (self.root / 'host/fd2/upstream/runtime/python.exe').write_bytes(b'EXPLICIT_OFFLINE_FIXTURE')
        (self.root / 'launch_host.py').write_text('# EXPLICIT_OFFLINE_FIXTURE')
        self.client = FakeClient()
        self.starts = []
        def launch(argv, **kwargs):
            self.starts.append((argv, kwargs))
            return FakeProcess()
        self.gateway = ManagedHostGateway(8371, root=self.root, store=self.root / 'local',
                                          client_factory=lambda **kwargs: self.client,
                                          launcher=launch, listening=lambda: False, timeout=.05)

    def test_absent_host_is_distinguished_from_unrecognized_occupied_port(self):
        self.client.offline = True
        self.assertIsNone(self.gateway.snapshot())
        self.gateway.listening = lambda: True
        with self.assertRaises(Exception):
            self.gateway.snapshot()

    def test_launch_is_only_explicit_with_known_runtime_and_unique_job_context(self):
        snapshot = self.gateway.reconnect('V5', {'port': 'COM8', 'mode': 'USB'}, 'job', previous_session='old')
        self.assertEqual(snapshot['session'], 'new')
        self.assertEqual(len(self.starts), 1)
        argv, options = self.starts[0]
        self.assertIn('--automation-connect', argv)
        self.assertIn('V5', argv)
        self.assertNotIn('--replay', argv)
        self.assertEqual(options['cwd'], str(self.root))
        self.assertFalse(options.get('shell', False))
        # The emitted file must be accepted by the actual launcher's strict
        # parser, including the first-download path without a prior Host.
        from launch_host import load_automation_connect
        context_file = argv[argv.index('--automation-connect') + 1]
        context = load_automation_connect(context_file)
        self.assertEqual(context['connection']['ble_address'], '')
        self.assertEqual(self.client.calls, [])
        self.gateway.complete()
        self.assertEqual(self.client.calls[0][0], '/automation/complete')
        self.assertEqual(self.client.calls[0][1]['job_id'], 'job')

    def test_unrelated_host_on_same_port_cannot_complete_job(self):
        self.client.current['automation']['launch_job_id'] = 'someone-else'
        with self.assertRaises(Exception):
            self.gateway.reconnect('V5', {'port': 'COM8', 'mode': 'USB'}, 'job', previous_session='old')
        self.assertEqual(self.client.calls, [])

    def test_existing_listener_prevents_starting_another_owner(self):
        self.gateway.listening = lambda: True
        with self.assertRaises(Exception):
            self.gateway.reconnect('V5', {'port': 'COM8', 'mode': 'USB'}, 'job')
        self.assertEqual(self.starts, [])


if __name__ == '__main__':
    unittest.main()
