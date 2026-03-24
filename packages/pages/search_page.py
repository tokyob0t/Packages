import re
import sys

from gi.events import GLibTask
from gi.repository import Adw, Gio, GLib, GObject, Gtk
from utils import PackageIndexer, asztalify, idle, task
from utils.packages import IndexedPackage


class SpecialIcons:
    linux = 'linux-assistant-symbolic'

    @classmethod
    def get(cls, package_name: str, fallback: str) -> str | None:
        return getattr(cls, package_name, fallback)


def format_version(version: str) -> str:  # X:X.X.X-X -> X.X.X
    match = re.match(r'(?:\d+:)?([^-]+)-\d+', version)
    return match.group(1) if match else version


def format_size(size: int | None) -> str:
    if not size:
        return '(Unknown)'
    for unit in ['B', 'KiB', 'MiB', 'GiB']:
        if size < 1024:
            return f'{size:.1f} {unit}'
        size /= 1024
    return f'{size:.1f} TiB'


class PackageRow(Adw.ExpanderRow):
    package = GObject.Property(type=object,
                               flags=GObject.ParamFlags.CONSTRUCT_ONLY
                               | GObject.ParamFlags.READWRITE)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if 'package' not in kwargs:
            raise TypeError(
                "PackageRow missing required positional argument: 'package'")

        self.setup()

    @task
    async def setup(self):
        pkg = self.get_package()
        self.set_title(pkg.name)
        self.set_subtitle(GLib.markup_escape_text(pkg.description))

        self.add_property_row('Repository', pkg.repository)
        self.add_property_row('Repository', pkg.repository)

        if pkg.arch != 'any':
            self.add_property_row('Architecture', pkg.arch)

        self.add_property_row('Packager', pkg.packager)
        self.add_property_row('Licenses', ' '.join(pkg.licenses))

        if pkg.optdepends:
            deps = [s.partition(':')[0] for s in pkg.optdepends]

            regex = f'^({' | '.join(deps)})(-git)?$'

            self.add_property_row(
                'Optional dependencies',
                ', '.join(deps),
                activatable=True,
                tooltip_text='Copy as regex',
                suffix=Gtk.Image.new_from_icon_name('edit-copy-symbolic'),
                on_activated=lambda _: Gtk.Application.get_default(
                ).copy_to_clipboard(regex))

        if pkg.url:
            self.add_property_row(title='URL',
                                  subtitle=pkg.url,
                                  activatable=True,
                                  suffix=Gtk.Image.new_from_icon_name(
                                      'adw-external-link-symbolic'),
                                  on_activated=lambda _: Gio.AppInfo.
                                  launch_default_for_uri(pkg.url))

        if pkg.installed:
            self.add_suffix(
                Gtk.Image.new_from_icon_name(
                    SpecialIcons.get(pkg.name, 'checkmark-small-symbolic')))

        box = asztalify(Gtk.Box,
                        setup=self.add_suffix,
                        spacing=3,
                        valign='CENTER')

        for badge in pkg.badges:
            box.append(child=Gtk.Label(
                label=badge, css_classes=['badge', f'{badge}-badge-color']))
        self.add_property_row(
            suffix=asztalify(Gtk.Button,
                             label="An ugly install button that doesn't work",
                             valign='CENTER',
                             on_clicked=lambda _: self.emit('installed'),
                             css_classes=['suggested-action']))

    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST)
    def installed(self) -> None:
        ...

    def get_package(self) -> IndexedPackage:
        return self.props.package

    def add_property_row(self,
                         title: str | None = None,
                         subtitle: str | None = None,
                         activatable_widget: Gtk.Widget = None,
                         suffix: Gtk.Widget = None,
                         **kwargs) -> None:

        action_row = asztalify(Adw.ActionRow,
                               title=title,
                               subtitle=subtitle
                               and GLib.markup_escape_text(subtitle),
                               css_classes=['property'],
                               **kwargs)

        if suffix:
            action_row.add_suffix(suffix)
        if activatable_widget:
            action_row.set_activatable_widget(activatable_widget)

        self.add_row(action_row)


