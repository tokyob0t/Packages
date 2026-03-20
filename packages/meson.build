python = import('python')

configure_file(
  input: 'packages.in.py',
  output: 'packages',
  configuration: {
    'PYTHON': python.find_installation('python3').full_path(),
    'APP_ID': APP_ID,
    'VERSION': VERSION,
    'PKGDATADIR': PREFIX / get_option('datadir') / NAME,
    'SCHEMA_PATH': SCHEMA_PATH,
  },
  install: true,
  install_dir: get_option('bindir'),
  install_mode: ['rwxr-xr-x'],
)

files = [
  'app.py',
]

install_subdir(
  'pages',
  install_dir: PREFIX / get_option('datadir') / NAME,
  exclude_directories: ['__pycache__'],
)

install_subdir(
  'utils',
  install_dir: PREFIX / get_option('datadir') / NAME,
  exclude_directories: ['__pycache__'],
)

install_data(
  files,
  install_dir: PREFIX / get_option('datadir') / NAME,
)
