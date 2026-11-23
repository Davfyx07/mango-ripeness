import pytest

from api.app import create_app
from api.tests.make_random_weights import make_weights


@pytest.fixture(scope="session")
def weights_dir(tmp_path_factory):
    """Pesos aleatorios de los 5 modelos reales (se crean una vez por sesión de pruebas)."""
    return make_weights(tmp_path_factory.mktemp("weights"))


@pytest.fixture(scope="session")
def app(weights_dir):
    """La app con los 5 modelos; se comparte para no volver a cargarlos en cada prueba."""
    return create_app(models_dir=weights_dir, web_dir=None)


@pytest.fixture
def client(app):
    return app.test_client()
