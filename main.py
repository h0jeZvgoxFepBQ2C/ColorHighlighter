"""The main program."""

import os

import sublime  # pylint: disable=import-error

import sublime_plugin  # pylint: disable=import-error

try:
    from .debug import DEBUG
    from . import st_helper
    from . import path
    from .color_converter import ColorConverter
    from .color_searcher import ColorSearcher
    from .dummy_event_listener import DummyEventListener
    from .settings import Settings, COLOR_HIGHLIGHTER_SETTINGS_NAME
    from .content_listener import ContentListener
    from .color_highlighter import CachingColorHighlighter
    from .phantoms_color_highlighter import PhantomColorHighlighter
    from .gutter_icons_color_highlighter import IconFactory, GutterIconsColorHighlighter
    from .color_scheme import parse_color_scheme
    from .color_scheme_color_highlighter import ColorSchemeBuilder, ColorSchemeColorHighlighter
    from .color_selection_listener import ColorSelectionListener
    from .load_resource import load_resource
    from .regex_compiler import compile_regex
except ValueError:
    from debug import DEBUG
    import st_helper
    import path
    from color_converter import ColorConverter
    from color_searcher import ColorSearcher
    from dummy_event_listener import DummyEventListener
    from settings import Settings, COLOR_HIGHLIGHTER_SETTINGS_NAME
    from content_listener import ContentListener
    from phantoms_color_highlighter import PhantomColorHighlighter
    from color_highlighter import CachingColorHighlighter
    from gutter_icons_color_highlighter import IconFactory, GutterIconsColorHighlighter
    from color_scheme import parse_color_scheme
    from color_scheme_color_highlighter import ColorSchemeBuilder, ColorSchemeColorHighlighter
    from color_selection_listener import ColorSelectionListener
    from load_resource import load_resource
    from regex_compiler import compile_regex

# ST2's python doesn't have XMLTreeBuilder, this code is supposed to fix this, see
# https://stackoverflow.com/questions/1068510/using-simplexmltreebuilder-in-elementtree for details.
if not st_helper.is_st3():
    from xml.etree import ElementTree
    from elementtree import SimpleXMLTreeBuilder  # pylint: disable=no-name-in-module
    ElementTree.XMLTreeBuilder = SimpleXMLTreeBuilder.TreeBuilder


PREFERENCES_SETTINGS_NAME = "Preferences.sublime-settings"


def set_fake_color_scheme(color_scheme, fake_color_scheme):
    """
    Set current color scheme to a fake one.

    If the fake color scheme is not yet created, creates it.
    Arguments:
    - color_scheme -- current color scheme.
    - fake_color_scheme -- a fake color scheme for the current color scheme.
    """
    packages_path = os.path.dirname(path.packages_path(path.ABSOLUTE))
    fake_color_scheme_path = os.path.join(packages_path, fake_color_scheme)
    if not os.path.exists(fake_color_scheme_path):
        if DEBUG:
            print("ColorHighlighter: action=copy_color_scheme scheme=%s fake_scheme=%s"
                  % (color_scheme, fake_color_scheme))
        with open(fake_color_scheme_path, "w") as file:
            file.write(load_resource(color_scheme))

    settings = sublime.load_settings(PREFERENCES_SETTINGS_NAME)  # pylint: disable=assignment-from-none
    if settings.get("color_scheme", None) != fake_color_scheme:
        if DEBUG:
            print("ColorHighlighter: action=set_color_scheme scheme=%s" % (fake_color_scheme))
        settings.set("color_scheme", fake_color_scheme)
    sublime.save_settings(PREFERENCES_SETTINGS_NAME)


