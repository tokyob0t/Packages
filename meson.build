project(
  'packages',
  version: run_command('cat', meson.project_source_root() / 'version').stdout().strip(),
)

PREFIX = get_option('prefix')

NAME = meson.project_name()
VERSION = meson.project_version()
APP_NAME = 'Packages'
APP_ID = 'io.github.tokyob0t.' + NAME
SCHEMA_PATH = '/' + APP_ID.replace('.', '/')

subdir('data')
subdir('packages')

import('gnome').post_install(
  # gtk_update_icon_cache: true,
  glib_compile_schemas: true,
  # update_desktop_database: true,
)
