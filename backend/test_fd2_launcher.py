import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FD2LauncherTests(unittest.TestCase):
    def test_five_help(self):
        for variant in range(1, 6):
            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    str(ROOT / "launch_host.py"),
                    f"V{variant}",
                    "--help",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--offline-preview", result.stdout)

    def test_detached_preview_once(self):
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(ROOT / "launch_host.py"),
                "V5",
                "--offline-preview",
                "--headless",
                "--once",
                "--port",
                "0",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"connected": false', result.stdout)
        self.assertIn('"variant": 5', result.stdout)

class AutomationLauncherTests(unittest.TestCase):
    def test_explicit_connect_option_is_documented(self):
        result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/'launch_host.py'),
            'V5', '--help'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--automation-connect', result.stdout)

    def config(self, **changes):
        connection = dict(port='COM11', mode='USB', ble_address='', log_dir=str(ROOT/'离线日志'))
        connection.update(changes)
        return dict(job_id='firmware-1', token='0123456789abcdef0123456789abcdef', connection=connection)

    def test_strict_connection_json_and_exclusive_modes(self):
        import json, tempfile
        import launch_host
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'中文 connection.json'
            path.write_text(json.dumps(self.config()), encoding='utf8')
            self.assertEqual(launch_host.load_automation_connect(path), self.config())
            bad = [self.config(port=''), self.config(mode='BLE'), self.config(ble_address='unexpected'),
                self.config(log_dir='relative'), dict(self.config(), extra=True),
                dict(self.config(), job_id=True), dict(self.config(), token='')]
            for data in bad:
                path.write_text(json.dumps(data), encoding='utf8')
                with self.assertRaises(ValueError):
                    launch_host.load_automation_connect(path)
            path.write_text(json.dumps(self.config()), encoding='utf8')
            for flag in ('--replay', '--offline-preview', '--once'):
                args = ['V5', '--headless', '--port', '0', '--automation-connect', str(path), flag]
                if flag == '--replay': args.append('unused.zip')
                result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/'launch_host.py'), *args],
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('cannot be combined', result.stderr)

    def test_gui_connect_is_queued_to_main_loop_and_has_no_control_actions(self):
        import launch_host
        from host.fd2_bridge import Bridge
        class Variable:
            def __init__(self): self.value = None
            def set(self, value): self.value = value
        class Window:
            def __init__(self): self.pending = []
            def after(self, delay, callback): self.pending.append((delay, callback))
        class App:
            closing = False
            def __init__(self):
                self.port, self.logdir, self.route_mode, self.ble_address = [Variable() for _ in range(4)]
                self.calls = []
            def connect(self): self.calls.append(('connect', threading.get_ident()))
            def close(self): self.calls.append(('close', threading.get_ident()))
        import threading
        bridge, window, app = Bridge(5), Window(), App()
        connection = self.config(mode='USB+BLE', ble_address='AA:BB:CC:DD:EE:FF')['connection']
        launch_host.queue_fd2_gui_lifecycle(bridge, window, app, connection)
        self.assertFalse(app.calls)
        _, connect = window.pending.pop(0)
        connect()
        self.assertEqual(app.calls, [('connect', threading.get_ident())])
        self.assertEqual(app.port.value, 'COM11')
        self.assertEqual(app.route_mode.value, 'USB+BLE')
        self.assertEqual(app.ble_address.value, 'AA:BB:CC:DD:EE:FF')
        bridge.automation.exit_event.set()
        _, poll = window.pending.pop(0)
        poll()
        self.assertEqual(app.calls[-1], ('close', threading.get_ident()))

    def test_v1_to_v3_gui_route_variables_are_created_on_main_thread_for_native_connect(self):
        import launch_host
        from host.fd2_bridge import Bridge
        from unittest.mock import patch
        class Variable:
            def set(self, value): self.value = value
        class Window:
            def __init__(self): self.pending = []
            def after(self, delay, callback): self.pending.append(callback)
        class App:
            closing = False
            def __init__(self): self.port, self.logdir = Variable(), Variable()
            def connect(self): self.connected = True
        for variant in (1, 2, 3):
            bridge, window, app = Bridge(variant), Window(), App()
            connection = self.config(mode='USB+BLE', ble_address='selected-address')['connection']
            launch_host.queue_fd2_gui_lifecycle(bridge, window, app, connection)
            with patch('tkinter.StringVar', side_effect=lambda **kwargs: Variable()):
                try:
                    window.pending[0]()
                except AttributeError as exc:
                    self.fail(f'V{variant} native GUI has no route selectors: {exc}')
            self.assertTrue(app.connected)
            self.assertEqual(app.route_mode.value, 'USB+BLE')
            self.assertEqual(app.ble_address.value, 'selected-address')

    def test_headless_explicit_connect_uses_original_trace_policy_and_duplex(self):
        import launch_host
        from host.fd2_bridge import Bridge, load_upstream, install
        from unittest.mock import patch
        modules = load_upstream()
        bridge = Bridge(5)
        cls = modules['client'].SerialOwner
        saved = {name: getattr(cls, name) for name in ('__init__', '_receive', 'trace', 'command', '_send', 'start', 'stop')}
        try:
            install(bridge)
            connection = self.config(mode='USB+BLE', ble_address='selected-address')['connection']
            with patch.object(modules['log_policy'], 'shared_roots', return_value=[Path('registered')]) as policy:
                with patch.object(cls, 'start', lambda self: self):
                    owner = launch_host.connect_fd2_headless(bridge, modules, connection)
            policy.assert_called_once_with(Path(connection['log_dir']))
            self.assertIs(owner.logger_factory, modules['trace_log'].TraceLogger)
            self.assertEqual(owner.logger_options['shared_roots'], [Path('registered')])
            self.assertEqual(owner.port, 'COM11')
            with patch.object(modules['dual_transport'], 'DuplexPort') as duplex:
                owner.serial_factory('ignored', 0)
                self.assertEqual(duplex.call_args.args, ('COM11', 'selected-address'))
            self.assertTrue(owner.queue.empty())
        finally:
            for name, method in saved.items(): setattr(cls, name, method)