class ColorHighlighterComponents(object):
    """A factory for providing all applications components."""

    def __init__(self):
        """Create a ColorHighlighterComponents object."""
        self._settings = Settings(sublime.load_settings(COLOR_HIGHLIGHTER_SETTINGS_NAME))
        self._color_searcher = None
        self._fake_color_scheme_data = None
        self._color_scheme_builder = None
        self._icon_factory = None
        self._color_selection_event_listener = None
        self._color_highlighters = {}
        for name in self._settings.search_colors_in.color_searcher_names:
            self._color_highlighters[name] = {}

    def provide_formats(self):
        """Provide the formats config."""
        return self._settings.regex_compiler.formats.keys()

    def provide_color_converter(self):
        """Provide a color converter."""
        return ColorConverter(self.provide_formats())

    def provide_color_searcher(self):
        """Provide a color searcher."""
        if self._color_searcher is not None:
            return self._color_searcher

        self._color_searcher = ColorSearcher(
            compile_regex(self._settings.regex_compiler),
            self.provide_color_converter())
        return self._color_searcher

    def provide_color_selection_listener(self, view):  # pylint: disable=invalid-name
        """
        Provide a color selection listener for a view.

        Arguments:
        - view -- the view.
        """
        if not self._settings.search_colors_in.selection.enabled:
            return DummyEventListener()
        return ColorSelectionListener(
            self.provide_color_searcher(), view,
            self.provide_color_highlighter(view, self._settings.search_colors_in.selection))

    def provide_content_listener(self, view):
        """
        Provide a content listener for a view.

        Arguments:
        - view -- the view.
        """
        if not self._settings.search_colors_in.all_content.enabled:
            return DummyEventListener()
        return ContentListener(
            self.provide_color_searcher(), view,
            self.provide_color_highlighter(view, self._settings.search_colors_in.all_content))

    def provide_color_selection(self, view):
        """
        Provide a color selection for a view.

        Arguments:
        - view -- the view.
        """
        return ColorSelection(
            self.provide_color_highlighter(view, self._settings.search_colors_in.selection),
            self.provide_color_highlighter(view, self._settings.search_colors_in.all_content),
            self.provide_color_selection_listener(view),
            self.provide_content_listener(view))

    def provide_fake_color_scheme_data(self):
        """Provide a fake color scheme data."""
        if self._fake_color_scheme_data is not None:
            return self._fake_color_scheme_data

        self._fake_color_scheme_data = parse_color_scheme(self.provide_color_scheme())
        return self._fake_color_scheme_data

    def provide_fake_color_scheme(self):
        """Provide a fake color scheme."""
        return self.provide_fake_color_scheme_data()[0]

    def provide_color_scheme(self):  # pylint: disable=no-self-use
        """Provide a current color scheme."""
        settings = sublime.load_settings(PREFERENCES_SETTINGS_NAME)  # pylint: disable=assignment-from-none
        color_scheme = settings.get("color_scheme", None)
        return color_scheme

    def provide_color_scheme_builder(self):
        """Provide a color scheme builder."""
        if self._color_scheme_builder is not None:
            return self._color_scheme_builder

        _, color_scheme_data, color_scheme_writer = self.provide_fake_color_scheme_data()
        self._color_scheme_builder = ColorSchemeBuilder(color_scheme_data, color_scheme_writer)
        return self._color_scheme_builder

    def provide_icon_factory(self):
        """Provide an icon factory."""
        if self._icon_factory is not None:
            return self._icon_factory

        settings = self._settings.icon_factory
        self._icon_factory = IconFactory(
            path.icons_path(path.ABSOLUTE), path.icons_path(path.RELATIVE),
            settings.convert_command, settings.convert_timeout)
        return self._icon_factory

    def provide_color_highlighter(self, view, searcher):
        """
        Provide a color highlighter for a view.

        Arguments:
        - view -- the view.
        - searcher - the color searcher settings.
        """
        color_highlighter = self._color_highlighters[searcher.name].get(view.id(), None)
        if color_highlighter is not None:
            return color_highlighter

        color_highlighters = []
        if searcher.color_highlighters.color_scheme.enabled:
            color_highlighters.append(ColorSchemeColorHighlighter(
                view, searcher.color_highlighters.color_scheme.highlight_style, self.provide_color_scheme_builder(),
                searcher.name))
        if searcher.color_highlighters.gutter_icons.enabled:
            color_highlighters.append(GutterIconsColorHighlighter(
                view, searcher.color_highlighters.gutter_icons.icon_style, self.provide_icon_factory(), searcher.name))
        if searcher.color_highlighters.phantoms.enabled:
            color_highlighters.append(PhantomColorHighlighter(view, searcher.name))
        color_highlighter = CachingColorHighlighter(color_highlighters)
        self._color_highlighters[searcher.name][view.id()] = color_highlighter
        return color_highlighter

    def provide_color_selection_event_listener(self):  # pylint: disable=invalid-name
        """Provide a color selection event listener."""
        if self._color_selection_event_listener is not None:
            return self._color_selection_event_listener

        self._color_selection_event_listener = ColorSelectionEventListener(self._settings.file_extensions)
        return self._color_selection_event_listener


