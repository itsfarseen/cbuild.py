#!/usr/bin/env python3

import os
import sys
import json

import dataclasses
from dataclasses import dataclass, field
import copy

# Config

_CBUILD_CONFIG_FILENAME = "cbuild.json"


@dataclass
class Config:
    project_root: str = "."
    cc: str = field(default="gcc")
    cflags: str = ""
    ldflags: str = ""
    ignore_dirs: list = field(default_factory=lambda: [".git", ".ccls-cache"])
    build_dir: str = "build"
    binary: str = "main"


try:
    config_json = json.load(open(_CBUILD_CONFIG_FILENAME))
    config_loaded = True
except FileNotFoundError:
    config_json = {}
    config_loaded = False

CONFIG = Config(**config_json)


# End of Config


def usage():
    print()
    print("Commands:")
    print("  build\t\t\t Build the project")
    print("  run\t\t\t Build and run the project")
    print("  clean\t\t\t Remove the build directory")
    print("  config\t\t View the config")
    print("  help\t\t\t Show this message")


def main():
    if len(sys.argv) <= 1:
        usage()
    elif sys.argv[1] == "build":
        build()
    elif sys.argv[1] == "run":
        if build():
            run(CONFIG.binary)
    elif sys.argv[1] == "clean":
        run(f"rm -rf {CONFIG.build_dir}")
    elif sys.argv[1] == "config":
        print_config()
    else:
        usage()


def build(
    config: Config,
):
    os.chdir(config.project_root)
    config = copy.deepcopy(config)
    if config.build_dir not in config.ignore_dirs:
        config.ignore_dirs.append(config.build_dir)

    cflags_iter = iter(config.cflags.split())
    include_dirs = []
    for flag in cflags_iter:
        if flag == "-I":
            try:
                include_dirs.append(next(cflags_iter))
            except StopIteration:
                print("Expected a directory after -I: ", config.cflags)
                exit(-1)
        elif flag.startswith("-I"):
            include_dir = flag[2:].strip()
            include_dirs.append(include_dir)

    c_files = list(
        get_files_recursively(
            ".",
            dirs_filter=lambda d: d not in config.ignore_dirs,
            files_filter=lambda f: any(f.endswith(ext) for ext in [".c"]),
        )
    )
    dependencies = {}
    collect_dependencies(config.project_root, include_dirs, dependencies, c_files)

    if len(c_files) == 0:
        print("No files to compile.")
        return

    object_files = []

    any_compiled = False
    for file in c_files:
        file_stat = os.stat(file)
        file_mtime = file_stat.st_mtime

        object_file_name = file[:-2] + ".o"
        object_file = os.path.join(config.build_dir, object_file_name)
        object_files.append(object_file)

        try:
            object_stat = os.stat(object_file)
            object_mtime = object_stat.st_mtime
        except FileNotFoundError:
            object_mtime = 0

        should_recompile = False
        if file_mtime > object_mtime:
            should_recompile = True
        else:
            should_recompile = any_dep_changed(dependencies, file, object_mtime)

        if should_recompile:
            if not any_compiled:
                print("Compiling ..")
            any_compiled = True
            object_file_dir = os.path.dirname(object_file)
            os.makedirs(object_file_dir, exist_ok=True)
            cmd = f"{config.cc} {config.cflags} -c {file} -o {object_file}"
            run(cmd)

    binary = os.path.join(config.build_dir, config.binary)
    if (not os.path.exists(binary)) or any_compiled:
        print("Linking ..")
        object_files_list = " ".join(str(f) for f in object_files)
        run(f"{config.cc} {config.ldflags} {object_files_list} -o {binary}")
    else:
        print("All up-to-date")
    return True


def any_dep_changed(dependencies, file, object_mtime):
    for dep in dependencies[file]:
        dep_stat = os.stat(dep)
        dep_mtime = dep_stat.st_mtime
        if dep_mtime > object_mtime:
            return True
        if any_dep_changed(dependencies, dep, object_mtime):
            return True
    return False


def collect_dependencies(project_root, include_dirs, dependencies, files):
    """
    Find dependencies of each file in `files`, store them in dependencies.
    Recursively store their dependencies as well.
    """
    for file in files:
        if file in dependencies:
            continue

        with open(file) as fp:
            includes = get_includes(fp)

        include_paths = resolve_include_paths(
            project_root, file, includes, include_dirs
        )
        dependencies[file] = include_paths
        collect_dependencies(project_root, include_dirs, dependencies, include_paths)


def resolve_include_paths(
    project_root,
    file,
    includes,
    include_dirs,
):
    """
    Given a list of (include_type, include), return those in the project folder.

    We don't mind if an include referenced by a file is not found.

    If it's a non-standard header, user must specify it in include_dirs, which will get passed as '-I' to the compiler.
    If the user doesn't specify it, the compiler will catch it.

    If it's a standard header, we don't have to track the changes to them.
    """

    project_root = os.path.realpath(project_root)
    file_dir = os.path.dirname(file)

    local_includes = []
    for include_type, include in includes:
        if include_type == "quote":
            include_path = os.path.realpath(os.path.join(file_dir, include))
            if include_path.startswith(project_root + "/"):
                relative_path = include_path[len(project_root) + 1 :]
                local_includes.append(relative_path)
                continue

        for include_dir in include_dirs:
            include_path = os.path.join(include_dir, include)
            if os.path.exists(include_path):
                include_path = os.path.realpath(include_path)
                if include_path.startswith(project_root + "/"):
                    relative_path = include_path[len(project_root) + 1 :]
                    local_includes.append(relative_path)
                    break

    return local_includes


def get_files_recursively(root, dirs_filter, files_filter):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if dirs_filter(os.path.join(dirpath, d))]
        dirpath = os.path.normpath(dirpath)
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            filepath = os.path.normpath(filepath)
            if files_filter(filepath):
                yield filepath


def filter_subdirs(root, dirs, ignore: list[str]):
    dirs[:] = [d for d in dirs if str(root / d) not in ignore]


def get_includes(file):
    """
    Returns a list of (include_type, file).

    For example:
    ```
    #include "foo.h"
    #include <bar.h>
    ```

    becomes:

    [("quote", "foo.h"), ("angle_bracket", "bar.h")]
    """
    includes = []
    for line in file:
        line = line.strip()
        if line.startswith("#include"):
            line = line[len("#include") :].strip()
            if line[0] == '"':
                include_type = "quote"
                open_bracket = 0
                close_bracket = line.find('"', open_bracket + 1)
            elif line[0] == "<":
                include_type = "angle_bracket"
                open_bracket = 0
                close_bracket = line.find(">", open_bracket + 1)
            else:
                continue
            if close_bracket == -1:
                continue

            include = line[open_bracket + 1 : close_bracket]
            includes.append((include_type, include))
    return includes


def run(cmd: str):
    print(">", cmd)
    ret = os.system(cmd)
    if ret != 0:
        print("Command exited with:", ret)
        exit(-1)


#


def print_config():
    if not config_loaded:
        print(f"{_CBUILD_CONFIG_FILENAME} not found. Loading defaults.")
        print()

    print(json.dumps(dataclasses.asdict(CONFIG), indent=2))


if __name__ == "__main__":
    main()
