from observ import scheduler, watch

from ..renderers import DictRenderer

scheduler.register_request_flush(scheduler.flush)


def create_component(fragment):
    fragment.create()


def mount_component(component, target, anchor):
    # print(f"mount component: {target=} {anchor=}")
    if target:
        component.fragment.mount(target, anchor)
    # TODO: run on_mount callbacks/handlers


def destroy_component(component):
    # TODO: run on_destroy callbacks/handlers
    component.fragment.destroy()
    component.fragment = None
    component.ctx = {}


class Component:
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

        self.invalidate = invalidate

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
        if "target" in options:
            self.fragment.create()

        # Mount the fragment onto the DOM
        mount_component(self, options.get("target"), options.get("anchor"))

        if props is not None:
            self._watch_props = watch(
                lambda: props,
                lambda new: self.set(new),
                deep=True,
            )

    def set(self, props):
        for key, value in props.items():
            self.invalidate(key, value)
        # self.fragment.update(props, list(props))
