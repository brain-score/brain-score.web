"""Check metadata pages on a running staging/local server using Playwright.

Use a curated model with more than three related variants and a comparison link.
Screenshots use the supplied site's data; point this at a disposable rehearsal
server for synthetic data, or at staging for the release acceptance check.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


def check_page(page, url):
    response = page.goto(url, wait_until='networkidle')
    assert response is not None and response.status == 200, f'Page failed: {url}'
    assert page.locator('#scores').count() == 1
    assert page.locator('.model-eval-io').count() == 1
    assert page.locator('.mc-grid').count() == 1
    assert page.locator('.mc-use-grid').count() == 1
    sizes = page.evaluate('({viewport: document.documentElement.clientWidth, width: document.documentElement.scrollWidth})')
    assert sizes['viewport'] == sizes['width'], f'Horizontal overflow: {sizes}'
    return sizes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url')
    parser.add_argument('--curated-id', required=True, type=int)
    parser.add_argument('--fallback-id', required=True, type=int)
    parser.add_argument('--empty-id', required=True, type=int)
    parser.add_argument('--browser', help='Optional Chromium/Chrome executable path')
    parser.add_argument('--output', type=Path, default=Path('metadata-ui-results'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**({'executable_path': args.browser} if args.browser else {}))
        try:
            for width in (1440, 768, 390):
                page = browser.new_page(viewport={'width': width, 'height': 1000}, is_mobile=width == 390)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                sizes = check_page(page, urljoin(args.base_url, f'/model/vision/{args.curated_id}'))
                assert page.locator('.mc-kicker').first.text_content().strip() == 'Curated metadata'
                extras = page.locator('[data-related-variant][hidden]')
                count = extras.count()
                assert count > 0, 'Choose a curated model with more than three relatives'
                assert extras.first.is_hidden()
                button = page.locator('[data-lineage-toggle]')
                button.focus()
                page.keyboard.press('Enter')
                assert button.get_attribute('aria-expanded') == 'true'
                assert not page.locator('[data-related-variant][hidden]').count()
                page.keyboard.press('Enter')
                assert page.locator('[data-related-variant][hidden]').count() == count
                confidence = page.locator('.mc-confidence summary').first
                if confidence.count():
                    confidence.focus()
                    page.keyboard.press('Enter')
                    assert confidence.locator('..').get_attribute('open') is not None
                assert not errors, errors
                page.screenshot(path=str(args.output / f'curated-{width}.png'), full_page=True)
                results.append({'width': width, 'size': sizes, 'hidden_relatives': count, 'errors': errors})
                if width == 1440:
                    link = page.locator('.mc-lineage-compare').first.get_attribute('href')
                    response = page.goto(urljoin(args.base_url, link), wait_until='networkidle')
                    assert response.status == 200
                    assert page.locator('#compare-dashboard').count() == 1
                    assert page.locator('#compare-dashboard-load-error').is_hidden()
                    results.append({'comparison_url': page.url, 'status': response.status})
                page.close()
            for model_id, label in ((args.fallback_id, 'fallback'), (args.empty_id, 'empty')):
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                check_page(page, urljoin(args.base_url, f'/model/vision/{model_id}'))
                assert page.locator('.mc-kicker').first.text_content().strip() == 'Submission metadata'
                toggle = page.locator('[data-metadata-toggle]').first
                if toggle.count():
                    assert toggle.get_attribute('aria-expanded') == 'false'
                    toggle.focus()
                    page.keyboard.press('Enter')
                    assert toggle.get_attribute('aria-expanded') == 'true'
                    target = page.locator('#' + toggle.get_attribute('aria-controls'))
                    assert target.is_visible()
                    page.keyboard.press('Enter')
                    assert target.is_hidden()
                page.screenshot(path=str(args.output / f'{label}.png'), full_page=True)
                page.close()
        finally:
            browser.close()
    (args.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
