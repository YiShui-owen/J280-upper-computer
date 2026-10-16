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
    runtime = Path(sys.base_prefix if base_prefix is None else base_prefix) / 'tcl'
    for variable, directory, entry in (
        ('TCL_LIBRARY', f'tcl{_tkinter.TCL_VERSION}', 'init.tcl'),
        ('TK_LIBRARY', f'tk{_tkinter.TK_VERSION}', 'tk.tcl'),
    ):
        library = runtime / directory
        if not environment.get(variable) and (library / entry).is_file():
            environment[variable] = str(library)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('variant', choices=('gesture', 'adaptive', 'precise'))
    options, host_arguments = parser.parse_known_args()
    if '--headless' not in host_arguments and '--help' not in host_arguments and '-h' not in host_arguments:
        configure_tk_runtime()
    root = Path(__file__).resolve().parent
    host_root = root / 'host' / ('sp24/gesture' if options.variant == 'precise' else options.variant)
    entry = host_root / 'host' / 'swing_tune_host.py'
    sys.path.insert(0, str(entry.parent))
    sys.argv = [str(entry), *host_arguments]
    if options.variant == 'precise':
        from host.sp24_bridge import install
        spec = importlib.util.spec_from_file_location('j280_sp24_host', entry)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        install(module)
        module.main()
    else:
        runpy.run_path(str(entry), run_name='__main__')


if __name__ == '__main__':
    main()
