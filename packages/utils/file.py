import gi
from gi.repository import Gio, GLib


class File:

    def __init__(self, path: str, mode: str) -> None:
        self.gfile: Gio.File = Gio.File.new_for_path(path)
        self.append_stream: Gio.FileOutputStream | None = None
        self.mode = mode

    async def write(self, contents: bytes | str) -> None:
        path = GLib.path_get_dirname(self.gfile.get_path())

        if not GLib.file_test(path, GLib.FileTest.IS_DIR):
            Gio.File.new_for_path(path).make_directory_with_parents()

        if isinstance(contents, str):
            contents = contents.encode("utf-8")

        if "a" in self.mode:
            self.append_stream = await self.gfile.append_to_async(
                Gio.FileCreateFlags.REPLACE_DESTINATION,
                GLib.PRIORITY_DEFAULT,
            )
            return await self.append_stream.write_bytes_async(
                GLib.Bytes.new(contents), GLib.PRIORITY_DEFAULT)

        elif "w" in self.mode:
            return await self.gfile.replace_contents_async(
                contents,
                None,
                False,
                Gio.FileCreateFlags.REPLACE_DESTINATION,
            )

        raise IOError("File not opened for writing")

    async def read(self) -> str:
        if "r" in self.mode:
            _, contents, _ = await self.gfile.load_contents_async()

            return contents.decode("utf-8")

        raise IOError("File not opened for reading")

    async def readLines(self) -> list[str]:
        return (await self.read()).splitlines()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.gfile:
            ...

        if self.append_stream:
            await self.append_stream.close_async(GLib.PRIORITY_DEFAULT)