class ColorHighlighterPlugin(object):
    """A main class."""

    components = None
    color_searcher = None
    color_selection_event_listener = None

    _settings = None
    _preferences = None
    _color_scheme = None
    _fake_color_scheme = None

    _ON_SETTINGS_CHANGE_KEY = "ColorHighlighter"

    @staticmethod
    def init():
        """Create all singletons."""
        ColorHighlighterPlugin.components = ColorHighlighterComponents()
        ColorHighlighterPlugin._settings = sublime.load_settings(  # pylint: disable=assignment-from-none
            COLOR_HIGHLIGHTER_SETTINGS_NAME)
        ColorHighlighterPlugin._preferences = sublime.load_settings(  # pylint: disable=assignment-from-none
            PREFERENCES_SETTINGS_NAME)
        settings = Settings(ColorHighlighterPlugin._settings)

        autoreload = settings.autoreload
        if autoreload.when_settings_change:
            ColorHighlighterPlugin._settings.add_on_change(
                ColorHighlighterPlugin._ON_SETTINGS_CHANGE_KEY, ColorHighlighterPlugin._on_settings_change)

        color_searchers = settings.search_colors_in
        selection_searcher = color_searchers.selection
        all_content_searcher = color_searchers.all_content
        color_scheme_color_highlighter_enabled = (  # pylint: disable=invalid-name
            (selection_searcher.enabled and selection_searcher.color_highlighters.color_scheme.enabled) or
            (all_content_searcher.enabled and all_content_searcher.color_highlighters.color_scheme.enabled))
        if color_scheme_color_highlighter_enabled:  # pylint: disable=invalid-name
            ColorHighlighterPlugin._color_scheme = ColorHighlighterPlugin.components.provide_color_scheme()
            ColorHighlighterPlugin._fake_color_scheme = ColorHighlighterPlugin.components.provide_fake_color_scheme()
            set_fake_color_scheme(ColorHighlighterPlugin._color_scheme, ColorHighlighterPlugin._fake_color_scheme)
            if autoreload.when_color_scheme_change:
                ColorHighlighterPlugin._preferences.add_on_change(
                    ColorHighlighterPlugin._ON_SETTINGS_CHANGE_KEY, ColorHighlighterPlugin._on_preferences_change)

        color_selection_event_listener = ColorHighlighterPlugin.components.provide_color_selection_event_listener()
        ColorHighlighterPlugin.color_selection_event_listener = color_selection_event_listener
        ColorHighlighterPlugin.color_selection_event_listener.start()
        for window in sublime.windows():
            for view in window.views():
                ColorHighlighterPlugin.color_selection_event_listener.on_new(view)
                ColorHighlighterPlugin.color_selection_event_listener.on_selection_modified(view)

    @staticmethod
    def _on_settings_change():
        ColorHighlighterPlugin.restart()

    @staticmethod
    def _on_preferences_change():
        new_color_scheme = ColorHighlighterPlugin.components.provide_color_scheme()
        if new_color_scheme in [ColorHighlighterPlugin._color_scheme, ColorHighlighterPlugin._fake_color_scheme]:
            return

        ColorHighlighterPlugin._color_scheme = new_color_scheme
        ColorHighlighterPlugin.restart()

    @staticmethod
    def restart():
        """Restart the plugin: deinit and then init it."""
        ColorHighlighterPlugin.deinit()
        ColorHighlighterPlugin.init()

    @staticmethod
    def deinit():
        """
        Clean up resources.

        This class is a singleton, so this method cleans up all static variables as well.
        """
        ColorHighlighterPlugin._settings.clear_on_change(ColorHighlighterPlugin._ON_SETTINGS_CHANGE_KEY)
        ColorHighlighterPlugin._preferences.clear_on_change(ColorHighlighterPlugin._ON_SETTINGS_CHANGE_KEY)
        ColorHighlighterPlugin.color_selection_event_listener.clear_all()


