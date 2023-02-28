import ast
from collections import defaultdict

from .parser import (
    DIRECTIVE_ELSE,
    DIRECTIVE_ELSE_IF,
    DIRECTIVE_IF,
    Conditional,
    Element,
    Expression,
    Script,
)


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
            "conditional_blocks": [],
        }

    # Demand that there is just one script tag
    assert len(script) == 1, "There is more than one script tag"
    script = script[0]

    scope_finder = ScopeFinder()
    scope_finder.visit(script.content)

    analysis = {
        "script": script,
        "variables": scope_finder.variables,
        "will_change": scope_finder.changed_variables,
        "will_use_in_template": set(),
        "will_change_elements": defaultdict(set),
        "scope": scope_finder,
        "conditional_blocks": [],
    }
    analyse_template_content(tree, analysis)
    find_conditionals(tree, analysis, Conditional())
    return analysis


def directive_for_element(element):
    if not hasattr(element, "attributes"):
        return
    for attr in element.attributes:
        if attr.name in {DIRECTIVE_IF, DIRECTIVE_ELSE_IF, DIRECTIVE_ELSE}:
            return attr.name


def close_conditional(conditional):
    parent = conditional.items[0].parent
    if parent:
        item_index = parent.items.index(conditional.items[0])
        del parent.children[item_index : item_index + len(conditional.items)]
        parent.children.insert(conditional)


def find_conditionals(element, analysis, current_block):
    if hasattr(element, "children"):
        for child in element.children:
            if directive := directive_for_element(child):
                if directive == DIRECTIVE_IF:
                    if current_block and current_block.items:
                        analysis["conditional_blocks"].append(current_block.items)
                        close_conditional(current_block)
                        current_block = Conditional()
                current_block.items.append(child)
            elif current_block and current_block.items:
                analysis["conditional_blocks"].append(current_block.items)
                close_conditional(current_block)
                current_block = Conditional()

        if current_block and current_block.items:
            analysis["conditional_blocks"].append(current_block.items)
            close_conditional(current_block)
            current_block = Conditional()

        find_conditionals(child, analysis, [])


def analyse_template_content(element, analysis):
    if hasattr(element, "children"):
        for child in element.children:
            analyse_template_content(child, analysis)
    if hasattr(element, "attributes"):
        for attr in element.attributes:
            analyse_template_content(attr, analysis)

    if isinstance(element, Element):
        for attr in element.attributes:
            if isinstance(attr.value, Expression):
                scope_finder = ScopeFinder()
                scope_finder.visit(attr.value.content)

                analysis["will_use_in_template"].update(scope_finder.symbols)
                for symbol in scope_finder.symbols:
                    analysis["will_change_elements"][symbol].add((element, attr))


class ScopeFinder(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        # Stack of scope names
        self._scope = ["global"]
        # Stack of names marked as global per scope (follows self._scope)
        self._elevated = [set()]

        # List of global name nodes (variables that are declared in global scope)
        self.globals: [ast.Name] = []
        # Set of names (variables and functions) within the global scope
        self.variables = set()
        # Set of all referenced names / symbols (used for template expressions)
        self.symbols = set()
        # Dict of all the global variables that are changed in non-global scopes
        self.changed_variables = defaultdict(set)
        # List of Import and ImportFrom nodes from the root scope
        self.imports = []

    def generic_visit(self, node):
        # Gather a list of all kinds of variables in global scope
        if len(self._scope) == 1:
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
            self._scope.append(node.name)
            self._elevated.append(set())
            scope_change = True

        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if len(self._scope) == 1:
                self.globals.append(node)
            elif node.id in self._elevated[-1]:
                self.changed_variables[node.id].add(node)

        # Keep track of which variables are 'elevated' from global for
        # the current scope
        if len(self._scope) != 1 and isinstance(node, ast.Global):
            self._elevated[-1].update(set(node.names))

        super().generic_visit(node)

        if scope_change:
            self._scope.pop()
            self._elevated.pop()
