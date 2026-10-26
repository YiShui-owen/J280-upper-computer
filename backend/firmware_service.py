"""Once-only SRAM jobs. Device access happens only after an explicit job/scan."""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
from pathlib import Path
import re
import threading
import time

from fd2_telemetry import IDENTITIES, identify

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VARIANTS = tuple(f'V{n}' for n in range(1, 6))
FINISHED = {'succeeded', 'failed', 'indeterminate'}


class FirmwareError(RuntimeError):
    def __init__(self, message, status_code=409):
        super().__init__(message)
        self.status_code = status_code


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def checked_usb_port(value, *, allow_empty=False):
    if not isinstance(value, str):
        raise FirmwareError('USB串口必须填写COM名称', 400)
    value = value.strip().upper()
    if allow_empty and not value:
        return ''
    if not re.fullmatch(r'COM[1-9][0-9]{0,4}', value):
        raise FirmwareError('请填写实际USB串口，例如COM8', 400)
    return value


def require_live(snapshot, target=None):
    """Check actual original Host authentication and its received identity."""
    if not isinstance(snapshot, dict):
        raise FirmwareError('Host状态格式无效')
    if snapshot.get('replay', {}).get('active'):
        raise FirmwareError('离线回放禁止下载固件')
    try:
        variant = identify(snapshot)
    except (ValueError, KeyError) as exc:
        raise FirmwareError('Host完整固件身份尚未核验') from exc
    age = snapshot.get('status_age_s')
    if (not snapshot.get('connected') or not snapshot.get('synced') or
            type(age) not in (int, float) or not math.isfinite(age) or not 0 <= age < .5):
        raise FirmwareError('Host未连接、未核验或状态超过500ms，请先恢复USB通信')
    if target is not None and target != variant:
        raise FirmwareError(f'下载后预期{target}，实际读回{variant}，未标记成功')
    if not snapshot.get('transport', {}).get('usb_connected'):
        raise FirmwareError('自动切换需要已核验的USB遥测连接')
    host = snapshot.get('host') or {}
    if host.get('error') or host.get('log_error'):
        raise FirmwareError('Host或日志存在错误，请先处理')
    actual = host.get('latest') or {}
    uid, schema, wire = IDENTITIES[int(variant[1:])]
    if (actual.get('firmware_id') != int(uid, 16) or actual.get('schema') != int(schema, 16) or
            actual.get('wire_version') != wire or actual.get('variant') != int(variant[1:])):
        raise FirmwareError('实际接收帧的完整身份与Host不一致')
    return variant


