"""Exclusive, explicit SRAM handoff around the unchanged FD2 owner."""

from pathlib import Path
import re
import secrets
import threading
import time


class AutomationError(ValueError):
    def __init__(self, message, lease=None):
        super().__init__(message)
        self.response = dict(error=message)
        if lease:
            self.response.update(job_id=lease['job_id'], token=lease['token'], prepared=False)


class Automation:
    def __init__(self, bridge):
        self.bridge = bridge
        self.exit_event = threading.Event()
        self.lease = None
        self.history = {}
        self.launch_job_id = None
        self.bootstrap = None
        self.connecting = False

    def status(self):
        with self.bridge.lock:
            active = self.active_record()
            return dict(supported=True, busy=active is not None,
                        job_id=active['job_id'] if active else None,
                        launch_job_id=self.launch_job_id)

    def active_record(self):
        return self.lease or (self.bootstrap if self.bootstrap and self.bootstrap['active'] else None)

    def start_bootstrap(self, job_id, token):
        self._body(dict(job_id=job_id, token=token), token=True)
        with self.bridge.dispatch_lock, self.bridge.lock:
            if self.active_record() or self.bridge.owner is not None:
                raise AutomationError('Bootstrap must precede any owner')
            self.launch_job_id = job_id
            self.bootstrap = dict(job_id=job_id, token=token, owner=None, session=None,
                                  active=True, consumed=False, result=None)

    def connect_once(self, callback):
        with self.bridge.dispatch_lock:
            with self.bridge.lock:
                if not self.bootstrap or not self.bootstrap['active'] or self.bootstrap['consumed']:
                    raise RuntimeError('Automatic connection is unavailable or already consumed')
                self.connecting = True
            try:
                return callback()
            finally:
                with self.bridge.lock:
                    self.connecting = False
                    self.bootstrap['consumed'] = True

    def attached(self, owner):
        if self.bootstrap and self.bootstrap['active']:
            self.bootstrap.update(owner=owner, session=self.bridge.session, consumed=True)

    def complete(self, body):
        job_id = self._body(body, token=True)
        with self.bridge.dispatch_lock:
            with self.bridge.lock:
                record = self.bootstrap
                if (not record or record['job_id'] != job_id
                        or not secrets.compare_digest(record['token'], body['token'])):
                    raise AutomationError('Invalid bootstrap lease')
                if record['result']:
                    return dict(record['result'])
                self._current(record)
                if record['owner'] is None:
                    raise AutomationError('Automatic owner has not connected')
            snapshot = self._snapshot(record)
            if not self._stopped(snapshot.get('latest') or {}):
                raise AutomationError('New Host must report actual stopped output before unlock')
            self._connection(record['owner'])
            with self.bridge.lock:
                self._current(record)
                record['active'] = False
                record['result'] = dict(job_id=job_id, session=record['session'], completed=True)
                return dict(record['result'])

    @staticmethod
    def _body(body, token=False):
        fields = {'job_id', 'token'} if token else {'job_id'}
        if not isinstance(body, dict) or set(body) != fields:
            raise AutomationError('Expected exactly ' + ', '.join(sorted(fields)))
        if not isinstance(body['job_id'], str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', body['job_id']):
            raise AutomationError('Invalid job_id')
        if token and (not isinstance(body['token'], str) or not body['token']):
            raise AutomationError('Invalid lease token')
        return body['job_id']

    def _current(self, lease):
        if ((self.lease is not lease and self.bootstrap is not lease)
                or self.bridge.owner is not lease['owner'] or self.bridge.session != lease['session']):
            raise AutomationError('Host session changed; handoff forbidden', lease)

    def ensure_new_owner(self):
        if self.lease:
            raise RuntimeError('SRAM handoff owns this Host; new Connect is blocked')
        if self.bootstrap and self.bootstrap['active'] and not (
                self.connecting and not self.bootstrap['consumed'] and self.bridge.owner is None):
            raise RuntimeError('Only the one trusted bootstrap Connect is allowed')

    def ensure_start(self, owner):
        if self.lease:
            raise RuntimeError('SRAM handoff blocks owner startup')
        if self.bootstrap and self.bootstrap['active'] and not (
                self.connecting and owner is self.bootstrap['owner']):
            raise RuntimeError('Only the trusted bootstrap owner may start')
        if owner is not self.bridge.owner:
            raise RuntimeError('Superseded Host owner cannot start')

    def ensure_stop(self, owner):
        lease = self.lease
        if lease and owner is lease['owner'] and not (lease['shutdown_authorized'] or lease.get('exit_requested')):
            raise RuntimeError('SRAM handoff is still confirming actual stop')

    def ensure_opcode(self, owner, opcode):
        from host.fd2_bridge import load_upstream

        lease = self.active_record()
        if lease and opcode not in load_upstream()['protocol'].SAFE:
            raise RuntimeError('SRAM handoff blocks non-STOP/ESTOP control writes')
        if lease and owner is not lease['owner']:
            raise RuntimeError('SRAM handoff rejects a different owner')

    def suppress_shutdown_stop(self, owner, opcode, internal):
        from host.fd2_bridge import load_upstream

        lease = self.lease
        return bool(lease and owner is lease['owner'] and lease['shutdown_authorized']
                    and internal and opcode == load_upstream()['protocol'].STOP
                    and owner.stop_event.is_set())

    def trace(self, event, fields):
        lease = self.lease
        if lease and event == 'write_requested' and fields.get('source') == 'WEB/' + lease['request_id']:
            # Time of the actual native wire request, never the HTTP intent/ACK.
            if lease['written_at'] is None:
                lease['written_at'] = time.monotonic()
                lease['wire_id'] = fields.get('request_id')
                lease['written_measurement'] = self._measurement(lease['owner'])
        if (lease and event == 'ack' and fields.get('matched')
                and fields.get('request_id') == lease.get('wire_id')
                and fields.get('status') == 0):
            lease['ack_measurement'] = self._measurement(lease['owner'])

    @staticmethod
    def _measurement(owner):
        # Native RX replaces this immutable decoded-frame reference. This hook
        # is under bridge.lock, so do not invert the order by taking state.lock.
        actual = owner.state.latest or {}
        return actual.get('sequence'), actual.get('board_ms')

    @staticmethod
    def _advanced(actual, baseline):
        if not baseline:
            return False
        return all(type(previous) is int and type(actual.get(key)) is int and
                   0 < (actual[key] - previous) & 0xffffffff < 0x80000000
                   for key, previous in zip(('sequence', 'board_ms'), baseline))

    def _snapshot(self, lease):
        with self.bridge.lock:
            self._current(lease)
        snapshot = lease['owner'].state.snapshot()
        now = time.monotonic()
        control = (snapshot.get('latest') or {}).get('coherent') is True
        if (not snapshot['connected'] or not snapshot['authenticated']
                or snapshot.get('error') or snapshot.get('log_error')
                or not snapshot.get('latest_rx')
                or not 0 <= now - snapshot['latest_rx'] < .5
                or (control and (not snapshot.get('last_control_rx')
                    or not 0 <= now - snapshot['last_control_rx'] < .5))):
            raise AutomationError('A verified live Host, healthy logging and fresh actual status are required', lease)
        return snapshot

    @staticmethod
    def _stopped(actual):
        flags = actual.get('flags', 6)
        stopped = (actual.get('mode') in (0, 1) and actual.get('fault') == 0
                   and actual.get('actual_applied_q15') == 0 and flags & 6 == 0)
        # Before ZERO the native RTL publishes 10Hz non-control T frames with
        # live actuator output/permissions and epoch=0. They are valid stop
        # evidence, but must never become control/plot samples.
        return bool(stopped and (actual.get('coherent') is True or
                    (actual.get('coherent') is False and actual.get('mode') == 0
                     and flags & 16 == 0 and actual.get('control_epoch') == 0)))

    def request_user_close(self):
        with self.bridge.dispatch_lock, self.bridge.lock:
            if self.lease:
                if not self.lease['done'].is_set():
                    raise AutomationError('SRAM交接期间请等待关闭确认')
                self.lease['exit_requested'] = True
            self.exit_event.set()

    def _connection(self, owner):
        serial = getattr(owner, '_serial', None)
        usb = getattr(serial, 'usb', None) if hasattr(serial, 'usb') else serial
        if usb is None or 0 in getattr(serial, 'route_errors', {}):
            raise AutomationError('A live USB route is required; BLE-only cannot hand off')
        port = getattr(usb, 'port', None) or owner.port
        if not isinstance(port, str) or not port.strip():
            raise AutomationError('The actual USB port is missing')
        ble = getattr(serial, 'ble', None)
        address = getattr(ble, 'address', '') if ble is not None else ''
        if ble is not None and (not isinstance(address, str) or not address.strip()):
            raise AutomationError('The actual BLE address is unavailable')
        return dict(port=port.strip(), mode='USB+BLE' if ble is not None else 'USB',
                    ble_address=address, log_dir=str(Path(owner.log_directory).resolve()))

    def prepare(self, body, *, timeout=3.0, close_timeout=5.0):
        job_id = self._body(body)
        with self.bridge.dispatch_lock, self.bridge.lock:
            previous = self.history.get(job_id)
            if previous:
                lease = previous
                first = False
            else:
                if self.active_record():
                    raise AutomationError('Another SRAM handoff is active')
                # Bound remembered IDs without ever forgetting the active lease.
                if len(self.history) >= 128:
                    raise AutomationError('Host handoff history is full; restart Host')
                lease = dict(job_id=job_id, token=secrets.token_urlsafe(32),
                    owner=self.bridge.owner, session=self.bridge.session,
                    request_id='automation-' + secrets.token_hex(16), written_at=None,
                    shutdown_authorized=False, done=threading.Event(), result=None, error=None)
                self.lease = lease
                self.history[job_id] = lease
                first = True
        if not first:
            if not lease['done'].wait(timeout + close_timeout + .5):
                raise AutomationError('The original prepare is still in progress; never retried', lease)
            if lease['error']:
                raise AutomationError(lease['error'], lease)
            return dict(lease['result'])
        try:
            if self.bridge.replay['active'] or lease['owner'] is None:
                raise AutomationError('Replay or disconnected Host cannot hand off', lease)
            owner = lease['owner']
            if owner.stop_event.is_set() or owner.closed.is_set():
                raise AutomationError('Owner is already closing', lease)
            self._snapshot(lease)
            connection = self._connection(owner)
            self.bridge.command(dict(request_id=lease['request_id'], action='stop'))
            deadline = time.monotonic() + timeout
            while True:
                snapshot = self._snapshot(lease)
                with self.bridge.lock:
                    self._current(lease)
                    request = dict(self.bridge.requests[lease['request_id']])
                    written = lease['written_at']
                if request['state'] in ('rejected', 'indeterminate'):
                    raise AutomationError('STOP was rejected or its physical result is unknown', lease)
                actual = snapshot.get('latest') or {}
                ack_epoch = request.get('ack_control_epoch')
                actual_epoch = actual.get('control_epoch')
                newer_epoch = (type(ack_epoch) is int and type(actual_epoch) is int
                    and 0 < (actual_epoch - ack_epoch) & 0xffffffff < 0x80000000)
                newer_status = (actual.get('coherent') is False
                    and self._advanced(actual, lease.get('written_measurement'))
                    and self._advanced(actual, lease.get('ack_measurement')))
                stopped = (written is not None and snapshot['latest_rx'] > written
                    and snapshot['latest_rx'] > request.get('ack_received_mono', float('inf'))
                    and ((actual.get('coherent') is True and newer_epoch) or newer_status)
                    and self._stopped(actual))
                if request['state'] == 'accepted' and stopped:
                    break
                if time.monotonic() >= deadline:
                    raise AutomationError('STOP ACK and a newer independent zero-output stopped control were not both confirmed; never retried', lease)
                lease['done'].wait(.005)
            with self.bridge.dispatch_lock:
                with self.bridge.lock:
                    self._current(lease)
                    lease['shutdown_authorized'] = True
                # Native stop is nonblocking. Native _run still closes its
                # transports/logger/mutex; only its redundant final STOP is skipped.
                owner.stop(wait=False)
            if not owner.closed.wait(close_timeout):
                raise AutomationError('Native owner did not confirm closed', lease)
            closed_state = owner.state.snapshot()
            if closed_state.get('log_error') or closed_state.get('error'):
                raise AutomationError('Native owner closed with a log/transport error', lease)
            with self.bridge.dispatch_lock, self.bridge.lock:
                self._current(lease)
                lease['result'] = dict(job_id=job_id, token=lease['token'], prepared=True,
                    connection=connection, session=lease['session'])
            return dict(lease['result'])
        except Exception as exc:
            with self.bridge.lock:
                lease['error'] = str(exc)
            raise AutomationError(str(exc), lease) from exc
        finally:
            lease['done'].set()

    def _authenticate(self, body):
        job_id = self._body(body, token=True)
        lease = self.lease
        if not lease or job_id != lease['job_id'] or not secrets.compare_digest(body['token'], lease['token']):
            raise AutomationError('Invalid active handoff lease')
        return lease

    def release(self, body):
        with self.bridge.dispatch_lock, self.bridge.lock:
            lease = self._authenticate(body)
            owner = lease['owner']
            if not lease['done'].is_set() or lease['shutdown_authorized'] or (owner and owner.closed.is_set()):
                raise AutomationError('Only a failed prepare with an open owner can be released', lease)
            self.lease = None
            return dict(job_id=lease['job_id'], released=True)

    def close(self, body):
        with self.bridge.dispatch_lock, self.bridge.lock:
            lease = self._authenticate(body)
            self._current(lease)
            if not lease['result'] or not lease['owner'].closed.is_set():
                raise AutomationError('Prepare must close the native owner first', lease)
            return dict(job_id=lease['job_id'], closed=True)

    def finish_close(self):
        """Called only after the successful HTTP response has been flushed."""
        self.exit_event.set()
