"""
Best-effort undefined-name checker across bot/ -- AST-based scope tracking
(module/function/class/comprehension scopes, imports, params, assignments,
except-handler names). Catches the class of bug a plain syntax parse and
cross-module import validator both miss: a bare module-like name used via
attribute access (`module.attr(...)`) where `module` was never imported at
all (no `import X` or `from X import Y` anywhere in scope) -- a NameError
at call time, not at import time, so it only surfaces when that code path
actually runs. This is exactly the shape of a real bug found in
bot/cogs/economy.py (used `embedder.gacha_pull_embed(...)` without ever
importing `embedder`).

Not a full linter -- no real Python scoping (class scopes are treated
leniently, `del`/comprehension edge cases are approximate) -- but it's
cheap, dependency-free (no pyflakes/pylint needed), and verified to
actually catch the bug above when reintroduced. Run with:

    python3 tools/check_undefined_names.py

from the repo root. Zero output (aside from the summary line) means clean.
"""

import ast, builtins, os, sys

BUILTINS = set(dir(builtins)) | {'__name__', '__file__', '__doc__', '__builtins__', '__package__', '__spec__', '__loader__', '__class__', '__annotations__', '__module__', '__qualname__', '__all__'}

class Scope:
    def __init__(self, parent=None, is_class=False):
        self.names = set()
        self.parent = parent
        self.is_class = is_class

    def resolve(self, name):
        scope = self
        # class scopes are skipped for nested function lookups (like real Python),
        # but we're lenient here: just walk up through everything.
        while scope:
            if name in scope.names:
                return True
            scope = scope.parent
        return False

def collect_assigned_names(node, scope):
    """Best-effort: add every name this node binds to `scope`."""
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store,)):
            scope.names.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope.names.add(n.name)
        elif isinstance(n, ast.ClassDef):
            scope.names.add(n.name)
        elif isinstance(n, ast.Global):
            pass
        elif isinstance(n, (ast.Import,)):
            for alias in n.names:
                scope.names.add((alias.asname or alias.name.split(".")[0]))
        elif isinstance(n, ast.ImportFrom):
            for alias in n.names:
                scope.names.add(alias.asname or alias.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            scope.names.add(n.name)
        elif isinstance(n, (ast.arg,)):
            scope.names.add(n.arg)


def check_file(path):
    src = open(path).read()
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError as e:
        return [f"{path}: SYNTAX ERROR {e}"]

    errors = []
    module_scope = Scope()
    collect_assigned_names(tree, module_scope)  # crude: treat whole module as flat scope for top-level names

    def visit(node, scope):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in BUILTINS:
                return
            if not scope.resolve(node.id):
                errors.append(f"{path}:{node.lineno}: possibly undefined name '{node.id}'")
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_scope = Scope(parent=scope)
            # params
            args = node.args
            for a in (args.posonlyargs + args.args + args.kwonlyargs):
                fn_scope.names.add(a.arg)
            if args.vararg: fn_scope.names.add(args.vararg.arg)
            if args.kwarg: fn_scope.names.add(args.kwarg.arg)
            collect_assigned_names(node, fn_scope)
            for stmt in node.body:
                visit(stmt, fn_scope)
            for d in node.decorator_list:
                visit(d, scope)
            for default in args.defaults + [d for d in args.kw_defaults if d]:
                visit(default, scope)
            return
        if isinstance(node, ast.ClassDef):
            cls_scope = Scope(parent=scope, is_class=True)
            collect_assigned_names(node, cls_scope)
            for stmt in node.body:
                visit(stmt, cls_scope)
            for d in node.decorator_list:
                visit(d, scope)
            for b in node.bases:
                visit(b, scope)
            return
        if isinstance(node, ast.Lambda):
            lam_scope = Scope(parent=scope)
            for a in node.args.args:
                lam_scope.names.add(a.arg)
            visit(node.body, lam_scope)
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            comp_scope = Scope(parent=scope)
            for gen in node.generators:
                collect_assigned_names(gen.target, comp_scope)
                visit(gen.iter, scope if gen is node.generators[0] else comp_scope)
                for cond in gen.ifs:
                    visit(cond, comp_scope)
            if isinstance(node, ast.DictComp):
                visit(node.key, comp_scope)
                visit(node.value, comp_scope)
            else:
                visit(node.elt, comp_scope)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    for stmt in tree.body:
        visit(stmt, module_scope)

    return errors


root = "bot"
all_errors = []
for dirpath, _, filenames in os.walk(root):
    for fn in filenames:
        if fn.endswith(".py"):
            path = os.path.join(dirpath, fn)
            all_errors.extend(check_file(path))

for e in all_errors:
    print(e)
print(f"\n{len(all_errors)} possibly-undefined names found")
