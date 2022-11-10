import ast
from pathlib import Path

from . import analyser, generator, parser


def load(file):
    file = Path(file)
    component_name = "".join([part.capitalize() for part in file.stem.split("_")])
    source = file.read_text(encoding="utf-8")
    return load_from_string(source, component_name, file)


def load_from_string(source, component_name, filename=None):
    tree = parser.parse(source)
    analysis = analyser.analyse(tree)
    generated_code = generator.generate(tree, analysis, component_name)
    ast.fix_missing_locations(generated_code)

    pretty_code_print(generated_code)

    # Compile the tree into a code object (module)
    code = compile(generated_code, filename=filename or "<template>", mode="exec")
    # Execute the code as module and pass a dictionary that will capture
    # the global and local scope of the module
    module = {}
    exec(code, module)
    return module[component_name], module


def pretty_code_print(tree):  # pragma: no cover
    """Handy function for debugging an ast tree"""
    plain_result = ast.unparse(tree)

    try:
        import black

        result = black.format_file_contents(
            plain_result, fast=False, mode=black.mode.Mode()
        )
    except ImportError:
        pass

    try:
        from rich.console import Console
        from rich.syntax import Syntax

        console = Console()
    except ImportError:
        print(plain_result)  # noqa: T201
        return

    try:
        result = black.format_file_contents(
            plain_result, fast=False, mode=black.mode.Mode()
        )
    except black.parsing.InvalidInput:
        result = plain_result
        return

    syntax = Syntax(result, "python")
    console.print(syntax)
    # print("----")
    # print(result)
    # print("----")
