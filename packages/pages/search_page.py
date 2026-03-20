import re
import sys

from gi.events import GLibTask
from gi.repository import Adw, Gio, GLib, Gtk
from utils import PackageIndexer, asztalify, task
from utils.packages import IndexedPackage


class SpecialIcons:
    linux = 'linux-assistant-symbolic'

    @classmethod
    def get(cls, package_name: str, fallback: str) -> str | None:
        return getattr(cls, package_name, fallback)


def timeout(interval: int, cb: callable, *args) -> callable:

    def on_timeout():
        cb(*args)
        return GLib.SOURCE_REMOVE

    id = GLib.timeout_add(interval, on_timeout)

    return lambda: GLib.source_remove(id)


def idle(cb: callable, *args):

    def on_called():
        cb(*args)
        return GLib.SOURCE_REMOVE

    id = GLib.idle_add(on_called)

    return lambda: GLib.source_remove(id)


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


def is_regex(query: str) -> bool:
    return any(c in ".^$*+?{}[]|()" for c in query)


def PropertyRow(title: str,
                subtitle: str,
                activatable_widget: Gtk.Widget = None,
                suffix: Gtk.Widget = None,
                **kwargs):
    action_row = asztalify(Adw.ActionRow,
                           title=title,
                           subtitle=GLib.markup_escape_text(subtitle),
                           css_classes=['property'],
                           **kwargs)

    if suffix:
        action_row.add_suffix(suffix)
    if activatable_widget:
        action_row.set_activatable_widget(activatable_widget)

    return action_row


class _PackageRow(Adw.ExpanderRow):
    __gtype_name__ = 'PackageRow'

    def __init__(self, package: IndexedPackage, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


def PackageRow(package: IndexedPackage, on_row_expanded: callable,
               on_installed: callable):
    row = asztalify(Adw.ExpanderRow,
                    title=package.name,
                    subtitle=GLib.markup_escape_text(package.description),
                    on_notify_expanded=on_row_expanded)

    row.add_row(PropertyRow(title='Repository', subtitle=package.repository))

    if package.arch != 'any':
        row.add_row(PropertyRow(title='Architecture', subtitle=package.arch))

    row.add_row(PropertyRow(title='Packager', subtitle=package.packager))
    row.add_row(
        PropertyRow(title='Licenses', subtitle=' '.join(package.licenses)))

    if package.optdepends:

        row.add_row(
            PropertyRow(title='Optional dependencies',
                        subtitle=', '.join(
                            s.partition(':')[0] for s in package.optdepends)))

    if package.url:
        row.add_row(
            PropertyRow(title='URL',
                        subtitle=package.url,
                        activatable=True,
                        suffix=Gtk.Image.new_from_icon_name(
                            'adw-external-link-symbolic'),
                        on_activated=lambda _: Gio.AppInfo.
                        launch_default_for_uri(package.url)))

    if package.installed:
        row.add_suffix(
            Gtk.Image.new_from_icon_name(
                SpecialIcons.get(package.name, 'checkmark-small-symbolic')))

    flow = asztalify(Gtk.FlowBox,
                     setup=row.add_suffix,
                     row_spacing=3,
                     column_spacing=3,
                     min_children_per_line=3,
                     max_children_per_line=3,
                     selection_mode='NONE',
                     valign='CENTER')

    for badge in package.badges:
        flow.append(
            Gtk.FlowBoxChild(css_classes=['badge', f'{badge}-badge-color'],
                             child=Gtk.Label.new(badge)))

    return row


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
        self.packages = await PackageIndexer.get_default()

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
                f'Currently loaded repositories: {", ".join(self.packages.loaded_repositories)}'
            ),
                      wrap=True,
                      css_classes=['body'],
                      justify=Gtk.Justification.CENTER))

        searcher = Adw.Clamp(tightening_threshold=400,
                             maximum_size=600,
                             child=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                           spacing=10))

        searcher.get_child().append(self.search_entry)

        searcher.get_child().append(self.search_results)

        main_box.append(header)
        main_box.append(searcher)

        self.content.set_child(main_box)

        self.initial_packages = await self.packages.get_random(11)

        if not self.initial_packages:
            return

        self.search_entry.set_placeholder_text(self.initial_packages[-1].name)
        self.append_results(self.initial_packages[:-1])

        idle(self.search_entry.grab_focus)

    @task
    async def do_search(self, text: str):
        try:
            self.recently_searched.clear()
            self.recently_searched.extend(await self.packages.search(text))

            self.cleanup_results()
            self.append_results(self.recently_searched[:10])

        except GLib.GError as e:
            sys.stderr.write(e)
            sys.stderr.flush()

        finally:
            self.search_task = None

    def append_results(self, results: list[IndexedPackage]):
        for package in results:
            row = PackageRow(package,
                             on_row_expanded=self.on_row_expanded,
                             on_installed=self.on_install)

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

        self.search_task = self.do_search(text)

        # self.on_search_stopped()

    def on_search_started(self, _: Gtk.TextBuffer, pspec) -> None:
        text = self.search_entry.get_text().strip()
        image = self.search_entry.get_first_child()

        if is_regex(text):
            image.set_from_icon_name('regex-symbolic')
        else:
            image.set_from_icon_name('system-search-symbolic')

    def on_row_expanded(self, row: Adw.ExpanderRow, expanded: bool):
        if not expanded:
            return

        for r in filter(lambda r: r != row, self.search_results_rows):
            r.set_expanded(False)

    def on_install(self, _: Adw.ExpanderRow, package: IndexedPackage):
        print(package.name, package.url)
