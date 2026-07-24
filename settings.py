"""Load the tuning knobs from config.yaml (see that file for what each does)."""

import os
import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    with open(os.path.join(_HERE, "config.yaml")) as f:
        return yaml.safe_load(f)


CFG = load()
