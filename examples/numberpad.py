import pygfx as gfx  # noqa: I001
from wgpu.gui.auto import WgpuCanvas, run

import collagraph

from examples.number_pad import NumberPad


if __name__ == "__main__":
    canvas = WgpuCanvas(size=(600, 400))
    renderer = gfx.renderers.WgpuRenderer(canvas)

    camera = gfx.PerspectiveCamera(60, 16 / 9)
    camera.world.z = 7
    camera.world.y = -2
    camera.show_pos((0, 0, 0))

    controls = gfx.OrbitController(camera)
    controls.register_events(renderer)

    container = gfx.Scene()
    container.add(gfx.AmbientLight())
    point_light = gfx.PointLight()
    point_light.world.position = [10, 30, 40]
    container.add(point_light)

    def animate():
        renderer.render(container, camera)

    cg_renderer = collagraph.PygfxRenderer()
    cg_renderer.add_on_change_handler(lambda: canvas.request_draw(animate))

    gui = collagraph.Collagraph(renderer=cg_renderer)
    gui.render(NumberPad, target=container)
    run()
