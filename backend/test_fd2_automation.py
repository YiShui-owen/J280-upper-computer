import struct
import threading
import time
import unittest
from pathlib import Path

from host.fd2_bridge import Bridge, install, load_upstream
from backend.test_fd2_bridge import native_frame


class NativeHandoffFixture(unittest.TestCase):
    def setUp(self):
        self.modules = load_upstream()
        self.p = self.modules['protocol']
        self.cls = self.modules['client'].SerialOwner
        self.methods = ('__init__', '_receive', 'trace', 'command', '_send', 'start', 'stop')
        self.saved = {name: getattr(self.cls, name) for name in self.methods}
        self.bridge = Bridge(5)
        install(self.bridge)
        self.owner = self.cls(5, 'COM11', Path('离线日志'))
        self.owner.state.connected = True
        self.owner.state.authenticated = True
        self.owner._serial = type('Port', (), {'port': 'COM11', 'writes': [],
            'write': lambda port, raw: port.writes.append(raw) or len(raw)})()
        self.stops = []
        def stop(wait=True):
            self.stops.append(wait)
            self.owner.stop_event.set()
            # The original _run sends a final internal STOP before close.
            self.owner._send(self.p.STOP, internal=True)
            self.owner.state.connected = False
            self.owner.state.authenticated = False
            self.owner.closed.set()
        self.owner.stop = stop
        self.telemetry(1)

    def tearDown(self):
        for name, method in self.saved.items():
            setattr(self.cls, name, method)

    def telemetry(self, n, *, pwm=0, mode=1, flags=1):
        raw = bytearray(native_frame(sequence=n, board_ms=n*5))
        raw[6] = flags
        raw[7] = mode
        struct.pack_into('<h', raw, 62, pwm)
        struct.pack_into('<H', raw, 254, self.p.crc16(raw[:-2]))
        self.owner._receive(bytes(raw), self.p.decode(raw))

    def unzeroed_status(self, n):
        raw = bytearray(native_frame(sequence=n, board_ms=n*100))
        raw[6] = raw[7] = 0
        struct.pack_into('<I', raw, 16, 0)
        struct.pack_into('<h', raw, 62, 0)
        struct.pack_into('<H', raw, 254, self.p.crc16(raw[:-2]))
        self.owner._receive(bytes(raw), self.p.decode(raw))

    def ack(self, wire, *, opcode=None, status=0, epoch=0):
        raw = bytearray(80)
        raw[:4] = b'FD2A'
        raw[4:8] = bytes((5, self.p.STOP if opcode is None else opcode, status, 5))
        struct.pack_into('<I', raw, 8, wire)
        struct.pack_into('<I', raw, 20, epoch)
        struct.pack_into('<I', raw, 72, self.p.FIRMWARE[5])
        struct.pack_into('<H', raw, 78, self.p.crc16(raw[:-2]))
        self.owner._receive(bytes(raw), self.p.decode(raw))

    def begin(self, job='job-1', timeout=.3):
        self.result = {}
        def work():
            try:
                self.result['value'] = self.bridge.automation.prepare({'job_id': job}, timeout=timeout)
            except Exception as exc:
                self.result['error'] = exc
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        deadline = time.monotonic() + 1
        while self.owner.queue.empty() and worker.is_alive() and time.monotonic() < deadline:
            time.sleep(.002)
        return worker

    def send_stop(self):
        entry = self.owner.queue.get_nowait()
        self.assertEqual(entry[2], self.p.STOP)
        self.owner._sending_source = self.owner.queued_sources.pop(entry[1])
        return self.owner._send(entry[2], entry[3], entry[4])


class AutomationContractTests(unittest.TestCase):
    def test_status_advertises_automation_without_connecting(self):
        bridge = Bridge(5)
        self.assertIn('automation', bridge.status())
        self.assertEqual(bridge.status()['automation'], {
            'supported': True, 'busy': False, 'job_id': None, 'launch_job_id': None,
        })

    def test_prepare_is_available(self):
        self.assertTrue(callable(getattr(Bridge(5).automation, 'prepare', None)))


