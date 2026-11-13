"""The smallest useful IPrepareRendererResources.

Streams a 3D Tiles tileset for a few seconds from a camera placed above its
root bounding volume and prints the tiles selected for rendering. The
preparer reads each tile's ``cesium.gltf.Model`` and stores what a real
renderer would keep (here, vertex counts in place of GPU buffers).

    python examples/minimal_preparer.py https://example.com/tileset.json

The preparer runs in two places. ``prepare_in_load_thread`` is called on a
worker thread with the loaded model (while it holds the GIL, so keep it
short); ``prepare_in_main_thread`` is called from ``update_view_group`` and is
the place to touch anything that is not thread-safe. Whatever both return is
stored on the tile and handed back in ``free_tile`` when the tile unloads.

``tile_load_result.model`` is only valid during ``prepare_in_load_thread``:
cesium-native moves the model into the tile once the call returns. Read what
you need there, or get the model again on the main thread from
``tile.content.render_content.model``.
"""
import sys
import time

import numpy as np
from cesium.async_ import AsyncSystem, NativeTaskProcessor
from cesium.curl import CurlAssetAccessor
from cesium.tiles.selection import (
    IPrepareRendererResources,
    Tileset,
    TilesetExternals,
    TilesetOptions,
    ViewState,
)
from cesium.utility import CreditSystem


def vertex_count(model):
    """Sum of POSITION counts over every primitive of the model."""
    total = 0
    for mesh in model.meshes:
        for primitive in mesh.primitives:
            index = primitive.attributes.get("POSITION")
            if index is not None:
                total += model.accessors[index].count
    return total


class CountVertices(IPrepareRendererResources):
    """Read the model on the worker thread, keep only plain Python data."""

    def prepare_in_load_thread(self, async_system, tile_load_result, transform):
        model = tile_load_result.model          # None for tiles without glTF
        if model is None:
            return None
        # the model is only valid during this call: copy out what you need
        return {"vertices": vertex_count(model),
                "transform": np.asarray(transform).reshape(4, 4)}

    def prepare_in_main_thread(self, tile, load_thread_result):
        # the model now lives on the tile, valid until free_tile
        if load_thread_result is not None:
            model = tile.content.render_content.model
            load_thread_result["meshes"] = len(model.meshes)
        return load_thread_result

    def free_tile(self, tile, load_thread_result, main_thread_result):
        pass

    # raster overlays are not used here; the base class provides no-ops
    # for prepare_raster_*, attach_raster_* and free_raster.


def main(url: str, seconds: float = 10.0) -> int:
    asys = AsyncSystem(NativeTaskProcessor())
    externals = TilesetExternals(CurlAssetAccessor(), CountVertices(), asys, CreditSystem())
    options = TilesetOptions()
    options.maximum_screen_space_error = 16.0
    tileset = Tileset(externals, url, options)

    view_group = tileset.default_view_group
    deadline = time.monotonic() + seconds
    rendered = 0
    while time.monotonic() < deadline:
        asys.dispatch_main_thread_tasks()       # runs prepare_in_main_thread
        root = tileset.root_tile
        if root is None:                        # tileset.json still loading
            time.sleep(0.05)
            continue
        center = np.asarray(root.bounding_volume.center, dtype=np.float64)
        distance = float(np.linalg.norm(center))
        # ECEF: "up" points away from Earth's centre; a local tileset sitting at
        # the origin (no transform) is looked at from +Z instead
        up = center / distance if distance > 1.0 else np.array([0.0, 0.0, 1.0])
        camera_up = np.array([0.0, 0.0, 1.0]) if abs(up[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        eye = center + up * max(100.0, root.geometric_error * 4.0)
        view = ViewState(eye, -up, camera_up, [1280.0, 720.0], 1.2, 0.8)
        result = tileset.update_view_group(view_group, [view], 1.0 / 30.0)
        tileset.load_tiles()
        rendered = len(result.tiles_to_render)
        time.sleep(1.0 / 30.0)

    prepared, vertices = 0, 0
    for tile in tileset.loaded_tiles():
        content = tile.content.render_content
        if content is not None and content.render_resources is not None:
            prepared += 1
            vertices += content.render_resources["vertices"]
    print(f"{tileset.number_of_tiles_loaded} tiles loaded, {rendered} selected to render, "
          f"{prepared} prepared with {vertices} vertices in all")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
