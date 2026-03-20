conf = configuration_data()
conf.set('APP_ID', APP_ID)
conf.set('SCHEMA_PATH', SCHEMA_PATH)

configure_file(
  input: 'application.in.desktop',
  output: APP_ID + '.desktop',
  configuration: conf,
  install: true,
  install_dir: get_option('datadir') / 'applications',
)

configure_file(
  input: 'styles/styles.scss',
  output: 'styles.css',
  command: [find_program('sass'), '@INPUT@', '@OUTPUT@', '--no-source-map'],
)

custom_target(
  input: configure_file(
    input: 'gresource.in.xml',
    output: APP_ID + '.gresource.xml',
    configuration: conf,
  ),
  output: APP_ID + '.gresource',
  command: [
    find_program('glib-compile-resources'),
    '@INPUT@',
    '--target=@OUTPUT@',
  ],
  install: true,
  install_dir: get_option('datadir') / meson.project_name(),
)

configure_file(
  input: 'gschema.in.xml',
  output: APP_ID + '.gschema.xml',
  configuration: conf,
  install: true,
  install_dir: get_option('datadir') / 'glib-2.0' / 'schemas',
)

test(
  'validate-gschema',
  find_program('glib-compile-schemas'),
  args: [
    '--strict',
    '--dry-run', meson.current_source_dir(),
  ],
)

test(
  'validate-gresource',
  find_program('glib-compile-resources'),
  args: [
    '--strict',
    '--dry-run', meson.current_source_dir(),
  ],
)