class ColorSelection(object):
    """The main class for listening ST events."""

    def __init__(self, selection_color_highlighter, content_color_highlighter, color_selection_listener,
                 content_listener):
        """
        Initialize the event listener.

        Arguments:
        - selection_color_highlighter - color highlighter for selections.
        - content_color_highlighter - color highlighter for all content.
        - color_selection_listener - the color selection listener.
        - content_listener - the content listener.
        """
        self._selection_color_highlighter = selection_color_highlighter
        self._content_color_highlighter = content_color_highlighter
        self._color_selection_listener = color_selection_listener
        self._content_listener = content_listener

    def on_pre_save(self):
        """on_pre_save event."""
        self._content_listener.on_load()

    def on_new(self):
        """on_new event."""
        self._content_listener.on_load()

    def on_clone(self):
        """on_clone event."""
        self._content_listener.on_load()

    def on_load(self):
        """on_load event."""
        self._content_listener.on_load()

    def on_selection_modified(self):
        """on_selection_modified event."""
        self._color_selection_listener.on_selection_modified()

    def clear_all(self):
        """Clean up all highlightings."""
        self._selection_color_highlighter.clear_all()
        self._content_color_highlighter.clear_all()


class ColorSelectionEventListener(object):
    """The main class for listening ST events."""

    def __init__(self, file_extenstions):
        """
        Initialize the event listener.

        Arguments:
        - file_extenstions - a list with file extensions in which colors should be highlighted.
        """
        self._listening = False
        self._view_listeners = {}
        self._file_extenstions = file_extenstions

    def on_pre_save(self, view):
        """on_pre_save event."""
        if not self._listening:
            return
        if not self._init_view(view):
            return
        self._view_listeners[view.id()].on_pre_save()

    def on_new(self, view):
        """on_new event."""
        if not self._listening:
            return
        if not self._init_view(view):
            return
        self._view_listeners[view.id()].on_new()

    def on_load(self, view):
        """on_load event."""
        if not self._listening:
            return
        if not self._init_view(view):
            return
        self._view_listeners[view.id()].on_load()

    def on_clone(self, view):
        """on_clone event."""
        if not self._listening:
            return
        if not self._init_view(view):
            return
        self._view_listeners[view.id()].on_clone()

    def on_selection_modified(self, view):
        """on_selection_modified event."""
        if not self._listening:
            return
        if not self._init_view(view):
            return
        self._view_listeners[view.id()].on_selection_modified()

    def _init_view(self, view):
        view_id = view.id()
        if view_id not in self._view_listeners:
            if not self._supported_file_extension(view):
                return False
            self._view_listeners[view_id] = ColorHighlighterPlugin.components.provide_color_selection(view)
        return True

    def _supported_file_extension(self, view):
        if "all" in self._file_extenstions:
            return True
        file_name = view.file_name()
        if file_name is None:
            return False
        return os.path.splitext(file_name)[1] in self._file_extenstions

    def clear_all(self):
        """Clean up all highlightings."""
        for view_id in self._view_listeners:
            self._view_listeners[view_id].clear_all()
        self._view_listeners = {}

    def start(self):
        """Start listening to ST events."""
        self._listening = True


