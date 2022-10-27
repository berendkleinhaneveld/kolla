class Scheduler:
    def __init__(self):
        self.queue = []

    def add(self, component):
        if component not in self.queue:
            self.queue.append(component)

    def flush(self):
        while self.queue:
            component = self.queue.pop(0)
            component.flush_update()


def schedule_update(component):
    # SVELTE INTERNALS
    scheduler.add(component)


scheduler = Scheduler()


class Component:
    # SVELTE INTERNALS
    def __init__(self, options, instance, create_fragment, props=None, **kwargs):
        super().__init__()

        from kolla.renderers import DictRenderer

        if props is None:
            props = {}

        if options is None:
            options = {}

        self.renderer = options.get("renderer", DictRenderer())

        def invalidate(variable, new_value):
            self.ctx[variable] = new_value
            self.dirty.add(variable)
            schedule_update(self)

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
