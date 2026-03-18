import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from engine.temporada_engine import TemporadaEngine as Temporada

__all__ = ["Temporada"]
