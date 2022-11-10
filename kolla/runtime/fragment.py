class Fragment:
    __slots__ = ("create", "mount", "update", "destroy")

    def __init__(self, create, mount, update, destroy):
        self.create = create
        self.mount = mount
        self.update = update
        self.destroy = destroy
