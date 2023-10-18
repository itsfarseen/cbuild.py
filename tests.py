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

    def _assert_ran(self, cmd, msg=None):
        if msg:
            msg = "Reason: " + msg
        try:
            top = self.runs.popleft()
        except IndexError:
            self.fail(msg)
        self.assertEqual(top.split(), cmd.split(), msg)

    def _assert_nothing_ran(self):
        self.assertEqual(
            len(self.runs),
            0,
            "Expected runs to be empty. Got [{}] instead".format(", ".join(self.runs)),
        )

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
                "src/unused.h": "",
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

        self._assert_ran("gcc -Iincludes -c src/foo.c -o build/src/foo.o")
        self._assert_ran("gcc build/src/foo.o -o build/main")

        cbuild.build(config)
        self._assert_nothing_ran()

        for file in [
            "src/bar.h",
            "includes/liba.h",
            "baz.h",
            "vendor/libb/lib.h",
            "vendor/libc/lib.h",
        ]:
            file = os.path.join(self.tmpdir.name, file)
            os.utime(file)
            cbuild.build(config)
            self._assert_ran("gcc -Iincludes -c src/foo.c -o build/src/foo.o", file)
            self._assert_ran("gcc build/src/foo.o -o build/main", file)

        os.utime(
            os.path.join(
                self.tmpdir.name,
                "src",
                "unused.h",
            )
        )
        cbuild.build(config)
        self._assert_nothing_ran()

    #
    # def test_include_symlinks(self):
    #     pass

    # def test(self):
    #     files = {
    #         "src/foo.c": """
    #             #include "foo.h"
    #             #include "../bar.h"
    #             #include <liba.h>
    #             #include <libb.h>
    #         """,
    #         "src/bar/baz.c": "",
    #         "src/unused.h": "",
    #         "src/foo.h": "",
    #         "bar.h": "",
    #         "vendor/liba/lib.h": "",
    #         "include/liba.h": ("symlink", "vendor/liba/lib.h"),
    #         "include/libb.h": "",
    #     }
    #
    #     # Create files


if __name__ == "__main__":
    unittest.main()
