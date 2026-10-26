"""Graceful FD2 handoff and explicit launches; never kills unrelated processes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import uuid

from firmware_service import FirmwareError, PROJECT_ROOT, VARIANTS, atomic_json, checked_usb_port, require_live
from host_bridge import BridgeError, HostClient


class ManagedHostGateway:
    def __init__(self, port=8371, *, root=PROJECT_ROOT, store=None, client_factory=HostClient,
                 launcher=subprocess.Popen, listening=None, timeout=25):
        self.port = port
        self.root = Path(root)
        self.store = Path(store or self.root / '.local' / 'firmware')
        self.client_factory = client_factory
        self.launcher = launcher
        self.listening = listening or self._listening
        self.timeout = timeout
        self.process = None
        self._context = None
        self._context_file = None

    def _client(self, timeout=1):
        return self.client_factory(port=self.port, timeout=timeout)

    def _listening(self):
        with socket.socket() as sock:
            sock.settimeout(.3)
            return sock.connect_ex(('127.0.0.1', self.port)) == 0

    def snapshot(self):
        try:
            return self._client().status()
        except BridgeError as exc:
            if self.listening():
                raise FirmwareError('桥端口已被占用，但无法核验当前Host；请检查原Host') from exc
            return None

    def prepare(self, request_id):
        try:
            return self._client(18).exchange('/automation/prepare', dict(job_id=request_id))
        except BridgeError as exc:
            raise FirmwareError('原Host排他准备失败：' + str(exc)) from exc

    def close(self, prepared):
        body = dict(job_id=prepared['job_id'], token=prepared['token'])
        error = None
        try:
            self._client(3).exchange('/automation/close', body)
        except BridgeError as exc:
            error = exc  # Do not repeat a close after losing the response.
        deadline = time.monotonic() + min(self.timeout, 12)
        while time.monotonic() < deadline:
            if not self.listening():
                return
            time.sleep(.1)
        raise FirmwareError('原Host尚未释放桥端口，未继续下载' + (f'：{error}' if error else ''))

    def reconnect(self, target, connection, request_id, previous_session=None):
        if target not in VARIANTS:
            raise FirmwareError('目标Host版本无效')
        checked_usb_port(connection.get('port'))
        connection = dict(connection)
        connection.setdefault('ble_address', '')
        if not connection.get('log_dir'):
            connection['log_dir'] = str((self.store / 'host-sessions').resolve())
        if self.listening():
            raise FirmwareError('桥端口已被其他进程占用，未启动第二个Host')
        runtime = self.root / 'host/fd2/upstream/runtime/python.exe'
        launcher = self.root / 'launch_host.py'
        if not runtime.is_file() or not launcher.is_file():
            raise FirmwareError('配套Host运行时或启动器缺失，请恢复完整工程')
        key = hashlib.sha256(request_id.encode('utf-8')).hexdigest()
        self._context = dict(job_id=request_id, token=uuid.uuid4().hex, connection=connection)
        self._context_file = self.store / 'connections' / (key + '.json')
        atomic_json(self._context_file, self._context)
        log = self.store / 'connections' / (key + '.host.log')
        argv = [str(runtime), '-B', '-X', 'utf8', str(launcher), target, '--port', str(self.port),
                '--automation-connect', str(self._context_file)]
        flags = (getattr(subprocess, 'CREATE_NO_WINDOW', 0) |
                 getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)) if os.name == 'nt' else 0
        try:
            with log.open('ab') as output:
                self.process = self.launcher(argv, cwd=str(self.root), stdin=subprocess.DEVNULL,
                                             stdout=output, stderr=subprocess.STDOUT,
                                             shell=False, creationflags=flags)
            deadline = time.monotonic() + self.timeout
            last_error = '等待新Host'
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise FirmwareError('目标Host启动后退出，请查看本机Host日志')
                try:
                    actual = self._client().status()
                    if actual.get('automation', {}).get('launch_job_id') != request_id:
                        raise FirmwareError('桥端口上的Host不属于本次下载任务')
                    require_live(actual, target)
                    if not actual.get('session') or actual['session'] == previous_session:
                        raise FirmwareError('目标Host尚未建立新的通信会话')
                    return actual
                except (BridgeError, FirmwareError) as exc:
                    last_error = str(exc)
                time.sleep(.1)
            raise FirmwareError('目标Host连接或身份核验未完成：' + last_error)
        except Exception:
            # This is only the process started above; its bootstrap gate still
            # forbids motion. An unrelated Host is never terminated.
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            raise

    def complete(self):
        if not self._context:
            raise FirmwareError('没有本次目标Host的释放凭据')
        body = {key: self._context[key] for key in ('job_id', 'token')}
        self._client(3).exchange('/automation/complete', body)
        state = self._client().status()
        if (state.get('automation', {}).get('launch_job_id') != body['job_id'] or
                state.get('automation', {}).get('busy') is not False):
            raise FirmwareError('目标Host尚未确认解除本次控制锁')
        if self._context_file:
            self._context_file.unlink(missing_ok=True)
