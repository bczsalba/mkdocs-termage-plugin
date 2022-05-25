from __future__ import annotations

import re

from mkdocs.plugins import BasePlugin

from pathlib import Path

import pytermgui as ptg
from pytermgui.pretty import print
from pytermgui.terminal import Terminal

RE_BLOCK = re.compile(r"(\`\`\`termage(.*?)\n([\s\S]*?)\`\`\`)")

OUTPUT_BLOCK_TEMPLATE = """\
=== "Python"
    ```py
{code}
    ```

=== "Output"
{svg}
"""


def _get_terminal_from_opts(width: int, height: int) -> ptg.Terminal:
    """Creates a terminal with the size options."""

    return ptg.Terminal(size=(width, height))


def _find_indent(line: str) -> int:
    """Finds the indentation of the line."""

    return len(line) - len(line.lstrip())


ptg.WindowManager.autorun = False


class TermagePlugin(BasePlugin):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._svg_count = 0

    def _parse_options(self, options: str) -> dict[str, int | str]:
        """Parses option strings.

        Each option follows the pattern `key=value`. Spaces are only allowed when escaped.
        """

        opt_dict = {
            "width": ptg.terminal.width,
            "height": ptg.terminal.height,
            "foreground": "#dddddd",
            "background": "#212121",
            "title": "",
            "include": None,
        }

        for option in re.split(r"(?<!\\) ", options):
            if len(option) == 0:
                continue

            key, value = option.split("=")
            value = value.replace("\\", "")

            if key not in opt_dict:
                raise ValueError(
                    f"Unexpected key {key!r}. Please choose from {list(opt_dict)!r}."
                )

            if value.isdigit():
                value = int(value)
            opt_dict[key] = value

        return opt_dict

    def _handle_options(self, options: str) -> tuple[ptg.Terminal, str, str | None]:
        """Handles the options provided within the code block.

        Returns:
            A tuple of the custom terminal instance, and the contents of the file
            passed with the `include` option, or None if not given.
        """

        opt_dict = self._parse_options(options)

        include = None
        if opt_dict["include"] is not None:
            with open(opt_dict["include"], "r") as include_file:
                include = include_file.read()

        terminal = _get_terminal_from_opts(opt_dict["width"], opt_dict["height"])

        ptg.set_global_terminal(terminal)
        assert terminal is ptg.get_terminal()

        ptg.Color.default_foreground = ptg.str_to_color(
            opt_dict["foreground"], is_background=True
        )
        ptg.Color.default_background = ptg.str_to_color(
            opt_dict["background"], is_background=True
        )

        return terminal, opt_dict["title"], include

    def _get_next_path(self) -> str:
        """Gets the next SVG path."""

        self._svg_count += 1

        return f"assets/termage_{self._svg_count}.svg"

    def _replace_codeblock(self, matchobj) -> str:
        """Replaces a codeblock with the Termage content."""

        full, options, code = matchobj.groups()
        start, end = matchobj.span()

        terminal, title, include = self._handle_options(options)

        if include is not None:
            code = include + code

        buffer = ""
        code_filtered = []

        lines = code.splitlines()
        first_line_indent = max(_find_indent(lines[0]), 4)

        exec_globals = {}

        with terminal.record() as recording:
            for line in lines:
                if line.startswith("@"):
                    line = line.replace("@", " ", 1)
                else:
                    code_filtered.append(line)

                if line == "":
                    continue

                buffer += line + "\n"

            code_obj = compile(buffer, "<string>", "exec")
            exec(code_obj, exec_globals)

            if "manager" in exec_globals:
                exec_globals["manager"].compositor.draw()

        path = self._get_next_path()
        recording.save_svg(str(Path("docs") / path), title=title)

        indent = first_line_indent * " "
        code_indented = indent + f"\n{indent}".join(code_filtered)

        return OUTPUT_BLOCK_TEMPLATE.format(
            code=code_indented, svg=f"{indent}![]({path})"
        )

    def on_page_markdown(self, markdown, page, files, config) -> str:

        return RE_BLOCK.sub(self._replace_codeblock, markdown)