class ColorSelectionEventSublimeListener(sublime_plugin.EventListener):
    """The main class for listening ST events."""

    def on_pre_save(self, view):  # pylint: disable=no-self-use
        """on_pre_save event."""
        # ST2 calls these events before our simulated plugin_loaded.
        if ColorHighlighterPlugin.components is None:
            return
        ColorHighlighterPlugin.components.provide_color_selection_event_listener().on_pre_save(view)

    def on_new(self, view):  # pylint: disable=no-self-use
        """on_new event."""
        # ST2 calls these events before our simulated plugin_loaded.
        if ColorHighlighterPlugin.components is None:
            return
        ColorHighlighterPlugin.components.provide_color_selection_event_listener().on_new(view)

    def on_load(self, view):  # pylint: disable=no-self-use
        """on_load event."""
        # ST2 calls these events before our simulated plugin_loaded.
        if ColorHighlighterPlugin.components is None:
            return
        ColorHighlighterPlugin.components.provide_color_selection_event_listener().on_load(view)

    def on_clone(self, view):  # pylint: disable=no-self-use
        """on_clone event."""
        # ST2 calls these events before our simulated plugin_loaded.
        if ColorHighlighterPlugin.components is None:
            return
        ColorHighlighterPlugin.components.provide_color_selection_event_listener().on_clone(view)

    def on_selection_modified(self, view):  # pylint: disable=no-self-use
        """on_selection_modified event."""
        ColorHighlighterPlugin.components.provide_color_selection_event_listener().on_selection_modified(view)


def plugin_loaded():  # noqa: D401
    """Called when plugin has finished loading."""
    if DEBUG:
        print("ColorHighlighter: action=start st=%s" % (st_helper.st_version()))

    def _create_if_not_exists(path_to_create):
        if not os.path.exists(path_to_create):
            os.mkdir(path_to_create)

    _create_if_not_exists(path.data_path(path.ABSOLUTE))
    _create_if_not_exists(path.icons_path(path.ABSOLUTE))
    _create_if_not_exists(path.themes_path(path.ABSOLUTE))
    ColorHighlighterPlugin.init()


def plugin_unloaded():  # noqa: D401
    """Called when plugin is getting unloaded."""
    if DEBUG:
        print("ColorHighlighter: action=stop st=%s" % (st_helper.st_version()))
    ColorHighlighterPlugin.deinit()


# ST2 doesn't have plugin_loaded and plugin_unloaded they need to be emulated.
if not st_helper.is_st3():
    def unload_handler():  # noqa: D401
        """
        Called when ST2 plugin gets unloaded.

        This is an undocumented ST2 feature. It's maps to ST3's plugin_unloaded function call.
        """
        plugin_unloaded()

    def call_plugin_loaded_when_settings_loaded():  # pylint: disable=invalid-name
        """
        Run plugin_loaded when preferences are loaded.

        ST2 doesn't have plugin_loaded and the API can be called right away. However, settings are loaded asynchronosly
        and return the defaut value until loaded, which is useless. This function emulates plugin_unloaded by
        waiting until settings are loaded and calling plugin_loaded when they do.
        """
        color_scheme = sublime.load_settings(PREFERENCES_SETTINGS_NAME).get("color_scheme", None)
        color_searchers = sublime.load_settings(COLOR_HIGHLIGHTER_SETTINGS_NAME).get("search_colors_in", None)
        if color_scheme is not None and color_searchers is not None:
            plugin_loaded()
        else:
            sublime.set_timeout(call_plugin_loaded_when_settings_loaded, 100)

    call_plugin_loaded_when_settings_loaded()
