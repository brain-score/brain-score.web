import pytest
from playwright.sync_api import sync_playwright
import zipfile

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture(scope="function")
def page(browser):
    context = browser.new_context(ignore_https_errors=True, permissions=["clipboard-read"])
    page = context.new_page()
    page.set_default_navigation_timeout(60000)
    page.goto("http://127.0.0.1:8000/vision/leaderboard")
    page.wait_for_selector('.ag-root', timeout=60000)
    yield page
    context.close()


# ----------------- SORTING -----------------

class TestSort:
    def test_sort_rank_descending(self, page):
        """
        Verify that the rank column is sorted in descending order by default.
        """
        scores_actual = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[0:5]
        scores_expected = [str(x) for x in [1, 2, 2, 2, 5]]
        assert scores_actual == scores_expected

    def test_model_descending(self, page):
        """
        Verify that the model column is sorted in descending order after clicking the header.
        """
        header = page.locator('.ag-header-cell[col-id="model"]')
        header.click()
        page.wait_for_timeout(5000)

        scores_actual = page.locator('.ag-cell[col-id="model"]').all_text_contents()[0:2]
        scores_actual = [i[:-8] for i in scores_actual]  # Strip suffix (e.g., timestamp) from model names

        scores_expected = [
            "yudixie_resnet50_translation_rotation_0_240908",
            "yudixie_resnet50_translation_reg_0_240908"
        ]
        assert scores_actual == scores_expected

    def test_sort_average_descending(self, page):
        """
        Verify that the average_vision_v0 column is sorted in descending order by default.
        """
        scores_actual = page.locator('.ag-cell[col-id="average_vision_v0"]').all_text_contents()[0:5]
        scores_expected = [str(x) for x in [0.47, 0.45, 0.45, 0.45, 0.44]]
        assert scores_actual == scores_expected

    @pytest.mark.skip(reason="Sorting tests are flaky on EC2; revisit later")
    def test_sort_neural_descending(self, page):
        """
        Verify that the neural_vision_v0 column is sorted in descending order after clicking the header.
        """
        header = page.locator('.ag-header-cell[col-id="neural_vision_v0"]')
        header.click()
        page.wait_for_timeout(5000)

        scores_actual = page.locator('.ag-cell[col-id="neural_vision_v0"]').all_text_contents()[0:5]
        scores_expected = [str(x) for x in [0.39, 0.39, 0.39, 0.38, 0.38]]
        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        assert actual_ranks == ["13", "144", "150", "5", "1"]
        assert scores_actual == scores_expected

    @pytest.mark.skip(reason="Sorting tests are flaky on CI; revisit later")
    def test_sort_behavioral_descending(self, page):
        """
        Verify that the behavior_vision_v0 column is sorted in descending order after clicking the header.
        """
        header = page.locator('.ag-header-cell[col-id="behavior_vision_v0"]')
        header.click()
        page.wait_for_timeout(5000)

        scores_actual = page.locator('.ag-cell[col-id="behavior_vision_v0"]').all_text_contents()[0:5]
        scores_expected = [str(x) for x in [0.56, 0.56, 0.56, 0.55, 0.55]]
        assert scores_actual == scores_expected

    @pytest.mark.skip(reason="Sorting tests are flaky on CI; revisit later")
    def test_sort_engineering_descending(self, page):
        """
        Verify that the engineering_vision_v0 column is sorted in descending order after clicking the header.
        """
        header = page.locator('.ag-header-cell[col-id="engineering_vision_v0"]')
        header.click()
        page.wait_for_timeout(5000)

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
            # (
            #     "behavior_vision_v0",
            #     [13, 144, 150, 5, 1],
            #     [
            #         "convnext_tiny_imagenet_full_seed-0",
            #         "alexnet_training_seed_01",
            #         "alexnet_training_seed_10",
            #         "vit_relpos_base_patch16_clsgap_224:sw_in1k",
            #         "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384"
            #     ],
            #     ["0.39", "0.39", "0.39", "0.38", "0.38"]
            # ),
            #   (
            #     "engineering_vision_v0",
            #     [1, 2, 2, 2, 5],
            #     [
            #         "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
            #         "convnext_xlarge:fb_in22k_ft_in1k",
            #         "vit_base_patch16_clip_224:openai_ft_in12k_in1k",
            #         "vit_large_patch14_clip_224:laion2b_ft_in1k",
            #         "vit_base_patch16_clip_224:openai_ft_in1k"
            #     ],
            #     ["0.47", "0.45", "0.45", "0.45", "0.44"]
            # ),
            # (
            #     "V1_v0",
            #     [1, 2, 2, 2, 5],
            #     [
            #         "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
            #         "convnext_xlarge:fb_in22k_ft_in1k",
            #         "vit_large_patch14_clip_224:laion2b_ft_in1k",
            #         "vit_base_patch16_clip_224:openai_ft_in12k_in1k",
            #         "vit_large_patch14_clip_224:openai_ft_in1k"
            #     ],
            #     ["0.47", "0.45", "0.45", "0.44", "0.44"]
            # ),
            # (
            #     "Ferguson2024_v0",
            #     [1, 2, 2, 5, 2],
            #     [
            #         "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
            #         "convnext_xlarge:fb_in22k_ft_in1k",
            #         "vit_large_patch14_clip_224:laion2b_ft_in1k",
            #         "vit_large_patch14_clip_224:openai_ft_in1k",
            #         "vit_base_patch16_clip_224:openai_ft_in12k_in1k"
            #     ],
            #     ["0.47", "0.44", "0.44", "0.44", "0.44"]
            # ),
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
    @pytest.mark.skip(reason="Test is flaky on CI; revisit later")
    def test_single_filter_out_and_verify_top(self, page, benchmark_to_exclude, expected_ranks, expected_models,
                                              expected_scores):
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
                '#benchmarkFilterPanel .tree-node-header:has-text(" behavior_vision") .tree-toggle'  # note the space
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
        page.wait_for_timeout(5000)

        # test engineering exclusion in score logic
        if benchmark_to_exclude == "engineering_vision_v0" or benchmark_to_exclude == "Hermann2020_v0":
            filtered = page.locator('.expandable-header-label:has-text("Global Score")')
            assert filtered.count() == 1, f"'Global Score' header not found, headers are {all_headers}"
        else:
            filtered = page.locator('.ag-header-cell-text:has-text("Filtered Score")')
            assert filtered.count() == 1, f"'Filtered Score' header not found, headers are {all_headers}"

        # grab actual top-5 values
        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]

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

    def test_architecture_filter(self, page):
        """
        Verifies that filtering by a single model architecture:

        1) Opens the Architecture dropdown.
        2) Selects SKIP_CONNECTIONS
        3) Closes the dropdown.
        4) Waits for the leaderboard to update.
        5) Asserts that the top-5 model names all contain the selected architecture substring.
        """
        # 1) Open the Architecture dropdown
        page.click('#advancedFilterBtn')
        page.click('#architectureFilter .filter-input')
        page.wait_for_selector('#architectureFilter .dropdown-option', timeout=5000)

        # 2) Click the "Transformer" option
        skip_con_opt = page.locator(
            '#architectureFilter .dropdown-option:has-text("SKIP_CONNECTIONS")'
        )
        assert skip_con_opt.count() > 0, "Skip Connections option not found in architecture dropdown"
        skip_con_opt.click()

        # 3) Close the dropdown by clicking outside
        page.click('body')

        # 4) Wait for the grid to re-render (you might wait for at least one model cell to refresh)
        page.wait_for_timeout(500)

        expected_ranks = [103, 120, 120, 120, 120]
        expected_models = [
            "ReAlnet10_cornet",
            "ReAlnet01_cornet",
            "ReAlnet02_cornet",
            "ReAlnet03_cornet",
            "ReAlnet04_cornet"
        ]
        expected_scores = ["0.31", "0.30", "0.30", "0.30", "0.30"]

        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        actual_scores = page.locator('.ag-cell[col-id="average_vision_v0"]').all_text_contents()[:5]

        # compare against the parameters
        assert actual_ranks == [str(r) for r in expected_ranks], \
            f"Expected top ranks {expected_ranks}, got {actual_ranks}"
        assert actual_models == expected_models, \
            f"Expected top models {expected_models}, got {actual_models}"
        assert actual_scores == expected_scores, \
            f"Expected top scores {expected_scores}, got {actual_scores}"

    def test_model_family_filter(self, page):
        """
        Verifies that filtering by a single model architecture:

        1) Opens the Model Family dropdown.
        2) Selects resnet family option
        3) Closes the dropdown.
        4) Waits for the leaderboard to update.
        5) Asserts that the top-5 model names all contain the selected architecture substring.
        """
        # 1) Open the Architecture dropdown
        page.click('#advancedFilterBtn')
        page.click('#modelFamilyFilter .filter-input')
        page.wait_for_selector('#modelFamilyFilter .dropdown-option', timeout=5000)

        # 2) Click the "Transformer" option
        resnet_opt = page.locator(
            '#modelFamilyFilter .dropdown-option:has-text("resnet")'
        )
        assert resnet_opt.count() > 0, "resnet option not found in Model Family dropdown"
        resnet_opt.click()

        # 3) Close the dropdown by clicking outside
        page.click('body')

        # 4) Wait for the grid to re-render (you might wait for at least one model cell to refresh)
        page.wait_for_timeout(500)

        expected_ranks = [20, 25, 36, 39, 39]
        expected_models = [
            "resnet50-VITO-8deg-cc",
            "resnet152_imagenet_full",
            "resnet50_robust_l2_eps1",
            "resnet50_tutorial",
            "resnet_50_v2"
        ]
        expected_scores = ['0.40', '0.39', '0.38', '0.37', '0.37']

        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        actual_scores = page.locator('.ag-cell[col-id="average_vision_v0"]').all_text_contents()[:5]

        # compare against the parameters
        assert actual_ranks == [str(r) for r in expected_ranks], \
            f"Expected top ranks {expected_ranks}, got {actual_ranks}"
        assert actual_models == expected_models, \
            f"Expected top models {expected_models}, got {actual_models}"
        assert actual_scores == expected_scores, \
            f"Expected top scores {expected_scores}, got {actual_scores}"

    def test_parameter_count_filter(self, page):
        """
        Verifies parameter‐count filtering by directly driving the filter logic:

        1) Opens the Advanced Filtering panel.
        2) Sets the minimum parameter count to 25 and maximum to 50 by updating the inputs in JS.
        3) Calls applyCombinedFilters() to re‐apply the filter pipeline.
        4) Waits for the grid to repaint.
        5) Asserts that:
           a) the slider inputs read "25" and "50",
           b) window.activeFilters.min_param_count == 25 and
              window.activeFilters.max_param_count == 50.
        6) Extracts and verifies the top-5 rows (ranks, model names, scores) match expectations.
        """
        page.click('#advancedFilterBtn')
        page.wait_for_selector('#paramCountMin', state='visible')
        page.wait_for_selector('#paramCountMax', state='visible')

        # 1) Set both inputs, then rerun the filter pipeline
        page.evaluate("""
        () => {
          const minInput = document.getElementById('paramCountMin');
          const maxInput = document.getElementById('paramCountMax');
          minInput.value = 25;
          maxInput.value = 50;
          applyCombinedFilters();
        }
        """)

        # 2) wait for the grid to repaint
        page.wait_for_timeout(500)

        # 3) assert both the UI and the JS state
        assert page.locator('#paramCountMin').input_value() == "25"
        assert page.locator('#paramCountMax').input_value() == "50"
        assert page.evaluate('() => window.activeFilters.min_param_count') == 25
        assert page.evaluate('() => window.activeFilters.max_param_count') == 50

        expected_ranks = [8, 13, 20, 25, 36]
        expected_models = [
            "swin_small_patch4_window7_224:ms_in22k_ft_in1k",
            "convnext_tiny_imagenet_full_seed-0",
            "resnet50-VITO-8deg-cc",
            "convnext_tiny:in12k_ft_in1k",
            "resnet50_robust_l2_eps1"
        ]
        expected_scores = ['0.43', '0.41', '0.40', '0.39', '0.38']

        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        actual_scores = page.locator('.ag-cell[col-id="average_vision_v0"]').all_text_contents()[:5]

        # compare against the parameters
        assert actual_ranks == [str(r) for r in expected_ranks], \
            f"Expected top ranks {expected_ranks}, got {actual_ranks}"
        assert actual_models == expected_models, \
            f"Expected top models {expected_models}, got {actual_models}"
        assert actual_scores == expected_scores, \
            f"Expected top scores {expected_scores}, got {actual_scores}"

    def test_model_size_filter(self, page):
        """
        Verifies model size filtering by directly driving the filter logic:

        1) Opens the Advanced Filtering panel.
        2) Sets the minimum model size to 100MB and maximum to 1000MB by updating the inputs in JS.
        3) Calls applyCombinedFilters() to re‐apply the filter pipeline.
        4) Waits for the grid to repaint.
        5) Asserts that:
           a) the slider inputs read "100" and "1000",
           b) window.activeFilters.min_param_count == 100 and
              window.activeFilters.max_param_count == 1000.
        6) Extracts and verifies the top-5 rows (ranks, model names, scores) match expectations.
        """
        page.click('#advancedFilterBtn')
        page.wait_for_selector('#modelSizeMin', state='visible')
        page.wait_for_selector('#modelSizeMax', state='visible')

        # 1) Set both inputs, then rerun the filter pipeline
        page.evaluate("""
        () => {
          const minInput = document.getElementById('modelSizeMin');
          const maxInput = document.getElementById('modelSizeMax');
          minInput.value = 100;
          maxInput.value = 1000;
          applyCombinedFilters();
        }
        """)

        # 2) wait for the grid to repaint
        page.wait_for_timeout(500)

        # 3) assert both the UI and the JS state
        assert page.locator('#modelSizeMin').input_value() == "100"
        assert page.locator('#modelSizeMax').input_value() == "1000"
        assert page.evaluate('() => window.activeFilters.min_model_size') == 100
        assert page.evaluate('() => window.activeFilters.max_model_size') == 1000

        expected_ranks = [1, 2, 5, 5, 8]
        expected_models = [
            "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
            "vit_base_patch16_clip_224:openai_ft_in12k_in1k",
            "vit_base_patch16_clip_224:openai_ft_in1k",
            "vit_relpos_base_patch16_clsgap_224:sw_in1k",
            "convnext_large:fb_in22k_ft_in1k"
        ]
        expected_scores = ['0.47', '0.45', '0.44', '0.44', '0.43']

        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        actual_scores = page.locator('.ag-cell[col-id="average_vision_v0"]').all_text_contents()[:5]

        # compare against the parameters
        assert actual_ranks == [str(r) for r in expected_ranks], \
            f"Expected top ranks {expected_ranks}, got {actual_ranks}"
        assert actual_models == expected_models, \
            f"Expected top models {expected_models}, got {actual_models}"
        assert actual_scores == expected_scores, \
            f"Expected top scores {expected_scores}, got {actual_scores}"

    # @pytest.mark.skip(reason="Sorting tests are flaky on CI; revisit later")
    def test_public_data_filter(self, page):
        """
        Verifies that filtering to only publicly available benchmarks:

        1) Opens the Advanced Filtering panel.
        2) Waits for the “Public Data Only” checkbox to appear.
        3) Checks that checkbox.
        4) Scrolls back to the top of the grid.
        5) Waits for the grid to repaint.
        6) Extracts the top-5 rows and asserts on:
           a) Global ranks,
           b) Model names,
           c) (Optional) Scores or other columns as desired.
        """
        # 1) Open the filter panel
        page.click('#advancedFilterBtn')

        # 2) Wait for the Public Data Only checkbox
        public_cb = page.wait_for_selector(
            '#publicDataFilter',
            state='visible',
            timeout=5000
        )
        # 3) Enable it
        if not public_cb.is_checked():
            public_cb.check()

        # 4) Scroll grid to top
        page.evaluate('window.globalGridApi.ensureIndexVisible(0)')
        page.wait_for_timeout(500)

        # 5) (Optional) Verify “Filtered Score” appears if applicable
        filtered = page.locator('.ag-header-cell-text:has-text("Filtered Score")')
        assert filtered.count() == 1, "Filtered Score not visible after Public Data filter"

        # 6) Grab the top-5 rows
        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        actual_scores = page.locator('.ag-cell[col-id="filtered_score"]').all_text_contents()[:5]

        # Replace these with the expected values for your public-data-only run:
        expected_ranks = [1, 5, 2, 5, 2]
        expected_models = [
            "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
            "vit_relpos_base_patch16_clsgap_224:sw_in1k",
            "convnext_xlarge:fb_in22k_ft_in1k",
            "vit_base_patch16_clip_224:openai_ft_in1k",
            "vit_base_patch16_clip_224:openai_ft_in12k_in1k"
        ]
        expected_scores = ["0.46", "0.43", "0.43", "0.43", "0.43"]

        assert actual_ranks == [str(r) for r in expected_ranks], \
            f"Expected public-only ranks {expected_ranks}, got {actual_ranks}"
        assert actual_models == expected_models, \
            f"Expected public-only models {expected_models}, got {actual_models}"
        assert actual_scores == expected_scores, \
            f"Expected public-only scores {expected_scores}, got {actual_scores}"

    @pytest.mark.parametrize(
        "selected_regions, absent_regions, expected_ranks, expected_models, expected_scores",
        [
            (
                ["V1"], ["V2", "V4", "IT"],
                [144, 150, 150, 162, 162],
                [
                    "alexnet_training_seed_01",
                    "alexnet_training_seed_07",
                    "alexnet_training_seed_10",
                    "alexnet_training_seed_09",
                    "alexnet_training_seed_02"
                ],
                ["0.08", "0.07", "0.07", "0.07", "0.07"]
            ),
            (
                ["IT"], ["V1", "V2", "V4"],
                [13, 1, 5, 8, 58],
                [
                    "convnext_tiny_imagenet_full_seed-0",
                    "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
                    "vit_relpos_base_patch16_clsgap_224:sw_in1k",
                    "swin_small_patch4_window7_224:ms_in22k_ft_in1k",
                    "resnet50-SIN"
                ],
                ["0.07", "0.07", "0.07", "0.07", "0.07"]
            ),
        ]
    )
    @pytest.mark.skip(reason="Sorting tests are flaky on CI; revisit later")
    def test_region_filtering(self, page, selected_regions, absent_regions, expected_ranks,
                                                          expected_models, expected_scores):
        """
        Verifies that when filtering by brain-region checkboxes:

        1) Opens the Advanced Filtering panel.
        2) Unchecks all regions, then checks only `selected_regions`.
        3) Scrolls back to the top of the grid.
        4) Asserts that the “Filtered Score” column appears.
        5) Extracts the top-5 rows for rank, model, and score, and
           compares them to the expected lists.
        """
        # 1) open the filter panel
        page.click('#advancedFilterBtn')

        # 2) uncheck all then check only our selections
        for cb in page.locator('.region-checkbox').all():
            if cb.is_checked():
                cb.uncheck()
        for region in selected_regions:
            cb = page.wait_for_selector(
                f'.region-checkbox[value="{region}_v0"], .region-checkbox[value="{region}"]',
                state='visible',
                timeout=30000)
            if not cb.is_checked():
                cb.check()

        # 3) scroll grid to top
        page.evaluate('window.globalGridApi.ensureIndexVisible(0)')
        page.wait_for_timeout(5000)

        # 4) verify “Filtered Score” appears
        assert page.locator('.ag-header-cell-text:has-text("Filtered Score")').count() == 1

        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        print(actual_ranks)
        print(expected_ranks)
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        actual_scores = page.locator('.ag-cell[col-id="filtered_score"]').all_text_contents()[:5]

        assert actual_ranks == [str(r) for r in expected_ranks], f"Ranks: {actual_ranks}"
        assert actual_models == expected_models, f"Models: {actual_models}"
        assert actual_scores == expected_scores, f"Scores: {actual_scores}"

    @pytest.mark.parametrize(
        "selected_species, absent_species, expected_ranks, expected_models, expected_scores",
        [
            (
                    ["human"], ["primate"],
                    [13, 1, 5, 8, 5],
                    [
                        "convnext_xxlarge:clip_laion2b_soup_ft_in1k",
                        "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
                        "vit_large_patch14_clip_224:openai_ft_in1k",
                        "swin_small_patch4_window7_224:ms_in22k_ft_in1k",
                        "vit_relpos_base_patch16_clsgap_224:sw_in1k"
                    ],
                    ["0.35", "0.34", "0.32", "0.32", "0.30"]
            ),
            (
                    ["primate"], ["human"],
                    [1, 2, 2, 2, 5],
                    [
                        "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
                        "convnext_xlarge:fb_in22k_ft_in1k",
                        "vit_base_patch16_clip_224:openai_ft_in12k_in1k",
                        "vit_large_patch14_clip_224:laion2b_ft_in1k",
                        "vit_base_patch16_clip_224:openai_ft_in1k"
                    ],
                    ["0.00", "0.00", "0.00", "0.00", "0.00"]
            ),
        ]
    )
    @pytest.mark.skip(reason="Sorting tests are flaky on CI; revisit later")
    def test_species_filtering(self, page, selected_species, absent_species, expected_ranks,
                            expected_models, expected_scores):
        """
        Verifies that when filtering by task checkboxes:

        1) Opens the Advanced Filtering panel.
        2) Unchecks all species, then checks only `selected_species`.
        3) Scrolls back to the top of the grid.
        4) Asserts that the “Filtered Score” column appears.
        5) Extracts the top-5 rows for rank, model, and score, and
           compares them to the expected lists.
        """
        # 1) open the filter panel
        page.click('#advancedFilterBtn')

        # 2) uncheck all then check only our selections
        for cb in page.locator('.species-checkbox').all():
            if cb.is_checked():
                cb.uncheck()
        for species in selected_species:
            cb = page.wait_for_selector(
                f'.species-checkbox[value="{species}"], .species-checkbox[value="{species}"]',
                state='visible',
                timeout=30000)
            if not cb.is_checked():
                cb.check()

        # 3) scroll grid to top
        page.evaluate('window.globalGridApi.ensureIndexVisible(0)')
        page.wait_for_timeout(5000)

        # 4) verify “Filtered Score” appears
        assert page.locator('.ag-header-cell-text:has-text("Filtered Score")').count() == 1

        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        print(actual_ranks)
        print(expected_ranks)
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        actual_scores = page.locator('.ag-cell[col-id="filtered_score"]').all_text_contents()[:5]

        assert actual_ranks == [str(r) for r in expected_ranks], f"Ranks: {actual_ranks}"
        assert actual_models == expected_models, f"Models: {actual_models}"
        assert actual_scores == expected_scores, f"Scores: {actual_scores}"

    @pytest.mark.parametrize(
        "selected_tasks, absent_tasks, expected_ranks, expected_models, expected_scores",
        [
            (
                    ["2_way_afc"], [],
                    [8, 25, 2, 2, 5],
                    [
                        "cvt_cvt-w24-384-in22k_finetuned-in1k_4",
                        "resnext101_32x32d_wsl",
                        "convnext_xlarge:fb_in22k_ft_in1k",
                        "vit_base_patch16_clip_224:openai_ft_in12k_in1k",
                        "vit_base_patch16_clip_224:openai_ft_in1k"
                    ],
                    ["0.07", "0.07", "0.07", "0.07", "0.07"]
            )
        ]
    )
    @pytest.mark.skip(reason="Sorting tests are flaky on CI; revisit later")
    def test_task_filtering(self, page, selected_tasks, absent_tasks, expected_ranks,
                                                          expected_models, expected_scores):
        """
        Verifies that when filtering by task checkboxes:

        1) Opens the Advanced Filtering panel.
        2) Unchecks all tasks, then checks only `selected_tasks`.
        3) Scrolls back to the top of the grid.
        4) Asserts that the “Filtered Score” column appears.
        5) Extracts the top-5 rows for rank, model, and score, and
           compares them to the expected lists.
        """
        # 1) open the filter panel
        page.click('#advancedFilterBtn')

        # 2) uncheck all then check only our selections
        for cb in page.locator('.task-checkbox').all():
            if cb.is_checked():
                cb.uncheck()
        for task in selected_tasks:
            cb = page.wait_for_selector(
                f'.task-checkbox[value="{task}"], .task-checkbox[value="{task}"]',
                state='visible',
                timeout=30000)
            if not cb.is_checked():
                cb.check()

        # 3) scroll grid to top
        page.evaluate('window.globalGridApi.ensureIndexVisible(0)')
        page.wait_for_timeout(5000)

        # 4) verify “Filtered Score” appears
        assert page.locator('.ag-header-cell-text:has-text("Filtered Score")').count() == 1

        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        print(actual_ranks)
        print(expected_ranks)
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        actual_scores = page.locator('.ag-cell[col-id="filtered_score"]').all_text_contents()[:5]

        assert actual_ranks == [str(r) for r in expected_ranks], f"Ranks: {actual_ranks}"
        assert actual_models == expected_models, f"Models: {actual_models}"
        assert actual_scores == expected_scores, f"Scores: {actual_scores}"

    @pytest.mark.skip(reason="Sorting tests are flaky on CI; revisit later")
    def test_stimuli_count_filter(self, page):
        """
        Verifies stimuli‐count filtering by directly driving the filter logic:

        1) Opens the Advanced Filtering panel.
        2) Sets the minimum stimuli count to 100 and maximum to 5000 by updating the inputs in JS.
        3) Calls applyCombinedFilters() to re‐apply the filter pipeline.
        4) Waits for the grid to repaint.
        5) Asserts that:
           a) the slider inputs read "100" and "5000",
           b) window.activeFilters.min_stimuli_count == 100 and
              window.activeFilters.max_stimuli_count == 5000.
        6) Extracts and verifies the top-5 rows (ranks, model names, global scores) match expectations.
        """
        # 1) open the panel
        page.click('#advancedFilterBtn')
        page.wait_for_selector('#stimuliCountMin', state='visible')
        page.wait_for_selector('#stimuliCountMax', state='visible')

        # 2) set both inputs, then rerun the filter pipeline in JS
        page.evaluate("""
        () => {
          const minInput = document.getElementById('stimuliCountMin');
          const maxInput = document.getElementById('stimuliCountMax');
          minInput.value = 100;
          maxInput.value = 5000;
          applyCombinedFilters();
        }
        """)

        # 3) give the grid a moment to re-filter
        page.wait_for_timeout(500)

        # 4) assert both the UI and the JS state
        assert page.locator('#stimuliCountMin').input_value() == "100"
        assert page.locator('#stimuliCountMax').input_value() == "5000"
        assert page.evaluate('() => window.activeFilters.min_stimuli_count') == 100
        assert page.evaluate('() => window.activeFilters.max_stimuli_count') == 5000

        # 5) now verify top‐5 rows
        expected_ranks = [1, 8, 5, 25, 2]
        expected_models = [
            "convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384",
            "vit_large_patch14_clip_224:laion2b_ft_in12k_in1k",
            "vit_large_patch14_clip_224:openai_ft_in1k",
            "vit_large_patch14_clip_336:openai_ft_in12k_in1k",
            "vit_large_patch14_clip_224:laion2b_ft_in1k"
        ]
        expected_scores = ["0.39", "0.39", "0.39", "0.39", "0.39"]

        actual_ranks  = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        actual_scores = page.locator('.ag-cell[col-id="filtered_score"]').all_text_contents()[:5]

        assert actual_ranks  == [str(r) for r in expected_ranks], f"Expected ranks {expected_ranks}, got {actual_ranks}"
        assert actual_models == expected_models, f"Expected models {expected_models}, got {actual_models}"
        assert actual_scores == expected_scores, f"Expected scores {expected_scores}, got {actual_scores}"


    def test_copy_bibtex_button_all(self, page):
        """
        Validates the BibTeX copy functionality.

        Steps:
        1) Opens the Advanced Filter panel and resets all filters to ensure default benchmark visibility.
        2) Clicks the "Copy BibTeX" button.
        3) Retrieves BibTeX entries directly via the browser's collectBenchmarkBibtex() function.
        4) Asserts that exactly 19 BibTeX entries were collected, each separated by two newlines.
        """

        # Ensure advanced filter is open (if needed)
        page.click('#advancedFilterBtn')
        page.evaluate("resetAllFilters()")
        page.wait_for_timeout(5000)
        assert page.locator('#copyBibtexBtn').is_visible(), "❌ BibTeX button is not visible"

        # Click the BibTeX copy button
        page.click('#copyBibtexBtn')

        # Wait briefly to allow clipboard population
        page.wait_for_timeout(500)

        # Read from the clipboard
        copied = page.evaluate("""
            () => {
                const bibs = window.collectBenchmarkBibtex();
                return bibs.join('\\n\\n');
            }
        """)

        # Validate
        assert copied is not None and copied.strip(), "No text was copied to clipboard."
        entries = copied.strip().split('\n\n')
        assert len(entries) == 19, f"Expected 19 BibTeX entries, got {len(entries)}."

    @pytest.mark.skip(reason="Test is flaky on CI; revisit later")
    def test_copy_bibtex_button_subset(self, page):
        """
        Validates the BibTeX copy functionality.

        Steps:
        1) Opens the Advanced Filter panel and resets all filters to ensure default benchmark visibility.
        2) Deselects Neural benchmarks
        2) Clicks the "Copy BibTeX" button.
        3) Retrieves BibTeX entries directly via the browser's collectBenchmarkBibtex() function.
        4) Asserts that exactly 9 BibTeX entries were collected, each separated by two newlines.
        """

        # Ensure advanced filter is open (if needed)
        page.click('#advancedFilterBtn')

        cb_locator = page.locator(
            '#benchmarkFilterPanel input[type="checkbox"][value="neural_vision_v0"]'
        ).first
        cb_locator.wait_for(state="visible")
        cb_locator.click(force=True)

        # Wait until the app JS thinks it's excluded
        page.wait_for_function(
            """() => window.filteredOutBenchmarks?.has("neural_vision_v0")"""
        )

        assert page.locator('#copyBibtexBtn').is_visible(), "BibTeX button is not visible"
        page.click('#copyBibtexBtn')

        page.wait_for_timeout(500)
        copied = page.evaluate("""
            () => window.collectBenchmarkBibtex().join('\\n\\n')
        """)
        # Validate
        assert copied is not None and copied.strip(), "No text was copied to clipboard."
        entries = copied.strip().split('\n\n')
        assert len(entries) == 9, f" Expected 9 BibTeX entries, got {len(entries)}."

