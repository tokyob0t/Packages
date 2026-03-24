import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import aiosqlite
from gi.repository import Gio, GLib
from pyalpm import DB, Handle, Package
from pypika import NULL, Column, Index, Order, Parameter
from pypika import SQLLiteQuery as Query
from pypika import Table
from utils.requests import Requests as requests

CACHE_DIR = os.path.expanduser('~/.cache/packages')
DATABASE_PATH = os.path.join(CACHE_DIR, 'packages.db')

OFFICIAL_REPOSITORIES = {'core', 'extra', 'community'}

FOSS = {
    'mit', 'gpl', 'lgpl', 'agpl', 'apache', 'bsd', 'isc', 'mpl', 'zlib', 'cc0',
    'unlicense', 'artistic', 'wtfpl'
}

PROPRIETARY = {
    'proprietary', 'eula', 'commercial', 'nvidia', 'intel', 'amd', 'busl',
    'sspl', 'polyform', 'chrome', 'custom'
}

LIB_PREFIXES = ('lib', 'python-', 'lua-', 'ruby-', 'perl-', 'php-', 'haskell-')
LIB_SUFFIXES = ('-dev', '-devel')

if not GLib.file_test(CACHE_DIR, GLib.FileTest.EXISTS | GLib.FileTest.IS_DIR):
    GLib.mkdir_with_parents(CACHE_DIR, 0o777)


def is_regex(q: str) -> bool:
    return any(c in '.^$*+?{}[]|()' for c in q)


class LicenseType:
    UNKNOWN = 0
    PROPRIETARY = 1 << 0  # 1
    FOSS = 1 << 1  # 2
    MIXED = PROPRIETARY | FOSS  # 3

    @classmethod
    def get_type(cls, licenses: list[str]) -> 'LicenseType':
        license_flag = cls.UNKNOWN

        for lic in licenses:
            for token in re.split(r'\s*(?:,|AND|OR|WITH|\(|\))\s*', lic):
                t = token.strip().lower().replace('custom:', '').replace(
                    'licenseref-', '')
                if not t:
                    continue

                if any(k in t for k in PROPRIETARY):
                    license_flag |= cls.PROPRIETARY
                elif any(k in t for k in FOSS):
                    license_flag |= cls.FOSS

        return license_flag


@dataclass(slots=True, frozen=True)
class IndexedPackage:
    name: str
    version: str
    description: str
    repository: str
    arch: str
    url: Optional[str] = None

    licenses: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    depends: List[str] = field(default_factory=list)
    optdepends: List[str] = field(default_factory=list)
    makedepends: List[str] = field(default_factory=list)
    checkdepends: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    replaces: List[str] = field(default_factory=list)

    size: Optional[int] = None
    compressed_size: Optional[int] = None
    build_date: Optional[int] = None

    packager: Optional[str] = None
    filename: Optional[str] = None
    base: Optional[str] = None

    installed_version: Optional[str] = None

    @property
    def installed(self) -> bool:
        return bool(self.installed_version)

    @property
    def badges(self) -> list[str]:
        name = self.name.lower()
        badges = []

        # if self.repository not in OFFICIAL_REPOSITORIES:
        #     badges.append(self.repository.lower())

        if name.endswith(LIB_SUFFIXES) or name.startswith(LIB_PREFIXES):
            badges.append('lib')

        if self.packager == 'Orphaned':
            badges.append('orphaned')

        if LicenseType.get_type(self.licenses) == LicenseType.PROPRIETARY:
            badges.append('third-party')

        if self.name.endswith('-git'):
            badges.append('git')

        if self.groups:
            # for g in self.groups:
            #     badges.append(g)
            badges.append(self.groups[0])

        return badges

    @staticmethod
    def _join(values: List[str]) -> Optional[str]:
        if values is not None:
            return ','.join(values)

    @classmethod
    def from_row(cls: 'IndexedPackage', row):
        return cls(
            name=row['name'],
            version=row['version'],
            description=row['description'] or '(Unavailable)',
            repository=row['repository'],
            arch=row['arch'],
            url=row['url'],
            licenses=row['licenses'].split(',') if row['licenses'] else [],
            groups=row['groups'].split(',') if row['groups'] else [],
            depends=row['depends'].split(',') if row['depends'] else [],
            optdepends=row['optdepends'].split(',')
            if row['optdepends'] else [],
            makedepends=row['makedepends'].split(',')
            if row['makedepends'] else [],
            checkdepends=row['checkdepends'].split(',')
            if row['checkdepends'] else [],
            provides=row['provides'].split(',') if row['provides'] else [],
            conflicts=row['conflicts'].split(',') if row['conflicts'] else [],
            replaces=row['replaces'].split(',') if row['replaces'] else [],
            size=row['size'],
            compressed_size=row['compressed_size'],
            build_date=row['build_date'],
            packager=row['packager'],
            filename=row['filename'],
            base=row['base'],
            installed_version=row['installed_version'],
        )

    @classmethod
    def from_pkg(cls: 'IndexedPackage', pkg: Package, repository_name: DB):

        return cls(
            name=pkg.name,
            version=pkg.version,
            description=pkg.desc or '(Unavailable)',
            repository=repository_name,
            arch=pkg.arch,
            url=pkg.url,
            licenses=pkg.licenses or [],
            groups=pkg.groups or [],
            depends=pkg.depends or [],
            optdepends=pkg.optdepends or [],
            makedepends=pkg.makedepends or [],
            checkdepends=pkg.checkdepends or [],
            provides=pkg.provides or [],
            conflicts=pkg.conflicts or [],
            replaces=pkg.replaces or [],
            size=pkg.size,
            build_date=pkg.builddate,
            packager=pkg.packager,
            filename=pkg.filename,
        )

    @classmethod
    def from_aur_json(cls: 'IndexedPackage', p: dict):
        return cls(
            name=p['Name'],
            version=p['Version'],
            description=p.get('Description') or '(Unavailable)',
            repository='aur',
            arch='any',
            url=p.get('URL'),
            licenses=p.get('License') or [],
            groups=p.get('Groups') or [],
            depends=p.get('Depends') or [],
            optdepends=p.get('OptDepends') or [],
            makedepends=p.get('MakeDepends') or [],
            checkdepends=p.get('CheckDepends') or [],
            provides=p.get('Provides') or [],
            conflicts=p.get('Conflicts') or [],
            replaces=p.get('Replaces') or [],
            size=None,
            compressed_size=None,
            build_date=p.get('LastModified'),
            packager=p.get('Maintainer') or 'Orphaned',
            filename=p.get('URLPath'),
            base=p.get('PackageBase'),
            installed_version=None,
        )

    def to_row(self):
        return (
            self.name,
            self.version,
            self.description,
            self.repository,
            self.arch,
            self.url,
            self._join(self.licenses),
            self._join(self.groups),
            self._join(self.depends),
            self._join(self.optdepends),
            self._join(self.makedepends),
            self._join(self.checkdepends),
            self._join(self.provides),
            self._join(self.conflicts),
            self._join(self.replaces),
            self.size,
            self.compressed_size,
            self.build_date,
            self.packager,
            self.filename,
            self.base,
            self.installed_version,
        )


