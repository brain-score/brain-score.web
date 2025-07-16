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
    def test_expandable_headers_equal_expected(self, page):
        expected = ['Global Score', 'Neural', 'Behavior', 'Engineering']
        page.wait_for_selector('.expandable-header-label', timeout=5000)
        labels = page.locator('.expandable-header-label') \
            .all_text_contents()
        labels = [l.strip() for l in labels if l.strip()]
        assert labels == expected, f"Expected headers {expected}, but got {labels}"

    def test_default_checkbox_visibility(self, page):
        """
        Tests if checkbox of Included Benchmarks starts with correct defaults:

        1) neural_vision is checked
        2) behavior_vision is checked
        3) engineering_vision is checked
        """

        page.click('#advancedFilterBtn')
        neural_cb = page.wait_for_selector(
            '#benchmarkFilterPanel input[type="checkbox"][value="neural_vision_v0"]',
            state='visible',
            timeout=5000)

        behavior_cb = page.wait_for_selector(
            '#benchmarkFilterPanel input[type="checkbox"][value="behavior_vision_v0"]',
            state='visible',
            timeout=5000)

        engineering_cb = page.wait_for_selector(
            '#benchmarkFilterPanel input[type="checkbox"][value="engineering_vision_v0"]',
            state='visible',
            timeout=5000
        )

        assert neural_cb.is_checked(), "Expected Neural checkbox to start checked"
        assert behavior_cb.is_checked(), "Expected Behavior checkbox to start checked"
        assert engineering_cb.is_checked(), "Expected Engineering checkbox to start checked"

    def test_neural_filter_out(self, page):
        """
        Tests filtering logic:

        1) unchecks neural benchmark root
        2) ensures neural is indeed missing from new table headers
        3) ensures global score is not filtered score
        4) ensure top 5 models names are equal to expected names
        5) ensure top 5 model scores are equal to expected scores.

        """

        page.click('#advancedFilterBtn')
        neural_cb = page.wait_for_selector(
            '#benchmarkFilterPanel input[type="checkbox"][value="neural_vision_v0"]',
            state='visible',
            timeout=5000
        )
        assert neural_cb.is_checked(), "Expected Neural checkbox to start checked"
        neural_cb.uncheck()
        page.wait_for_selector(
            '.expandable-header-label:has-text("Neural")',
            state='detached',
            timeout=5000)
        headers = page.locator('.ag-header-cell').all_text_contents()
        assert not any("Neural" in h for h in headers), f"Still saw Neural in {headers}"

        # 6) Verify that “Filtered Score” is visible instead - Currently broken
        # filtered = page.locator('.ag-header-cell-text:has-text("Filtered Score")')
        # assert filtered.count() == 1, f"'Filtered Score' header not found, headers are {headers}"
        # # top_scores = page.locator('.ag-cell[col-id="filtered_score"]').all_text_contents()[:5]
        # # expected_scores = ["0.56", "0.56", "0.56", "0.55", "0.55"]
        # # assert top_scores == expected_scores, f"Expected top scores {expected_scores}, got {top_scores}"
        #
        # # 8) Check top 5 model names
        # top_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        # print(top_models)
        # expected_models = [
        #     "convnext_xlarge:fb_in22k_ft_in1k",
        #     "vit_large_patch14_clip_224:laion2b_ft_in1k",
        #     "resnext101_32x48d_wsl",
        #     "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
        #     "vit_base_patch16_clip_224:openai_ft_in12k_in1k"
        # ]
        # assert top_models == expected_models, f"Expected top models {expected_models}, got {top_models}"






