import importlib


def test_entrypoint_importable():
    mod = importlib.import_module('tarno_shell.__main__')
    assert hasattr(mod, 'main')
