import logging
from pathlib import Path
from .png import PngPetRenderer


def create_renderer(name: str, image: Path, parent=None):
    if name != "png":
        logging.warning("Renderer %r is not installed; using PNG", name)
    return PngPetRenderer(image, parent)
