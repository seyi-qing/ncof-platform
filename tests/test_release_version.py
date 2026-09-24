from app.main import app

def test_release_version_is_1_7_0():
    assert app.version == "1.7.0"
