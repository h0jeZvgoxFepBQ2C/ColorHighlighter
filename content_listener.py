"""Component for listening for loaded views and highlighting colors in them."""

try:
    from .regions import NormalizedRegion
except ValueError:
    from regions import NormalizedRegion


class ContentListener(object):
    """Component for listening for loaded views and highlighting colors in them."""

    def __init__(self, color_searcher, view, color_highlighter):
        """
        Init ContentListener.

        Arguments:
        - color_searcher - a color searcher to search colors with.
        - view - a view to highlight colors in.
        - color_highlighter - a combined color highlighter to highlight colors with.
        """
        self._color_searcher = color_searcher
        self._view = view
        self._color_highlighter = color_highlighter

    def on_load(self):
        """Call when view's content is loaded."""
        color_regions = self._generate_color_regions()
        self._color_highlighter.highlight_regions(color_regions)

    def _generate_color_regions(self):
        for line in self._generate_lines():
            for color_region in self._color_searcher.search(self._view, line):
                yield color_region

    def _generate_lines(self):
        for line in self._view.lines(NormalizedRegion(0, self._view.size()).region()):
            yield NormalizedRegion(line)
