from bot.config import ROOT, DATA_DIR, MOCK_TESTS_DIR, MOCK_IMAGES_DIR, PDF_RESULTS_DIR, RENDERED_IMAGES_DIR


def test_root_is_directory():
    assert ROOT.is_dir()
    assert (ROOT / "__init__.py").exists()


def test_data_dir_is_defined():
    assert DATA_DIR.name == "data"


def test_mock_tests_dir_path():
    assert str(MOCK_TESTS_DIR).endswith("mock_tests")


def test_mock_images_dir_path():
    assert str(MOCK_IMAGES_DIR).endswith("mock_images")


def test_pdf_results_dir_path():
    assert str(PDF_RESULTS_DIR).endswith("pdf_results")


def test_rendered_images_dir_path():
    assert str(RENDERED_IMAGES_DIR).endswith("rendered_images")


def test_all_dirs_are_under_data():
    assert str(MOCK_TESTS_DIR).startswith(str(DATA_DIR))
    assert str(MOCK_IMAGES_DIR).startswith(str(DATA_DIR))
    assert str(PDF_RESULTS_DIR).startswith(str(DATA_DIR))
    assert str(RENDERED_IMAGES_DIR).startswith(str(DATA_DIR))
