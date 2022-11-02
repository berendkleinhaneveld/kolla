from ..renderers import DictRenderer


class Component:
    # SVELTE INTERNALS
    def __init__(self, options, instance, create_fragment, props=None, **kwargs):
        super().__init__()

        if props is None:
            props = {}

        if options is None:
            options = {}

        self.renderer = options.get("renderer", DictRenderer())
        self.scheduler = options.get("scheduler", self.renderer.scheduler)

        def invalidate(variable, new_value):
            self.ctx[variable] = new_value
            self.dirty.add(variable)
            self.scheduler.add(self)

        self.ctx = instance(self, props, invalidate)
        self.fragment = create_fragment(self.ctx, self.renderer)
        self.dirty = set()
        self.invalidate = invalidate

        def flush_update():
            # Update the fragment
            self.fragment.update(self.ctx, self.dirty)
            # Clear the dirty flags
            self.dirty.clear()

        self.flush_update = flush_update
        # Create the fragment
        self.fragment.create()
        # Mount the fragment onto the DOM
        self.fragment.mount(options["target"], None)