class FirmwareService:
    def __init__(self, store_dir=None, *, tools=None, host_factory=None,
                 commit_variant=None, car_quiesce=None, is_replay=None):
        self.store = Path(store_dir or PROJECT_ROOT / '.local' / 'firmware')
        self.tools = tools or importlib.import_module('gowin_programmer')
        self.host_factory = host_factory
        self.commit_variant = commit_variant or (lambda variant: None)
        self.car_quiesce = car_quiesce or (lambda: None)
        self.is_replay = is_replay or (lambda: False)
        self._lock = threading.RLock()
        self._admission = threading.Lock()
        self._worker = None
        self._active = None
        self._scanning = False
        self._epoch = 0
        self._jobs = {}
        self._latest = None
        self._journal_error = None
        self._load_jobs()

    def bind(self, *, host_factory, commit_variant, car_quiesce, is_replay):
        self.host_factory = host_factory
        self.commit_variant = commit_variant
        self.car_quiesce = car_quiesce
        self.is_replay = is_replay

    @property
    def epoch(self):
        with self._lock:
            return self._epoch

    @property
    def busy(self):
        with self._lock:
            return self._active is not None or self._scanning

    def _load_jobs(self):
        for file in sorted((self.store / 'jobs').glob('*.json')):
            try:
                job = json.loads(file.read_text(encoding='utf-8'))
                rid = job['request_id']
                if (not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', rid) or
                        job['target'] not in VARIANTS or job.get('state') not in FINISHED | {'queued', 'running'}):
                    raise ValueError('任务字段无效')
                if job['state'] not in FINISHED:
                    job.update(state='indeterminate', phase='indeterminate', updated_at=time.time(),
                               message='后台曾中断，下载结果未知；未自动重试，请核对设备')
                    atomic_json(file, job)
                self._jobs[rid] = job
                if not self._latest or job['updated_at'] >= self._jobs[self._latest]['updated_at']:
                    self._latest = rid
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self._journal_error = f'本机任务记录无法读取：{file.name}；{exc}'

    def _read_config(self):
        file = self.store / 'programming.json'
        if not file.exists():
            return dict(programmer_path='', cable=None, usb_port='')
        try:
            cfg = json.loads(file.read_text(encoding='utf-8'))
            if not isinstance(cfg, dict) or set(cfg) != {'programmer_path', 'cable', 'usb_port'}:
                raise ValueError('配置字段无效')
            return cfg
        except (OSError, ValueError) as exc:
            raise FirmwareError('本机烧录配置无法读取，请重新保存设置', 400) from exc

    def config(self):
        with self._lock:
            cfg = self._read_config()
        candidates = self.tools.discover_programmers()
        if not cfg['programmer_path'] and candidates:
            cfg['programmer_path'] = str(candidates[0])
        configured = False
        try:
            self.tools.resolve_programmer(cfg['programmer_path'])
            self.tools.validate_cable(cfg['cable'])
            checked_usb_port(cfg['usb_port'])
            configured = cfg['cable'] is not None
        except (ValueError, RuntimeError, TypeError, OSError):
            pass
        return dict(cfg, detected_paths=[str(p) for p in candidates], configured=bool(configured),
                    firmwares=list(VARIANTS))

    def _available(self):
        if self.busy:
            raise FirmwareError('固件切换或下载器扫描正在进行，请等待当前任务')
        if self.is_replay():
            raise FirmwareError('离线回放禁止固件下载和硬件扫描')
        if self._journal_error:
            raise FirmwareError(self._journal_error)

    def save_config(self, body):
        with self._admission:
            self._available()
            if not isinstance(body, dict) or set(body) != {'programmer_path', 'cable', 'usb_port'}:
                raise FirmwareError('配置仅接受Programmer路径、下载器和USB串口', 400)
            try:
                exe = self.tools.resolve_programmer(body['programmer_path'])
                cable = None if body['cable'] is None else self.tools.validate_cable(body['cable'])
                cfg = dict(programmer_path=str(exe), cable=cable,
                           usb_port=checked_usb_port(body['usb_port'], allow_empty=True))
            except (ValueError, RuntimeError, TypeError, OSError) as exc:
                if isinstance(exc, FirmwareError):
                    raise
                raise FirmwareError(str(exc), 400) from exc
            with self._lock:
                atomic_json(self.store / 'programming.json', cfg)
            return self.config()

    def run_control(self, action, function, *args):
        # STOP must not queue behind a slow normal request or an active download.
        if action in ('stop', 'estop', 'disconnect'):
            return function(*args)
        with self._admission:
            if self.busy:
                raise FirmwareError('正在切换固件，运动与连接设置暂不可用')
            return function(*args)

    def scan(self, programmer_path):
        with self._admission:
            self._available()
            if self.host_factory:
                current = self.host_factory().snapshot()
                if current and current.get('replay', {}).get('active'):
                    raise FirmwareError('离线回放禁止扫描下载器')
            exe = self.tools.resolve_programmer(programmer_path)
            with self._lock:
                self._scanning = True
                self._epoch += 1
        try:
            tool = self.tools.GowinProgrammer(exe)
            tool.probe()
            return dict(cables=tool.scan_cables())
        except (ValueError, RuntimeError, OSError) as exc:
            raise FirmwareError(str(exc), 400) from exc
        finally:
            with self._lock:
                self._scanning = False
                self._epoch += 1

    def _public(self, job):
        return copy.deepcopy({k: v for k, v in job.items() if not k.startswith('_')})

    def status(self):
        with self._lock:
            job = self._public(self._jobs[self._latest]) if self._latest else None
            return dict(busy=self.busy, phase='scanning_cables' if self._scanning else
                        job['phase'] if job else 'idle', job=job, error=self._journal_error)

    def summary(self):
        status = self.status()
        job = status['job'] or {}
        return dict(busy=status['busy'], phase=status['phase'], target=job.get('target'),
                    request_id=job.get('request_id'), epoch=self.epoch)

    def result(self, request_id):
        with self._lock:
            if request_id not in self._jobs:
                raise FirmwareError('找不到这个下载任务', 404)
            return self._public(self._jobs[request_id])

    def _persist(self, job):
        key = hashlib.sha256(job['request_id'].encode('utf-8')).hexdigest()
        atomic_json(self.store / 'jobs' / (key + '.json'), job)

    def start(self, *, request_id, target, motor_isolated=False):
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', request_id):
            raise FirmwareError('下载任务需要唯一request_id', 400)
        if target not in VARIANTS or type(motor_isolated) is not bool:
            raise FirmwareError('仅接受V1～V5及明确的本次电机隔离状态', 400)
        fingerprint = dict(target=target, motor_isolated=motor_isolated)
        with self._admission:
            with self._lock:
                previous = self._jobs.get(request_id)
                if previous:
                    if previous.get('_fingerprint') != fingerprint:
                        raise FirmwareError('相同任务ID不能更换版本或隔离条件')
                    return self._public(previous)
            self._available()
            cfg = self.config()
            if not cfg['configured']:
                raise FirmwareError('请先保存Programmer路径、下载器和USB串口设置', 400)
            if self.host_factory is None:
                raise FirmwareError('后台尚未完成Host切换服务初始化')
            now = time.time()
            job = dict(request_id=request_id, target=target, state='queued', phase='checking',
                       message='已接收一次下载请求，正在检查', created_at=now, updated_at=now,
                       log=[], _fingerprint=fingerprint)
            with self._lock:
                self._persist(job)  # A disk error must happen before any device operation.
                self._jobs[request_id] = job
                self._active = self._latest = request_id
                self._epoch += 1
                self._worker = threading.Thread(target=self._execute, args=(job, cfg, motor_isolated),
                                                name='J280SRAMJob', daemon=True)
                self._worker.start()
                return self._public(job)

    def _update(self, job, phase, message, state='running'):
        with self._lock:
            job.update(phase=phase, message=message, state=state, updated_at=time.time())
            job['log'] = (job['log'] + [message[:1000]])[-200:]
            self._persist(job)

    def _log(self, job, message):
        with self._lock:
            job['log'] = (job['log'] + [str(message)[:1000]])[-200:]
            job['updated_at'] = time.time()

    def _execute(self, job, cfg, isolated):
        wrote = False
        closed = False
        try:
            if self.is_replay():
                raise FirmwareError('离线回放禁止下载固件')
            self._update(job, 'checking', '正在核对位流、官方工具和当前连接')
            self.tools.load_firmware(job['target'])
            tool = self.tools.GowinProgrammer(self.tools.resolve_programmer(cfg['programmer_path']))
            tool.probe()  # --help only; no cable or JTAG access.
            gateway = self.host_factory()
            snapshot = gateway.snapshot()
            previous_session = None
            connection = dict(port=cfg['usb_port'], mode='USB')
            if snapshot is not None:
                require_live(snapshot)
                if not snapshot.get('automation', {}).get('supported'):
                    raise FirmwareError('请先用更新后的START_HOST重启配套Host，再使用自动切换')
                if snapshot['automation'].get('busy'):
                    raise FirmwareError('原Host仍处于交接锁定状态，请先关闭并重开Host')
            elif not isolated:
                raise FirmwareError('没有可核验的Host；首次下载请明确确认电机电源已断开')
            self.car_quiesce()
            if snapshot is not None:
                self._update(job, 'stopping', '正在由原Host停止输出并等待真实停止读回')
                prepared = gateway.prepare(job['request_id'])
                if prepared.get('prepared') is not True:
                    raise FirmwareError('原Host未确认排他停止，不执行下载')
                connection = prepared['connection']
                checked_usb_port(connection.get('port'))
                previous_session = prepared['session']
                self._update(job, 'closing', '停止已确认，正在释放原Host与串口')
                gateway.close(prepared)
                closed = True
            else:
                self._log(job, '本次已由操作人确认电机电源隔离；未推断设备已停止')
            self._update(job, 'programming', '正在核验JTAG目标并执行SRAM下载及校验')
            wrote = True
            result = tool.program(job['target'], cfg['cable'], emit=lambda line: self._log(job, line))
            if result.get('verified') is not True:
                raise FirmwareError('官方工具未确认SRAM校验成功')
            for line in result.get('log', []):
                self._log(job, line)
            self._update(job, 'reconnecting', 'SRAM校验通过，正在打开目标Host并恢复USB连接')
            actual = gateway.reconnect(job['target'], connection, job['request_id'],
                                       previous_session=previous_session)
            self._update(job, 'verifying', '正在核对新会话、目标固件身份和实时状态')
            require_live(actual, job['target'])
            if not actual.get('session') or actual['session'] == previous_session:
                raise FirmwareError('仍是原Host会话，未确认目标版本切换')
            self.commit_variant(job['target'])
            gateway.complete()  # Unlock the new Host only after the above real checks.
            self._update(job, 'completed', f'{job["target"]} SRAM下载、校验和USB身份核验完成', 'succeeded')
        except Exception as exc:
            unknown = wrote and (isinstance(exc, TimeoutError) or getattr(exc, 'indeterminate', False))
            state = 'indeterminate' if unknown else 'failed'
            message = str(exc) or type(exc).__name__
            if not wrote and not closed:
                message += '；未执行下载。若旧Host保持交接锁，请关闭并重开Host'
            elif wrote:
                message += '；未自动重试，请核对设备及下载日志'
            for line in getattr(exc, 'log', []):
                self._log(job, line)
            try:
                self._update(job, state, message, state)
            except OSError:
                with self._lock:
                    job.update(state='indeterminate', phase='indeterminate',
                               message='任务记录写入失败，结果未知；未自动重试', updated_at=time.time())
        finally:
            with self._lock:
                self._active = None
                self._epoch += 1

    def wait_idle(self, timeout):
        worker = self._worker
        if worker:
            worker.join(timeout)
        return not self.busy