class SearchPage(Gtk.Box):

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.search_task: GLibTask | None = None
        self.recently_searched: list[IndexedPackage] = []
        self.search_results_rows: list[Adw.ExpanderRow] = []

        self.content = asztalify(Adw.Bin, setup=self.append)

        spinner_box = asztalify(Gtk.Box,
                                halign='CENTER',
                                valign='CENTER',
                                orientation='VERTICAL',
                                spacing=12,
                                hexpand=True,
                                vexpand=True)

        spinner_box.append(Adw.Spinner(height_request=48, width_request=48))
        spinner_box.append(
            Gtk.Label(label='Loading Package Database...',
                      css_classes=['title-2']))

        self.content.set_child(spinner_box)

        self.search_results = Adw.PreferencesGroup()
        self.search_entry = Gtk.SearchEntry(search_delay=300, hexpand=True)

        self.setup()

    @task
    async def setup(self):
        packages = await PackageIndexer.get_default()

        main_box = asztalify(Gtk.Box,
                             orientation='VERTICAL',
                             spacing=30,
                             margin_start=12,
                             margin_end=12,
                             margin_top=36,
                             margin_bottom=36)

        self.search_entry.connect('search-changed', self.on_search_changed)

        # hacky stuff to trigger events instantly while typing
        # SearchEntry
        # | Gtk.Image
        # | Gtk.Text
        # | Gtk.Image
        image = self.search_entry.get_first_child()
        text = image.get_next_sibling()
        text.get_buffer().connect('notify::text', self.on_search_started)

        header = Adw.Clamp(maximum_size=600,
                           tightening_threshold=400,
                           child=asztalify(Gtk.Box,
                                           spacing=10,
                                           orientation='VERTICAL',
                                           halign='CENTER',
                                           valign='CENTER'))

        header.get_child().append(
            Gtk.Label(label='Search for Packages',
                      css_classes=['title-1'],
                      justify=Gtk.Justification.CENTER))

        header.get_child().append(
            Gtk.Label(label=(
                'Enter a keyword to search.\n'
                f'Currently loaded repositories: {", ".join(packages.get_loaded_repositories())}'
            ),
                      wrap=True,
                      css_classes=['body'],
                      justify=Gtk.Justification.CENTER))

        searcher = Adw.Clamp(tightening_threshold=400,
                             maximum_size=600,
                             child=Gtk.Box(
                                 orientation=Gtk.Orientation.VERTICAL,
                                 spacing=10))

        searcher.get_child().append(self.search_entry)

        searcher.get_child().append(self.search_results)

        main_box.append(header)
        main_box.append(searcher)

        self.content.set_child(main_box)

        self.initial_packages = await packages.get_random(10)

        if not self.initial_packages:
            return

        self.search_entry.set_placeholder_text(
            f'Search across {await packages.get_count()} packages...')

        self.append_results(self.initial_packages)

        idle(self.search_entry.grab_focus)

    @task
    async def search(self, text: str):
        packages = await PackageIndexer.get_default()
        try:
            self.recently_searched.clear()
            self.recently_searched.extend(await packages.search(text))

            self.cleanup_results()
            self.append_results(self.recently_searched[:10])

        except GLib.GError as e:
            sys.stderr.write(e)
            sys.stderr.flush()

        finally:
            self.search_task = None

    def append_results(self, results: list[IndexedPackage]):
        for package in results:
            row = asztalify(
                PackageRow,
                package=package,
                on_installed=self.on_installed,
                on_notify_expanded=self.on_row_expanded,
            )

            self.search_results.add(row)
            self.search_results_rows.append(row)

    def cleanup_results(self):
        for row in self.search_results_rows:
            self.search_results.remove(row)

        self.search_results_rows.clear()

    def on_search_changed(self, search_entry):
        text = self.search_entry.get_text().strip()

        if not text:
            self.cleanup_results()
            self.append_results(self.initial_packages[:-1])
            return

        if self.search_task and not self.search_task.done():
            self.search_task.cancel()

        self.search_task = self.search(text)

    def on_search_started(self, _: Gtk.TextBuffer, pspec) -> None:
        text = self.search_entry.get_text().strip()
        image = self.search_entry.get_first_child()

        if any(c in ".^$*+?{}[]|()" for c in text):  # is-regex
            image.set_from_icon_name('regex-symbolic')
        else:
            image.set_from_icon_name('system-search-symbolic')

    def on_row_expanded(self, row: Adw.ExpanderRow, expanded: bool):
        if not expanded:
            return

        for r in filter(lambda r: r != row, self.search_results_rows):
            r.set_expanded(False)

    def on_installed(self, row: PackageRow):
        pkg = row.get_package()
        print(pkg.name, pkg.url)
        # pkg = pkg_row.get_package()

        # print(pkg.name, pkg.url)