class PackageRepository(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def sync(self) -> list[IndexedPackage]:
        pass


class PacmanRepository(PackageRepository):
    HANDLE = Handle('/', '/var/lib/pacman')
    LOCALDB = HANDLE.get_localdb()

    def __init__(self, name: str):

        self.database: DB = PacmanRepository.HANDLE.register_syncdb(name, 0)

    @property
    def name(self):
        return self.database.name

    async def sync(self) -> list[IndexedPackage]:
        return [
            IndexedPackage.from_pkg(pkg, self.name)
            for pkg in self.database.pkgcache
        ]

    @staticmethod
    def list_repositories():
        sync_dir = '/var/lib/pacman/sync'
        return [
            f.removesuffix('.db') for f in os.listdir(sync_dir)
            if f.endswith('.db')
        ]


class AurRepository(PackageRepository):
    # PACKAGES_META_URL = 'https://aur.archlinux.org/packages-meta-v1.json.gz'
    PACKAGES_META_URL = 'https://aur.archlinux.org/packages-meta-ext-v1.json.gz'
    CHUNK_SIZE = 256 * 1024

    @property
    def name(self):
        return 'aur'

    async def sync(self) -> list[IndexedPackage]:
        r = await requests.get(self.PACKAGES_META_URL)

        stream = Gio.ConverterInputStream.new(
            Gio.MemoryInputStream.new_from_data(r.bytes),
            Gio.ZlibDecompressor.new(Gio.ZlibCompressorFormat.GZIP),
        )

        data = []

        gbytes = await stream.read_bytes_async(self.CHUNK_SIZE,
                                               GLib.PRIORITY_DEFAULT)
        while gbytes.get_size() > 0:
            data.append(gbytes.get_data())
            gbytes = await stream.read_bytes_async(self.CHUNK_SIZE,
                                                   GLib.PRIORITY_DEFAULT)

        json_data = json.loads(b''.join(data))
        return [IndexedPackage.from_aur_json(p) for p in json_data]


class PackageIndexer:
    instance: 'PackageIndexer | None' = None
    ROWS_LIMIT = 50

    def __init__(self):
        self.repositories = list(
            map(PacmanRepository, PacmanRepository.list_repositories()))
        self.repositories.append(AurRepository())
        self.db: Optional[aiosqlite.Connection] = None

    async def open(self):
        self.db = await aiosqlite.connect(DATABASE_PATH)
        self.db.row_factory = aiosqlite.Row

        def REGEXP(pattern: str, value: str) -> bool:
            if value is None:
                return False
            return re.search(pattern, value) is not None

        await self.db.create_function('REGEXP', 2, REGEXP)

    async def close(self):
        if self.db:
            await self.db.close()

    def stop(self):
        if self.db:
            return self.db.stop()

    async def init_schema(self):
        pkgs = Table('packages')
        idx_packages_name = Index('idx_packages_name')

        q = Query.create_table(pkgs).if_not_exists().columns(
            Column('name', 'TEXT', nullable=False),
            Column('version', 'TEXT', nullable=False),
            ('description', 'TEXT'),
            Column('repository', 'TEXT', nullable=False),
            ('arch', 'TEXT'),
            ('url', 'TEXT'),
            ('licenses', 'TEXT'),
            ('groups', 'TEXT'),
            ('depends', 'TEXT'),
            ('optdepends', 'TEXT'),
            ('makedepends', 'TEXT'),
            ('checkdepends', 'TEXT'),
            ('provides', 'TEXT'),
            ('conflicts', 'TEXT'),
            ('replaces', 'TEXT'),
            ('size', 'INTEGER'),
            ('compressed_size', 'INTEGER'),
            ('build_date', 'INTEGER'),
            ('packager', 'TEXT'),
            ('filename', 'TEXT'),
            ('base', 'TEXT'),
            ('installed_version', 'TEXT'),
        ).primary_key('name', 'repository', 'version')

        await self.db.execute(q.get_sql())

        q = Query.create_index(idx_packages_name).if_not_exists().on(
            pkgs).columns(pkgs.name)

        await self.db.execute(q.get_sql())
        await self.db.commit()

    async def sync(self):
        await self.init_schema()
        await self.db.execute('BEGIN')

        pkgs = Table('packages')

        q = Query.into(pkgs).insert_or_replace(*list(
            Parameter('?') for _ in range(22)))

        for repo in self.repositories:
            packages = await repo.sync()
            rows = [p.to_row() for p in packages]

            await self.db.executemany(q.get_sql(), rows)

        await self.db.commit()

    async def soft_sync(self):
        installed_pkgs = [(pkg.name, pkg.version)
                          for pkg in PacmanRepository.LOCALDB.pkgcache]

        pkgs = Table('packages')
        temp_installed = Table('temp_installed')

        await self.db.execute('BEGIN')

        q = Query.update(pkgs).set(pkgs.installed_version, NULL)

        await self.db.execute(q.get_sql())

        q = Query.create_table('temp_installed').temporary().columns(
            ('name', 'TEXT'), ('version', 'TEXT')).primary_key('name')

        await self.db.execute(q.get_sql())

        q = Query.into(temp_installed).columns('name', 'version').insert(
            Parameter('?'), Parameter('?'))

        await self.db.executemany(q.get_sql(), installed_pkgs)

        q = Query.from_(temp_installed).update(pkgs).set(
            pkgs.installed_version,
            temp_installed.version).where(temp_installed.name == pkgs.name)

        await self.db.execute(q.get_sql())

        q = Query.drop_table(temp_installed)

        await self.db.execute(q.get_sql())

        await self.db.commit()

    async def search(self, query: str) -> list[IndexedPackage]:
        query = query.strip()

        if not query:
            return []

        pkgs = Table('packages')

        q = Query.from_(pkgs).select('*')

        params = []

        if is_regex(query):
            q = q.where(pkgs.name.regexp(Parameter('?')))
            params.append(query)

        else:
            tokens = query.split()

            q = q.where(pkgs.name.like(Parameter('?')))

            params.append(f'{tokens.pop(0)}%')

            if tokens:
                for t in tokens:
                    q = q.where(
                        pkgs.name.like(Parameter('?'))
                        | pkgs.description.like(Parameter('?')))

                    params.extend((f'%{t}%', f'%{t}%'))

        q = q.limit(Parameter('?'))

        params.append(self.ROWS_LIMIT)

        async with self.db.execute(q.get_sql(), params) as cursor:
            return [IndexedPackage.from_row(row) async for row in cursor]

    async def get(self, name: str) -> IndexedPackage | None:
        pkgs = Table('packages')

        q = Query.from_(pkgs).select('*').where(
            pkgs.name == Parameter('?')).limit(1)

        async with self.db.execute(q.get_sql(), (name, )) as cursor:
            if row := await cursor.fetchone():
                return IndexedPackage.from_row(row)

    async def get_random(self, limit: int = 1) -> IndexedPackage | None:
        pkgs = Table('packages')

        q = Query.from_(pkgs).select('*').orderby('RANDOM()').limit(
            Parameter('?'))

        async with self.db.execute(q.get_sql(), (limit, )) as cursor:
            return [IndexedPackage.from_row(row) async for row in cursor]

    async def get_installed(self) -> list[IndexedPackage]:
        pkgs = Table('packages')

        q = Query.from_(pkgs).select('*').where(
            pkgs.installed_version.isnotnull())

        async with self.db.execute(q.get_sql()) as cursor:
            return [IndexedPackage.from_row(row) async for row in cursor]

    @property
    def loaded_repositories(self) -> list[str]:
        return [repo.name for repo in self.repositories]

    @staticmethod
    async def get_default():
        if PackageIndexer.instance is None:
            i = PackageIndexer()

            if not GLib.file_test(DATABASE_PATH, GLib.FileTest.EXISTS):
                await i.open()
                await i.sync()
                await i.soft_sync()
            else:
                await i.open()
                await i.soft_sync()

            PackageIndexer.instance = i

        return PackageIndexer.instance

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