class TestExtraFunctionality:

    def test_csv_export_contains_expected_files(self, page, tmp_path):
        """
        Verifies that clicking the CSV export button:
        1) Triggers a ZIP download.
        2) The ZIP contains both `leaderboard.csv` and `plugin-info.csv`.
        """

        # Wait for the button to appear and click it
        assert page.locator('#exportCsvButton').is_visible(), "Export CSV button not visible"

        with page.expect_download() as download_info:
            page.click('#exportCsvButton')

        download = download_info.value
        zip_path = tmp_path / download.suggested_filename
        download.save_as(zip_path)

        # Read and inspect ZIP contents
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            file_list = zip_file.namelist()

            assert any(name.startswith("brain-score-plugin-metadata") and name.endswith(".csv") for name in file_list), \
                "leaderboard*.csv not found in ZIP"
            assert any(name.startswith("brain-score-leaderboard") and name.endswith(".csv") for name in file_list), \
                "leaderboard*.csv not found in ZIP"


    def test_search_bar_filters_models_by_name(self, page):
        """
        Verifies that typing 'Ferguson' into the search bar filters the leaderboard,
        and that the top 5 visible rows match expected rank, model name, and score.
        """

        # Reset filters to default
        page.click('#advancedFilterBtn')
        page.evaluate("resetAllFilters()")
        page.wait_for_timeout(5000)

        # Type "Ferguson" into the search input
        search_input = page.locator('#modelSearchInput')
        assert search_input.is_visible(), "❌ Search bar not found"
        search_input.fill("Ferguson")
        page.wait_for_timeout(5000)

        # Capture top 5 visible rows
        actual_ranks = page.locator('.ag-cell[col-id="rank"]').all_text_contents()[:5]
        actual_models = page.locator('.ag-cell[col-id="model"] a').all_text_contents()[:5]
        actual_scores = page.locator('.ag-cell[col-id="average_vision_v0"]').all_text_contents()[:5]

        # Replace these with actual expected values
        expected_ranks = [269, 346, 412, 441, 445]
        expected_models = [
            "alexnet",
            "yudixie_resnet50_imagenet1kpret_0_240312",
            "bp_resnet50_julios",
            "unet_entire",
            "TAU"
        ]
        expected_scores = ["0.17", "0.14", "0.07", "0.04", "0.01"]
        print(actual_models)
        print(expected_models)

        # Compare results
        assert actual_ranks == [str(r) for r in expected_ranks], f"Ranks: {actual_ranks}"
        assert actual_models == expected_models, f"Models: {actual_models}"
        assert actual_scores == expected_scores, f"Scores: {actual_scores}"