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
