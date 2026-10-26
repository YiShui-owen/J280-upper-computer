"""受限的 Gowin SRAM 适配器；导入/路径发现不启动任何进程。

runner(argv, *, cwd, timeout, shell, creationflags) -> CompletedProcess。
仅显式 probe/scan/program 会运行工具；program 的唯一写操作是 --run 4。
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEVICE = 'GW2A-55C'
MAX_OUTPUT_BYTES = 256 * 1024
MAX_LOG_LINES = 400
MAX_LINE_LENGTH = 2000
FIRMWARE_HASHES = {
    'V1': 'b1f76dee49ae4aeaf11772944865bf94ecc8a444e085271fa3fc2638b2990971',
    'V2': '3cccd930c73e9b9c83ff5dbf845eadd8e68e93248c8a5946f5da466e915c7cc4',
    'V3': 'c3485c3e2abf0ccefbb4d4fad2b3a22b27e9464167585a02c386497d7771edd5',
    'V4': 'a64cee672cd34fa2a402f866a9fc248c8dae1de08a889b99b91b535484196e48',
    'V5': '066a086ea57d51e9da3e14eff8a4dfa94532a3190e737a3361f77bd69e99abc5',
}
FIRMWARE_SIZE = 18588969
_UID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:\-]{0,127}\Z')
_ERROR = re.compile(r'\b(?:error|fail|failed|failure|fatal|mismatch|abort|aborted|unsupported|exception|unable|cannot|timeout|denied)\b|timed out|失败|错误|不匹配', re.I)
_CABLE_TYPES = {'GWU2X': 0, 'FT2CH': 1, 'WINUSB': 5}


class ProgrammerError(RuntimeError):
    def __init__(self, message, *, log=None, indeterminate=False):
        super().__init__(message)
        self.log = list(log or [])[-MAX_LOG_LINES:]
        self.indeterminate = indeterminate


def resolve_programmer(value: str) -> Path:
    """接受exe、bin、Programmer目录或Gowin安装根，不解释命令行。"""
    if not isinstance(value, str) or not value.strip() or any(c in value for c in ('"', '\n', '\r', '\x00')):
        raise ProgrammerError('请选择 Programmer 的目录或 programmer_cli.exe 完整路径')
    path = Path(value.strip()).expanduser()
    candidates = [path] if path.name.lower() == 'programmer_cli.exe' else [
        path / 'programmer_cli.exe', path / 'bin' / 'programmer_cli.exe',
        path / 'Programmer' / 'bin' / 'programmer_cli.exe',
    ]
    matches = [p.resolve() for p in candidates if p.is_file() and p.name.lower() == 'programmer_cli.exe']
    if len(set(matches)) != 1:
        raise ProgrammerError('未找到唯一的 programmer_cli.exe；请指定准确目录（不能附加参数）')
    return matches[0]


def _discovery_roots():
    roots = []
    for name in ('GOWIN_PROGRAMMER_HOME', 'GOWIN_HOME', 'GOWIN_INSTALL_PATH'):
        if os.environ.get(name):
            roots.append(Path(os.environ[name]))
    roots.append(Path(os.environ.get('SystemDrive', 'C:') + '/') / 'Gowin')
    for name in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        if os.environ.get(name):
            base = Path(os.environ[name])
            roots.extend((base / 'Gowin', base / 'GOWIN'))
    found = shutil.which('programmer_cli.exe')
    if found:
        roots.append(Path(found))
    return roots


def discover_programmers() -> list[str]:
    found = set()
    for root in _discovery_roots():
        candidates = [root]
        if root.is_dir():
            candidates.extend(root.glob('Gowin*'))
            candidates.extend(root.glob('V*'))
        for candidate in candidates:
            try:
                found.add(str(resolve_programmer(str(candidate))))
            except (ProgrammerError, OSError):
                continue

    def version(value):
        match = re.search(r'(?:Gowin[_ -]?)?V(\d+(?:\.\d+)+)', value, re.I)
        return tuple(int(part) for part in match.group(1).split('.')) if match else ()
    return sorted(found, key=lambda value: (version(value), value.casefold()), reverse=True)


def validate_cable(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) - {'cable_index', 'channel', 'location', 'uid', 'label'}:
        raise ProgrammerError('下载器配置字段无效')
    index, channel = value.get('cable_index'), value.get('channel', 0)
    location, uid = value.get('location'), value.get('uid')
    if type(index) is not int or index not in (0, 1, 5):
        raise ProgrammerError('必须明确选择受支持的下载器类型（0、1或5）')
    if type(channel) is not int or not 0 <= channel <= 255:
        raise ProgrammerError('下载器 channel 必须是0～255整数')
    if location is not None and (type(location) is not int or not 0 <= location <= 0xffffffff):
        raise ProgrammerError('下载器 location 必须是无符号32位整数')
    if uid is not None and (not isinstance(uid, str) or not _UID.fullmatch(uid)):
        raise ProgrammerError('下载器 UID 格式无效')
    return {'cable_index': index, 'channel': channel, 'location': location, 'uid': uid}


def load_firmware(variant: str, root: Path = PROJECT_ROOT) -> dict:
    if not isinstance(variant, str) or variant not in FIRMWARE_HASHES:
        raise ProgrammerError('固件只允许 V1～V5')
    root = Path(root).resolve()
    relative = f'firmware/{variant}/J280_{variant}.fs'
    try:
        manifest = json.loads((root / 'firmware' / 'manifest.json').read_text(encoding='utf-8'))
        item = manifest['firmwares'][variant]
        if (manifest['format_version'] != 1 or manifest['device'] != DEVICE
                or item['path'] != relative or item['device'] != DEVICE
                or item['sha256'] != FIRMWARE_HASHES[variant] or item['size'] != FIRMWARE_SIZE):
            raise ValueError('manifest mismatch')
        path = (root / relative).resolve()
        if not path.is_relative_to(root / 'firmware') or not path.is_file() or path.stat().st_size != FIRMWARE_SIZE:
            raise ValueError('file size/path mismatch')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != FIRMWARE_HASHES[variant]:
            raise ValueError('SHA256 mismatch')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ProgrammerError(f'{variant} 位流原件或来源清单验证失败：{exc}') from exc
    return {'variant': variant, 'path': path, 'sha256': FIRMWARE_HASHES[variant], 'size': FIRMWARE_SIZE, 'device': DEVICE}


def _decode(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    for encoding in ('utf-8', 'gb18030'):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            pass
    return value.decode('utf-8', errors='replace')


def _run_process(argv, *, cwd, timeout, shell=False, creationflags=0):
    """仅终止本次 Popen；有界收集stdout/stderr，不启动shell或重试。"""
    process = subprocess.Popen(argv, cwd=cwd, shell=False, creationflags=creationflags,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = bytearray()
    overflow = threading.Event()

    def collect():
        while True:
            chunk = process.stdout.read(4096)
            if not chunk:
                break
            if len(output) + len(chunk) > MAX_OUTPUT_BYTES:
                overflow.set()
                process.kill()
                break
            output.extend(chunk)
    reader = threading.Thread(target=collect, daemon=True, name='gowin-output')
    reader.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        reader.join(timeout=2)
        exc.output = bytes(output)
        raise
    finally:
        reader.join(timeout=2)
        if not reader.is_alive():
            process.stdout.close()
    if reader.is_alive() or overflow.is_set():
        raise ProgrammerError('Programmer 输出超限或输出管道未关闭，结果未知', log=_log(_decode(output)))
    return subprocess.CompletedProcess(argv, process.returncode, _decode(output), '')


def _log(output):
    return [line[:MAX_LINE_LENGTH] for line in output.splitlines() if line.strip()][-MAX_LOG_LINES:]


def _is_banner(line):
    return bool(re.fullmatch(r'(?:GOWIN (?:Semiconductor|Programmer)[^\n]*|Copyright[^\n]*|Version\s+V?[\d.]+[^\n]*|[-=]+)', line, re.I))


def _is_timing(line):
    return bool(re.fullmatch(r'Cost\s+\d+(?:\.\d+)?\s+second\(s\)', line))


def _target_cable(line, selected):
    match = re.fullmatch(r'Target Cable:\s*Gowin USB Cable\s*\((GWU2X|FT2CH|WINUSB)\)/(\d+)/(\d+|None)/(null|[A-Za-z0-9_.:\-]+)@\d+(?:\.\d+)?[ \t]*MHz', line)
    if not match:
        return False
    kind, channel, location, uid = match.groups()
    actual = {'cable_index': _CABLE_TYPES[kind], 'channel': int(channel),
              'location': None if location == 'None' else int(location), 'uid': None if uid == 'null' else uid}
    return all(selected[k] is None or actual[k] == selected[k] for k in selected)


class GowinProgrammer:
    def __init__(self, executable: Path, *, runner=None):
        self.executable = resolve_programmer(str(executable))
        self.runner = runner or _run_process

    def _execute(self, args, *, timeout=30, emit=None):
        argv = [str(self.executable), *args]
        try:
            result = self.runner(argv, cwd=str(self.executable.parent), timeout=timeout,
                                 shell=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0)
        except subprocess.TimeoutExpired as exc:
            log = _log(_decode(exc.output) + '\n' + _decode(exc.stderr))
            if emit:
                for line in log:
                    emit(line)
            raise ProgrammerError('Programmer 超时，本次进程已终止；结果未知，未重试', log=log) from exc
        except OSError as exc:
            raise ProgrammerError(f'无法启动 Programmer：{exc}') from exc
        output = _decode(result.stdout) + '\n' + _decode(result.stderr)
        log = _log(output)
        if emit:
            for line in log:
                emit(line)
        if len(output.encode('utf-8')) > MAX_OUTPUT_BYTES:
            raise ProgrammerError('Programmer 输出超限，结果未知', log=log)
        if result.returncode != 0 or _ERROR.search(output):
            raise ProgrammerError(f'Programmer 失败（退出码 {result.returncode}）：' + (log[-1] if log else '无输出'), log=log)
        return output, log

    def probe(self) -> dict:
        output, log = self._execute(['--help'])
        if (not re.search(r'(?<![A-Z0-9-])GW2A-55C(?![A-Z0-9-])', output)
                or not re.search(r'(?m)^\s*4\s*[:=.)-]\s*SRAM Program and Verify\s*;?\s*$', output, re.I)
                or any(option not in output for option in ('--cable-index', '--channel', '--location', '--uid', '--scan', '--scan-cables', '--fsFile', '--run'))):
            raise ProgrammerError('Programmer 帮助未确认 GW2A-55C 与操作4 SRAM Program and Verify', log=log)
        return {'supported': True, 'device': DEVICE, 'operation': 4, 'log': log}

    def scan_cables(self) -> list[dict]:
        output, log = self._execute(['--scan-cables'])
        cables = []
        # SUG502E 4.2 的完整路径及其 location/SN 说明；不从自由文本猜索引。
        pattern = re.compile(r'(?:Cable found:\s*)?Gowin USB Cable\s*\((GWU2X|FT2CH|WINUSB)\)/(\d+)/(\d+)/([A-Za-z0-9_.:\-]+)\s*\(USB location\s*:\s*(\d+)\)(?:\s*\(SN\s*:\s*([A-Za-z0-9_.:\-]+)\))?', re.I)
        no_cables = False
        for raw in output.splitlines():
            line = raw.strip()
            if not line or _is_banner(line) or _is_timing(line) or line.lower() in ('scan cables:', 'usb cables:', 'cable list:'):
                continue
            match = pattern.fullmatch(line)
            if not match:
                if line.lower() in ('no cable found.', 'no cables found.', 'no cable found', 'no cables found') and not cables:
                    no_cables = True
                    continue
                raise ProgrammerError('下载器扫描格式无法明确识别；未选择默认缆线，请保留日志核对驱动/CLI版本', log=log)
            kind, channel, location, uid, described_location, described_uid = match.groups()
            if no_cables or location != described_location or (described_uid is not None and uid != described_uid):
                raise ProgrammerError('下载器扫描身份字段不一致', log=log)
            cable = validate_cable({'cable_index': _CABLE_TYPES[kind.upper()], 'channel': int(channel), 'location': int(location), 'uid': None if uid.lower() == 'null' else uid})
            if any(all(cable[k] == other[k] for k in cable) for other in cables):
                raise ProgrammerError('下载器扫描出现重复身份，无法唯一选择', log=log)
            cables.append(dict(cable, label=line))
        if not cables and not no_cables:
            raise ProgrammerError('下载器扫描无输出，结果未知', log=log)
        return cables

    def _cable_args(self, cable):
        cable = validate_cable(cable)
        args = ['--cable-index', str(cable['cable_index']), '--channel', str(cable['channel'])]
        # CLI声明UID会忽略location/channel；只使用一个身份选择器，避免优先级矛盾。
        if cable['uid'] is not None:
            args.extend(['--uid', cable['uid']])
        elif cable['location'] is not None:
            args.extend(['--location', str(cable['location'])])
        return args

    def scan_device(self, cable: dict) -> dict:
        cable = validate_cable(cable)
        if cable['uid'] is None and cable['location'] is None:
            raise ProgrammerError('JTAG扫描需要明确的下载器 UID 或 location，禁止默认选择物理缆线')
        output, log = self._execute(['--scan', *self._cable_args(cable)])
        records = []
        fields, count, target_seen = None, None, False
        for raw in output.splitlines():
            line = re.sub(r'^Info:\s*', '', raw.strip(), flags=re.I)
            if not line or _is_banner(line) or _is_timing(line) or line.lower() in ('scan devices:', 'device list:', 'scan completed.'):
                continue
            if line == 'Scanning!':
                continue
            if line.startswith('Target Cable:'):
                if target_seen or not _target_cable(line, cable):
                    raise ProgrammerError('JTAG扫描实际下载器与明确选择不符或无法核验', log=log)
                target_seen = True
                continue
            if line == 'Device Info:':
                if fields is not None:
                    if set(fields) != {'Family', 'Name', 'ID'}:
                        raise ProgrammerError('JTAG设备信息不完整', log=log)
                    records.append(fields['Name'])
                fields = {}
                continue
            match = re.fullmatch(r'(Family|Name|ID):\s*(.+)', line)
            if match:
                key, value = match.groups()
                if fields is None or key in fields or (key == 'ID' and not re.fullmatch(r'0x[0-9A-Fa-f]{8}', value)):
                    raise ProgrammerError('JTAG设备信息重复或无效', log=log)
                fields[key] = value.strip()
                continue
            found = re.fullmatch(r'(\d+) device\(s\) found!', line)
            if found:
                if count is not None:
                    raise ProgrammerError('JTAG设备计数重复', log=log)
                count = int(found.group(1))
                continue
            raise ProgrammerError('JTAG扫描输出无法确认完整单设备链；禁止下载', log=log)
        if fields is not None:
            if set(fields) != {'Family', 'Name', 'ID'}:
                raise ProgrammerError('JTAG设备信息不完整', log=log)
            records.append(fields['Name'])
        if not target_seen or count != 1 or count != len(records):
            raise ProgrammerError('JTAG扫描未提供一致的目标下载器与完整设备计数', log=log)
        if any(re.search(r'\(One of them\)', name, re.I) for name in records):
            raise ProgrammerError('JTAG扫描型号不唯一：' + repr(records) +
                                  '；请核对芯片丝印，本项目仅允许明确的 GW2A-55C，未执行下载', log=log)
        if records != [DEVICE]:
            raise ProgrammerError('JTAG必须且只能有一个 GW2A-55C；实际：' + repr(records), log=log)
        return {'device': DEVICE, 'count': 1, 'cable': validate_cable(cable), 'log': log}

    def program(self, variant: str, cable: dict, emit=None) -> dict:
        firmware = load_firmware(variant)
        selected = validate_cable(cable)
        cables = self.scan_cables()
        matches = [c for c in cables if all(selected[k] is None or c[k] == selected[k] for k in selected)]
        if len(matches) != 1:
            raise ProgrammerError('配置下载器未唯一匹配当前扫描结果；禁止下载')
        selected = validate_cable(matches[0])
        selector = 'uid' if selected['uid'] is not None else 'location'
        effective = [c for c in cables if c['cable_index'] == selected['cable_index']
                     and (selected['cable_index'] != 1 or c[selector] == selected[selector])]
        if len(effective) != 1:
            raise ProgrammerError('CLI身份选择器会忽略channel且匹配多个端口；禁止猜测默认目标')
        self.scan_device(selected)
        if emit:
            emit('已核验原位流、下载器和单设备链；开始 SRAM Program and Verify（操作4）')
        try:
            output, log = self._execute(['--device', DEVICE, '--run', '4', '--fsFile', str(firmware['path']), *self._cable_args(selected)], timeout=180, emit=emit)
        except ProgrammerError as exc:
            if isinstance(exc.__cause__, subprocess.TimeoutExpired) or '输出' in str(exc):
                exc.indeterminate = True
            raise
        success = verified = combined = False
        seen = set()
        for raw in output.splitlines():
            line = re.sub(r'^Info:\s*', '', raw.strip(), flags=re.I)
            if not line or _is_banner(line) or _is_timing(line):
                continue
            if line.startswith(('Operation ', 'Target Device:', 'Target Cable:')):
                kind = line.split(':', 1)[0] if ':' in line else 'Operation'
                valid = (bool(re.fullmatch(r'Operation "SRAM Program and Verify" for device#1\.{3}', line))
                         if kind == 'Operation' else
                         bool(re.fullmatch(r'Target Device:\s*GW2A-55C\s*\(0x[0-9A-Fa-f]{8}\)', line))
                         if kind == 'Target Device' else _target_cable(line, selected))
                if not valid or kind in seen:
                    raise ProgrammerError('工具报告的操作、目标或下载器无法唯一核验，结果未知', log=log, indeterminate=True)
                seen.add(kind)
                continue
            if re.fullmatch(r'Program\s+(?:success|successful|successfully|succeeded|Finished)\s*[.!]?', line, re.I):
                success = True
            elif re.fullmatch(r'Verify\s+(?:success|successful|successfully|succeeded)\s*[.!]?', line, re.I):
                verified = True
            elif re.fullmatch(r'SRAM Program and Verify\s+(?:success|successful|successfully|succeeded)\s*[.!]?', line, re.I):
                combined = True
            elif line in ('SRAM Program and Verify', 'Finished.', 'Finished!'):
                pass  # A title or trailer is never verification evidence.
            elif re.fullmatch(r'(?:[\[\]=#>.\-\s]*)(?:100|[0-9]{1,2})%[\[\]=#>.\-\s]*', line):
                pass
            else:
                raise ProgrammerError('Programmer含未识别或矛盾的编程输出；结果未知，未重试',
                                      log=log, indeterminate=True)
        if not (combined or (success and verified)):
            raise ProgrammerError('Programmer 未明确报告 SRAM 编程及校验成功；结果未知，未重试', log=log, indeterminate=True)
        return {'variant': variant, 'device': DEVICE, 'verified': True, 'log': log}
