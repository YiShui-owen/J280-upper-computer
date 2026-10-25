"""Launch an unchanged delivered Host with its Python's bundled Tcl/Tk libraries."""

import argparse
import importlib.util
import os
from pathlib import Path
import runpy
import sys


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
    import threading
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
        "--headless", action="store_true", help="HTTP only; never connects hardware"
    )
    parser.add_argument(
        "--once", action="store_true", help="print status and exit (headless only)"
    )
    parser.add_argument(
        "--replay", type=Path, help="ForestFive.Physical.v1 ZIP, RX-only"
    )
    parser.add_argument("--replay-speed", type=float, default=1.0)
    options = parser.parse_args(arguments)
    if options.once and not options.headless:
        parser.error("--once requires --headless")
    bridge = Bridge(variant, replay=bool(options.replay))
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
            f"FD2 V{variant}: http://127.0.0.1:{server.server_port} (disconnected until explicit Connect)",
            flush=True,
        )
        if options.headless:
            threading.Event().wait()
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
                app.App(window, variant)
                window.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        if replay:
            replay.stop()
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
