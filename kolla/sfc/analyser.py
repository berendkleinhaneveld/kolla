import ast
from collections import defaultdict

from .parser import Element, Expression, Script


def analyse(tree):
    script = [element for element in tree.children if isinstance(element, Script)]
    if not script:
        return {
            "script": None,
            "variables": set(),
            "will_change": set(),
            "will_use_in_template": set(),
            "will_change_elements": defaultdict(set),
            "scope": ScopeFinder(),
        }

    script = script[0]

    scope_finder = ScopeFinder()
    scope_finder.visit(script.content)

    result = {
        "script": script,
        "variables": scope_finder.variables,
        "will_change": scope_finder.result,
        "will_use_in_template": set(),
        "will_change_elements": defaultdict(set),
        "scope": scope_finder,
    }
    traverse(tree, result)
    return result


def traverse(element, result):
    if hasattr(element, "children"):
        for child in element.children:
            traverse(child, result)
    if hasattr(element, "attributes"):
        for attr in element.attributes:
            traverse(attr, result)

    if isinstance(element, Element):
        for attr in element.attributes:
            if isinstance(attr.value, Expression):
                scope_finder = ScopeFinder()
                scope_finder.visit(attr.value.content)

                result["will_use_in_template"].update(scope_finder.symbols)
                for symbol in scope_finder.symbols:
                    result["will_change_elements"][symbol].add((element, attr))


class ScopeFinder(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        self.scope = ["global"]
        self.elevated = [set()]
        self.globals = []
        self.variables = set()
        self.symbols = set()
        self.result = defaultdict(set)
        self.imports = []

    def generic_visit(self, node):
        # Gather a list of all kinds of variables in global scope
        if len(self.scope) == 1:
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                self.variables.add(node.id)
            elif isinstance(node, ast.FunctionDef):
                self.variables.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    self.variables.add(alias.name)
                self.imports.append(node)

            if isinstance(node, ast.Name):
                self.symbols.add(node.id)

        # Figure out if scope is changed
        scope_change = False
        if isinstance(node, ast.FunctionDef):
            self.scope.append(node.name)
            self.elevated.append(set())
            scope_change = True

        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if len(self.scope) == 1:
                self.globals.append(node)
            elif node.id in self.elevated[-1]:
                self.result[node.id].add(node)

        # Keep track of which variables are 'elevated' from global for
        # the current scope
        if len(self.scope) != 1 and isinstance(node, ast.Global):
            self.elevated[-1].update(set(node.names))

        super().generic_visit(node)

        if scope_change:
            self.scope.pop()
            self.elevated.pop()
