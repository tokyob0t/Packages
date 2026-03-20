from gi.events import GLibEventLoopPolicy
from gi.repository import Gio, GLib, GObject


class EasyDataInputStream(Gio.DataInputStream):

    @staticmethod
    def new(base_stream: Gio.InputStream):
        return EasyDataInputStream(base_stream=base_stream)

    async def read(self, chunk_size: int = -1):
        if chunk_size == -1:
            data: list[str] = []

            gbytes: GLib.Bytes = await self.get_base_stream().read_bytes_async(
                self.get_buffer_size(), GLib.PRIORITY_DEFAULT)

            while gbytes.get_size() > 0:
                data.append(gbytes.get_data().decode(errors="replace"))

                gbytes = await self.get_base_stream().read_bytes_async(
                    self.get_buffer_size(), GLib.PRIORITY_DEFAULT)

            return "".join(data)

        gbytes: GLib.Bytes = await self.get_base_stream().read_bytes_async(
            chunk_size, GLib.PRIORITY_DEFAULT)

        return gbytes.get_data().decode(errors="replace")

    async def read_lines(self):
        lines = []
        async for line in self:
            lines.append(line)

        return lines

    async def readline(self):
        gbytes, _ = await self.read_line_async(GLib.PRIORITY_DEFAULT, None)

        return gbytes.decode(errors="replace")

    def __aiter__(self):
        return self

    async def __anext__(self):
        gbytes, count = await self.read_line_async(GLib.PRIORITY_DEFAULT, None)

        if count == 0:
            raise StopAsyncIteration
        return gbytes.decode(errors="replace")


class Process:

    def __init__(
        self,
        argv: str | list[str],
        flags: Gio.SubprocessFlags = Gio.SubprocessFlags.STDOUT_PIPE
        | Gio.SubprocessFlags.STDERR_PIPE,
    ):
        if isinstance(argv, str):
            ok, argv = GLib.shell_parse_argv(argv)

        self.subprocess: Gio.Subprocess = Gio.Subprocess.new(argv=argv,
                                                             flags=flags)
        self._stdout: EasyDataInputStream = None
        self._stderr: EasyDataInputStream = None
        self._stdin: Gio.DataOutputStream = None

    @property
    def stdout(self) -> EasyDataInputStream:
        if self._stdout is None:
            self._stdout = EasyDataInputStream.new(
                self.subprocess.get_stdout_pipe())
        return self._stdout

    @property
    def stderr(self) -> EasyDataInputStream:
        if self._stderr is None:
            self._stderr = EasyDataInputStream.new(
                self.subprocess.get_stderr_pipe())
        return self._stderr

    @property
    def stdin(self) -> Gio.DataOutputStream:
        if self._stdin is None:
            self._stdin = EasyDataInputStream.new(
                self.subprocess.get_stdin_pipe())
        return self._stdin

    @property
    def pid(self):
        return self.subprocess.get_identifier()

    async def wait(self):
        return await self.subprocess.wait_async()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        ...
