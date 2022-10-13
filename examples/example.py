from observ import scheduler
from PySide6 import QtWidgets


import kolla  # isort: split
from examples.counter import Counter  # noqa: I100


# class Counter(kolla.Component):
#     def __init__(self, props):
#         super().__init__(props)
#         self.state["count"] = 0

#     @property
#     def label_text(self):
#         return f"Count: {self.state['count']}"

#     def bump(self):
#         self.state["count"] += 1

#     def render(self, renderer):
#         from observ import watch
#         from kolla.types import Element

#         elements = []
#         el0 = Element("window")
#         el1 = Element("widget", parent=el0)
#         el2 = Element("label", parent=el1)
#         el2._watchers["bind:text"] = watch(
#             lambda: self._lookup("label_text", globals()),
#             lambda new: renderer.set_attribute(el2._instance, "text", new),
#         )
#         el3 = Element("label", parent=el1)
#         el3.set_attribute("text", "Even!")
#         el1.add_conditional_item(
#             "el3",
#             el3,
#             lambda: bool(self._lookup("count", globals()) % 2 == 0),
#             renderer,
#         )
#         widget0 = Element("widget", parent=el1)
#         el1.add_conditional_item(
#             "widget0",
#             widget0,
#             lambda: bool(self._lookup("count", globals()) % 2 == 1),
#             renderer,
#         )
#         el4 = Element("label", parent=widget0)
#         el4.set_attribute("text", "Uneven!")
#         el5 = Element("button", parent=el1)
#         el5.set_attribute("text", "Click")
#         el5.add_event("clicked", self._lookup("bump", globals()))
#         elements.append(el0)
#         return elements


if __name__ == "__main__":
    app = QtWidgets.QApplication()
    scheduler.register_qt()

    gui = kolla.Kolla(renderer=kolla.PySideRenderer())
    gui.render(Counter, state=None, container=app)

    app.exec()
