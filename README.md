# replx

[![PyPI version](https://badge.fury.io/py/replx.svg)](https://badge.fury.io/py/replx)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`replx` is a command-line tool for developing and working with MicroPython boards.

**Requirements:** Windows, macOS, or Linux; Python 3.10 or newer.  
**Device support:** MicroPython 1.29 or newer on supported boards, plus legacy Digi XBee3 Zigbee support.

---

## Supported boards

Device features depend on the firmware APIs available on the connected board; see [Hardware platform support](#hardware-platform-support).

| Board | Requirements and notes |
|---|---|
| Raspberry Pi Pico 2 W (RP2350) | MicroPython 1.29 or newer |
| Waveshare ESP32-P4-WIFI6 (P4 + C6) | Use firmware matching the P4 chip revision. Wi-Fi/BLE require a compatible C6 Wi-Fi build and ESP-Hosted firmware. |
| Digi XBee3 Zigbee (EFR32MG) | Digi firmware 1014 or later with its vendor MicroPython runtime; use `.py` source rather than the bundled modern `mpy-cross` compiler. |
| PlanXLab TiCLE RP2350 variants | Profiles are included; firmware downloads are available for `ticle-lite` and `ticle-sensor`. |
| Teensy 4.x (`MIMXRT1062DVJ6A`) | A software profile is included; supported features depend on the installed firmware. |

### Waveshare ESP32-P4-WIFI6 notes

- Match the firmware to the board revision and wiring. Wi-Fi and BLE use the separate C6 coprocessor; install compatible P4 `C6_WIFI` firmware and C6 ESP-Hosted 2.7.0 firmware. BLE availability can vary between MicroPython images.
- The Type-C connector is a CH343 USB-UART port. The separate 4-pin V/D-/D+/G connector is the USB OTG port; native USB CDC is available only when supported and enabled by the firmware.
- Use MCU GPIO numbers, not physical header positions. Check the board pinout before connecting peripherals.
- P4 ADC commands require explicit ADC-capable pins. Voltage conversion is an estimate based on `--vref`, not calibrated ESP32 ADC output.
- `i2s` drives the I2S peripheral; it does not configure the onboard audio codec or amplifier.

### Digi XBee3 Zigbee notes

- Use XCTU to select MicroPython mode (`AP=4`) and set the REPL UART to 115200 baud. Zigbee transparent/API mode is not a Python REPL; `replx` does not change the module's AT settings.
- The board filesystem root `/` maps to `/flash`. Use small `.py` programs; XBee's older vendor runtime may not support current MicroPython syntax or packages. `mip install` uses source mode, but package compatibility is still up to the package.
- Use Digi pin names. `gpio` supports level read/write and sequences; `adc` supports D0-D3 and reports native counts; I2C controller mode uses bus 1 with SDA=P1 and SCL=D1.
- `mpy`, PWM, SPI, secondary UART, I2S, WS2812, Wi-Fi, and replx BLE commands are not supported for XBee3. Vendor-specific radio features may still be available through Digi APIs in your own scripts.

Examples:
```sh
replx COM7 -c "print('XBee legacy REPL')"
replx COM7 put main.py /
replx COM7 run -d /main.py
replx COM7 gpio write D0 1
replx COM7 adc read D0 D1 --repeat 5 --interval 1000
replx COM7 i2c scan
```

References: [Waveshare board documentation](https://www.waveshare.com/wiki/ESP32-P4-WIFI6), [MicroPython P4 firmware](https://micropython.org/download/ESP32_GENERIC_P4/), and Digi [Pin](https://docs.digi.com/resources/documentation/digidocs/90002219/reference/r_class_pin.htm), [ADC](https://docs.digi.com/resources/documentation/digidocs/90002219/reference/r_class_adc.htm), and [I2C](https://docs.digi.com/resources/documentation/digidocs/90002219/reference/r_class_i2c.htm) APIs.

---

## Getting started and connections

A quick start for a new workspace:

```sh
replx scan
replx COM3 setup
replx ls
```

`setup` initializes the workspace and registers the selected board as its default target.

### Selecting a board

- An explicit port takes priority. Without one, commands use the current terminal session's foreground (FG) board, then the workspace default if no FG board is set.
- A session can have one FG board and multiple background (BG) boards. Use `replx fg` to select a board, or specify its port directly.
- Typical port names are `COM4` on Windows, `/dev/ttyACM0` on Linux, and `/dev/cu.usbmodem14101` on macOS.

### Agent and workspace settings

Workspace connection and theme settings are saved in `.vscode/.replx` when changed by configuration commands. `replx close` releases a board connection but leaves the agent running; `replx agent stop` stops the configured agent and releases its board connections.

For remote connections, set the same `REPLX_AGENT_TOKEN` on the agent and client machines. The token is sent over unencrypted TCP, so use a trusted LAN or VPN. See [`agent`](#agent) for commands and endpoint options.

---

## Command Reference

### Command Summary

#### Connection / Session

| Command | Description |
|---|---|
| `setup` | Register the board as the default target and initialize the development environment. |
| `scan` | Discover available ports and board information. |
| `status` | Show FG/BG connection state per session. |
| `fg` | Switch the FG board for the current session. |
| `whoami` | Show the FG board the current session is targeting. |
| `close` | Close the board connection and remove it from every session that references it. |
| `agent` | Inspect status, start/stop the configured agent, connect to another endpoint, or disconnect a client IP. |
| `theme` | Show or customize panel colors and box style. |

#### Execution / Interaction

| Command | Description |
|---|---|
| `exec` (`-c`) | Execute a short Python snippet immediately. |
| `run` | Run a local Python file on the board. |
| `repl` | Start an interactive REPL session. |
| `shell` | Open an interactive shell for board filesystem operations. |

#### File Operations

| Command | Description |
|---|---|
| `ls` | List files and directories at a board path. |
| `cat` | Print the contents of a board file. |
| `get` | Download a file or directory from the board to local. |
| `put` | Upload a local file or directory to the board. |
| `cp` | Copy files or directories within the board. |
| `mv` | Move or rename files or directories within the board. |
| `rm` | Delete files or directories on the board. |
| `mkdir` | Create a directory on the board. |
| `touch` | Create a file if missing; preserve existing contents. |

#### Board Management

| Command | Description |
|---|---|
| `usage` | Show storage and RAM usage with free space. |
| `reset` | Soft-reset the board. |
| `format` | Format the board filesystem. |
| `init` | Run initial setup scripts on the board. |
| `wifi` | Manage Wi-Fi configuration and connection state. |
| `firmware` | Check, download, or update board firmware. |

#### Package / Compile

| Command | Description |
|---|---|
| `mip` | Search and install MicroPython packages from the official index or GitHub. |
| `pkg` | Search, download, and update MicroPython packages. |
| `mpy` | Compile `.py` files to `.mpy` bytecode. |

#### Hardware

| Command | Description |
|---|---|
| `gpio` | Read, write, and run GPIO sequences. |
| `pwm` | Generate and monitor PWM signals. |
| `adc` | Read ADC pins and run a board-side scope UI. |
| `uart` | Open, write, read, and monitor UART. |
| `spi` | Open, write, read, and transfer SPI data. |
| `i2c` | Scan, read, write, and dump I2C devices. |
| `i2s` | Play I2S tones and capture/monitor an I2S microphone. |
| `ws2812` | Write pixels and regions on WS2812 LED matrices. |
| `ble` | Manage BLE radio, scan, advertise, GATT server/client, and L2CAP. |

---

### Connection / Session

#### `setup`
The first command to run when starting a new project. After confirming the board connection, it creates `.vscode/tasks.json`, `.vscode/settings.json`, and `.vscode/launch.json`, configures the Pylance typehint path, and saves the current port as the workspace Default. A port is required, except for `--clean`.
Settings apply at the workspace level; running from a subfolder applies them to the parent workspace scope. If no config exists in a parent path, each path is treated as an independent workspace with its own default port.
The filesystem root (`C:\`, `/`) cannot be used as a workspace.

Usage:
```sh
replx PORT setup [--theme THEME]
replx setup --clean
```

Options:
- `--theme THEME`: UI theme preset (`dark`, `white`, `one-dark-pro`, `atom-one-light`, `github-dark`, `github-light`). If omitted, replx tries to detect the VS Code theme and falls back to `dark`. Fine-tune colors later with `replx theme`.
- `--clean`: delete the `.vscode` folder of the current project (configuration and typehints). Does not take a PORT.

Examples:
```sh
replx COM3 setup
replx /dev/ttyACM0 setup
replx /dev/serial/by-id/usb-MicroPython_board setup
replx /dev/cu.usbmodem14101 setup
replx COM3 setup --theme github-light
replx setup --clean
```

#### `scan`
Use this to identify which port belongs to which board before connecting. Combines already-connected agent ports with freshly scanned ports and displays Port / Version / Core / Device / Manufacturer along with connected and Default status.

Usage:
```sh
replx scan
```

Examples:
```sh
replx scan
replx COM3 setup                  # setup using port found by scan
replx /dev/ttyACM0 setup          # Linux example
replx /dev/serial/by-id/usb-MicroPython_board setup # stable Linux port example
replx /dev/cu.usbmodem14101 setup # macOS example
```

Notes:
- `scan` only detects boards; it does not establish a connection.
- `scan` does not require a running agent. When an agent already holds a serial port, it reuses the agent's board metadata and skips reopening that port.
- Using `-p/--port` with `scan` is an error.
- For USB-UART bridges (CH34x, CP210x, FTDI, PL2303) and unknown adapters, `scan` tries each REPL baud candidate. Native USB CDC ports ignore the baud rate and are probed once.

<a id="serial-baud-rate"></a>
**Serial baud rate:** When connecting, replx probes the REPL at 115200, then at 921600, and keeps the first rate that answers. If the board was just reset and is still booting, the probe repeats up to three times. Native USB CDC boards (Pico, ESP32-S3/C6 USB) ignore the rate. To try other rates first, set `REPLX_BAUD`. It accepts a comma- or semicolon-separated list; the defaults are still tried afterwards.

```sh
REPLX_BAUD=1500000 replx COM3 setup        # bash
$env:REPLX_BAUD="1500000"; replx COM3 setup # PowerShell
```

#### `status`
Use this in a multi-terminal environment to inspect FG/BG connections per session at a glance. Shows the current session, foreground/background ports for each session, and the default port.

When a board is idle, the agent checks both serial-port presence and a bounded raw-REPL prompt probe every few seconds. Health probes do not run while a replx command or interactive session owns the board; a deliberately silent running script is not stopped by an inactivity timer.

Usage:
```sh
replx status
```

Examples:
```sh
replx status
replx fg                        # switch foreground after checking status
```

#### `fg`
Switch the foreground board for the current session. `replx fg` presents an interactive list to choose from; `replx PORT fg` immediately promotes the specified port to FG. Subsequent commands (`ls`, `run`, `cat`, etc.) will target the new FG board.

Usage:
```sh
replx fg
replx PORT fg
```

Examples:
```sh
replx fg
replx COM19 fg
replx /dev/ttyACM0 fg
replx /dev/cu.usbmodem14101 fg
```

#### `whoami`
Instantly shows what FG board the current terminal session is targeting.

Usage:
```sh
replx whoami
```

Examples:
```sh
replx whoami
replx COM3 fg && replx whoami   # confirm target after switching FG
```

#### `close`
Closes a specific board connection while keeping the agent process running. `replx close` targets the current session's FG; `replx PORT close` releases the specified port. The physical connection is removed from every session that referenced it. If the FG is removed, one of the BG boards becomes FG. Use `replx agent stop` to stop the configured agent.

Usage:
```sh
replx close
replx PORT close
```

Examples:
```sh
replx close
replx COM3 close
replx /dev/ttyACM0 close
replx /dev/cu.usbmodem14101 close
```

#### `agent`
Manage the configured agent endpoint. The default endpoint is `127.0.0.1:49153`; endpoint settings are saved per workspace in `.vscode/.replx`. `status` shows the endpoint and the current client's IP/SID with its assigned FG/BG boards. `start` stops any running agent at the selected local endpoint before starting it again. `connect` verifies an existing endpoint before saving it. `disconnect IP` removes that client's sessions and releases only boards not still assigned to another client. `stop` shuts down the configured agent and releases its board connections without assigning a replacement port.

Usage:
```sh
replx agent status
replx agent start --port 49153
replx agent connect 192.168.1.20 --port 49153
replx agent disconnect 192.168.1.30
replx agent stop
```

Examples:
```powershell
# On the agent machine:
$env:REPLX_AGENT_TOKEN = "<shared-secret>"
replx agent start --host 192.168.1.20 --port 49153

# On the client machine, set the same token:
$env:REPLX_AGENT_TOKEN = "<shared-secret>"
replx agent connect 192.168.1.20 --port 49153
replx agent status
```

For Linux/macOS, export `REPLX_AGENT_TOKEN` on both machines before starting or connecting. The token is sent over plain TCP; only use remote access on a trusted LAN or VPN.

#### `theme`
Show or customize the terminal UI: panel border colors per category and the global panel box style. Settings are saved in `.vscode/.replx` and apply to this workspace; no board connection is needed. Category overrides take priority over the base colors of the active theme (for example `vscode-auto` or `one-dark-pro`).

Usage:
```sh
replx theme                         # show the current theme and all panel colors
replx theme color CATEGORY [HEX]    # show or override one category color (#RRGGBB)
replx theme box [STYLE]             # show or set the panel box style
replx theme reset [CATEGORY]        # remove one override, or all overrides
```

- `CATEGORY`: `help`, `success`, `data`, `mode`, `warning`, `neutral`, `error`
- `STYLE`: `rounded` (default), `horizontals`, `square`, `heavy`, `double`, `minimal`

Examples:
```sh
replx theme color help #61afef
replx theme color error #ff4444
replx theme box double
replx theme reset
```

---

### Execution / Interaction

#### `exec` (`-c` alias)
Run a short MicroPython snippet without a file. Sends the `exec` command to the board once and returns standard output immediately. Multiple statements can be chained with semicolons (`;`).

Usage:
```sh
replx exec "CODE"
replx -c "CODE"
```

Examples:
```sh
replx -c "print('hello')"
replx -c "import os; print(os.listdir())"
replx exec "import machine; print(machine.freq())"
replx -c "import time; time.sleep(1); print('done')"
```

#### `run`
The primary command for running scripts. Default mode transfers a local file to the board and runs it interactively. `-d/--device` runs a file already stored on the board interactively. `-n/--non-interactive` detaches execution without waiting for I/O. `-e/--echo` echoes input to the terminal during interactive runs. `--line text|hex` switches to line input mode: output scrolls in a split region while the input line stays fixed at the bottom. `--non-interactive` and `--echo` cannot be used together, and `--line` cannot be combined with either.

Usage:
```sh
replx run SCRIPT
replx run -d SCRIPT
replx SCRIPT
replx run --line text SCRIPT
replx run --line hex SCRIPT
```

Examples:
```sh
replx run main.py
replx main.py              # shorthand for .py files
replx run -d /test.py      # run board's /test.py interactively
replx run -n server.py     # non-interactive (no I/O wait)
replx run -dn /main.py     # run board's /main.py non-interactively
replx run --line text main.py   # line mode: type text, Enter to send
replx run --line hex main.py    # line mode: type hex bytes (e.g. 0102ff), Enter to send
replx main.py --line hex        # shortcut form also works
```

Line mode key bindings:
- `Enter`: send the typed line to the board
- `Backspace`: delete last character
- `Ctrl+U`: clear the input line
- `Ctrl+C` twice: interrupt and exit

#### `repl`
Enter the board's Friendly REPL to experiment with code line by line. Output is displayed in real time. Type `exit()` to end the REPL session.

Usage:
```sh
replx repl
```

Examples:
```sh
replx repl
# Inside REPL:
>>> import os
>>> os.listdir()
>>> exit()
```

Key bindings:
- `Ctrl+C`: interrupt running code
- `Ctrl+D`: soft reset

#### `shell`
An interactive shell for continuous board filesystem management. Supports `ls/cat/cp/mv/rm/mkdir/touch` and `cd/pwd` relative to the current path. This is not a Python REPL. Inside the shell, `run` always operates on board files (`-d` mode), and `-n/-e` options are unavailable.

Usage:
```sh
replx shell
```

Available commands inside the shell:
```sh
# Files
ls cat cp mv rm mkdir touch

# Navigation
cd pwd clear

# Execution
exec run repl

# Other
usage wifi help exit
```

Examples:
```sh
replx shell
:/ > ls
:/ > cd lib
:/lib > cat boot.py
:/lib > exit
```

---

### File Operations

#### `ls`
List the contents of a board directory. Default shows a single-path listing; `-r/--recursive` outputs the full tree. Folder/file type icons and size information are shown, making it useful for pre/post-deploy comparisons.

Usage:
```sh
replx ls [PATH]
replx ls -r [PATH]
```

Examples:
```sh
replx ls
replx ls /lib
replx ls -r
replx ls -r /lib
```

#### `cat`
View the contents of a board file. Text files are shown as-is; binary files are displayed as a hex dump. `-n/--number` adds line numbers for text. `-L/--lines` selects a line range (`N:M`) for text or a byte range (`N:M`, `N:+M`) for binary.

Usage:
```sh
replx cat FILE
replx cat -n FILE
replx cat -L N:M FILE
```

Examples:
```sh
replx cat main.py
replx cat -n /lib/audio.py
replx cat -L 1:30 boot.py
replx cat -L 100:+64 app.mpy
```

#### `get`
Download files or directories from the board to local. Remote patterns (`*`, `?`) are resolved on the board side; directories are downloaded recursively. When downloading multiple sources, the last argument `LOCAL` must be a directory.

Usage:
```sh
replx get REMOTE LOCAL
replx get REMOTE... LOCAL
```

Examples:
```sh
replx get main.py ./
replx get / ./backup            # full board filesystem backup
replx get /a.py /b.py ./
replx get /lib/*.mpy ./compiled
```

#### `put`
Upload local files or directories to the board. Local wildcards (`*`, `?`) are expanded before upload; directories are transferred recursively. The last argument is always the remote destination path; remote directories are created automatically if needed. Directory uploads skip common caches and build artifacts such as `.git`, `.venv`, `__pycache__`, bytecode, and native binaries.

Large non-interactive uploads on standard boards use MicroPython raw-paste flow control from 4 KiB at up to 115200 baud and from 256 bytes at higher baud rates. Digi XBee3 always uses its paced classic raw-REPL path.

On standard runtimes, each 4 KiB block is sent in the shortest of three forms: a Python bytes literal, Base64, or raw-deflate-compressed Base64 (the last only when the firmware provides the built-in `deflate` module, which is checked once per file and decompressed on the board). Compressed blocks are typically 20–40% smaller for `.mpy` files. Measured with the 47 `.mpy` files (387 KB) installed by `init`: Pico 2 W 11.6 s → 10.2 s, ESP32-P4 (115200-baud UART) 63.7 s → 39.1 s. XBee3 retains its legacy bytes-literal path. Actual throughput depends on the board, filesystem, USB/UART connection, and firmware.

Usage:
```sh
replx put LOCAL REMOTE
replx put LOCAL... REMOTE
```

Examples:
```sh
replx put main.py /
replx put ./lib/audio.py /lib
replx put a.py b.py /lib
replx put *.py /lib
```

#### `cp`
Copy files or directories within the board. Supports single files, directories, multiple sources, and patterns. `-r/--recursive` is required for directories; the destination must be a directory when copying multiple sources.

Usage:
```sh
replx cp SRC DEST
replx cp -r DIR DEST
```

Examples:
```sh
replx cp /main.py /backup.py
replx cp x.py y.py /backup
replx cp /lib/*.mpy /backup
replx cp -r /lib /lib_backup
```

#### `mv`
Move or rename files and directories within the board. Supports single moves, multiple sources, and patterns. `-r/--recursive` is required for directories. When moving multiple sources, verify the destination is a directory first.

Usage:
```sh
replx mv SRC DEST
replx mv -r DIR DEST
```

Examples:
```sh
replx mv /old.py /new.py
replx mv /main.py /backup
replx mv *.py /backup
replx mv -r /lib/audio /lib/sound
```

#### `rm`
Delete files or directories on the board. By default, a confirmation prompt is shown before deletion; `-f/--force` skips the prompt. `-r/--recursive` is required for directories. Pattern deletion (`*.py`, `/lib/*.mpy`) is supported.

Usage:
```sh
replx rm FILE
replx rm -r DIR
replx rm -f FILE
```

Examples:
```sh
replx rm /main.py
replx rm -f /main.py
replx rm /a.py /b.py
replx rm /lib/*.mpy
replx rm -rf /tmp
```

Note: Without `-f`, `rm` cancels when stdin is not interactive (scripts, pipes, CI) and reports `Remove Cancelled`. Use `-f` in automation.

#### `mkdir`
Pre-create a directory structure on the board. Multiple paths can be created at once, including nested paths. Existing directories are silently retained.

Usage:
```sh
replx mkdir DIR
replx mkdir DIR...
```

Examples:
```sh
replx mkdir /lib
replx mkdir /tests
replx mkdir /lib/audio /lib/net
replx mkdir /a/b/c
```

#### `touch`
Create an empty file when it is missing, or ensure that it exists. Existing file contents are preserved; this command does not set modification timestamps.

Usage:
```sh
replx touch FILE
replx touch FILE...
```

Examples:
```sh
replx touch /config.py
replx touch /a.py /b.py /c.py
replx touch /lib/__init__.py
```

---

### Board Management

#### `usage`
Check RAM (`mem`) and filesystem (`df`) usage simultaneously. Shows a usage bar alongside Used/Free/Total values, making it ideal for capacity checks before uploading.

Usage:
```sh
replx usage
replx PORT usage
```

Examples:
```sh
replx usage
replx COM3 usage
replx /dev/ttyACM0 usage
replx /dev/cu.usbmodem14101 usage
```

#### `reset`
Reset the board's execution state. Default is `--soft` (restart the interpreter); `--hard` performs a hardware reset followed by automatic reconnection. Using `--soft` and `--hard` together is an error.

Usage:
```sh
replx reset
replx reset --soft
replx reset --hard
```

Examples:
```sh
replx reset
replx reset --soft
replx reset --hard
```

Options:
- `--soft`: restart the Python interpreter (default)
- `--hard`: hardware reset + auto-reconnect

#### `format`
Completely wipe the board filesystem and start fresh. All user files including `boot.py`, `main.py`, and `lib/` are deleted. Some boards may not support the format command — check the error message if it fails.

Usage:
```sh
replx format
```

Examples:
```sh
replx get /*.py ./backup
replx get /lib ./backup
replx format
```

#### `init`
Restore a board to its initial state and reinstall required libraries. Internally runs `format` followed by sequential core/device package installation. The local package store must be prepared first — run `replx pkg download` before using this for the first time.

Usage:
```sh
replx init
```

Examples:
```sh
replx pkg download
replx init
```

Operation order:
1. Format filesystem
2. Install core libraries
3. Install device libraries

Transfer optimizations are built into replx and MicroPython's REPL; no board-side helper is needed. Do not rerun `init` just to enable faster uploads: **it erases the filesystem**.

#### `wifi`
Manage the board's Wi-Fi status, connection, and boot auto-connect. `wifi connect SSID PW` saves credentials to the board (`wifi_config.py`) and connects immediately. `wifi connect` reconnects using saved settings. `wifi boot on|off` controls whether `boot.py` auto-connects on startup.

Usage:
```sh
replx wifi
replx wifi connect SSID PW
replx wifi connect
replx wifi scan
replx wifi off
replx wifi boot on|off
```

Examples:
```sh
replx wifi
replx wifi scan
replx wifi connect MySSID MyPassword
replx wifi connect
replx wifi boot on
replx wifi off
```

#### `firmware`
Download or install firmware for supported boards. For a connected ESP32-P4+C6, `download` and `update` offer the available official Release and Preview images. For other variants, use `--url` with `download` or `--file`/`--url` with `update` to select an image matching the board.

`download` saves an image without flashing it. `update` asks for confirmation before writing; back up board files first because firmware or partition changes can make stored files inaccessible. `--flash-port` selects the bootloader port for a board that cannot start a REPL. It selects the P4, not the separate C6 coprocessor.

Usage:
```sh
replx firmware download
replx firmware update
replx firmware update --file firmware.bin
replx firmware update --flash-port COM3 --file firmware.bin
```

Options:
- `-f, --force`: reinstall even if the installed version is unchanged
- `--baud`: ESP32-P4 flashing baud rate (default: 460800); try 115200 if the adapter is unreliable
- `--erase`: erase the full ESP32-P4 flash, including user data
- `--yes`: skip the ESP32-P4 update confirmation

Examples:
```sh
replx firmware download
replx firmware update
replx firmware update --file "D:\firmware\board.bin"
replx firmware update --flash-port COM3 --file "D:\firmware\board.bin" --baud 115200
```

---

### Package / Compile

#### `mip`
Install MicroPython packages from the official micropython.org index or directly from GitHub. All downloading and compilation happen on the PC — the board does not need a Wi-Fi connection. On standard runtimes, `.py` source files are compiled to `.mpy` using `mpy-cross` before upload. The target architecture is auto-detected from the connected board via `sys.implementation._mpy`. On Digi XBee3, installation automatically uses source mode and skips modern `.mpy` compilation; package compatibility with the vendor runtime is still the user's responsibility.

For packages in the official index, pre-compiled `.mpy` files are fetched directly from the CDN when available (`hashes` field). For `github:org/repo` specs without a `package.json`, replx automatically queries the board's architecture and fetches pre-built `.mpy` binaries from the repository's GitHub Pages CDN (e.g. `emlearn-micropython`).

Usage:
```sh
replx mip SUBCOMMAND [args]
```

Subcommands:

| Subcommand | Description |
|---|---|
| `search [QUERY]` | List all packages or filter by name/description |
| `search github:org/repo` | Browse a GitHub repo's package structure |
| `install TARGET[@version]` | Download, compile (if needed), and install to board |

Install Targets:
```sh
requests                  # latest version from official index
requests@0.10.0           # specific version
github:org/repo           # GitHub repo root (package.json or CDN fallback)
github:org/repo/path      # GitHub repo sub-path
github:org/repo/path/foo.py  # single GitHub source file
https://example.com/f.mpy # direct URL
```

Install Options:
- `--device PATH`: board destination path (default: `lib` → `/lib/`)
- `--no-compile`: upload `.py` files directly without `.mpy` compilation
- `--index URL`: use a custom package index instead of the default
- `-s, --source URL`: base URL; the remaining arguments are file names appended to it

Examples:
```sh
replx mip search
replx mip search mqtt
replx mip search github:micropython/micropython-lib
replx mip install requests
replx mip install requests@0.10.0
replx mip install aioble
replx mip install github:emlearn/emlearn-micropython
replx mip install github:org/repo/src
replx mip install --device /lib/ext umqtt.simple
replx mip install --no-compile logging
replx mip install --source https://host/path/ a.mpy b.mpy
```

Notes:
- All network I/O happens on the PC — board WiFi is **not** required.
- On standard runtimes, `.py` files are compiled to `.mpy` before upload (requires `mpy-cross`); XBee3 automatically uses source mode.
- Dependencies declared in `deps` are installed automatically.
- For packages without `package.json` (e.g. native C modules), replx reads the board's `sys.implementation._mpy` to determine architecture (`armv6m`, `armv7emsp`, `xtensawin`, etc.) and fetches matching pre-built `.mpy` files from GitHub Pages.

---

#### `pkg`
Manages the package workflow (`search → download → update`) between the GitHub remote registry, local store, and board. `search [QUERY]` shows results scoped to the connected board's core/device. `download` fetches the remote registry to the local store. `update TARGET` installs packages to the board using `core.all`, `device.all`, `core.<file>`, or `device.<file>`. `clean` removes the current core/device entries from the local store. `--owner/--repo/--ref` specify the GitHub remote and apply to `search/download/update`.

Usage:
```sh
replx pkg SUBCOMMAND [args]
```

Examples:
```sh
replx pkg search
replx pkg search audio
replx pkg search --owner PlanXLab --repo replx_libs --ref main
replx pkg download
replx pkg download --owner PlanXLab --repo replx_libs --ref main
replx pkg update core.all
replx pkg update device.all
replx pkg update core.slip.py
replx pkg update device.termio.py
replx pkg clean
```

> Note: `pkg search/download/update` operates within the **core/device scope of the currently connected board**.

#### `mpy`
Compile `.py` files to `.mpy` bytecode. Automatically selects the target architecture based on the connected board's `core` and version. `-o/--output` can only be used when compiling a single file. `mpy-cross` 1.29 or newer must be installed locally before use; `pip install replx` installs it automatically.

The bundled compiler is not used for Digi XBee3's legacy/vendor `.mpy` ABI. Use `put` for `.py` source or `mip install --no-compile` instead.

Usage:
```sh
replx mpy FILES...
replx mpy main.py -o out.mpy
```

Examples:
```sh
replx mpy main.py
replx mpy main.py -o build/main.mpy
replx mpy *.py
replx mpy src/
```

---

### Hardware

Hardware commands let you use board peripherals without writing a script. Standard MCU pins accept `GP<num>`, `GPIO<num>`, or a number (case-insensitive); all refer to a GPIO id, not a connector pin number. Digi XBee3 uses named pins as described above. Bus settings opened with `uart`, `spi`, or `i2c` remain active until closed or the agent is restarted. Streaming commands run until Ctrl+C.

#### Hardware platform support

Feature availability depends on the board, firmware APIs, and required on-board libraries. "Conditional" means the listed firmware API or dependency is required.

| Feature | Pico 2 W / RP2350 | ESP32-P4-WIFI6 | XBee3 Zigbee |
|---|---|---|---|
| GPIO level read/write, write/delay seq | Write/seq; level read via `seq ... read` | Same, with P4 GPIO ids | Named pins; `gpio read D0 read`, write/seq |
| GPIO pulse/wait, IRQ monitor | Supported; monitor needs `termviz` | `time_pulse_us` and **soft** Pin IRQ; monitor needs `termviz`, with scheduling/edge-rate limits | Excluded |
| PWM write/seq/stop | Supported | `machine.PWM` (LEDC) | Excluded |
| PWM monitor | RP2 PIO measurement | `time_pulse_us` fallback, not RP2 PIO | Excluded |
| ADC read | `read_u16()` | `read_u16()` on ADC-capable GPIOs | Native `read()` on D0..D3 |
| ADC scope | `termviz` + `ufilter`; RP2 default pins | Same dependencies; explicit pins required | Excluded |
| I2C controller | RP2 pin/bus mapping | GPIO matrix; valid exposed pins only | Bus 1, SDA=P1, SCL=D1 |
| I2C target | Firmware must expose `I2CTarget` | Available when `machine.I2CTarget` exists | Excluded |
| SPI controller | Supported | `machine.SPI` | Excluded |
| SPI `--slave` | **RP2350 only**, requires device-specific `SpiSlave` library | Excluded | Excluded |
| UART peripheral | Supported | `machine.UART`; avoid the REPL UART | Excluded (Zigbee REPL serial is not a secondary UART API) |
| I2S tone/read/scope | `machine.I2S`; scope needs `termviz` | Same API/dependencies; onboard codec setup is separate | Excluded |
| WS2812 | `neopixel`, RP2 PIO, or `bitstream` | `neopixel` or `machine.bitstream`; **no RP2 PIO** | Excluded |
| Wi-Fi / BLE | Firmware APIs required | Requires compatible C6 firmware/configuration; BLE support depends on the MicroPython image | Excluded |

RP2 PIO and the RP2350 SPI-slave driver are platform-specific; replx does not emulate them on unsupported boards. I2C Target is selected by firmware API availability, not the RP2350 name. Pin availability and firmware APIs take precedence over similarly named hardware blocks in a chip datasheet.

#### `gpio`
Read, write, and run sequences on GPIO pins. `read` performs a pulse/wait action and waits until it completes (Ctrl+C to cancel); multiple pins may be given and each reports as soon as its own action completes. `write` drives one pin high or low. `seq` executes a write+delay pattern with an optional final read action in a single board call. `monitor` captures edges with an IRQ and renders a live scope (requires `termviz` on the board). The approximately 10–50 µs timing figure applies to the RP2 hard-IRQ path, not ESP32 soft IRQ; ESP32 callback scheduling can delay or lose fast edges.

XBee3 uses the restricted level-I/O commands described in the board compatibility section: `gpio read D0 read`, `gpio write D0 1`, and `gpio seq D0 1 m10 0 D1 read`. Its pulse/wait actions and monitor are excluded.

Usage:
```sh
replx gpio read GP<num> [GP<num> ...] ACTION [--repeat N] [--expr EXPR]
replx gpio write GP<num> 0|1
replx gpio seq GP<num> TOKEN... [READ_ACTION]
replx gpio seq WRITE_GP TOKEN... [READ_GP READ_ACTION]
replx gpio monitor GP<num> [--interval MS]
```

- `ACTION` (`read`): `wait_h`, `wait_l` (wait for the level, report `wait_ms`), `pulse_h`, `pulse_l` (report the pulse width `pulse_us`).
- `TOKEN` (`seq`): `0`/`1` drive low/high, `u<N>` delay in µs, `m<N>` delay in ms. At least one write token is required.
- `READ_ACTION` (`seq`, last token only): `read`, `wait_h`, `wait_l`, `pulse_h`, `pulse_l`. Without `READ_GP` the write pin is read back.

Options:
- `--repeat N`: repeat count for `read`/`seq` (0 = until Ctrl+C, default: 1). Repeated `seq` runs as one on-board loop.
- `--interval MS`: `monitor` render interval (default: 10, min: 1), or delay between repeated `seq` iterations (default: 10, requires `--repeat`)
- `--timeout MS`: wait/pulse timeout for `seq` read actions (default: 100, 0 = unlimited). `read` always waits until completion.
- `--expr EXPR`: post-process the result; variables `pulse_us`, `wait_ms`, `value`, `writes`; functions `abs`, `round`, `min`, `max`

Examples:
```sh
replx gpio read GP2 pulse_h
replx gpio read GP2 pulse_h --expr "pulse_us/58"
replx gpio read GP14 GP15 GP16 GP17 pulse_h --repeat 0
replx gpio write GP15 1
replx gpio seq GP1 1 u50 0 m1 1 read
replx gpio seq GP20 0 u5 1 u10 0 GP21 pulse_h --timeout 100 --expr "pulse_us/58" --repeat 5
replx gpio monitor GP2 --interval 50
```

#### `pwm`
Generate PWM on one pin. `write` starts or updates PWM with a frequency and exactly one duty option. `seq` runs a duty+delay pattern in one board call; PWM stays at the last duty until `stop`. `stop` halts PWM and drives the pin low. `monitor` shows a scrolling log of frequency, period, and duty changes on an input pin (20–20000 Hz) using PIO state machine 0 on RP2350/RP2040, or `time_pulse_us()` on other boards.

Usage:
```sh
replx pwm write GP<num> --freq HZ (--duty-percent P | --duty-u16 N | --pulse-us US)
replx pwm seq GP<num> --freq HZ --duty MODE TOKEN... [--repeat N]
replx pwm stop GP<num>
replx pwm monitor GP<num> [--timeout MS]
```

- `MODE` (`seq`): `percent` (0–100), `u16` (0–65535), `pulse_us` (pulse width; must not exceed the PWM period)
- `TOKEN` (`seq`): a duty value in the selected mode, `u<N>` delay in µs, or `m<N>` delay in ms

Options:
- `--freq HZ`: PWM frequency (required for `write`/`seq`)
- `--duty-percent P`, `--duty-u16 N`, `--pulse-us US`: duty for `write` (exactly one)
- `--duty MODE`: duty basis for `seq`
- `-n, --repeat N`: `seq` repeat count (0 = until Ctrl+C, default: 1)
- `--timeout MS`: `monitor` no-signal timeout (default: 2000)

Examples:
```sh
replx pwm write GP15 --freq 1000 --duty-percent 25
replx pwm write GP15 --freq 50 --pulse-us 1500
replx pwm write GP15 --freq 20000 --duty-u16 32768
replx pwm seq GP15 --freq 100 --duty percent 0 m200 25 m200 50 m200 75 m200 100
replx pwm seq GP15 --freq 50 --duty pulse_us 1000 m500 1500 m500 2000 --repeat 0
replx pwm stop GP15
replx pwm monitor GP2 --timeout 5000
```

#### `adc`
Read analog pins or launch a board-side scope UI. `read` samples up to three ADC channels. `scope` runs an interactive waveform viewer on the board (requires `termviz` and `ufilter`); without pins it uses `GP26 GP27 GP28`.

Usage:
```sh
replx adc read GP<num>... [--repeat N] [--interval MS] [--vref V]
replx adc scope [GP<num>...] [--sample MS]
```

Options:
- `--repeat N`: `read` repeat count (0 = until Ctrl+C, default: 1)
- `--interval MS`: delay between repeated reads (default: 1000)
- `--vref V`: ADC reference voltage (default: 3.3)
- `--sample MS`: initial scope render interval (0, 1, 2, 5, 10, 20, 50, 100; default: 10)

Scope keys: `1`/`2`/`3` select the active channel, `LEFT`/`RIGHT` change the sample rate or selected item, `ENTER` opens the filter parameter editor, `ESC` goes back, Ctrl+C exits. Multi-channel scope normalizes each channel to its own 0..Vref range.

Examples:
```sh
replx adc read GP26
replx adc read GP26 GP27 GP28 --repeat 5 --interval 200
replx adc read GP26 --repeat 0 --vref 3.3
replx adc scope
replx adc scope GP26 GP27 --sample 20
```

#### `uart`
Manage a UART bus. `open` validates and saves the configuration; `bus` shows it; `write` sends text (or raw bytes with `--hex`); `read` receives data; `xfer` writes then reads; `monitor` displays incoming data until Ctrl+C; `close` deinitializes UART, returns its pins to GPIO input, and clears the saved configuration.

Buffer handling:
- `read` (all modes, including `--any` and `--timeout 0`) and all `monitor` modes discard buffered RX data once when the board starts the receive operation, then show only newly received data. The buffer is not cleared between bursts or frames.
- `write` and `xfer` discard any TX data still queued from an earlier operation (and old RX data) by re-creating the UART with the saved settings, then send the new data and wait until it has been transmitted. Bytes already shifted onto the wire cannot be recalled.
- `xfer` does not clear RX after sending, so an immediate reply is kept.

Usage:
```sh
replx uart open [--tx GP<num>] [--rx GP<num>] [--id N] [--baud N] [--bits 7|8] [--parity none|odd|even] [--stop 1|2]
replx uart bus
replx uart write TEXT...
replx uart write --hex HEX...
replx uart read [NBYTES] [--timeout MS] [--any]
replx uart xfer TEXT... [--rx-bytes N] [--timeout MS]
replx uart xfer --hex HEX... [--rx-bytes N] [--timeout MS]
replx uart monitor [--width 8|16] [--idle MS] [--text] [--chunk]
replx uart close
```

Options:
- `--tx GP<num>`, `--rx GP<num>`: TX and RX pins. `open` needs at least one. A TX-only UART can `write` but not `read`/`xfer`/`monitor`; an RX-only UART (e.g. a barcode reader) can `read`/`monitor` but not `write`/`xfer`. Teensy 4.x requires `--tx`.
- `--id N`: UART ID (`open` only; `--channel` is an alias). See *UART ID* below.
- `--baud N`: baud rate (default: 115200)
- `--bits 7|8`, `--parity none|odd|even`, `--stop 1|2`: frame format (default: 8, none, 1)
- `--timeout MS`: RX wait for `read`/`xfer` (default: 2000); not valid with `open` or `monitor`. With `0`, `read` keeps reading until Ctrl+C and prints each burst (data followed by 50 ms of silence) or each `NBYTES` frame as its own timestamped hex dump; `xfer` waits for the reply without a limit
- `--any`: after discarding old data, return the first new bytes as soon as they arrive, without the 50 ms burst gathering (`read`; waits up to `--timeout`)
- `--rx-bytes N`: receive exactly N bytes (`xfer`; omit to wait for any data)
- `--hex`: send raw hex bytes, space-separated or concatenated (`write`/`xfer`)
- `--width 8|16`: hex dump row width for `monitor` (default: 16)
- `--text`: stream raw UTF-8 (`monitor`)
- `--chunk`: per-chunk display with timestamp and length (`monitor`)
- `--idle MS`: insert a separator after MS of silence (`monitor`, default: 0 = off)

UART ID (`bus` shows how it was chosen):

| Platform | UART ID | Pins |
|---|---|---|
| RP2040 / RP2350 | Fixed by the pins; `--id` may be omitted and must match if given | UART0 TX `GP0,GP12,GP16,GP28`, UART1 TX `GP4,GP8,GP20,GP24`; RX is TX+1 on the same UART |
| Teensy 4.x | Fixed by the TX pin table | `--tx` is required |
| ESP32 family (P4, C6, S3, ...) | Your choice: default UART1, any other with `--id N`; UART0 is the REPL and is rejected | Any GPIO through the GPIO matrix |

With a single pin, ESP32 leaves the other direction unrouted. RP2 hardware always routes both pins, so replx routes the paired pin (TX+1 or RX−1) for `UART()` and immediately returns it to GPIO input; it can be used for other work afterwards.

Examples:
```sh
replx uart open --tx GP0 --rx GP1 --baud 9600
replx uart open --rx GP5 --baud 9600              # RX only (barcode reader on UART1)
replx uart read --timeout 0                       # every scan until Ctrl+C
replx COM3 uart open --id 2 --tx GPIO20 --baud 9600  # ESP32: TX only on UART2
replx uart write "AT+RST\r\n"
replx uart write --hex 48 65 6C 6C 6F
replx uart read 16 --timeout 5000
replx uart read --any
replx uart xfer "AT\r\n" --rx-bytes 8
replx uart xfer --hex 01 03 00 00 00 0A --rx-bytes 25
replx uart monitor --width 8 --idle 200
replx uart monitor --text --chunk
replx uart close
```

#### `spi`
Manage an SPI bus in master or slave mode. `open` validates and saves the configuration; `bus` shows it; `write`/`read`/`xfer` transfer data; `close` releases the peripheral. `--slave` enables PIO+DMA slave mode (requires `SpiSlave` on the device; MOSI must be SCK+1). In slave mode `write` preloads the MISO buffer, `read` blocks until the master sends a frame, and `xfer` does both.

Usage (master):
```sh
replx spi open --sck GP<num> --mosi GP<num> [--miso GP<num>] [--baud N] [--mode 0-3] [--bits 8|16] [--lsb]
replx spi write HEX... [--cs GP<num>]
replx spi read NBYTES [--fill HH] [--cs GP<num>]
replx spi xfer HEX... [--cs GP<num>]
replx spi bus
replx spi close
```

Usage (slave):
```sh
replx spi open --slave --sck GP<num> --mosi GP<num> --cs GP<num> [--miso GP<num>] [--slave-buf N]
replx spi write HEX...
replx spi read [--timeout MS]
replx spi xfer HEX... [--timeout MS]
```

Options:
- `--sck`, `--mosi`: bus pins (required for `open`); `--miso`: optional, required by master `read`/`xfer`
- `--cs GP<num>`: chip select (slave: `open` only; master: `write`/`read`/`xfer` only)
- `--baud N`: master clock (default: 1000000)
- `--mode 0-3`, `--bits 8|16`, `--lsb`: master frame format (default: mode 0, 8 bits, MSB first)
- `--fill HH`: fill byte for master `read` (default: 00)
- `--text`: text mode for `write`/`xfer` (supports `\n`, `\r`, `\t`, `\\`, `\xHH`)
- `--slave`: slave mode (`open` only); `--slave-buf N`: slave RX buffer bytes (default: 8192)
- `--timeout MS`: slave `read`/`xfer` timeout (default: 10000)

Channel resolution (master): RP2350 SPI0 `GP2,GP6,GP18,GP22`, SPI1 `GP10,GP14,GP26`; ESP32 uses channel 1 for all pins.

Examples:
```sh
replx spi open --sck GP2 --mosi GP3 --miso GP4 --baud 2000000
replx spi write 01 02 03 --cs GP5
replx spi read 8 --fill FF --cs GP5
replx spi xfer --text "Ping\r\n" --cs GP5
replx spi close
replx spi open --slave --sck GP2 --mosi GP3 --cs GP5 --miso GP4
replx spi write AA BB CC
replx spi xfer AA BB CC --timeout 10000
```

#### `i2c`
Manage an I2C bus in controller or target mode. `scan` discovers devices and saves the bus; `open` saves the bus without scanning; `bus` shows it; `read`/`write` transfer data; `dump` reads a register range; `seq` runs a write+delay sequence in one board call; `close` releases the peripheral. `open --target` activates I2CTarget mode when the firmware exposes `machine.I2CTarget` (including the tested RP2350 and P4 builds), where `read`/`write`/`mem` access the target memory buffer.

Usage (controller):
```sh
replx i2c scan --sda GP<num> --scl GP<num> [--freq HZ]
replx i2c open --sda GP<num> --scl GP<num> [--freq HZ]
replx i2c read ADDR NBYTES [REG] [--addr16] [-n N --interval MS]
replx i2c write ADDR DATA... [--addr16] [-n N --interval MS]
replx i2c dump ADDR [FROM [TO]] [--addr16] [-n N --interval MS]
replx i2c seq ADDR TOKEN...
replx i2c bus
replx i2c close
```

Usage (target, requires `machine.I2CTarget`):
```sh
replx i2c open --sda GP<num> --scl GP<num> --target --addr 0xNN [--mem-size N]
replx i2c read [OFFSET [NBYTES]]
replx i2c write OFFSET HEX...
replx i2c mem [OFFSET [NBYTES]]
```

Arguments: `ADDR`, `REG`, `DATA`, `OFFSET`, and dump `FROM`/`TO` are hex (`0x` optional; dump range defaults to 00–7F); `NBYTES` is decimal. `seq` tokens are hex bytes, `u<N>` (µs delay), or `m<N>` (ms delay).

Options:
- `--sda`, `--scl`: I2C pins (required for the initial `scan`/`open` on standard boards; XBee defaults to P1/D1)
- `--freq HZ`: clock frequency (default: 400000)
- `--addr16`: 16-bit register addresses
- `--target`, `--addr 0xNN` (1–127), `--mem-size N` (default: 256): target mode (`open` only)
- `-n, --repeat N`: repeat count for `read`/`write`/`dump` (N ≥ 1, default: 1)
- `--interval MS`: delay between repeats (default: 1000, requires `-n` ≥ 2)

Board support: RP2350 `GP%4==0` → CH0, `GP%4==2` → CH1 and SCL must equal SDA+1; Teensy uses fixed Wire pairs; ESP32 uses suitable available GPIOs. Digi XBee3/EFR32MG supports controller bus 1 only, with SDA=P1 and SCL=D1; the standard pin-selection and deinit APIs are not used. Target mode requires the firmware's `machine.I2CTarget` API.

Examples:
```sh
replx i2c scan --sda GP12 --scl GP13
replx i2c read 0x68 1 75
replx i2c write 0x68 6B 00
replx i2c read 0x68 6 3B -n 5 --interval 500
replx i2c dump 0x68
replx i2c dump 0x68 3B 48
replx i2c seq 27 3C u500 38 u100 m5 3C u500 38 u100
replx i2c open --sda GP12 --scl GP13 --target --addr 0x42 --mem-size 256
replx i2c write 0x10 DE AD BE EF
replx i2c mem
replx i2c close
```

#### `i2s`
Generate tones on an I2S DAC/amplifier or capture an I2S microphone. `tone` plays a series of frequency/duration pairs (16-bit mono TX with short fade-in/out). `read` captures microphone blocks and prints RMS, peak, min/max, DC offset, and the last sample; by default it streams blocks as rows until Ctrl+C (`--repeat 0`), `--repeat N` stops after N blocks, and `--repeat 1` shows a single block as a panel. `scope` runs a board-side level history in dBFS (-60..0) and requires `termviz` on the board; `UP`/`DOWN` double or halve the gain. Every call opens and deinitializes the I2S peripheral, so no `open`/`close` is needed.

Usage:
```sh
replx i2s tone FREQ mMS [FREQ mMS ...] --sck GP<num> --ws GP<num> --sd GP<num> [--amplitude A]
replx i2s read --sck GP<num> --ws GP<num> --sd GP<num> [--repeat N] [--interval-ms MS] [--frames N]
replx i2s scope --sck GP<num> --ws GP<num> --sd GP<num> [--sample MS]
```

- `FREQ mMS`: frequency in Hz (greater than 0 and below `rate/2`) followed by a duration such as `m500` (500 ms)

Options:
- `--sck`, `--ws`, `--sd`: I2S pins (required, must be distinct)
- `--id N`: I2S peripheral id (default: 0)
- `--rate HZ`: sample rate (default: 16000, min: 1000)
- `--ibuf N`: internal buffer bytes (default: 4096, min: 256)
- `--amplitude A`: `tone` output level, 0 < A ≤ 1 (default: 0.25)
- `--rx-bits 16|32`: microphone sample width for `read`/`scope` (default: 32)
- `--gain N`: software gain for `read`/`scope`, 0 < N ≤ 256 (default: 16)
- `--repeat N`: `read` block count (0 = until Ctrl+C, default: 0)
- `--interval-ms MS` (alias `--interval`): delay between `read` blocks (default: 20)
- `--frames N`: samples per `read` block (default: 256)
- `--sample MS`: `scope` render interval (0, 1, 2, 5, 10, 20, 50, 100; default: 20)

Examples:
```sh
replx i2s tone --sck GP4 --ws GP5 --sd GP7 440 m100 660 m500
replx i2s tone --sck GP4 --ws GP5 --sd GP7 1000 m1000 --amplitude 0.5 --rate 44100
replx i2s read --sck GP4 --ws GP5 --sd GP6 --repeat 1
replx i2s read --sck GP4 --ws GP5 --sd GP6 --repeat 10 --interval-ms 100
replx i2s read --sck GP4 --ws GP5 --sd GP6 --rx-bits 16 --gain 4
replx i2s scope --sck GP4 --ws GP5 --sd GP6 --sample 50
```

#### `ws2812`
Write one pixel or a rectangular region on a WS2812 (NeoPixel) LED matrix. Each `write` sends a complete fresh frame: the selected pixels get the color and all other pixels are turned off. The backend is chosen automatically: the `neopixel` module, then an RP2 PIO state machine, then `machine.bitstream`.

Usage:
```sh
replx ws2812 write GP<num> '[POSITION]' COLOR [--width N] [--height N] [--layout row-major|serpentine] [--sm N]
```

- `POSITION`: `[x,y]` where each axis is one coordinate or a Python-style slice with an exclusive end, e.g. `[0,0]`, `[1:7,3:10]`, `[:10:2,4::3]`
- `COLOR`: decimal `R G B` (0–255 each) or hexadecimal `0xRRGGBB`

Options:
- `--width N`, `--height N`: matrix size (default: 16×16, at most 65535 pixels)
- `--layout MODE`: `row-major` (default) or `serpentine` (odd rows wired right-to-left)
- `--sm N`: RP2 PIO state machine 0–7 used when `neopixel` is unavailable (default: 0)

Examples:
```sh
replx ws2812 write GP0 '[0,0]' 255 0 0
replx ws2812 write GP0 '[1:7,3:10]' 0x00FF00
replx ws2812 write GP0 '[:10:2,4::3]' 0x0000FF --layout serpentine
replx ws2812 write GP0 '[0:8,0]' 0xFF8000 --width 8 --height 1
```

Notes:
- Quote `POSITION` in PowerShell and POSIX shells so `[...]` is not treated as a wildcard or array.
- Do not power a large LED matrix from a GPIO pin or the board's 3.3 V regulator; use a separate 5 V supply with a common ground.

#### `ble`
Manage BLE (Bluetooth Low Energy) on the board. No subcommand shows adapter info and radio state. `on`/`off` toggles the radio. `scan` runs a passive advertisement scan with a live panel. `advertise` broadcasts an advertisement packet. `server` starts a GATT server; `client` connects to a GATT server. `ping` tests connectivity without subscribing. `read`/`write` perform one-shot characteristic access. `stream send/recv` use L2CAP CoC channels. Requires `aioble` on the board (`replx mip install aioble`).

Usage:
```sh
replx ble
replx ble on|off
replx ble scan [REFRESH_MS]                # 250-2000, default: 1000
replx ble advertise DEVICE_NAME [OPTIONS]
replx ble server --svc UUID --char UUID [OPTIONS]
replx ble client ADDR/TYPE --svc UUID --char UUID [OPTIONS]
replx ble ping ADDR/TYPE
replx ble read ADDR SVC_UUID CHAR_UUID
replx ble write ADDR SVC_UUID CHAR_UUID HEX
replx ble stream send ADDR PSM HEX
replx ble stream recv PSM
```

Advertise Options:
- `--service-uuid UUID`: advertised service UUID
- `--service-data UUID:hex:DATA` / `UUID:text:TEXT`: service data bytes or UTF-8 text
- `--manufacturer-data COMPANY_ID:hex:DATA` / `COMPANY_ID:text:TEXT`: manufacturer data
- `--duration-ms MS`: advertising interval in ms (default: 1000)
- `--no-connect`: broadcaster mode (non-connectable)

Server Options:
- `--svc UUID`, `--char UUID`: service/characteristic UUID
- `--value hex:HEX` / `text:TEXT`: initial characteristic value
- `--read`, `--write`, `--notify`, `--indicate`: GATT properties
- `--notify-on-change`: auto-notify connected clients when value changes
- `--name NAME`: GAP device name (default: replx-ble)
- `--interval MS`: auto-notify interval in ms (requires `--notify`)

Client Options:
- `--svc UUID`, `--char UUID`: service/characteristic UUID to connect to
- `--value hex:HEX` / `text:TEXT`: initial value to write after connecting
- `--notify`: subscribe to notifications after connecting

Address Format: `ADDR/1` for random address, `ADDR/0` for public. Use the Type shown by `replx ble scan`.

Examples:
```sh
replx ble
replx ble on
replx ble scan
replx ble advertise ticle-lite --service-data 1010:text:hello --no-connect
replx ble ping 4D:0E:55:65:19:15/1
replx ble server --svc 1010 --char 1011 --name ticle-lite --read --write --notify --notify-on-change
replx ble client AA:BB:CC:DD:EE:FF/1 --svc 1010 --char 1011 --notify
replx ble read AA:BB:CC:DD:EE:FF/1 1010 1011
replx ble write AA:BB:CC:DD:EE:FF/1 1010 1011 0102FF
replx ble stream send AA:BB:CC:DD:EE:FF/1 80 0102FF
replx ble stream recv 80
```

Notes:
- `scan`, `advertise`, `server`, `stream recv` run until stopped (q or Ctrl+C)
- scan panel: press `s` to pause/resume, `f` to toggle named/all devices
- server panel: press `v` to switch value view, `c` to change the value
- client panel: press `r` to read, `w` to write, `n` to toggle notify

---

## Troubleshooting

#### Connection / Session

| Symptom | Likely Cause | Resolution |
|---|---|---|
| `No active connections` | `setup` not run, agent stopped | `replx scan` → `replx PORT setup` → `replx status` |
| `Not connected` | No FG in current session | Check SID with `replx status`, then run `replx fg` or `replx PORT fg` |
| Board shows busy in another terminal | Another SID has it as FG/BG | Finish work in that terminal, use `replx close` to release the board, or `replx agent disconnect IP` to remove a client |
| Port remains occupied | Agent still running | `replx close` (individual board) or `replx agent stop` (all boards on the configured agent) |
| `Connected` panel shows version `?`, then `No response from agent` | REPL baud is not one of the candidates, or the board was not running MicroPython | Check the firmware's REPL baud and set `REPLX_BAUD`; run `replx agent stop`, reset the board, and connect again |

#### Execution (`exec/run/repl/shell`)

| Symptom | Likely Cause | Resolution |
|---|---|---|
| `run` fails immediately | Wrong file path | Local file: `run file.py`; board file: `run -d /path/file.py` |
| `--non-interactive` and `--echo` conflict | Invalid option combination | Use only one of the two |
| Hard to exit REPL | Unaware of exit method | Type `exit()` or press `Ctrl+D` |
| Unexpected path in shell | Current directory confusion | Check with `pwd`, navigate with `cd` |

#### File Operations

| Symptom | Likely Cause | Resolution |
|---|---|---|
| Wildcard behaves unexpectedly | Local vs. board expansion difference | `put` expands locally; `get/rm/cp/mv` resolve patterns on the board |
| Directory copy/move fails | Missing `-r` | Use `cp -r`, `mv -r`, `rm -r` |
| Multiple sources but destination is a file | Misunderstanding of last-arg rule | The last argument is always DEST; it must be a directory for multiple sources |
| Cannot recover after deletion | No backup | Back up with `replx get` before deleting |

#### Package / Compile

| Symptom | Likely Cause | Resolution |
|---|---|---|
| `mip install` — package not found | Typo or unofficial package | Try `replx mip search NAME` to confirm exact name |
| `mip install github:org/repo` — 404 | Repo has no `package.json` | replx falls back to GitHub Pages CDN; if no CDN files exist for your arch, the package does not support your board |
| `mip install` — arch not supported | Board arch not in package's prebuilt list | Check the repo for supported architectures; use `replx -c "import sys; print(sys.implementation._mpy)"` to confirm |
| `mip install` — compile error | `mpy-cross` missing or older than the target runtime | `python -m pip install --upgrade "mpy-cross>=1.29.0"`, or use `--no-compile` to skip compilation |
| No `pkg search` results | Outside current board's core/device scope | Check board with `whoami`, switch board and search again |
| `pkg update` fails | Local store not prepared | Run `replx pkg download` first, then retry `replx pkg update ...` |
| `mpy` fails | `mpy-cross` missing or outdated | `python -m pip install --upgrade "mpy-cross>=1.29.0"` |
| Architecture error | Missing board connection info | Ensure connection is established (`setup` or auto-connect) |

#### Format / Init / Firmware

| Symptom | Likely Cause | Resolution |
|---|---|---|
| Files lost after `format/init` | Expected behavior (full wipe) | Back up with `get` before formatting; restore with `put`/`pkg update` |
| `firmware` unsupported/image-selection error | Unsupported board or unspecified P4 variant | ticle-lite/sensor use UF2; connected P4+C6 prompts for the latest Release/Preview; other P4 variants require an explicit image matching the chip revision |
| `wifi connect` fails | Wrong SSID/PW, AP not visible | `wifi scan` → re-enter credentials → try `wifi off` then retry |

#### Hardware

| Symptom | Likely Cause | Resolution |
|---|---|---|
| `open` fails with pin error | Invalid pin for the board's channel mapping | Check pin constraints: RP2350 I2C requires SCL=SDA+1; SPI slave requires MOSI=SCK+1; RP2 UART RX must be TX+1 |
| `uart read` stops after the first burst | `--timeout N` is a one-shot read | Use `uart read --timeout 0` (continuous) or `uart monitor` |
| `uart write`/`read` says the UART was opened RX-only/TX-only | The missing direction was not given to `open` | Re-open with both `--tx` and `--rx` |
| ESP32 `uart open --id 0` rejected | UART0 carries the REPL | Use `--id 1` (default) or another free UART |
| XBee3 hardware command excluded | The standard API is unavailable or this CLI feature is not implemented for Digi's legacy runtime | Use named-pin GPIO, native ADC read, or fixed-bus I2C controller commands; consult the hardware platform table |
| XBee3 compile/ABI error | Modern `mpy-cross` output is not certified for Digi's legacy/vendor ABI | Upload `.py` with `put`; `mip install` uses source mode automatically |
| P4 Wi-Fi/BLE API unavailable | Standalone P4 firmware or mismatched C6 configuration | Use a board-compatible C6 Wi-Fi/BLE build and matching coprocessor firmware |
| P4 BLE unavailable or crashes | Incompatible C6 firmware or a MicroPython image without working BLE support | Use matching C6 ESP-Hosted and P4 `C6_WIFI` firmware; check that the image supports `bluetooth.BLE` |
| P4 native USB port missing | Wrong connector/cable or firmware without native USB CDC | Use the separate 4-pin V/D-/D+/G connector and check the [P4 notes](#waveshare-esp32-p4-wifi6-notes) |
| P4 ADC scope requests pins | The implicit GP26/GP27/GP28 list is RP2-only | Pass explicit ADC-capable P4 GPIOs |
| `monitor`/`scope` shows nothing | Missing board-side library | Install `termviz` (gpio monitor, adc/i2s scope) and `ufilter` (adc scope) via `replx pkg` |
| Slave/Target mode fails | Board not supported | PIO-based slave/target modes require RP2350 or RP2040 |
| `gpio seq` reports Timeout | Read action did not complete within `--timeout` (default 100 ms) | Increase `--timeout MS` or set 0 for unlimited |
| `gpio read --timeout` rejected | `read` always waits until completion | Press Ctrl+C to cancel, or use `gpio seq` with `--timeout` |
| `i2s read` shows silence or constant values | Wrong pins, sample width, or gain | Check SCK/WS/SD wiring, try `--rx-bits 16` or `32`, and adjust `--gain` |
| `i2s` reports `machine.I2S is unavailable` | Firmware built without I2S | Use a port/firmware with `machine.I2S` |
| `ws2812` colors look wrong or shifted | Matrix size or wiring order mismatch | Set `--width`/`--height` to the real size and use `--layout serpentine` for zig-zag wiring |
| `ws2812` position error in shell | `[...]` expanded by the shell | Quote the position, e.g. `'[0,0]'` |

#### BLE

| Symptom | Likely Cause | Resolution |
|---|---|---|
| `aioble not found` | Library not installed on board | `replx mip install aioble` |
| `ble scan` shows no devices | BLE radio off or no nearby advertisers | `replx ble on`, move devices closer, check `replx ble` for radio state |
| `ble client` cannot connect | Wrong address type (random vs. public) | Use the Type shown by `replx ble scan` — `ADDR/1` (random) or `ADDR/0` (public) |
| `ble server/client` exits immediately | UUID mismatch or missing `--svc`/`--char` | Confirm UUIDs on both sides; check with `replx ble scan` |
| `ble advertise` no response | `--no-connect` set but client expects connectable | Remove `--no-connect` or use a connectable advertisement |
| `ble stream` fails | L2CAP PSM not open on the other end | Ensure `stream recv PSM` is running before `stream send` |

---
