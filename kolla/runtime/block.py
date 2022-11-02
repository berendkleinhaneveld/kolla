class Block:
    __slots__ = ("create", "mount", "update", "unmount")

    def __init__(self, create, mount, update, unmount):
        self.create = create
        self.mount = mount
        self.update = update
        self.unmount = unmount
