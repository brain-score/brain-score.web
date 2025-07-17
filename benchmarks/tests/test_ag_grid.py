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
    page.set_default_navigation_timeout(60000)
    page.goto("https://brain-score-web-staging.eba-e8pevjnc.us-east-2.elasticbeanstalk.com/vision/leaderboard")
    page.wait_for_selector('.ag-root', timeout=60000)
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
        """
        Tests if default headers are what they should be:

        1) Headers are (upon page open) as listed in 'expected' list below
        """

        expected = ['Global Score', 'Neural', 'Behavior', 'Engineering']
        page.wait_for_selector('.expandable-header-label', timeout=30000)
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
            timeout=30000)

        behavior_cb = page.wait_for_selector(
            '#benchmarkFilterPanel input[type="checkbox"][value="behavior_vision_v0"]',
            state='visible',
            timeout=30000)

        engineering_cb = page.wait_for_selector(
            '#benchmarkFilterPanel input[type="checkbox"][value="engineering_vision_v0"]',
            state='visible',
            timeout=30000
        )

        assert neural_cb.is_checked(), "Expected Neural checkbox to start checked"
        assert behavior_cb.is_checked(), "Expected Behavior checkbox to start checked"
        assert engineering_cb.is_checked(), "Expected Engineering checkbox to start checked"

    @pytest.mark.parametrize(
        "benchmark_to_exclude, expected_ranks, expected_models, expected_scores",
        [
            (
                "neural_vision_v0",
                [2, 2, 13, 1, 2],
                [
                    "convnext_xlarge:fb_in22k_ft_in1k",
                    "vit_large_patch14_clip_224:laion2b_ft_in1k",
                    "resnext101_32x48d_wsl",
                    "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
                    "vit_base_patch16_clip_224:openai_ft_in12k_in1k"
                ],
                ["0.56", "0.56", "0.56", "0.55", "0.55"]
            ),
            (
                "behavior_vision_v0",
                [13, 144, 150, 5, 1],
                [
                    "convnext_tiny_imagenet_full_seed-0",
                    "alexnet_training_seed_01",
                    "alexnet_training_seed_10",
                    "vit_relpos_base_patch16_clsgap_224:sw_in1k",
                    "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384"
                ],
                ["0.39", "0.39", "0.39", "0.38", "0.38"]
            ),
              (
                "engineering_vision_v0",
                [1, 2, 2, 2, 5],
                [
                    "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
                    "convnext_xlarge:fb_in22k_ft_in1k",
                    "vit_base_patch16_clip_224:openai_ft_in12k_in1k",
                    "vit_large_patch14_clip_224:laion2b_ft_in1k",
                    "vit_base_patch16_clip_224:openai_ft_in1k"
                ],
                ["0.47", "0.45", "0.45", "0.45", "0.44"]
            ),
              (
                "V1_v0",
                [1, 2, 2, 2, 5],
                [
                    "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
                    "convnext_xlarge:fb_in22k_ft_in1k",
                    "vit_large_patch14_clip_224:laion2b_ft_in1k",
                    "vit_base_patch16_clip_224:openai_ft_in12k_in1k",
                    "vit_large_patch14_clip_224:openai_ft_in1k"
                ],
                ["0.47", "0.45", "0.45", "0.44", "0.44"]
            ),
            (
                "Ferguson2024_v0",
                [1, 2, 2, 5, 2],
                [
                    "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
                    "convnext_xlarge:fb_in22k_ft_in1k",
                    "vit_large_patch14_clip_224:laion2b_ft_in1k",
                    "vit_large_patch14_clip_224:openai_ft_in1k",
                    "vit_base_patch16_clip_224:openai_ft_in12k_in1k"
                ],
                ["0.47", "0.44", "0.44", "0.44", "0.44"]
            ),
              (
                "Hermann2020_v0",
                [1, 2, 2, 2, 5],
                [
                    "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
                    "convnext_xlarge:fb_in22k_ft_in1k",
                    "vit_base_patch16_clip_224:openai_ft_in12k_in1k",
                    "vit_large_patch14_clip_224:laion2b_ft_in1k",
                    "vit_base_patch16_clip_224:openai_ft_in1k"
                ],
                ["0.47", "0.45", "0.45", "0.45", "0.44"]
            ),
        ]
    )
    def test_single_filter_out_and_verify_top(self, page, benchmark_to_exclude, expected_ranks, expected_models, expected_scores):
        """
        Verifies that toggling a benchmark filter:

        1) Opens the advanced filter panel and unchecks the specified benchmark.
        2) Confirms the corresponding column header is removed.
        3) Scrolls to the top of the grid and checks that the "Filtered Score" column appears (for non-engineering)
        4) Extracts and asserts the top-5 row values for:
           a) Global ranks (static rank column),
           b) Model names,
           c) Filtered scores,
        against the expected lists provided via parametrization.
        5) Ensures that deselecting the engineering benchmark does not result in "Filtered Score appearing nor does the
           score change.
        """
        # open advanced filters tab
        page.click('#advancedFilterBtn')

        # expand benchmarks to click for subroots as needed
        if benchmark_to_exclude == "V1_v0":
            # expand Neural first
            page.click(
                '#benchmarkFilterPanel .tree-node-header:has-text(" neural_vision") .tree-toggle'  # note the space
            )
        elif benchmark_to_exclude == "Ferguson2024_v0":
            page.click(
                '#benchmarkFilterPanel .tree-node-header:has-text(" behavior_vision") .tree-toggle' # note the space
            )
        elif benchmark_to_exclude == "Hermann2020_v0":
            page.click(
                '#benchmarkFilterPanel .tree-node-header:has-text(" engineering_vision") .tree-toggle'  # note the space
            )

        # uncheck benchmark and wait for its header to detach
        cb = page.wait_for_selector(
            f'#benchmarkFilterPanel input[type="checkbox"][value="{benchmark_to_exclude}"]',
            state='visible',
            timeout=60000)
        assert cb.is_checked(), f"Expected {benchmark_to_exclude} to be checked initially"
        cb.uncheck()
        page.wait_for_selector(
            f'.expandable-header-label:has-text("{benchmark_to_exclude.split("_")[0].capitalize()}")',
            state='detached',
            timeout=60000)

        # ensure none of those labels remain in the headers
        all_headers = page.locator('.ag-header-cell').all_text_contents()
        assert not any(benchmark_to_exclude.split("_")[0].capitalize() in h for h in all_headers), \
            f"Still saw {benchmark_to_exclude} in {all_headers}"

        # scroll to top and let AG Grid repaint
        page.evaluate('window.globalGridApi.ensureIndexVisible(0)')
        page.wait_for_timeout(1000)

        # test engineering exclusion in score logic
        if benchmark_to_exclude == "engineering_vision_v0" or benchmark_to_exclude == "Hermann2020_v0":
            filtered = page.locator('.expandable-header-label:has-text("Global Score")')
            assert filtered.count() == 1, f"'Global Score' header not found, headers are {all_headers}"
        else:
            filtered = page.locator('.ag-header-cell-text:has-text("Filtered Score")')
            assert filtered.count() == 1, f"'Filtered Score' header not found, headers are {all_headers}"

        # grab actual top-5 values
        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]\

        # make sure engineering is still using Global Score
        if benchmark_to_exclude == "engineering_vision_v0" or benchmark_to_exclude == "Hermann2020_v0":
            actual_scores = page.locator('.ag-cell[col-id="average_vision_v0"]').all_text_contents()[:5]
        else:
            actual_scores = page.locator('.ag-cell[col-id="filtered_score"]').all_text_contents()[:5]

        assert actual_ranks == [str(r) for r in expected_ranks], \
            f"Expected top ranks {expected_ranks}, got {actual_ranks}"
        assert actual_models == expected_models, \
            f"Expected top models {expected_models}, got {actual_models}"
        assert actual_scores == expected_scores, \
            f"Expected top scores {expected_scores}, got {actual_scores}"


    @pytest.mark.parametrize(
        "benchmarks_to_exclude, expected_ranks, expected_models, expected_scores",
        [
            (
                    ["neural_vision_v0", "Baker2022_v0"],
                    [2, 2, 13, 1, 5],
                    [
                        "vit_large_patch14_clip_224:laion2b_ft_in1k",
                        "convnext_xlarge:fb_in22k_ft_in1k",
                        "convnext_xxlarge:clip_laion2b_soup_ft_in1k",
                        "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
                        "vit_large_patch14_clip_224:openai_ft_in1k"
                    ],
                    ["0.58", "0.55", "0.55", "0.55", "0.53"]
            ),
            (
                    ["V1_v0", "V2_v0", "IT_v0"],
                    [2, 2, 5, 13, 5],
                    [
                        "convnext_xlarge:fb_in22k_ft_in1k",
                        "vit_large_patch14_clip_224:laion2b_ft_in1k",
                        "vit_large_patch14_clip_224:openai_ft_in1k",
                        "resnext101_32x48d_wsl",
                        "vit_base_patch16_clip_224:openai_ft_in1k"
                    ],
                    ["0.50", "0.48", "0.48", "0.48", "0.47"]
            ),
            (
                    ["neural_vision_v0", "behavior_vision_v0"],
                    [1, 2, 2, 2, 5],
                    [
                        "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
                        "convnext_xlarge:fb_in22k_ft_in1k",
                        "vit_base_patch16_clip_224:openai_ft_in12k_in1k",
                        "vit_large_patch14_clip_224:laion2b_ft_in1k",
                        "vit_base_patch16_clip_224:openai_ft_in1k"
                    ],
                    ["X", "X", "X", "X", "X"]
            ),
        ]
    )
    def test_multiple_benchmark_exclusion(self, page, benchmarks_to_exclude, expected_ranks, expected_models, expected_scores):
        """
        Verifies that toggling MULTIPLE benchmark filters (no tags):

        1) Opens the advanced filter panel.
        2) Unchecks each specified benchmark in turn.
        3) Confirms each corresponding column header is removed.
        4) Scrolls to the top of the grid and checks that the "Filtered Score" column appears.
        5) Extracts and asserts the top-5 row values for:
           a) Global ranks (static rank column),
           b) Model names,
           c) Filtered scores,
        against the expected lists provided via parametrization.
        """
        # open advanced filters tab
        page.click('#advancedFilterBtn')

        # expand benchmarks to click for subroots as needed
        if "IT_v0" in benchmarks_to_exclude:
            # expand Neural first
            page.click(
                '#benchmarkFilterPanel .tree-node-header:has-text(" neural_vision") .tree-toggle'  # note the space
            )
            page.click(
                '#benchmarkFilterPanel .tree-node-header:has-text(" V1") .tree-toggle'  # note the space
            )
            page.click(
                '#benchmarkFilterPanel .tree-node-header:has-text(" V4") .tree-toggle'  # note the space
            )
        elif "Baker2022_v0" in benchmarks_to_exclude:
            page.click(
                '#benchmarkFilterPanel .tree-node-header:has-text(" behavior_vision") .tree-toggle'  # note the space
            )
        elif "Geirhos2021-top1" in benchmarks_to_exclude:
            page.click(
                '#benchmarkFilterPanel .tree-node-header:has-text(" engineering_vision") .tree-toggle'  # note the space
            )

        # uncheck each filter and wait for its header to detach
        human_labels = []
        for bench in benchmarks_to_exclude:
            human_label = bench.split('_')[0].capitalize()
            human_labels.append(human_label)

            cb = page.wait_for_selector(
                f'#benchmarkFilterPanel input[type="checkbox"][value="{bench}"]',
                state='visible',
                timeout=30000
            )
            assert cb.is_checked(), f"Expected {bench} to start checked"
            cb.uncheck()

            page.wait_for_selector(
                f'.expandable-header-label:has-text("{human_label}")',
                state='detached',
                timeout=30000
            )

        # ensure none of those labels remain in the headers
        all_headers = page.locator('.ag-header-cell').all_text_contents()
        for label in human_labels:
            assert not any(label in h for h in all_headers), f"Still saw {label} in {all_headers}"

        # scroll to top and let AG Grid repaint
        page.evaluate('window.globalGridApi.ensureIndexVisible(0)')
        page.wait_for_timeout(500)


        # test engineering exclusion in score logic
        if "engineering_vision_v0" in benchmarks_to_exclude or "Geirhos2021-top1" in benchmarks_to_exclude:
            filtered = page.locator('.expandable-header-label:has-text("Global Score")')
            assert filtered.count() == 1, f"'Global Score' header not found, headers are {all_headers}"
        else:
            filtered = page.locator('.ag-header-cell-text:has-text("Filtered Score")')
            assert filtered.count() == 1, f"'Filtered Score' header not found, headers are {all_headers}"

        # grab actual top-5 values
        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        actual_scores = page.locator('.ag-cell[col-id="filtered_score"]').all_text_contents()[:5]

        # compare against the parameters
        assert actual_ranks == [str(r) for r in expected_ranks], \
            f"Expected top ranks {expected_ranks}, got {actual_ranks}"
        assert actual_models == expected_models, \
            f"Expected top models {expected_models}, got {actual_models}"
        assert actual_scores == expected_scores, \
            f"Expected top scores {expected_scores}, got {actual_scores}"




