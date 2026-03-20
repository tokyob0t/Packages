import sys

import gi
from gi.events import GLibEventLoopPolicy

gi.require_versions({
    'Gtk': '4.0',
    'Gdk': '4.0',
    'Adw': '1',
    'GLib': '2.0',
    'Gio': '2.0',
    'Soup': '3.0',
    'GObject': '2.0'
})

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk
from pages import SearchPage
from utils import Config, PackageIndexer, asztalify, process, task


class ApplicationWindow(Adw.ApplicationWindow):

    def __init__(self, **kwargs: Adw.Application):
        super().__init__(**kwargs)

        self.root = asztalify(Adw.NavigationView, setup=self.set_content)
        self.main = asztalify(Adw.NavigationPage,
                              setup=self.root.add,
                              title='Packages',
                              child=Adw.ToolbarView())

        self.stack = Adw.ViewStack()
        self.search_page = Gtk.ScrolledWindow(child=SearchPage())
        self.installed_page = Gtk.ScrolledWindow(child=Adw.PreferencesPage())
        self.settings_page = Gtk.ScrolledWindow()

        self.setup()

    def setup(self):

        title_bar = Adw.HeaderBar(title_widget=Adw.ViewSwitcher(
            stack=self.stack,
            policy=Adw.ViewSwitcherPolicy.WIDE,
        ))

        bottom_bar = Adw.ViewSwitcherBar(stack=self.stack)

        self.main.get_child().add_top_bar(title_bar)
        self.main.get_child().add_bottom_bar(bottom_bar)

        breakpoint = Adw.Breakpoint.new(
            Adw.BreakpointCondition.parse('max-width: 550sp'))
        self.add_breakpoint(breakpoint)

        breakpoint.add_setter(title_bar, 'title-widget',
                              GObject.Value(value_type=Gtk.Widget))
        breakpoint.add_setter(bottom_bar, 'reveal', True)

        self.main.get_child().set_content(self.stack)

        self.stack.add_titled_with_icon(self.search_page, 'search-page',
                                        'Search', 'search-symbolic')
        self.stack.add_titled_with_icon(self.installed_page, 'installed-page',
                                        'Installed', 'package-symbolic')
        self.stack.add_titled_with_icon(self.settings_page, 'settings-page',
                                        'Settings', 'cogged-wheel-symbolic')


class Application(Adw.Application):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def do_activate(self):
        Gtk.Application.set_default(self)

        win = ApplicationWindow(application=self,
                                name='default-window',
                                title='Packages',
                                default_width=700,
                                default_height=550)

        win.present()


def main(cfg: Config):
    try:
        with GLibEventLoopPolicy():
            app = Application(application_id=cfg.APPLICATION_ID,
                              version=cfg.VERSION)
            return app.run()

    except KeyboardInterrupt:
        return 0
    except Exception as e:
        sys.stderr.write(e)
        sys.stderr.flush()

        return 1
    finally:
        if packages := PackageIndexer.instance:
            packages.stop()


if __name__ == '__main__':
    sys.exit(
        main(
            Config(APPLICATION_ID='xyz.application.Test',
                   VERSION='0.1.0',
                   SCHEMA_PATH='/xyz/application/Test')))
