/**
 * Compare Representations panel.
 *
 * Renders precomputed representational-similarity artifacts. Deliberately does
 * not fetch until its tab is first opened -- the payload is dead weight for the
 * majority of visitors who never leave the default tab.
 */
(function () {
    'use strict';

    var state = { loaded: false, loading: false };

    function el(id) { return document.getElementById(id); }

    function fmtBytes(n) {
        if (!n && n !== 0) return '—';
        if (n >= 1073741824) return (n / 1073741824).toFixed(1) + ' GB';
        if (n >= 1048576) return (n / 1048576).toFixed(0) + ' MB';
        if (n >= 1024) return (n / 1024).toFixed(0) + ' KB';
        return n + ' B';
    }

    function ckaCell(value) {
        // no colour scale: CKA is not a score and should not read like one
        return value === null || value === undefined ? '—' : value.toFixed(3);
    }

    function render(payload) {
        var status = el('representations-status');
        var content = el('representations-content');
        var rows = (payload && payload.comparisons) || [];

        if (!rows.length) {
            status.textContent = 'No representation artifacts available yet. These are ' +
                'precomputed from cached activations as models are scored.';
            status.style.display = '';
            content.style.display = 'none';
            return;
        }

        var models = payload.models || [];
        var tbody = el('representations-table').querySelector('tbody');
        tbody.innerHTML = '';

        rows.slice().sort(function (a, b) { return (b.cka || 0) - (a.cka || 0); })
            .forEach(function (r) {
                var tr = document.createElement('tr');
                var pr = r.participation_ratio || {};
                var prText = models.map(function (m) {
                    var v = pr[m];
                    return v === undefined ? '—' : v.toFixed ? v.toFixed(1) : v;
                }).join(' / ');
                // A readout-only entry compares classifier outputs, not internal
                // representations. Saying so inline is the difference between a
                // number and a misleading number.
                var layerNote = r.readout_only
                    ? '<span class="tag is-warning is-light" title="Compares classifier ' +
                      'outputs, not internal representations">readout only</span>'
                    : '<span class="tag is-info is-light">region layers</span>';
                tr.innerHTML =
                    '<td>' + escapeHtml(r.stimulus_set) + '</td>' +
                    '<td class="has-text-right">' + (r.n || '—') + '</td>' +
                    '<td class="has-text-right"><strong>' + ckaCell(r.cka) + '</strong></td>' +
                    '<td class="has-text-right">' + prText + '</td>' +
                    '<td class="has-text-right">' + fmtBytes(r.bytes_activations) + '</td>' +
                    '<td class="has-text-right">' + fmtBytes(r.bytes_gram) + '</td>' +
                    '<td>' + layerNote + '</td>';
                tbody.appendChild(tr);
            });

        var prov = el('representations-provenance');
        if (prov) {
            var when = payload.generated ? ' Generated ' + payload.generated + '.' : '';
            prov.textContent = 'Comparing ' + models.join(' vs ') + '.' + when +
                ' "Cached" is the stored activation size; "Derived" is the ' +
                'similarity matrix actually needed to compute CKA.';
        }

        status.style.display = 'none';
        content.style.display = '';
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function load() {
        if (state.loaded || state.loading) return;
        state.loading = true;
        var url = window.compare_representations_data_url;
        if (!url) { state.loading = false; return; }
        fetch(url, { credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (payload) {
                state.loaded = true;
                state.loading = false;
                render(payload);
            })
            .catch(function (err) {
                state.loading = false;
                var status = el('representations-status');
                if (status) {
                    status.textContent = 'Could not load representation data (' + err.message + ').';
                    status.classList.add('is-warning');
                }
            });
    }

    window.CompareRepresentations = { load: load };
})();
