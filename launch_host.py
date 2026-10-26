"""Launch an unchanged delivered Host with its Python's bundled Tcl/Tk libraries."""

import argparse
import importlib.util
import os
from pathlib import Path
import runpy
import sys


def load_automation_connect(path):
    """Read a bounded, data-only handoff file before starting HTTP or hardware."""
    import json
    import re

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate automation JSON field')
            result[key] = value
        return result

    raw = Path(path).read_bytes()
    if len(raw) > 16384:
        raise ValueError('automation JSON exceeds 16384 bytes')
    data = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique)
    if not isinstance(data, dict) or set(data) != {'job_id', 'token', 'connection'}:
        raise ValueError('automation JSON requires exactly job_id, token and connection')
    if not isinstance(data['job_id'], str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', data['job_id']):
        raise ValueError('invalid automation job_id')
    if not isinstance(data['token'], str) or not re.fullmatch(r'[A-Za-z0-9._:-]{16,256}', data['token']):
        raise ValueError('invalid automation token')
    connection = data['connection']
    if not isinstance(connection, dict) or set(connection) != {'port', 'mode', 'ble_address', 'log_dir'}:
        raise ValueError('invalid automation connection fields')
    for key, value in connection.items():
        if not isinstance(value, str) or value != value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError('invalid automation connection ' + key)
    if not re.fullmatch(r'(?:COM[1-9][0-9]{0,4}|\\\\\.\\COM[1-9][0-9]{0,4})', connection['port'], re.I):
        raise ValueError('automation requires an explicit Windows USB COM port')
    if connection['mode'] not in ('USB', 'USB+BLE'):
        raise ValueError('automation mode must include USB')
    address = connection['ble_address']
    if connection['mode'] == 'USB' and address:
        raise ValueError('USB connection must not add a BLE address')
    if connection['mode'] == 'USB+BLE' and not re.fullmatch(r'[A-Za-z0-9:._-]{1,128}', address):
        raise ValueError('USB+BLE requires the explicitly selected BLE address')
    if not connection['log_dir'] or not Path(connection['log_dir']).is_absolute():
        raise ValueError('automation log_dir must be absolute')
    return data


def connect_fd2_headless(bridge, modules, connection):
    """The explicit headless entry uses the same native logger/quota policy."""
    directory = Path(connection['log_dir'])
    owner = modules['client'].SerialOwner(bridge.variant, connection['port'], directory,
        logger_factory=modules['trace_log'].TraceLogger,
        logger_options=dict(shared_roots=modules['log_policy'].shared_roots(directory)))
    if connection['mode'] == 'USB+BLE':
        owner.serial_factory = lambda unused_port, unused_baud: modules['dual_transport'].DuplexPort(
            connection['port'], connection['ble_address'], logger=owner.logger, event_sink=owner.trace)
    return owner.start()


def guarded_fd2_app_class(bridge, app_class):
    """Guard native GUI lifecycle before its button/protocol callbacks are bound."""
    class GuardedApp(app_class):
        def connect(self):
            if bridge.automation.status()['busy'] and not bridge.automation.connecting:
                return self.show_error(RuntimeError('SRAM交接期间禁止连接'))
            return super().connect()

        def disconnect(self):
            if bridge.automation.status()['busy']:
                return self.show_error(RuntimeError('SRAM交接期间等待停止确认'))
            return super().disconnect()

        def close(self):
            if bridge.automation.status()['busy'] and not bridge.automation.exit_event.is_set():
                try:
                    bridge.automation.request_user_close()
                except ValueError as error:
                    return self.show_error(error)
            return super().close()

    return GuardedApp


def queue_fd2_gui_lifecycle(bridge, window, application, connection=None):
    """Only the Tk main thread calls after, variable.set, connect and close."""
    if connection:
        def connect():
            if application.closing or bridge.automation.exit_event.is_set():
                return
            application.port.set(connection['port'])
            application.logdir.set(connection['log_dir'])
            # V1-V3 have no route-selector widgets, but native App.connect
            # supports the same variables and DuplexPort for every FD2 variant.
            for name in ('route_mode', 'ble_address'):
                if not hasattr(application, name):
                    import tkinter as tk

                    setattr(application, name, tk.StringVar(master=window))
            application.route_mode.set(connection['mode'])
            application.ble_address.set(connection['ble_address'])
            if bridge.automation.bootstrap:
                bridge.automation.connect_once(application.connect)
            else:
                application.connect()

        window.after(0, connect)

    def poll():
        if bridge.automation.exit_event.is_set():
            application.close()
        elif not application.closing:
            window.after(25, poll)

    window.after(25, poll)


def configure_tk_runtime(*, base_prefix=None, environ=None):
    import _tkinter

    environment = os.environ if environ is None else environ
    runtime = Path(sys.base_prefix if base_prefix is None else base_prefix) / "tcl"
    for variable, directory, entry in (
        ("TCL_LIBRARY", f"tcl{_tkinter.TCL_VERSION}", "init.tcl"),
        ("TK_LIBRARY", f"tk{_tkinter.TK_VERSION}", "tk.tcl"),
    ):
        library = runtime / directory
        if not environment.get(variable) and (library / entry).is_file():
            environment[variable] = str(library)


def fd2_main(variant, arguments):
    import json
    from host.fd2_bridge import Bridge, load_upstream, install, ROOT

    parser = argparse.ArgumentParser(
        description="FD2 V1-V5 Host, explicit connection only"
    )
    parser.add_argument("--port", type=int, default=8371, help="loopback HTTP port")
    parser.add_argument(
        "--offline-preview",
        action="store_true",
        help="blank detached Host; no hardware",
    )
    parser.add_argument(
        "--headless", action="store_true", help="HTTP only; disconnected without --automation-connect"
    )
    parser.add_argument(
        "--once", action="store_true", help="print status and exit (headless only)"
    )
    parser.add_argument(
        "--replay", type=Path, help="ForestFive.Physical.v1 ZIP, RX-only"
    )
    parser.add_argument("--replay-speed", type=float, default=1.0)
    parser.add_argument('--automation-connect', type=Path,
                        help='explicit SRAM handoff JSON; connect once using the original Host')
    options = parser.parse_args(arguments)
    if options.once and not options.headless:
        parser.error("--once requires --headless")
    connection_request = None
    if options.automation_connect:
        if options.replay or options.offline_preview or options.once:
            parser.error('--automation-connect cannot be combined with replay/offline-preview/once')
        try:
            connection_request = load_automation_connect(options.automation_connect)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
    bridge = Bridge(variant, replay=bool(options.replay))
    if connection_request:
        bridge.automation.start_bootstrap(connection_request['job_id'], connection_request['token'])
    server = bridge.serve(options.port)
    replay = None
    try:
        if options.replay:
            from host.fd2_replay import Replay

            replay = Replay(bridge, options.replay, speed=options.replay_speed).start()
        if options.once:
            if replay:
                replay.thread.join(timeout=2)
            print(json.dumps(bridge.status(), ensure_ascii=False))
            return
        print(
            f"FD2 V{variant}: http://127.0.0.1:{server.server_port} "
            + ('(explicit automation Connect queued)' if connection_request else '(disconnected until explicit Connect)'),
            flush=True,
        )
        if options.headless:
            if connection_request:
                modules = load_upstream()
                sys.path.insert(0, str(ROOT))
                for name, module in modules.items():
                    sys.modules[name] = module
                install(bridge, modules)
                bridge.automation.connect_once(lambda: connect_fd2_headless(
                    bridge, modules, connection_request['connection']))
            bridge.automation.exit_event.wait()
        else:
            configure_tk_runtime()
            import tkinter as tk

            if options.offline_preview or options.replay:
                # A separate detached display has no original Connect or hardware callbacks.
                from tkinter import ttk

                window = tk.Tk()
                window.title(
                    f"FD2 V{variant} — " + ("回放" if options.replay else "离线预览")
                )
                window.geometry("800x300")
                ttk.Label(
                    window,
                    text=(
                        "原始日志离线回放：硬件操作已禁用"
                        if options.replay
                        else "未连接：离线预览，无硬件访问"
                    ),
                    font=("Microsoft YaHei UI", 18),
                ).pack(pady=40)
                ttk.Label(
                    window, text=f"网页数据桥：http://127.0.0.1:{server.server_port}"
                ).pack()
                window.mainloop()
            else:
                modules = load_upstream()
                # This is a dedicated Host process. Keep generic upstream imports
                # isolated here; do not import the backend app module in this process.
                sys.path.insert(0, str(ROOT))
                for name, module in modules.items():
                    sys.modules[name] = module
                import importlib

                spec = importlib.util.spec_from_file_location(
                    "j280_fd2_upstream_app", ROOT / "app.py"
                )
                app = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(app)
                install(bridge, modules)
                app.enable_dpi_awareness()
                window = tk.Tk()
                application = guarded_fd2_app_class(bridge, app.App)(window, variant)
                queue_fd2_gui_lifecycle(bridge, window, application,
                    connection_request['connection'] if connection_request else None)
                window.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        if replay:
            replay.stop()
        owner = bridge.owner
        if owner and not owner.closed.is_set():
            # Interrupts/error exits still use the native close path. A failed
            # prepare intentionally blocks normal GUI disconnect/reconnect.
            if bridge.automation.lease:
                bridge.automation.lease['exit_requested'] = True
            owner.stop(wait=False)
            owner.closed.wait(5)
        server.shutdown()
        server.server_close()


def main():
    if len(sys.argv) > 1 and sys.argv[1].upper() in ("V1", "V2", "V3", "V4", "V5"):
        return fd2_main(int(sys.argv[1][1]), sys.argv[2:])
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("variant", choices=("gesture", "adaptive", "precise"))
    options, host_arguments = parser.parse_known_args()
    if (
        "--headless" not in host_arguments
        and "--help" not in host_arguments
        and "-h" not in host_arguments
    ):
        configure_tk_runtime()
    root = Path(__file__).resolve().parent
    host_root = (
        root
        / "host"
        / ("sp24/gesture" if options.variant == "precise" else options.variant)
    )
    entry = host_root / "host" / "swing_tune_host.py"
    sys.path.insert(0, str(entry.parent))
    sys.argv = [str(entry), *host_arguments]
    if options.variant == "precise":
        from host.sp24_bridge import install

        spec = importlib.util.spec_from_file_location("j280_sp24_host", entry)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        install(module)
        module.main()
    else:
        runpy.run_path(str(entry), run_name="__main__")


if __name__ == "__main__":
    main()
