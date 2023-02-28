import ast


class RemoveImports(ast.NodeTransformer):
    def __init__(self, imports):
        super().__init__()
        self.imports = imports

    def generic_visit(self, node):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if node in self.imports:
                return None
        return super().generic_visit(node)


class GlobalToNonLocal(ast.NodeTransformer):
    def visit_Global(self, node):
        return ast.Nonlocal(names=node.names)


class SymbolsFromContext(ast.NodeTransformer):
    def __init__(self, symbols):
        super().__init__()
        self.symbols = symbols

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.symbols:
            return ast.Subscript(
                value=ast.Name(id="context", ctx=ast.Load()),
                slice=ast.Constant(value=node.id),
                ctx=ast.Load(),
            )

        return node


class WrapWithInvalidateCall(ast.NodeTransformer):
    def __init__(self, nodes):
        super().__init__()
        self.nodes = nodes

    def generic_visit(self, node):
        result = []
        targets = []
        if hasattr(node, "target"):
            targets = [node.target]
        elif hasattr(node, "targets"):
            targets = node.targets

        for target in targets:
            if target not in self.nodes:
                continue

            elements = target.elts if isinstance(target, ast.Tuple) else [target]
            for element in elements:
                result.append(
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Name(id="__invalidate", ctx=ast.Load()),
                            args=[
                                ast.Constant(value=element.id),
                                ast.Name(id=element.id, ctx=ast.Load()),
                            ],
                            keywords=[],
                        )
                    )
                )

        subtree = super().generic_visit(node)
        if result:
            if isinstance(result, list):
                return [subtree, *result]
            return [subtree, result]
        return subtree


class WrapWithGetFromProps(ast.NodeTransformer):
    def __init__(self, nodes):
        super().__init__()
        self.nodes = nodes

    def generic_visit(self, node):
        # Wrap each assign in the global root scope
        if isinstance(node, ast.Assign) and node.targets[0] in self.nodes:
            return ast.Assign(
                targets=node.targets,
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="__props", ctx=ast.Load()),
                        attr="get",
                        ctx=ast.Load(),
                    ),
                    args=[
                        ast.Constant(value=node.targets[0].id),
                        node.value,
                    ],
                    keywords=[],
                ),
            )
        return super().generic_visit(node)