class NativeHandoffTests(NativeHandoffFixture):
    def test_actual_stop_must_be_newer_than_ack_epoch_and_arrive_after_ack(self):
        worker = self.begin()
        wire = self.send_stop()
        self.telemetry(2)
        self.ack(wire, epoch=2)
        time.sleep(.02)
        self.assertTrue(worker.is_alive(), 'pre-ACK buffered telemetry cannot complete prepare')
        self.telemetry(3)
        worker.join(1)
        self.assertTrue(self.result['value']['prepared'])

    def test_original_owner_loop_releases_transport_logger_and_lease_with_one_stop(self):
        import queue

        fixture = self
        class Logger:
            error = ''
            written = queued_bytes = 0
            archive_path = partial_path = None
            def __init__(self, *args, **kwargs): self.closed = False
            def start(self): pass
            def close(self): self.closed = True
            def submit(self, raw, item): return True
            def event(self, *args, **kwargs): pass
            def io(self, *args): pass
        class Lease:
            exited = False
            def __enter__(self): return self
            def __exit__(self, *args): self.exited = True
        class Port:
            port = 'COM11'
            def __init__(self):
                self.responses = queue.Queue()
                self.opcodes = []
                self.epoch = 2
                self.closed = False
            def __enter__(self): return self
            def __exit__(self, *args): self.closed = True
            def write(self, raw):
                self.opcodes.append(raw[5])
                ack = bytearray(80)
                ack[:4] = b'FD2A'
                ack[4:8] = bytes((5, raw[5], 0, 5))
                struct.pack_into('<I', ack, 8, struct.unpack_from('<I', raw, 8)[0])
                struct.pack_into('<I', ack, 72, fixture.p.FIRMWARE[5])
                struct.pack_into('<H', ack, 78, fixture.p.crc16(ack[:-2]))
                self.responses.put(bytes(ack))
                return len(raw)
            def read(self, count):
                time.sleep(.001)
                self.epoch += 1
                raw = bytearray(native_frame(sequence=self.epoch, board_ms=self.epoch*5))
                raw[7] = 1
                struct.pack_into('<H', raw, 254, fixture.p.crc16(raw[:-2]))
                data = bytes(raw)
                while not self.responses.empty(): data = self.responses.get_nowait() + data
                return data
        port, lease = Port(), Lease()
        owner = self.owner
        owner.state.authenticated = False
        owner.serial_factory = lambda *args: port
        owner.logger_factory = Logger
        owner.lease_factory = lambda: lease
        owner.stop = self.cls.stop.__get__(owner)
        owner.start()
        try:
            deadline = time.monotonic()+1
            while not owner.state.authenticated and time.monotonic() < deadline: time.sleep(.002)
            result = self.bridge.automation.prepare({'job_id': 'native-loop'}, timeout=1, close_timeout=1)
            self.assertTrue(result['prepared'])
            self.assertTrue(owner.closed.is_set())
            self.assertTrue(owner.logger.closed)
            self.assertTrue(port.closed)
            self.assertTrue(lease.exited)
            self.assertEqual(port.opcodes.count(self.p.STOP), 1)
            self.assertIn(self.p.STATUS, port.opcodes)
            self.assertIn(self.p.READ_GAINS, port.opcodes)
        finally:
            if not owner.closed.is_set():
                if self.bridge.automation.lease:
                    self.bridge.automation.lease['exit_requested'] = True
                owner.stop(wait=False)
                owner.closed.wait(1)

    def test_stop_ack_and_independently_new_actual_stop_then_close_once(self):
        worker = self.begin()
        wire = self.send_stop()
        self.ack(wire)
        time.sleep(.02)
        self.assertTrue(worker.is_alive(), 'a STOP ACK cannot stand in for actual PWM')
        self.telemetry(2, pwm=10)
        time.sleep(.02)
        self.assertTrue(worker.is_alive())
        self.telemetry(3)
        worker.join(1)
        self.assertNotIn('error', self.result)
        result = self.result['value']
        self.assertTrue(result['prepared'])
        self.assertEqual(result['connection'], {'port': 'COM11', 'mode': 'USB',
            'ble_address': '', 'log_dir': str(Path('离线日志').resolve())})
        self.assertEqual(result['session'], self.bridge.session)
        self.assertEqual(self.stops, [False])
        self.assertEqual(len(self.owner._serial.writes), 1)
        self.assertEqual(result, self.bridge.automation.prepare({'job_id': 'job-1'}))
        self.assertEqual(len(self.owner._serial.writes), 1)

    def test_unzeroed_idle_status_can_confirm_stop_without_creating_control_samples(self):
        self.owner.state.last_control = None
        self.owner.state.last_control_rx = 0
        self.unzeroed_status(2)
        worker = self.begin()
        wire = self.send_stop()
        self.ack(wire, epoch=0)
        self.unzeroed_status(3)
        worker.join(1)
        self.assertNotIn('error', self.result)
        self.assertTrue(self.result['value']['prepared'])
        self.assertIsNone(self.owner.state.last_control)

    def test_unzeroed_duplicate_pre_stop_packet_after_ack_is_not_new_stop_evidence(self):
        self.owner.state.last_control = None
        self.owner.state.last_control_rx = 0
        self.unzeroed_status(2)
        worker = self.begin()
        wire = self.send_stop()
        self.ack(wire, epoch=0)
        self.unzeroed_status(2)  # Exact same pre-STOP bytes delivered again.
        time.sleep(.025)
        self.assertTrue(worker.is_alive(), 'duplicate status must not authorize owner close')
        self.assertFalse(self.owner.closed.is_set())
        self.unzeroed_status(3)
        worker.join(1)
        self.assertNotIn('error', self.result)
        self.assertTrue(self.result['value']['prepared'])

    def test_unzeroed_status_cannot_use_epoch_wrap_as_control_evidence(self):
        self.owner.state.last_control = None
        self.owner.state.last_control_rx = 0
        self.unzeroed_status(2)
        worker = self.begin()
        wire = self.send_stop()
        self.ack(wire, epoch=0xffffffff)
        self.unzeroed_status(2)
        time.sleep(.025)
        self.assertTrue(worker.is_alive())
        self.unzeroed_status(3)
        worker.join(1)
        self.assertTrue(self.result['value']['prepared'])

    def test_failed_prepare_can_be_closed_manually_to_restore_original_startup(self):
        import launch_host
        worker = self.begin(timeout=.04)
        self.send_stop()
        worker.join(1)
        self.assertIn('error', self.result)
        class App:
            def __init__(self): self.closed = False
            def close(self): self.closed = True
            def show_error(self, error): self.error = str(error)
        application = launch_host.guarded_fd2_app_class(self.bridge, App)()
        application.close()
        self.assertTrue(application.closed)

    def test_prepared_stopped_owner_can_be_closed_by_operator_without_waiting_for_http(self):
        import launch_host
        worker = self.begin()
        wire = self.send_stop()
        self.ack(wire)
        self.telemetry(2)
        worker.join(1)
        self.assertTrue(self.result['value']['prepared'])
        class App:
            def __init__(self): self.closed = False
            def close(self): self.closed = True
            def show_error(self, error): self.error = str(error)
        application = launch_host.guarded_fd2_app_class(self.bridge, App)()
        application.close()
        self.assertTrue(application.closed)

    def test_wrong_ack_times_out_retains_fence_without_retry(self):
        worker = self.begin(timeout=.08)
        wire = self.send_stop()
        self.ack(wire, opcode=self.p.ZERO)
        self.telemetry(2)
        worker.join(1)
        self.assertIn('error', self.result)
        self.assertTrue(self.bridge.status()['automation']['busy'])
        self.assertEqual(len(self.owner._serial.writes), 1)
        self.assertFalse(self.stops)
        with self.assertRaises(ValueError):
            self.bridge.automation.prepare({'job_id': 'job-1'})
        self.assertEqual(len(self.owner._serial.writes), 1)
        detail = self.result['error'].response
        self.bridge.automation.release({'job_id': 'job-1', 'token': detail['token']})
        self.assertFalse(self.bridge.status()['automation']['busy'])

    def test_all_gui_keyboard_web_and_direct_writes_are_fenced_but_reads_and_stop_pass(self):
        worker = self.begin(timeout=.15)
        self.send_stop()
        for source in ('GUI', 'KEYBOARD/space', 'internal'):
            with self.assertRaises(RuntimeError):
                self.owner.command(self.p.RUN, source=source)
        with self.assertRaises(ValueError):
            self.bridge.command({'request_id': 'web-run', 'action': 'balance'})
        with self.assertRaises(RuntimeError):
            self.owner._send(self.p.RUN, internal=True)
        self.owner.command(self.p.STATUS)
        self.owner.command(self.p.READ_GAINS, 255)
        self.owner.command(self.p.STOP)
        self.owner.command(self.p.ESTOP)
        with self.assertRaises(RuntimeError):
            self.cls(5, 'COM12', 'unused')
        with self.assertRaises(ValueError):
            self.bridge.automation.prepare({'job_id': 'another'})
        worker.join(1)

    def test_already_popped_control_is_discarded_without_killing_receive_thread(self):
        self.bridge.command({'request_id': 'already-popped', 'action': 'balance'})
        entry = self.owner.queue.get_nowait()
        source = self.owner.queued_sources.pop(entry[1])
        worker = self.begin(timeout=.05)
        # The native owner can pop a pre-existing queue entry just before the
        # prepare fence wins the dispatch lock. Its _send must become a no-op.
        self.owner._sending_source = source
        self.owner._send(self.p.RUN)
        self.assertFalse(self.owner._serial.writes)
        self.assertEqual(self.bridge.requests['already-popped']['state'], 'rejected')
        self.send_stop()
        worker.join(1)

    def test_session_switch_fails_closed_and_never_stops_owner(self):
        worker = self.begin()
        wire = self.send_stop()
        self.ack(wire)
        self.bridge.new_session()
        self.telemetry(2)
        worker.join(1)
        self.assertIn('error', self.result)
        self.assertFalse(self.stops)
        self.assertTrue(self.bridge.status()['automation']['busy'])

    def test_replay_usb_absence_identity_and_log_errors_reject_without_stop(self):
        cases = ('replay', 'usb', 'identity', 'logging', 'stale')
        for case in cases:
            with self.subTest(case=case):
                bridge = self.bridge
                if case == 'replay': bridge.replay['active'] = True
                if case == 'usb': self.owner._serial = type('BLE', (), {'usb': None, 'ble': object()})()
                if case == 'identity': self.owner.state.authenticated = False
                if case == 'logging': self.owner.state.log_error = 'disk full'
                if case == 'stale': self.owner.state.last_control_rx = time.monotonic()-1
                with self.assertRaises(ValueError) as caught:
                    bridge.automation.prepare({'job_id': case}, timeout=.01)
                self.assertTrue(self.owner.queue.empty())
                bridge.automation.release({'job_id': case, 'token': caught.exception.response['token']})
                bridge.replay['active'] = False
                self.owner._serial = type('USB', (), {'port': 'COM11'})()
                self.owner.state.authenticated = True
                self.owner.state.log_error = ''
                self.owner.state.last_control_rx = time.monotonic()

    def test_close_requires_prepared_token_and_signals_only_after_response(self):
        worker = self.begin()
        wire = self.send_stop()
        self.ack(wire)
        self.telemetry(2)
        worker.join(1)
        value = self.result['value']
        with self.assertRaises(ValueError):
            self.bridge.automation.close({'job_id': 'job-1', 'token': 'wrong'})
        with self.assertRaises(ValueError):
            self.bridge.automation.release({'job_id': 'job-1', 'token': value['token']})
        result = self.bridge.automation.close({'job_id': 'job-1', 'token': value['token']})
        self.assertTrue(result['closed'])
        self.assertFalse(self.bridge.automation.exit_event.is_set())
        self.bridge.automation.finish_close()
        self.assertTrue(self.bridge.automation.exit_event.is_set())

    def test_bootstrap_only_authorizes_one_automatic_connect_and_complete_unlocks_without_actions(self):
        bridge = Bridge(5)
        install(bridge)
        self.assertTrue(callable(getattr(bridge.automation, 'start_bootstrap', None)))
        bridge.automation.start_bootstrap('target-job', 'bootstrap-token')
        self.assertTrue(bridge.status()['automation']['busy'])
        self.assertEqual(bridge.status()['automation']['launch_job_id'], 'target-job')
        with self.assertRaises(RuntimeError):
            self.cls(5, 'COM22', 'unused')
        owner = bridge.automation.connect_once(lambda: self.cls(5, 'COM22', 'unused'))
        owner.state.connected = True
        owner.state.authenticated = True
        owner._serial = type('USB', (), {'port': 'COM22'})()
        with self.assertRaises(RuntimeError):
            owner.command(self.p.RUN)
        with self.assertRaises(RuntimeError):
            bridge.automation.connect_once(lambda: self.cls(5, 'COM22', 'unused'))
        with self.assertRaises(ValueError):
            bridge.automation.prepare({'job_id': 'competing'})
        with self.assertRaises(ValueError):
            bridge.automation.complete({'job_id': 'target-job', 'token': 'wrong'})
        with self.assertRaises(ValueError):
            bridge.automation.complete({'job_id': 'target-job', 'token': 'bootstrap-token'})
        raw = bytearray(native_frame())
        raw[6], raw[7] = 1, 1
        struct.pack_into('<h', raw, 62, 0)
        struct.pack_into('<H', raw, 254, self.p.crc16(raw[:-2]))
        owner._receive(raw, self.p.decode(raw))
        result = bridge.automation.complete({'job_id': 'target-job', 'token': 'bootstrap-token'})
        self.assertTrue(result['completed'])
        self.assertFalse(bridge.status()['automation']['busy'])
        self.assertTrue(owner.queue.empty(), 'complete cannot send a control action')
        self.assertEqual(result, bridge.automation.complete({'job_id': 'target-job', 'token': 'bootstrap-token'}))
        owner.command(self.p.RUN)

    def test_new_bootstrap_accepts_real_unzeroed_idle_status_without_running_zero(self):
        bridge = Bridge(5)
        install(bridge)
        bridge.automation.start_bootstrap('target-new', 'bootstrap-token')
        owner = bridge.automation.connect_once(lambda: self.cls(5, 'COM22', 'unused'))
        owner.state.connected = owner.state.authenticated = True
        owner._serial = type('USB', (), {'port': 'COM22'})()
        raw = bytearray(native_frame())
        raw[6] = raw[7] = 0
        struct.pack_into('<I', raw, 16, 0)
        struct.pack_into('<h', raw, 62, 0)
        struct.pack_into('<H', raw, 254, self.p.crc16(raw[:-2]))
        owner._receive(bytes(raw), self.p.decode(raw))
        self.assertIsNone(owner.state.last_control)
        self.assertTrue(bridge.automation.complete({'job_id': 'target-new', 'token': 'bootstrap-token'})['completed'])
        self.assertTrue(owner.queue.empty())

    def test_http_prepare_and_close_respond_before_exit_and_reject_foreign_clients(self):
        import http.client
        import json

        server = self.bridge.serve(0)
        def post(path, body, local=True):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
            connection.request('POST', path, json.dumps(body) if local else None,
                {'X-J280-Local': '1'} if local else {})
            response = connection.getresponse()
            status, result = response.status, json.loads(response.read())
            connection.close()
            return status, result
        try:
            self.assertEqual(post('/automation/prepare', {'job_id': 'http'}, False)[0], 403)
            self.assertEqual(post('/automation/prepare', {'job_id': 'http', 'extra': True})[0], 409)
            outcome = {}
            worker = threading.Thread(target=lambda: outcome.update(value=post(
                '/automation/prepare', {'job_id': 'http'})), daemon=True)
            worker.start()
            deadline = time.monotonic()+1
            while self.owner.queue.empty() and time.monotonic() < deadline: time.sleep(.002)
            wire = self.send_stop()
            self.ack(wire)
            self.telemetry(2)
            worker.join(2)
            status, data = outcome['value']
            self.assertEqual(status, 200)
            self.assertFalse(self.bridge.automation.exit_event.is_set())
            status, data = post('/automation/close', {'job_id': 'http', 'token': data['token']})
            self.assertEqual(status, 200)
            self.assertTrue(data['closed'])
            self.assertTrue(self.bridge.automation.exit_event.wait(.2))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
