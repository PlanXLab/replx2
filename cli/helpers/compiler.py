import os
import hashlib
import subprocess
import sys

import typer

from . import get_global_context
from .store import StoreManager
from replx.utils.exceptions import CompilationError, ValidationError
from replx.utils.device_info import normalize_core, normalize_version


class CompilerHelper:
    _compile_cache = {}
    _XBEE_COMPILER_RELEASES = (
        ((1, 23, 0), "1.23", 6),
        ((1, 22, 0), "1.22", 6),
        ((1, 20, 0), "1.20.0", 6),
        ((1, 19, 0), "1.19", 6),
        ((1, 12, 0), "1.12", 5),
        ((1, 11, 0), "1.11", 4),
        ((1, 9, 3), "1.9.3", 3),
        ((1, 9, 0), "1.9", 2),
    )

    @staticmethod
    def _run_mpy_cross(
        args: list[str],
        source_path: str,
        compat_version: str = None,
    ) -> None:
        try:
            import mpy_cross
        except ImportError as e:
            raise CompilationError("mpy-cross is not installed") from e

        try:
            if compat_version:
                proc = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "mpy_cross",
                        "--compat",
                        compat_version,
                        *args,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            else:
                proc = mpy_cross.run(
                    *args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
        except Exception as e:
            raise CompilationError(f"MPY compilation failed for {source_path}: {e}") from e

        stdout = ""
        stderr = ""
        returncode = 0

        if hasattr(proc, "communicate"):
            stdout, stderr = proc.communicate()
            returncode = proc.returncode or 0

        if returncode != 0:
            details = (stderr or stdout or f"mpy-cross exited with code {returncode}").strip()
            raise CompilationError(f"MPY compilation failed for {source_path}: {details}")

    @classmethod
    def _xbee_compiler_profile(cls, version: str) -> tuple[str, int, list[str]]:
        normalized = normalize_version(version)
        if normalized == "?":
            raise CompilationError(
                "XBee3 .mpy compilation requires the connected firmware's "
                "MicroPython version."
            )

        try:
            parts = tuple(int(part) for part in normalized.split("."))
        except ValueError as e:
            raise CompilationError(
                f"Unsupported XBee3 MicroPython version: {version!r}"
            ) from e

        newest = cls._XBEE_COMPILER_RELEASES[0][0]
        if parts > newest:
            raise CompilationError(
                f"XBee3 MicroPython {normalized} is newer than the supported "
                f"compiler range (newest supported: {cls._XBEE_COMPILER_RELEASES[0][1]})."
            )

        for minimum, compiler_version, bytecode_version in cls._XBEE_COMPILER_RELEASES:
            if parts >= minimum:
                args = ["-msmall-int-bits=31"]
                if minimum >= (1, 12, 0):
                    args.insert(0, "-march=xtensawin")
                if minimum < (1, 19, 0):
                    args.append("-mno-unicode")
                return compiler_version, bytecode_version, args

        oldest = cls._XBEE_COMPILER_RELEASES[-1][1]
        raise CompilationError(
            f"XBee3 MicroPython {normalized} is older than the supported "
            f"compiler range (oldest supported: {oldest})."
        )

    @classmethod
    def compiler_staging_tag(cls, core: str, version: str) -> str:
        normalized_core = normalize_core(core)
        if normalized_core != "EFR32MG":
            return cls.mpy_arch_tag()
        compiler_version, bytecode_version = cls._xbee_compiler_profile(version)[:2]
        return f"{normalized_core}-mpy{bytecode_version}-cross{compiler_version}"

    @staticmethod
    def _validate_xbee_output(out_mpy: str, bytecode_version: int) -> None:
        try:
            with open(out_mpy, "rb") as compiled:
                header = compiled.read(4)
        except OSError as e:
            raise CompilationError(f"Cannot read compiled output: {out_mpy}") from e

        if (
            len(header) != 4
            or header[0] != ord("M")
            or header[1] != bytecode_version
            or header[3] != 31
        ):
            actual = header.hex(" ") or "<empty>"
            raise CompilationError(
                f"XBee3 compiler produced an incompatible .mpy header "
                f"(expected bytecode {bytecode_version}, small-int 31; got {actual})."
            )

    @classmethod
    def compile_file(cls, abs_py: str, out_mpy: str, core: str, version: str) -> str:
        if not os.path.exists(abs_py):
            raise ValidationError(f"Source file not found: {abs_py}")

        normalized_core = normalize_core(core)
        compat_version = None
        bytecode_version = None
        if normalized_core == "EFR32MG":
            compat_version, bytecode_version, arch_args = cls._xbee_compiler_profile(version)
        else:
            arch_args = cls._march_for_core(core, version or "1.29.0")

        out_dir = os.path.dirname(out_mpy)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        args = [abs_py, '-o', out_mpy]
        args.extend(arch_args)
        cls._run_mpy_cross(args, abs_py, compat_version=compat_version)

        if os.path.exists(out_mpy) and os.path.getsize(out_mpy) > 0:
            if bytecode_version is not None:
                cls._validate_xbee_output(out_mpy, bytecode_version)
            return out_mpy

        raise CompilationError(f"Compilation failed: {out_mpy} not found or empty")
    
    @staticmethod
    def mpy_arch_tag() -> str:
        _core, _device, _version, _device_root_fs, _device_path = get_global_context()
        if not _core:
            return "unknown"
        if "/" in _core:
            return _core.split("/", 1)[0]
        return _core
    
    @staticmethod
    def staging_out_for(abs_py: str, base: str, arch_tag: str) -> str:
        rel = os.path.relpath(abs_py, base).replace("\\", "/")
        rel_mpy = os.path.splitext(rel)[0] + ".mpy"
        out_path = StoreManager.HOME_STAGING / arch_tag / rel_mpy
        out_path.parent.mkdir(parents=True, exist_ok=True)
        return str(out_path)
    
    @staticmethod
    def _compute_file_hash(filepath: str) -> str:
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    @staticmethod
    def _march_for_core(core: str, version: str) -> list[str]:
        if not core:
            raise typer.BadParameter("The core is unknown")

        if "/" in core:
            core = core.split("/", 1)[0]

        args: list[str] = ['-msmall-int-bits=31']

        if core == "EFR32MG":
            return CompilerHelper._xbee_compiler_profile(version)[2]

        if core in ("ESP32", "ESP32S2"):
            args.append('-march=xtensa')
            return args

        if core == "ESP32S3":
            args.append('-march=xtensawin')
            return args

        if core.startswith("ESP32C"):
            args.append('-march=rv32imc')
            return args

        if core.startswith("ESP32P"):
            args.append('-march=rv32imc')
            return args

        if core == "RP2350":
            args.append('-march=armv7emsp')
            return args

        raise typer.BadParameter(f"The {core} is not supported")
    
    @classmethod
    def compile_to_staging(cls, abs_py: str, base: str) -> str:
        _core, _device, _version, _device_root_fs, _device_path = get_global_context()
        
        if not os.path.exists(abs_py):
            raise ValidationError(f"Source file not found: {abs_py}")
        
        arch_tag = cls.compiler_staging_tag(_core, _version)
        out_mpy = cls.staging_out_for(abs_py, base, arch_tag)
        
        cache_key = (abs_py, arch_tag, normalize_version(_version))
        current_hash = cls._compute_file_hash(abs_py)
        
        if cache_key in cls._compile_cache:
            cached_hash, cached_out = cls._compile_cache[cache_key]
            if cached_hash == current_hash and os.path.exists(cached_out) and os.path.getsize(cached_out) > 0:
                return cached_out

        cls.compile_file(abs_py, out_mpy, _core, _version or "1.29.0")
        cls._compile_cache[cache_key] = (current_hash, out_mpy)
        return out_mpy
