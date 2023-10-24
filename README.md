# cbuild.py

A simple C build system.

## Algorithm

- Find all .c files recursively starting from project root.
- Parse `#include` lines and figure out which `.c` files depend on which `.h` files.
- Recompile the `.o` file if either `.c` file or any of the header files it depends on is newer than the `.o` file.
- Link all the `.o` files into the binary.

## How to use

- Copy `cbuild.py` to your project root.
- Run `./cbuild.py config` to see the default config.
- Create `cbuild.json` if you want to override any of the config values.
- Run `./cbuild.py run` to build and run your project.
- See the output of `./cbuild.py help` for more info.

## Configuration

Create a `cbuild.json` file in the project root.

### Example config

```jsonc
{
  // Scan only files under this folder.
  // Files outside this folder (eg. system libraries) are assumed to never change.
  "project_root": ".", 
  // C compiler executable.
  "cc": "gcc",
  // Flags to pass in during compiling
  "cflags": "",
  // Flags to pass in during linking
  "ldflags": "",
  // Ignore .c files in these folders.
  "ignore_dirs": [
    ".git",
    ".ccls-cache"
  ],
  // Put build artifacts in this folder.
  "build_dir": "build",
  // Path to the final binary, relative to the build folder.
  "binary": "main",
  // List of dependencies.
  // For each entry in this list,
  //   `pkg-config --cflags {lib}` will be invoked to get the cflags and
  //   `pkg-config --libs {lib}` will be invoked to get the ldflags.
  // Run `pkg-config --list-all` to see libraries available to in your system.
  "dependencies": []
}
```
