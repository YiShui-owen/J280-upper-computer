import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

LAUNCHER = Path(__file__).resolve().parents[1] / 'launch_host.py'


class HostLauncherTests(unittest.TestCase):
    def launcher(self):
        self.assertTrue(LAUNCHER.is_file(), '需要在启动入口修复虚拟环境的 Tcl/Tk 路径')
        spec = importlib.util.spec_from_file_location('host_launcher', LAUNCHER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_selected_python_can_initialize_tcl_without_global_environment_changes(self):
        self.launcher()
        environment = dict(os.environ)
        environment.pop('TCL_LIBRARY', None)
        environment.pop('TK_LIBRARY', None)
        code = (
            'import tkinter, json; from launch_host import configure_tk_runtime; '
            'configure_tk_runtime(); t=tkinter.Tcl(); '
            'print(json.dumps({"version":t.eval("info patchlevel"),"library":t.eval("info library")}))'
        )
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', code],
                                cwd=LAUNCHER.parent, env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        runtime = json.loads(result.stdout)
        self.assertTrue((Path(runtime['library']) / 'init.tcl').is_file())
        self.assertTrue(runtime['version'])

    def test_missing_bundled_libraries_do_not_replace_explicit_configuration(self):
        module = self.launcher()
        environment = {'TCL_LIBRARY':'custom Tcl', 'TK_LIBRARY':'custom Tk'}
        with tempfile.TemporaryDirectory() as base:
            module.configure_tk_runtime(base_prefix=base, environ=environment)
        self.assertEqual(environment, {'TCL_LIBRARY':'custom Tcl', 'TK_LIBRARY':'custom Tk'})

    def test_host_help_passes_through_for_both_variants_without_starting_devices(self):
        self.launcher()
        for variant in ('gesture', 'adaptive'):
            with self.subTest(variant=variant):
                result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(LAUNCHER), variant, '--help'],
                                        capture_output=True, text=True, encoding='utf-8', timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('--offline-preview', result.stdout)
                self.assertIn('--headless', result.stdout)


if __name__ == '__main__':
    unittest.main()
