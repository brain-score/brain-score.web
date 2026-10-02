// Keep metadata editing and review on the model card.
document.addEventListener('DOMContentLoaded', function () {
    const dialog = document.querySelector('[data-metadata-dialog]');
    if (!dialog) return;
    const body = dialog.querySelector('[data-metadata-dialog-body]');
    const title = dialog.querySelector('h2');
    const status = dialog.querySelector('[data-metadata-status]');
    let loaded = false;
    let busy = false;
    let savedEdit = null;
    let opener = null;
    let retryUrl = null;

    function updateHeading() {
        const reviewing = Boolean(body.querySelector('[data-metadata-stage="review"]'));
        const signingIn = Boolean(body.querySelector('[data-metadata-stage="login"]'));
        dialog.classList.toggle('is-signing-in', signingIn);
        title.textContent = signingIn ? 'Sign in to edit metadata' : reviewing ? 'Review metadata changes' : 'Propose metadata changes';
        const back = body.querySelector('[data-metadata-back]');
        if (back) back.hidden = !savedEdit;
        const scroll = body.querySelector('[data-metadata-scroll]');
        if (scroll) scroll.scrollTop = 0;
        title.focus();
    }

    async function load(url, form) {
        if (busy) return;
        busy = true;
        status.textContent = form ? 'Checking your changes…' : 'Loading metadata…';
        body.setAttribute('aria-busy', 'true');
        const submit = form && form.querySelector('[type="submit"]');
        if (submit) submit.disabled = true;
        try {
            const response = await fetch(url, {
                method: form ? 'POST' : 'GET',
                credentials: 'same-origin',
                headers: { 'X-Metadata-Modal': '1' },
                body: form ? new FormData(form) : undefined
            });
            if ((response.headers.get('content-type') || '').includes('application/json')) {
                const result = await response.json();
                const destination = new URL(result.redirect);
                if (destination.origin !== 'https://github.com') throw new Error('Invalid authorization destination.');
                window.location.assign(destination.href);
                return;
            }
            const fragment = document.createElement('template');
            fragment.innerHTML = await response.text();
            const stage = fragment.content.querySelector('[data-metadata-stage]');
            if (!stage) throw new Error('The editor is unavailable or your proposal expired. Close and reopen it to retry.');
            if (stage.dataset.metadataStage === 'login') retryUrl = url;
            if (stage.dataset.metadataStage === 'review' && body.querySelector('[data-metadata-stage="edit"]')) {
                savedEdit = Array.from(body.childNodes);
            }
            body.replaceChildren(fragment.content);
            loaded = stage.dataset.metadataStage !== 'login';
            status.textContent = '';
            updateHeading();
            const error = body.querySelector('.errorlist, [role="alert"]');
            if (error) {
                reveal(error);
                error.setAttribute('tabindex', '-1');
                error.focus();
            }
        } catch (error) {
            status.textContent = 'Could not load the proposal. Your edits are still here. Please retry.';
            if (!loaded) {
                body.replaceChildren(document.createTextNode('Metadata could not be loaded. Close and reopen to retry.'));
            }
        } finally {
            busy = false;
            body.removeAttribute('aria-busy');
            if (submit) submit.disabled = false;
        }
    }

    function open(button, url) {
        opener = button || document.querySelector('[data-metadata-edit-open]');
        if (!dialog.open) dialog.showModal();
        if (!loaded || url) load(url || dialog.dataset.editUrl);
    }

    document.querySelectorAll('[data-metadata-edit-open]').forEach(function (button) {
        button.addEventListener('click', function () { open(button); });
    });
    dialog.addEventListener('click', function (event) {
        if (event.target.closest('[data-metadata-close]')) dialog.close();
    });
    dialog.addEventListener('close', function () { if (opener) opener.focus(); });

    function reveal(element) {
        for (let parent = element.parentElement; parent && parent !== body; parent = parent.parentElement) {
            if (parent.tagName === 'DETAILS') parent.open = true;
        }
    }
    body.addEventListener('invalid', function (event) { reveal(event.target); }, true);

    body.addEventListener('submit', function (event) {
        const form = event.target.closest('[data-metadata-form], [data-metadata-authorize]');
        if (!form) return;
        event.preventDefault();
        load(form.action, form);
    });
    body.addEventListener('click', function (event) {
        if (event.target.closest('[data-metadata-login-retry]')) {
            load(retryUrl || dialog.dataset.editUrl);
            return;
        }
        if (event.target.closest('[data-metadata-back]') && savedEdit) {
            body.replaceChildren(...savedEdit);
            savedEdit = null;
            status.textContent = '';
            updateHeading();
            return;
        }
        const add = event.target.closest('[data-add-row]');
        if (!add) return;
        const group = add.closest('[data-formset]');
        const total = group.querySelector('input[name$="-TOTAL_FORMS"]');
        const index = Number(total.value);
        if (index >= 500) return;
        const row = group.querySelector('[data-empty-row]').content.cloneNode(true);
        row.querySelectorAll('[name], [id], [for]').forEach(function (element) {
            ['name', 'id', 'for'].forEach(function (attr) {
                if (element.hasAttribute(attr)) element.setAttribute(attr, element.getAttribute(attr).replace(/__prefix__/g, String(index)));
            });
        });
        group.querySelector('[data-rows]').appendChild(row);
        total.value = index + 1;
    });

    const params = new URLSearchParams(window.location.search);
    const proposal = params.get('metadata_proposal');
    if (proposal && /^[A-Za-z0-9_-]{1,100}$/.test(proposal)) {
        open(null, dialog.dataset.reviewUrl.replace('PROPOSAL', encodeURIComponent(proposal)));
    } else if (params.get('metadata_edit') === '1') {
        open();
    }
});
