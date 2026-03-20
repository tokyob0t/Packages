#!@PYTHON@

import sys

APP_ID, VERSION, PKGDATADIR, SCHEMA_PATH = ('@APP_ID@', '@VERSION@',
                                            '@PKGDATADIR@', '@SCHEMA_PATH@')

gresource = f'{PKGDATADIR}/{APP_ID}.gresource'

sys.path.insert(1, PKGDATADIR),

if __name__ == '__main__':
    from app import Gdk, Gio, Gtk, main
    from utils.config import Config

    Gio.Resource.load(gresource)._register()

    Gtk.IconTheme.get_for_display(
        Gdk.Display.get_default()).add_resource_path(SCHEMA_PATH + '/icons/')

    provider = Gtk.CssProvider.new()
    provider.load_from_resource(SCHEMA_PATH + '/styles.css')

    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),
                                              provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_USER)

    sys.exit(
        main(
            Config(APPLICATION_ID=APP_ID,
                   SCHEMA_PATH=SCHEMA_PATH,
                   VERSION=VERSION)))
