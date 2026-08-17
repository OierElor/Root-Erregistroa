"""Testen ingurune isolatua.

Bi gauza ezarri behar dira moduluak inportatu AURRETIK:
  * KONFIG_DIR — testek ez dezaten zure benetako konfigurazioa ukitu.
  * ROOT_KDF_N — scrypt-en kostua jaitsi (testetan bakarrik; produkzioan 2^17).
"""

import os
import sys
import tempfile
from pathlib import Path

_ALDI_BATERAKOA = tempfile.mkdtemp(prefix="root-testak-")
os.environ["KONFIG_DIR"] = _ALDI_BATERAKOA
os.environ["ROOT_KDF_N"] = "10"
# `app` inportatzeak DB_FILE irakurtzen du: zure benetako erregistroa ez ukitzeko.
os.environ.setdefault("DB_FILE", os.path.join(_ALDI_BATERAKOA, "testak.db"))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
