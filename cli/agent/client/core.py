import atexit
import hashlib
import ipaddress
import locale
import os
import posixpath
import socket
import subprocess
import sys
import tempfile
import threading
import time
import warnings
from typing import Any, Callable, Dict, Optional

from replx_agent import __version__ as AGENT_VERSION
from replx_agent.commands import Cmd
from replx_agent.rpc.protocol import AgentProtocol, FrameReader, FrameType
from replx_agent.utils.constants import (
    AGENT_HOST,
    DEFAULT_AGENT_PORT,
    MAX_PAYLOAD_SIZE,
    PUTDIR_EXCLUDED_DIRS,
    PUTDIR_EXCLUDED_EXTENSIONS,
)
from replx.utils.constants import AGENT_BIND_ALL_HOST
from .session import get_cached_session_id

_INLINE_SCRIPT_LIMIT = (MAX_PAYLOAD_SIZE - 4096) // 6
_FILE_CHUNK_SIZE = 64 * 1024
_VERIFIED_AGENT_PORTS: set[tuple[str, int]] = set()
_VERIFIED_AGENT_PORTS_LOCK = threading.Lock()


class AgentClient:
    TIMEOUT = 5.0

    def __init__(self, port: int = None, device_port: str = None, host: str = None):
        from ...config import AgentPortManager

        self.agent_port = port or DEFAULT_AGENT_PORT
        self.device_port = device_port
        self.host = host or AgentPortManager._read_registered_ip() or AGENT_HOST
        self.auth_token = self._get_auth_token(self.host)
        self.sock: Optional[socket.socket] = None
        self._frame_reader: Optional[FrameReader] = None
        self._ppid = get_cached_session_id()
        self._send_lock = threading.Lock()
        self._request_lock = threading.RLock()
        self._atexit_registered = False
        self._release_on_exit = False
        self._version_checked = False
        self._agent_info: Optional[dict] = None
        self._agent_info_time = 0.0

    @staticmethod
    def _get_auth_token(host: str) -> Optional[str]:
        token = os.environ.get("REPLX_AGENT_TOKEN", "").strip()
        normalized_host = str(host).strip().lower()
        try:
            loopback = ipaddress.ip_address(normalized_host.split('%', 1)[0]).is_loopback
        except ValueError:
            loopback = normalized_host == "localhost"
        if not loopback and not token:
            raise RuntimeError(
                "Remote agent connections require REPLX_AGENT_TOKEN to be set."
            )
        return token or None

    def connect(self, timeout: float = None) -> None:
        if self.sock is None:
            connect_timeout = self.TIMEOUT if timeout is None else timeout
            try:
                sock = socket.create_connection((self.host, self.agent_port), timeout=connect_timeout)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                raise
            self.sock = sock
            self._frame_reader = FrameReader(sock)
            self._version_checked = False
            self._agent_info = None

        if not self._version_checked:
            self._check_agent_version(timeout)

        if not self._atexit_registered and self.device_port:
            atexit.register(self._atexit_release)
            self._atexit_registered = True

    def _check_agent_version(self, timeout: float = None) -> None:
        endpoint = (self.host, self.agent_port)
        with _VERIFIED_AGENT_PORTS_LOCK:
            already_verified = endpoint in _VERIFIED_AGENT_PORTS
        if already_verified:
            self._version_checked = True
            return

        self._version_checked = True
        try:
            info = self._request(Cmd.PING, None, timeout or self.TIMEOUT, {})
        except (ConnectionError, OSError, RuntimeError, ValueError):
            self.disconnect()
            raise

        if info.get("protocol_version") != 2:
            self.disconnect()
            raise RuntimeError(
                f"Incompatible replx-agent protocol: {info.get('protocol_version')!r}"
            )

        if info.get("agent_version") != AGENT_VERSION:
            self._restart_outdated_agent(info)
            return

        self._agent_info = info
        self._agent_info_time = time.monotonic()
        with _VERIFIED_AGENT_PORTS_LOCK:
            _VERIFIED_AGENT_PORTS.add(endpoint)

    def _restart_outdated_agent(self, info: dict) -> None:
        old_version = info.get("agent_version", "unknown")
        from ...config import AgentPortManager

        if not AgentPortManager._is_local_ip(self.host):
            self.disconnect()
            raise RuntimeError(
                f"Remote replx-agent {old_version} is outdated; upgrade it on "
                f"{self.host}:{self.agent_port}."
            )
        try:
            self._request(Cmd.SHUTDOWN, None, 1.0, {})
        except (ConnectionError, OSError, RuntimeError, ValueError):
            pass
        self.disconnect()
        with _VERIFIED_AGENT_PORTS_LOCK:
            _VERIFIED_AGENT_PORTS.discard((self.host, self.agent_port))

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if not self._is_tcp_port_open(self.agent_port, host=self.host):
                break
            time.sleep(0.05)
        else:
            raise RuntimeError(
                f"replx-agent {old_version} is still running on port "
                f"{self.agent_port}; stop it and retry after upgrading."
            )

        listen_host = info.get("listen_host") or self.host
        AgentClient.start_agent(port=self.agent_port, host=listen_host, _force=True)
        self.connect()

    @staticmethod
    def _is_tcp_port_open(port: int, timeout: float = 0.1, host: str = None) -> bool:
        target_host = host or AGENT_HOST
        try:
            with socket.create_connection((target_host, port), timeout=timeout):
                return True
        except OSError:
            return False

    @staticmethod
    def _probe_host(bind_host: str) -> str:
        try:
            address = ipaddress.ip_address(str(bind_host).split("%", 1)[0])
        except ValueError:
            return bind_host
        if not address.is_unspecified:
            return bind_host
        return "::1" if address.version == 6 else AGENT_HOST

    def _atexit_release(self) -> None:
        if self._release_on_exit and self.device_port:
            try:
                self._send_command(
                    Cmd.DISCONNECT_PORT,
                    timeout=1.0,
                    max_retries=1,
                    port=self.device_port,
                )
            except (OSError, RuntimeError, ValueError):
                pass
        self.disconnect()

    def disconnect(self) -> None:
        sock = self.sock
        self.sock = None
        self._frame_reader = None
        self._version_checked = False
        self._agent_info = None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

    def _send_frame(self, data: bytes) -> None:
        self.connect()
        with self._send_lock:
            sock = self.sock
            if sock is None:
                raise ConnectionError("Agent connection is closed")
            sock.sendall(data)

    def _receive_frame(self, timeout: Optional[float] = None):
        self.connect()
        reader = self._frame_reader
        if reader is None:
            raise ConnectionError("Agent connection is closed")
        raw = reader.receive(timeout)
        if raw is None:
            return None
        frame_type, seq, payload = AgentProtocol.decode_frame(raw)
        if frame_type is FrameType.JSON:
            import json

            message = json.loads(payload.decode("utf-8"))
            if not isinstance(message, dict):
                raise ValueError("Agent sent a non-object JSON frame")
            return frame_type, seq, message
        return frame_type, seq, payload

    @staticmethod
    def _print_notifications(response: Dict[str, Any]) -> None:
        for notification in response.get("notifications", ()):
            if notification:
                print(f"replx: {notification}", file=sys.stderr)

    def send_command(
        self,
        command: str,
        timeout: float = None,
        max_retries: int = None,
        wait_on_busy: float = 30.0,
        **args,
    ) -> Dict[str, Any]:
        try:
            return self._send_command(
                command, timeout, max_retries, wait_on_busy, **args
            )
        except KeyboardInterrupt:
            self._release_on_exit = True
            raise

    def _send_command(
        self,
        command: str,
        timeout: float = None,
        max_retries: int = None,
        wait_on_busy: float = 30.0,
        **args,
    ) -> Dict[str, Any]:
        timeout = timeout or self.TIMEOUT
        port = args.pop("port", None) or self.device_port

        if command in {"put_from_local", "put_from_local_streaming"}:
            file_specs = args.pop("file_specs", None)
            if file_specs:
                return self._upload_file_specs(
                    file_specs, port=port, timeout=timeout
                )
            return self._upload_file(
                args.pop("local_path", None),
                args.pop("remote_path", None),
                port=port,
                timeout=timeout,
            )
        if command in {"putdir_from_local", "putdir_from_local_streaming"}:
            return self._upload_directory(
                args.pop("local_path", None),
                args.pop("remote_path", None),
                port=port,
                timeout=timeout,
            )
        if command == "get_to_local":
            return self._download_file(
                args.pop("remote_path", None),
                args.pop("local_path", None),
                port=port,
                timeout=timeout,
            )
        if command == "getdir_to_local":
            return self._download_directory(
                args.pop("remote_path", None),
                args.pop("local_path", None),
                port=port,
                timeout=timeout,
            )
        if command == "put_file_batch" and self._has_local_file_specs(args):
            return self._upload_file_batch(args.pop("file_specs"), port, timeout)
        if command == "run" and args.get("script_path"):
            script_path = args.pop("script_path")
            return self._run_local_script(
                script_path, port=port, timeout=timeout, **args
            )
        if (
            command == "run"
            and isinstance(args.get("script_content"), str)
            and len(args["script_content"].encode("utf-8")) > _INLINE_SCRIPT_LIMIT
        ):
            content = args.pop("script_content")
            result, _seq, _completed = self._send_script_content_transfer(
                content,
                purpose="script_run",
                port=port,
                timeout=timeout,
                options=args,
            )
            return result

        busy_deadline = time.monotonic() + wait_on_busy
        while True:
            try:
                return self._request(command, port, timeout, args)
            except RuntimeError as exc:
                if (
                    "is busy. Another command" not in str(exc)
                    or time.monotonic() >= busy_deadline
                ):
                    raise
                time.sleep(1.0)

    def _request(
        self,
        command: str,
        port: str,
        timeout: float,
        args: dict,
        progress_callback: Callable[[Dict[str, Any]], None] = None,
    ) -> Dict[str, Any]:
        with self._request_lock:
            request = AgentProtocol.create_request(
                command,
                ppid=self._ppid,
                port=port,
                auth_token=self.auth_token,
                **args,
            )
            seq = request["seq"]
            self._send_frame(AgentProtocol.encode_message(request))
            result, _completed = self._wait_for_response(
                seq,
                timeout,
                progress_callback=progress_callback,
            )
            return result

    def _wait_for_response(
        self,
        seq: int,
        timeout: float,
        *,
        progress_callback: Callable[[Dict[str, Any]], None] = None,
        output_callback: Callable[[bytes, str], None] = None,
    ) -> tuple[Dict[str, Any], bool]:
        deadline = time.monotonic() + timeout
        completed = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"Agent timed out after {timeout:g}s")
            frame = self._receive_frame(remaining)
            if frame is None:
                continue
            frame_type, frame_seq, payload = frame
            if frame_seq != seq:
                continue
            if frame_type is FrameType.BINARY:
                raise RuntimeError("Unexpected binary data in a command response")

            msg_type = payload.get("type")
            if msg_type == "ack":
                continue
            if msg_type == "stream":
                if progress_callback:
                    stream_data = payload.get("data")
                    if isinstance(stream_data, dict):
                        progress_callback(stream_data)
                output = payload.get("output", "")
                if output and output_callback:
                    output_callback(output.encode("utf-8"), "stdout")
                if payload.get("completed"):
                    completed = True
                    error = payload.get("error")
                    if error and output_callback:
                        output_callback(error.encode("utf-8"), "stderr")
                continue
            if msg_type != "response":
                continue

            self._print_notifications(payload)
            if payload.get("error"):
                raise RuntimeError(payload["error"])
            return payload.get("result") or {}, completed

    def _run_local_script(
        self, script_path: str, *, port: str, timeout: float, **args
    ) -> Dict[str, Any]:
        path = os.path.abspath(script_path)
        if not os.path.isfile(path):
            raise RuntimeError(f"Local script not found: {path}")
        size = os.path.getsize(path)
        if size > _INLINE_SCRIPT_LIMIT:
            result, _seq, _completed = self._send_file_transfer(
                path,
                purpose="script_run",
                port=port,
                timeout=timeout,
                options=args,
            )
            return result
        try:
            args["script_content"] = self._read_script(path)
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(f"Could not read local script {path}: {exc}") from exc
        return self._request(Cmd.RUN, port, timeout, args)

    @staticmethod
    def _read_script(path: str) -> str:
        with open(path, "r", encoding="utf-8-sig", newline="") as file:
            return file.read()

    def run_interactive(
        self,
        script_path: str = None,
        script_content: str = None,
        echo: bool = False,
        output_callback: Callable[[bytes, str], None] = None,
        input_provider: Callable[[], Optional[bytes]] = None,
        stop_check: Callable[[], bool] = None,
        ctrl_c_grace_s: float = 3.0,
        reset: bool = True,
    ) -> Dict[str, Any]:
        with self._request_lock:
            port = self.device_port
            if script_path:
                path = os.path.abspath(script_path)
                if not os.path.isfile(path):
                    raise RuntimeError(f"Local script not found: {path}")
                if os.path.getsize(path) > _INLINE_SCRIPT_LIMIT:
                    _result, seq, completed = self._send_file_transfer(
                        path,
                        purpose="script_interactive",
                        port=port,
                        timeout=60.0,
                        options={"echo": echo, "reset": reset},
                        output_callback=output_callback,
                    )
                    if completed:
                        return {"run": True, "completed": True}
                else:
                    try:
                        script_content = self._read_script(path)
                    except (OSError, UnicodeError) as exc:
                        raise RuntimeError(
                            f"Could not read local script {path}: {exc}"
                        ) from exc
                    seq, completed = self._start_interactive(
                        port,
                        script_content,
                        echo,
                        reset,
                        output_callback,
                    )
                    if completed:
                        return {"run": True, "completed": True}
            else:
                if (
                    isinstance(script_content, str)
                    and len(script_content.encode("utf-8")) > _INLINE_SCRIPT_LIMIT
                ):
                    _result, seq, completed = self._send_script_content_transfer(
                        script_content,
                        purpose="script_interactive",
                        port=port,
                        timeout=60.0,
                        options={"echo": echo, "reset": reset},
                        output_callback=output_callback,
                    )
                else:
                    seq, completed = self._start_interactive(
                        port,
                        script_content,
                        echo,
                        reset,
                        output_callback,
                    )
                if completed:
                    return {"run": True, "completed": True}

            return self._interactive_loop(
                seq,
                port=port,
                output_callback=output_callback,
                input_provider=input_provider,
                stop_check=stop_check,
                ctrl_c_grace_s=ctrl_c_grace_s,
            )

    def _start_interactive(
        self,
        port: str,
        script_content: str,
        echo: bool,
        reset: bool,
        output_callback: Callable[[bytes, str], None],
    ) -> tuple[int, bool]:
        request = AgentProtocol.create_request(
            Cmd.RUN_INTERACTIVE,
            ppid=self._ppid,
            port=port,
            auth_token=self.auth_token,
            script_content=script_content,
            echo=echo,
            reset=reset,
        )
        seq = request["seq"]
        self._send_frame(AgentProtocol.encode_message(request))
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            frame = self._receive_frame(min(0.2, deadline - time.monotonic()))
            if frame is None:
                continue
            frame_type, frame_seq, payload = frame
            if frame_seq != seq:
                continue
            if frame_type is FrameType.BINARY:
                raise RuntimeError("Unexpected binary data during interactive startup")
            if payload.get("type") == "ack":
                return seq, False
            if payload.get("type") == "response":
                self._print_notifications(payload)
                if payload.get("error"):
                    raise RuntimeError(payload["error"])
                return seq, bool((payload.get("result") or {}).get("completed"))
            if payload.get("type") == "stream":
                completed = self._deliver_interactive_stream(
                    payload, output_callback
                )
                if completed:
                    return seq, True
                return seq, False
        raise RuntimeError("Agent did not acknowledge the interactive run")

    def _interactive_loop(
        self,
        seq: int,
        *,
        port: str,
        output_callback: Callable[[bytes, str], None],
        input_provider: Callable[[], Optional[bytes]],
        stop_check: Callable[[], bool],
        ctrl_c_grace_s: float,
    ) -> Dict[str, Any]:
        last_stream_time = time.monotonic()
        stream_timeout = 5.0
        try:
            while True:
                if stop_check and stop_check():
                    if input_provider:
                        for _ in range(16):
                            input_data = input_provider()
                            if not input_data:
                                break
                            self._send_frame(AgentProtocol.encode_message(
                                AgentProtocol.create_input(
                                    seq, input_data, ppid=self._ppid, port=port
                                )
                            ))
                    if self._wait_for_interactive_completion(
                        seq,
                        ctrl_c_grace_s,
                        output_callback,
                    ):
                        return {"run": True, "completed": True}
                    try:
                        self.send_command(Cmd.RUN_STOP, timeout=2.0, port=port)
                    except (OSError, RuntimeError, ValueError):
                        pass
                    return {"run": True, "completed": True}

                if input_provider:
                    input_data = input_provider()
                    if input_data:
                        self._send_frame(AgentProtocol.encode_message(
                            AgentProtocol.create_input(
                                seq, input_data, ppid=self._ppid, port=port
                            )
                        ))

                frame = self._receive_frame(0.01)
                if frame is None:
                    if time.monotonic() - last_stream_time > stream_timeout:
                        raise RuntimeError(
                            f"Connection lost - no data from board for {stream_timeout:g}s"
                        )
                    continue
                frame_type, frame_seq, payload = frame
                if frame_seq != seq:
                    continue
                if frame_type is FrameType.BINARY:
                    raise RuntimeError("Unexpected binary data during interactive run")
                if payload.get("type") == "stream":
                    last_stream_time = time.monotonic()
                    if self._deliver_interactive_stream(payload, output_callback):
                        return {"run": True, "completed": True}
                elif payload.get("type") == "response" and payload.get("error"):
                    raise RuntimeError(payload["error"])
        except KeyboardInterrupt:
            try:
                self.send_command(Cmd.RUN_STOP, timeout=2.0, port=port)
            except (OSError, RuntimeError, ValueError):
                pass
            raise

    @staticmethod
    def _deliver_interactive_stream(
        msg: dict,
        output_callback: Callable[[bytes, str], None],
    ) -> bool:
        output = msg.get("output", "")
        if output and output_callback:
            output_callback(output.encode("utf-8"), "stdout")
        error = msg.get("error")
        if error and output_callback:
            output_callback(error.encode("utf-8"), "stderr")
        return bool(msg.get("completed"))

    def _wait_for_interactive_completion(
        self,
        seq: int,
        grace_seconds: float,
        output_callback: Callable[[bytes, str], None],
    ) -> bool:
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            frame = self._receive_frame(min(0.1, deadline - time.monotonic()))
            if frame is None:
                continue
            frame_type, frame_seq, payload = frame
            if frame_seq != seq or frame_type is FrameType.BINARY:
                continue
            if payload.get("type") == "stream":
                if self._deliver_interactive_stream(payload, output_callback):
                    return True
        return False

    def send_command_streaming(
        self,
        command: str,
        timeout: float = None,
        progress_callback: Callable[[Dict[str, Any]], None] = None,
        **args,
    ) -> Dict[str, Any]:
        try:
            return self._send_command_streaming(
                command, timeout, progress_callback, **args
            )
        except KeyboardInterrupt:
            self._release_on_exit = True
            raise

    def _send_command_streaming(
        self,
        command: str,
        timeout: float = None,
        progress_callback: Callable[[Dict[str, Any]], None] = None,
        **args,
    ) -> Dict[str, Any]:
        timeout = timeout or 60.0
        port = args.pop("port", None) or self.device_port
        if command in {"put_from_local", "put_from_local_streaming"}:
            file_specs = args.pop("file_specs", None)
            if file_specs:
                return self._upload_file_specs(
                    file_specs,
                    port=port,
                    timeout=timeout,
                    progress_callback=progress_callback,
                )
            return self._upload_file(
                args.pop("local_path", None),
                args.pop("remote_path", None),
                port=port,
                timeout=timeout,
                progress_callback=progress_callback,
            )
        if command in {"putdir_from_local", "putdir_from_local_streaming"}:
            return self._upload_directory(
                args.pop("local_path", None),
                args.pop("remote_path", None),
                port=port,
                timeout=timeout,
                progress_callback=progress_callback,
            )
        if command == "get_to_local":
            return self._download_file(
                args.pop("remote_path", None),
                args.pop("local_path", None),
                port=port,
                timeout=timeout,
                progress_callback=progress_callback,
            )
        if command == "getdir_to_local":
            return self._download_directory(
                args.pop("remote_path", None),
                args.pop("local_path", None),
                port=port,
                timeout=timeout,
                progress_callback=progress_callback,
            )
        return self._request(
            command, port, timeout, args, progress_callback=progress_callback
        )

    def _send_file_transfer(
        self,
        local_path: str,
        *,
        purpose: str,
        port: str,
        timeout: float,
        remote_path: str = None,
        options: Optional[dict] = None,
        progress_callback: Callable[[Dict[str, Any]], None] = None,
        output_callback: Callable[[bytes, str], None] = None,
    ) -> tuple[Dict[str, Any], int, bool]:
        if not local_path or not os.path.isfile(local_path):
            raise RuntimeError(f"Local file not found: {local_path}")

        size = os.path.getsize(local_path)
        if purpose == "firmware":
            request = AgentProtocol.create_request(
                Cmd.FIRMWARE_STAGE,
                ppid=self._ppid,
                port=port,
                auth_token=self.auth_token,
                file_name=os.path.basename(local_path),
                size=size,
            )
        else:
            transfer_args = {
                "purpose": purpose,
                "file_name": os.path.basename(local_path),
                "size": size,
                **(options or {}),
            }
            if remote_path is not None:
                transfer_args["remote_path"] = remote_path
            request = AgentProtocol.create_request(
                Cmd.TRANSFER_START,
                ppid=self._ppid,
                port=port,
                auth_token=self.auth_token,
                **transfer_args,
            )

        seq = request["seq"]
        request_sent = False
        end_sent = False
        with self._request_lock:
            try:
                self._send_frame(AgentProtocol.encode_message(request))
                request_sent = True
                self._wait_for_transfer_ack(
                    seq, timeout, progress_callback, output_callback
                )

                sent = 0
                digest = hashlib.sha256()
                with open(local_path, "rb") as file:
                    while chunk := file.read(_FILE_CHUNK_SIZE):
                        self._send_frame(AgentProtocol.encode_binary(seq, chunk))
                        digest.update(chunk)
                        sent += len(chunk)
                        if progress_callback:
                            progress_callback({
                                "current": sent,
                                "total": size,
                                "bytes": sent,
                                "file": os.path.basename(local_path),
                                "status": "sending",
                            })

                if sent != size or os.path.getsize(local_path) != size:
                    raise RuntimeError("Local file changed during transfer")

                self._send_frame(AgentProtocol.encode_message({
                    "seq": seq,
                    "type": "transfer_end",
                    "size": sent,
                    "sha256": digest.hexdigest(),
                }))
                end_sent = True
                result, completed = self._wait_for_response(
                    seq,
                    timeout,
                    progress_callback=progress_callback,
                    output_callback=output_callback,
                )
                return result, seq, completed
            except Exception:
                if request_sent and not end_sent:
                    self._abort_transfer(seq)
                raise

    def _send_script_content_transfer(
        self,
        content: str,
        *,
        purpose: str,
        port: str,
        timeout: float,
        options: Optional[dict] = None,
        output_callback: Callable[[bytes, str], None] = None,
    ) -> tuple[Dict[str, Any], int, bool]:
        descriptor, path = tempfile.mkstemp(
            prefix="replx-inline-", suffix=".py"
        )
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(content.encode("utf-8"))
            return self._send_file_transfer(
                path,
                purpose=purpose,
                port=port,
                timeout=timeout,
                options=options,
                output_callback=output_callback,
            )
        finally:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass

    def _wait_for_transfer_ack(
        self,
        seq: int,
        timeout: float,
        progress_callback: Callable[[Dict[str, Any]], None],
        output_callback: Callable[[bytes, str], None],
    ) -> None:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Agent did not acknowledge file transfer")
            frame = self._receive_frame(remaining)
            if frame is None:
                continue
            frame_type, frame_seq, payload = frame
            if frame_seq != seq:
                continue
            if frame_type is FrameType.BINARY:
                raise RuntimeError("Agent sent binary data before upload began")
            if payload.get("type") == "ack":
                return
            if payload.get("type") == "stream":
                if progress_callback and isinstance(payload.get("data"), dict):
                    progress_callback(payload["data"])
                output = payload.get("output", "")
                if output and output_callback:
                    output_callback(output.encode("utf-8"), "stdout")
                continue
            if payload.get("type") == "response":
                self._print_notifications(payload)
                if payload.get("error"):
                    raise RuntimeError(payload["error"])
                raise RuntimeError("Agent completed transfer setup without an ACK")

    def _abort_transfer(self, seq: int) -> None:
        try:
            self._send_frame(AgentProtocol.encode_message({
                "seq": seq,
                "type": "transfer_abort",
                "error": "Client cancelled transfer",
            }))
        except OSError:
            pass

    def _upload_file(
        self,
        local_path: str,
        remote_path: str,
        *,
        port: str,
        timeout: float,
        progress_callback: Callable[[Dict[str, Any]], None] = None,
    ) -> Dict[str, Any]:
        if not remote_path:
            raise ValueError("Remote file path is required")
        result, _seq, _completed = self._send_file_transfer(
            os.path.abspath(local_path) if local_path else local_path,
            purpose="put",
            port=port,
            timeout=timeout,
            remote_path=remote_path,
            progress_callback=progress_callback,
        )
        return result

    def _upload_directory(
        self,
        local_path: str,
        remote_path: str,
        *,
        port: str,
        timeout: float,
        progress_callback: Callable[[Dict[str, Any]], None] = None,
    ) -> Dict[str, Any]:
        if not local_path or not os.path.isdir(local_path):
            raise RuntimeError(f"Local directory not found: {local_path}")
        if not remote_path:
            raise ValueError("Remote directory path is required")

        base_local = os.path.abspath(local_path)
        base_remote = remote_path.replace("\\", "/").rstrip("/") or "/"
        files = []
        directories = set()
        for parent, child_dirs, child_files in os.walk(
            base_local, followlinks=False
        ):
            child_dirs[:] = [
                name for name in child_dirs
                if name.lower() not in PUTDIR_EXCLUDED_DIRS
                and not os.path.islink(os.path.join(parent, name))
            ]
            relative = os.path.relpath(parent, base_local).replace("\\", "/")
            remote_dir = posixpath.normpath(
                posixpath.join(base_remote, "" if relative == "." else relative)
            )
            directories.add(remote_dir)
            for name in child_files:
                local_file = os.path.join(parent, name)
                if os.path.islink(local_file):
                    continue
                extension = os.path.splitext(name)[1].lower()
                if extension in PUTDIR_EXCLUDED_EXTENSIONS:
                    continue
                files.append((
                    local_file,
                    posixpath.join(remote_dir, name),
                    name,
                ))

        for directory in sorted(directories, key=lambda path: path.count("/")):
            exists = self.send_command(
                "is_dir", path=directory, port=port, timeout=timeout
            )
            if not exists.get("is_dir"):
                self.send_command("mkdir", path=directory, port=port, timeout=timeout)

        total = len(files)
        for index, (local_file, remote_file, name) in enumerate(files, start=1):
            if progress_callback:
                progress_callback({
                    "current": index - 1,
                    "total": total,
                    "file": name,
                    "status": "uploading",
                })
            self._upload_file(
                local_file,
                remote_file,
                port=port,
                timeout=timeout,
            )
            if progress_callback:
                progress_callback({
                    "current": index,
                    "total": total,
                    "file": name,
                    "status": "uploading",
                })

        return {
            "uploaded_dir": remote_path,
            "files_count": total,
            "success": True,
        }

    def _download_file(
        self,
        remote_path: str,
        local_path: str,
        *,
        port: str,
        timeout: float,
        progress_callback: Callable[[Dict[str, Any]], None] = None,
    ) -> Dict[str, Any]:
        if not remote_path:
            raise ValueError("Remote file path is required")
        if not local_path:
            raise ValueError("Local destination path is required")

        destination = os.path.abspath(local_path)
        parent = os.path.dirname(destination) or os.getcwd()
        os.makedirs(parent, exist_ok=True)
        descriptor, temp_path = tempfile.mkstemp(
            prefix=".replx-", suffix=".tmp", dir=parent
        )
        os.close(descriptor)
        request = AgentProtocol.create_request(
            Cmd.GET_FILE_STREAMING,
            ppid=self._ppid,
            port=port,
            auth_token=self.auth_token,
            remote_path=remote_path,
        )
        seq = request["seq"]
        digest = hashlib.sha256()
        received = 0
        response = None

        with self._request_lock:
            try:
                self._send_frame(AgentProtocol.encode_message(request))
                deadline = time.monotonic() + timeout
                with open(temp_path, "wb") as file:
                    while response is None:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise RuntimeError(f"Agent timed out after {timeout:g}s")
                        frame = self._receive_frame(remaining)
                        if frame is None:
                            continue
                        frame_type, frame_seq, payload = frame
                        if frame_seq != seq:
                            continue
                        if frame_type is FrameType.BINARY:
                            file.write(payload)
                            digest.update(payload)
                            received += len(payload)
                            continue
                        msg_type = payload.get("type")
                        if msg_type == "stream":
                            if progress_callback and isinstance(payload.get("data"), dict):
                                progress_callback(payload["data"])
                        elif msg_type == "response":
                            response = payload

                self._print_notifications(response)
                if response.get("error"):
                    raise RuntimeError(response["error"])
                result = response.get("result") or {}
                if (
                    result.get("size") != received
                    or result.get("sha256") != digest.hexdigest()
                ):
                    raise RuntimeError("Downloaded file failed size or SHA-256 verification")
                os.replace(temp_path, destination)
                return {
                    "downloaded": remote_path,
                    "local_path": destination,
                    "bytes": received,
                    "success": True,
                }
            except Exception:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass
                raise

    def _download_directory(
        self,
        remote_path: str,
        local_path: str,
        *,
        port: str,
        timeout: float,
        progress_callback: Callable[[Dict[str, Any]], None] = None,
    ) -> Dict[str, Any]:
        if not remote_path or not local_path:
            raise ValueError("Remote directory and local destination are required")

        listing = self.send_command(
            "ls_recursive", path=remote_path, port=port, timeout=timeout
        )
        items = listing.get("items", [])
        base = posixpath.normpath(
            "/" + remote_path.replace("\\", "/").lstrip("/")
        )
        destination_root = os.path.abspath(local_path)
        os.makedirs(destination_root, exist_ok=True)
        files = [item for item in items if not item.get("is_dir")]
        total = len(files)
        completed = 0

        for item in items:
            listed_name = str(item.get("name") or "").replace("\\", "/")
            if listed_name.startswith("/"):
                remote_file = posixpath.normpath(listed_name)
            else:
                remote_file = posixpath.normpath(
                    posixpath.join(base, listed_name)
                )
            try:
                if posixpath.commonpath((base, remote_file)) != base:
                    raise RuntimeError(
                        f"Agent returned a path outside {remote_path}: {listed_name}"
                    )
            except ValueError as exc:
                raise RuntimeError(
                    f"Agent returned an invalid path: {listed_name}"
                ) from exc

            relative = posixpath.relpath(remote_file, base)
            if relative == "." and not item.get("is_dir"):
                relative = posixpath.basename(remote_file)
            if relative == ".." or relative.startswith("../"):
                raise RuntimeError(f"Agent returned a path outside {remote_path}: {listed_name}")

            local_file = os.path.abspath(
                os.path.join(destination_root, *relative.split("/"))
            )
            if os.path.commonpath((destination_root, local_file)) != destination_root:
                raise RuntimeError(
                    f"Agent returned a path outside {remote_path}: {listed_name}"
                )
            if item.get("is_dir"):
                os.makedirs(local_file, exist_ok=True)
                continue

            if progress_callback:
                progress_callback({
                    "current": completed,
                    "total": total,
                    "file": posixpath.basename(relative),
                    "status": "downloading",
                })
            self._download_file(
                remote_file,
                local_file,
                port=port,
                timeout=timeout,
                progress_callback=None,
            )
            completed += 1
            if progress_callback:
                progress_callback({
                    "current": completed,
                    "total": total,
                    "file": posixpath.basename(relative),
                    "status": "downloading",
                })

        return {
            "downloaded_dir": remote_path,
            "local_path": destination_root,
            "files_count": completed,
            "success": True,
        }

    @staticmethod
    def _has_local_file_specs(args: dict) -> bool:
        specs = args.get("file_specs")
        return isinstance(specs, list) and any(
            isinstance(spec, dict) and spec.get("local_path")
            for spec in specs
        )

    def _upload_file_specs(
        self,
        file_specs: list,
        *,
        port: str,
        timeout: float,
        progress_callback: Callable[[Dict[str, Any]], None] = None,
    ) -> Dict[str, Any]:
        if not isinstance(file_specs, list) or not file_specs:
            raise ValueError("file_specs must be a non-empty list")

        sized_specs = []
        total_bytes = 0
        for spec in file_specs:
            local_path = spec.get("local_path") if isinstance(spec, dict) else None
            remote_path = spec.get("remote_path") if isinstance(spec, dict) else None
            if not local_path or not os.path.isfile(local_path):
                raise RuntimeError(f"Local file not found: {local_path}")
            if not remote_path:
                raise ValueError("Remote file path is required")
            size = os.path.getsize(local_path)
            sized_specs.append((os.path.abspath(local_path), remote_path, size))
            total_bytes += size

        completed_bytes = 0
        for local_path, remote_path, size in sized_specs:
            per_file_callback = None
            if progress_callback:
                base = completed_bytes
                file_name = os.path.basename(local_path)

                def per_file_callback(data, _base=base, _file=file_name):
                    current = data.get("current", 0) if isinstance(data, dict) else 0
                    progress_callback({
                        "current": _base + current,
                        "total": total_bytes,
                        "file": _file,
                        "status": "uploading",
                    })

            self._upload_file(
                local_path,
                remote_path,
                port=port,
                timeout=timeout,
                progress_callback=per_file_callback,
            )
            completed_bytes += size
            if progress_callback:
                progress_callback({
                    "current": completed_bytes,
                    "total": total_bytes,
                    "file": os.path.basename(local_path),
                    "status": "uploading",
                })

        return {
            "success": True,
            "files_count": len(sized_specs),
            "bytes": total_bytes,
        }

    def _upload_file_batch(
        self, file_specs: list, port: str, timeout: float
    ) -> Dict[str, Any]:
        results = []
        for spec in file_specs:
            local_path = spec.get("local_path")
            remote_path = spec.get("remote_path")
            try:
                result = self._upload_file(
                    local_path, remote_path, port=port, timeout=timeout
                )
                results.append({
                    "path": remote_path,
                    "success": True,
                    "result": result,
                })
            except (OSError, RuntimeError, ValueError) as exc:
                results.append({
                    "path": remote_path,
                    "success": False,
                    "error": str(exc),
                })
        return {
            "results": results,
            "success_count": sum(1 for result in results if result["success"]),
            "total": len(file_specs),
        }

    def stage_firmware(self, image_path: str, timeout: float = 300.0) -> Dict[str, Any]:
        result, _seq, _completed = self._send_file_transfer(
            os.path.abspath(image_path),
            purpose="firmware",
            port=None,
            timeout=timeout,
        )
        return result

    def firmware_info(self, stage_id: str, timeout: float = 30.0) -> Dict[str, Any]:
        return self.send_command(
            Cmd.FIRMWARE_INFO, stage_id=stage_id, timeout=timeout
        )

    def firmware_flash(
        self,
        stage_id: str,
        port: str,
        baud: int,
        erase: bool,
        timeout: float = 300.0,
    ) -> Dict[str, Any]:
        return self.send_command(
            Cmd.FIRMWARE_FLASH,
            stage_id=stage_id,
            port=port,
            baud=baud,
            erase=erase,
            timeout=timeout,
        )

    def discard_firmware(self, stage_id: str) -> Dict[str, Any]:
        return self.send_command(Cmd.FIRMWARE_DISCARD, stage_id=stage_id)

    def ping(self, timeout: float = 0.3) -> bool:
        try:
            if self.sock is None:
                self.connect(timeout=timeout)
            if (
                self._agent_info is not None
                and time.monotonic() - self._agent_info_time <= min(timeout, 0.1)
            ):
                return (
                    self._agent_info.get("pong", False)
                    and self._agent_info.get("protocol_version") == 2
                )
            result = self.send_command(Cmd.PING, timeout=timeout)
            if result.get("protocol_version") != 2:
                return False
            if result.get("agent_version") != AGENT_VERSION:
                self._restart_outdated_agent(result)
                return self.ping(timeout=timeout)
            return (
                result.get("pong", False)
            )
        except (OSError, RuntimeError, ValueError):
            return False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.disconnect()

    @staticmethod
    def is_agent_running(port: int = None, timeout: float = 0.2, host: str = None) -> bool:
        client = None
        try:
            client = AgentClient(port=port, host=host)
            return client.ping(timeout=timeout)
        except (OSError, RuntimeError, ValueError):
            return False
        finally:
            if client is not None:
                client.disconnect()

    @staticmethod
    def start_agent(
        port: int = None,
        background: bool = True,
        host: str = None,
        _force: bool = False,
    ) -> bool:
        from ...config import AgentPortManager

        agent_host = host or AgentPortManager._read_registered_ip() or AGENT_HOST
        agent_port = port or DEFAULT_AGENT_PORT
        auth_token = AgentClient._get_auth_token(agent_host)
        if host is None and auth_token:
            try:
                default_host_is_loopback = ipaddress.ip_address(
                    str(agent_host).split("%", 1)[0]
                ).is_loopback
            except ValueError:
                default_host_is_loopback = str(agent_host).strip().lower() == "localhost"
            if default_host_is_loopback:
                agent_host = AGENT_BIND_ALL_HOST
                AgentClient._get_auth_token(agent_host)
        if not AgentPortManager._is_local_ip(agent_host):
            raise ValueError(f"Cannot start an agent on non-local IP {agent_host}.")
        probe_host = AgentClient._probe_host(agent_host)
        if not _force and AgentClient.is_agent_running(port=agent_port, host=probe_host):
            return False

        python_exe = sys.executable
        command = [python_exe, "-m", "replx_agent", str(agent_port), "--host", agent_host]

        stderr_path = None
        stderr_file = None
        process = None
        if background:
            try:
                descriptor, stderr_path = tempfile.mkstemp(
                    prefix="replx_agent_", suffix=".err"
                )
                os.close(descriptor)
                stderr_file = open(stderr_path, "wb")
            except OSError:
                stderr_path = None
                stderr_file = None

            options = {
                "stdout": subprocess.DEVNULL,
                "stderr": stderr_file or subprocess.DEVNULL,
                "stdin": subprocess.DEVNULL,
            }
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                options["startupinfo"] = startupinfo
                options["creationflags"] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.CREATE_NO_WINDOW
                )
            else:
                options["start_new_session"] = True
                options["close_fds"] = True
            try:
                process = subprocess.Popen(command, **options)
            finally:
                if stderr_file:
                    stderr_file.close()
        else:
            process = subprocess.Popen(command)

        try:
            for _ in range(100):
                time.sleep(0.1)
                if process is not None and process.poll() is not None:
                    detail = ""
                    if stderr_path:
                        try:
                            encoding = locale.getpreferredencoding(False) or "utf-8"
                            with open(stderr_path, "rb") as file:
                                detail = file.read().decode(
                                    encoding, errors="replace"
                                ).strip()
                        except OSError:
                            pass
                    message = (
                        f"Failed to start agent (process exited with code "
                        f"{process.returncode})"
                    )
                    if detail:
                        message += f"\n{detail}"
                    raise RuntimeError(message)
                if AgentClient.is_agent_running(port=agent_port, timeout=0.1, host=probe_host):
                    if process is not None:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", ResourceWarning)
                            process = None
                    return True
        finally:
            if stderr_path:
                try:
                    os.unlink(stderr_path)
                except OSError:
                    pass
        raise RuntimeError("Failed to start agent (timeout)")

    @staticmethod
    def stop_agent(port: int = None, timeout: float = 0.7, host: str = None) -> bool:
        if not AgentClient.is_agent_running(port=port, timeout=0.1, host=host):
            return False
        try:
            with AgentClient(port=port, host=host) as client:
                client.send_command(Cmd.SHUTDOWN, timeout=0.5)
        except (OSError, RuntimeError, ValueError):
            pass

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.05)
            if not AgentClient.is_agent_running(port=port, timeout=0.05, host=host):
                return True
        return not AgentClient.is_agent_running(port=port, timeout=0.05, host=host)
