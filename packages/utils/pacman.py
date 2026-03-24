from pathlib import Path
from shlex import quote

from utils import process


class Pacman:

    def __init__(self, binary: str = '/usr/bin/pacman'):
        self.binary = Path(quote(binary))

    async def install(self, packages: list[str], needed: bool = True):
        flags = ['-S', '--noconfirm']
        if needed:
            flags.append('--needed')
        flags.extend(packages)
        return await self._run(flags, 'Install failed')

    async def remove(self, packages: list[str], purge: bool = False):
        flags = ['-Rc' + ('n' if purge else ''), '--noconfirm']
        flags.extend(packages)
        return await self._run(flags, 'Remove failed')

    async def upgrade(self, packages: list[str] = []):
        if packages:
            return await self.install(packages)
        return await self._run(['-Su', '--noconfirm'], 'Upgrade failed')

    async def refresh(self):
        return await self._run(['-Sy', '--noconfirm'], 'Refresh failed')

    async def _run(self, flags: list[str], error_msg: str = 'Pacman failed'):
        async with process([str(self.binary)] + flags) as proc:
            stdout = await proc.stdout.read()
            stderr = await proc.stderr.read()
            code = await proc.wait()
        if code != 0:
            raise RuntimeError(f'{error_msg}: {stderr}')
        return type('Result', (), {
            'stdout': stdout,
            'stderr': stderr,
            'code': code
        })()
