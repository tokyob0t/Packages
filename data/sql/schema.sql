CREATE TABLE IF NOT EXISTS packages(
    name TEXT,
    version TEXT,
    description TEXT,
    repository TEXT,
    arch TEXT,
    url TEXT,
    licenses TEXT,
    groups TEXT,
    depends TEXT,
    optdepends TEXT,
    makedepends TEXT,
    checkdepends TEXT,
    provides TEXT,
    conflicts TEXT,
    replaces TEXT,
    size INTEGER,
    compressed_size INTEGER,
    build_date INTEGER,
    packager TEXT,
    filename TEXT,
    base TEXT,
    installed INTEGER,
    installed_version TEXT,
    PRIMARY KEY(
        name,
        repository,
        version
    )
);

CREATE INDEX IF NOT EXISTS idx_packages_name ON packages(name);
