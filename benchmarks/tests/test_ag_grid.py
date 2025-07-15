import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture(scope="function")
def page(browser):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    page.goto("https://brain-score-web-staging.eba-e8pevjnc.us-east-2.elasticbeanstalk.com/vision/leaderboard")
    page.wait_for_selector('.ag-root', timeout=10000)
    yield page
    context.close()


# ----------------- SORTING -----------------

class TestSort:
    def test_sort_rank_descending(self, page):
        scores_actual = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[0:5]
        scores_expected = [str(x) for x in [1, 2, 2, 2, 5]]
        assert scores_actual == scores_expected

    def test_model_descending(self, page):
        header = page.locator('.ag-header-cell[col-id="model"]')
        header.click()
        page.wait_for_timeout(1000)
        scores_actual = page.locator('.ag-cell[col-id="model"]').all_text_contents()[0:2]
        scores_actual = [i[:-8] for i in scores_actual]  # get rid of name suffix on model column entires
        scores_expected = ["yudixie_resnet50_translation_rotation_0_240908", "yudixie_resnet50_translation_reg_0_240908"]
        assert scores_actual == scores_expected

    def test_sort_average_descending(self, page):
        scores_actual = page.locator('.ag-cell[col-id="average_vision_v0"]').all_text_contents()[0:5]
        scores_expected = [str(x) for x in [0.47, 0.45, 0.45, 0.45, 0.44]]
        assert scores_actual == scores_expected

    def test_sort_neural_descending(self, page):
        header = page.locator('.ag-header-cell[col-id="neural_vision_v0"]')
        header.click()
        page.wait_for_timeout(1000)
        scores_actual = page.locator('.ag-cell[col-id="neural_vision_v0"]').all_text_contents()[0:5]
        scores_expected = [str(x) for x in [0.39, 0.39, 0.39, 0.38, 0.38]]
        assert scores_actual == scores_expected

    def test_sort_behavioral_descending(self, page):
        header = page.locator('.ag-header-cell[col-id="behavior_vision_v0"]')
        header.click()
        page.wait_for_timeout(1000)
        scores_actual = page.locator('.ag-cell[col-id="behavior_vision_v0"]').all_text_contents()[0:5]
        scores_expected = [str(x) for x in [0.56, 0.56, 0.56, 0.55, 0.55]]
        assert scores_actual == scores_expected

    def test_sort_engineering_descending(self, page):
        header = page.locator('.ag-header-cell[col-id="engineering_vision_v0"]')
        header.click()
        page.wait_for_timeout(1000)
        scores_actual = page.locator('.ag-cell[col-id="engineering_vision_v0"]').all_text_contents()[0:5]
        scores_expected = [str(x) for x in [0.63, 0.59, 0.59, 0.59, 0.58]]
        assert scores_actual == scores_expected

    # ----------------- FILTERING -----------------
class TestFilter:
    def test_visible_column_headers(self, page):
        # select the three possible label locations:
        labels = page.locator(
            '.ag-header-cell-text, .leaf-header-label, .expandable-header-label'
        ).all_text_contents()
        labels = [lbl.strip() for lbl in labels if lbl.strip()]
        expected = [
            'Rank',
            'Model',
            'Global Score',
            'Neural',
            'Behavior',
            'Engineering'
        ]
        for want in expected:
            assert want in labels, f"Missing header: {want}. Got: {labels}"






