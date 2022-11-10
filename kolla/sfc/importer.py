import ast
import pathlib
import sys
from importlib.machinery import ModuleSpec

from . import analyser, generator, parser, pretty_code_print

SUFFIX = "kolla"


class KollaImporter:
    def __init__(self, sfc_path):
        """Store path to kolla file"""
        self.sfc_path = sfc_path

    @classmethod
    def find_spec(cls, name, path, target=None):
        """Look for kolla files"""
        # print(name, path, target)
        if target is not None:
            # Target is set when module is being reloaded.
            # In our case we can just return the existing spec.
            return target.__spec__

        package, _, module_name = name.rpartition(".")
        sfc_file_name = f"{module_name}.{SUFFIX}"
        directories = sys.path if path is None else path
        for directory in directories:
            sfc_path = pathlib.Path(directory) / sfc_file_name
            if sfc_path.exists():
                spec = ModuleSpec(name, cls(sfc_path), origin=str(sfc_path))
                spec.has_location = True
                return spec

    def create_module(self, spec):
        """Returning None uses the standard machinery for creating modules"""
        return

    def exec_module(self, module):
        """Executing the module means reading the kolla file"""

        source = self.sfc_path.read_text(encoding="utf-8")
        component_name = "".join(
            [part.capitalize() for part in self.sfc_path.stem.split("_")]
        )

        tree = parser.parse(source)
        analysis = analyser.analyse(tree)
        generated_code = generator.generate(tree, analysis, component_name)
        ast.fix_missing_locations(generated_code)

        pretty_code_print(generated_code)
        # Compile the tree into a code object (module)
        code = compile(generated_code, filename=self.sfc_path, mode="exec")
        # Execute the code as module and pass a dictionary that will capture
        # the global and local scope of the module
        module_namespace = {}
        # exec(code, module)
        exec(code, module_namespace)

        # component = module_namespace[component_name]

        # Add the default module keys to the context such that
        # __file__, __name__ and such are available to the loaded module
        # context.update(module.__dict__)
        module.__dict__.update(module_namespace)
        # module.__dict__.update(context)
        # module.__dict__[component.__name__] = component


# Add the Cgx importer at the end of the list of finders
sys.meta_path.append(KollaImporter)
