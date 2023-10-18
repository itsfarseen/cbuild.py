from collections import deque
import unittest
import cbuild
import tempfile
import os


class CBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

        self.runs = deque()
        old_run = cbuild.run

        def new_run(cmd):
            self._record_runs(cmd)
            old_run(cmd)

        cbuild.run = new_run

    def tearDown(self):
        self.tmpdir.cleanup()

    def _setup_files(self, files):
        for file, val in files.items():
            file = os.path.join(self.tmpdir.name, file)
            dir = os.path.dirname(file)
            os.makedirs(dir, exist_ok=True)
            if isinstance(val, str):
                with open(file, "w") as f:
                    f.write(val)
            elif isinstance(val, tuple):
                typ, val = val
                if typ == "symlink":
                    target = os.path.join(self.tmpdir.name, val)
                    os.symlink(target, file)
                else:
                    raise ValueError(f"Unknown type: {typ}")
            else:
                raise ValueError(f"Unknown entry: ({file}, {val})")

    def _assert_file_exists(self, *path):
        path = os.path.join(self.tmpdir.name, *path)
        self.assertTrue(os.path.exists(path), f"Path doesn't exist: {path}")
        self.assertTrue(os.path.isfile(path))

    def _assert_dir_exists(self, *path):
        path = os.path.join(self.tmpdir.name, *path)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.isdir(path))

    def _record_runs(self, cmd):
        self.runs.append(cmd)

    def _assert_ran(self, cmd_components, msg=None):
        try:
            top = self.runs.popleft()
        except IndexError:
            if msg:
                msg = "Reason: " + msg
            self.fail(msg)

        top_exec = top.split()[0]
        self.assertEqual(
            top_exec,
            cmd_components[0],
            "executable is not the same. " + (msg or ""),
        )

        for comp in cmd_components[1:]:
            self.assertIn(
                comp,
                top,
                f"'{comp}' is missing in {top}. " + (msg or ""),
            )

    def _assert_nothing_ran(self):
        self.assertEqual(
            len(self.runs),
            0,
            "Expected runs to be empty. Got [{}] instead".format(", ".join(self.runs)),
        )

    def _touch(self, file):
        file = os.path.join(self.tmpdir.name, file)
        os.utime(file)

    def test_gcc_works(self):
        self._setup_files(
            {
                "src/bar/baz.c": """
                    int main() {
                        return 0;
                    }
                """
            }
        )
        config = cbuild.Config(
            project_root=self.tmpdir.name,
            cc="gcc",
            build_dir="build",
            binary="main",
        )
        cbuild.build(config)
        self._assert_file_exists("build", "src", "bar", "baz.o")
        self._assert_file_exists("build", "main")

    def test_include_dirs(self):
        self._setup_files(
            {
                "src/foo.c": """
                    #include <liba.h>
                    #include <libb/lib.h>
                    #include "libc/lib.h"
                    #include "bar.h"
                    #include "../baz.h"

                    int main() {}
                """,
                "src/bar.h": "",
                "includes/liba.h": "",
                "baz.h": "",
                "vendor/libb/lib.h": "",
                "includes/libb": ("symlink", "vendor/libb"),
                "vendor/libc/lib.h": "",
                "src/libc": ("symlink", "vendor/libc"),
            }
        )
        config = cbuild.Config(
            project_root=self.tmpdir.name,
            cc="gcc",
            build_dir="build",
            binary="main",
            cflags="-Iincludes",
        )
        cbuild.build(config)

        self._assert_ran(["gcc", "src/foo.c"])
        self._assert_ran(["gcc", "build/main"])

        cbuild.build(config)
        self._assert_nothing_ran()

        for file in [
            "src/bar.h",
            "includes/liba.h",
            "baz.h",
            "vendor/libb/lib.h",
            "vendor/libc/lib.h",
        ]:
            self._touch(file)
            cbuild.build(config)
            self._assert_ran(["gcc", "src/foo.c"], file)
            self._assert_ran(["gcc", "build/main"], file)

    def test_unused_include(self):
        self._setup_files(
            {
                "src/foo.c": """
                    #include "bar.h"

                    int main() {}
                """,
                "src/bar.h": "",
                "src/unused.h": "",
            }
        )
        config = cbuild.Config(
            project_root=self.tmpdir.name,
            cc="gcc",
            build_dir="build",
            binary="main",
        )
        cbuild.build(config)

        self._assert_ran(["gcc", "src/foo.c"])
        self._assert_ran(["gcc", "build/main"])

        cbuild.build(config)
        self._assert_nothing_ran()

        self._touch("src/bar.h")
        cbuild.build(config)
        self._assert_ran(["gcc", "src/foo.c"])
        self._assert_ran(["gcc", "build/main"])

        self._touch("src/unused.h")
        cbuild.build(config)
        self._assert_nothing_ran()

    def test_transitive_deps(self):
        self._setup_files(
            {
                "src/foo.c": """
                    #include "bar.h"

                    int main() {}
                """,
                "src/bar.h": """
                    #include "baz.h"
                """,
                "src/baz.h": "",
            }
        )
        config = cbuild.Config(
            project_root=self.tmpdir.name,
            cc="gcc",
            build_dir="build",
            binary="main",
        )
        cbuild.build(config)

        self._assert_ran(["gcc", "src/foo.c"])
        self._assert_ran(["gcc", "build/main"])

        cbuild.build(config)
        self._assert_nothing_ran()

        self._touch("src/baz.h")
        cbuild.build(config)
        self._assert_ran(["gcc", "src/foo.c"])
        self._assert_ran(["gcc", "build/main"])

    def test_multiple_c_files(self):
        self._setup_files(
            {
                "src/foo.c": """
                    int main() {}
                """,
                "src/bar.c": """
                    int foo() {}
                """,
            }
        )
        config = cbuild.Config(
            project_root=self.tmpdir.name,
            cc="gcc",
            build_dir="build",
            binary="main",
        )
        cbuild.build(config)

        self._assert_ran(["gcc"])
        self._assert_ran(["gcc"])
        self._assert_ran(["gcc", "build/src/foo.o", "build/src/bar.o", "build/main"])

        cbuild.build(config)
        self._assert_nothing_ran()

        self._touch("src/foo.c")
        cbuild.build(config)
        self._assert_ran(["gcc", "src/foo.c"])
        self._assert_ran(["gcc", "build/src/foo.o", "build/src/bar.o", "build/main"])

        self._touch("src/bar.c")
        cbuild.build(config)
        self._assert_ran(["gcc", "src/bar.c"])
        self._assert_ran(["gcc", "build/src/foo.o", "build/src/bar.o", "build/main"])


if __name__ == "__main__":
    unittest.main()
