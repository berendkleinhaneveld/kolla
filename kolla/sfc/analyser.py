import ast
from collections import defaultdict

import ast_scope

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
        }

    script = script[0]

    scope_info = ast_scope.annotate(script.content)

    variables = scope_info.global_scope.symbols_in_frame

    dep_finder = DependencyFinder(scope_info)
    dep_finder.visit(script.content)

    result = {
        "script": script,
        "variables": variables,
        "will_change": dep_finder.result,
        "will_use_in_template": set(),
        "will_change_elements": defaultdict(set),
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
                scope_info = ast_scope.annotate(attr.value.content)
                result["will_use_in_template"].update(
                    scope_info.global_scope.symbols_in_frame
                )
                if changes := scope_info.global_scope.symbols_in_frame & set(
                    result["will_change"]
                ):
                    for change in changes:
                        result["will_change_elements"][change].add((element, attr))


class DependencyFinder(ast.NodeVisitor):
    def __init__(self, scope_info):
        super().__init__()
        self.scope_info = scope_info
        self.result = defaultdict(set)
        self.depth = 0

    def generic_visit(self, node):
        # Increase scope depth when entering functions
        if isinstance(node, ast.FunctionDef):
            self.depth += 1

        if self.depth > 0 and hasattr(node, "ctx"):
            if isinstance(node.ctx, ast.Store):
                # Variables have to be marked 'global'
                if self.scope_info[node] == self.scope_info.global_scope:
                    # TODO: maybe add the node itself instead of just id?
                    self.result[node.id].add(node)

        super().generic_visit(node)

        if isinstance(node, ast.FunctionDef):
            self.depth -= 1
