"""Automatic destinations must match a literal registration at the target ref."""

from unittest.mock import Mock, patch
from django.core.cache import cache
from django.test import SimpleTestCase
from benchmarks.model_metadata.github import ProposalError
from benchmarks.model_metadata.proposal_source import discover_model_folder, registered_identifiers


class ModelDestinationTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.config = {'repository': 'brain-score/vision', 'branch': 'master',
                       'model_root': 'brainscore_vision/models'}
        self.head = 'a' * 40

    def github(self, registrations):
        api = Mock()
        root = self.config['model_root']
        items = [{'path': f'{root}/{folder}/__init__.py',
                  'repository': {'full_name': self.config['repository']}}
                 for folder in registrations]
        api.cached_request.side_effect = [
            {'incomplete_results': False, 'total_count': len(items), 'items': items},
            {'object': {'sha': self.head}},
        ]
        api.file.side_effect = lambda repo, path, ref: (registrations[path.split('/')[-2]], 'blob')
        return api

    def test_similar_names_are_filtered_and_all_candidates_use_target_commit(self):
        api = self.github({'example_variant': 'model_registry["example_variant"] = build',
                           'actual_folder': "model_registry['example'] = build"})
        self.assertEqual(discover_model_folder(api, self.config, 'example'), ('actual_folder', ''))
        self.assertEqual(api.file.call_count, 2)
        for call in api.file.call_args_list:
            self.assertEqual(call.args[0], self.config['repository'])
            self.assertEqual(call.args[2], self.head)
        self.assertIn('/git/ref/heads/master', api.cached_request.call_args.args[0])

    def test_ambiguous_or_absent_registration_requires_manual_selection(self):
        for registrations in [
            {'one': "model_registry['example'] = build", 'two': 'model_registry["example"] = build'},
            {'similar': 'model_registry["example_variant"] = build'},
            {'computed': 'model_registry[identifier] = build'},
            {},
        ]:
            with self.subTest(registrations=registrations):
                cache.clear()
                folder, message = discover_model_folder(self.github(registrations), self.config, 'example')
                self.assertIsNone(folder)
                self.assertTrue(message)

    def test_incomplete_or_truncated_search_never_selects_a_candidate(self):
        for result in [
            {'incomplete_results': True, 'total_count': 1, 'items': [{'path': 'anything'}]},
            {'incomplete_results': False, 'total_count': 101, 'items': [{'path': 'anything'}]},
            {'items': []},
        ]:
            cache.clear()
            api = Mock()
            api.cached_request.return_value = result
            folder, message = discover_model_folder(api, self.config, 'example')
            self.assertIsNone(folder)
            self.assertIn('incomplete', message)
            api.file.assert_not_called()

    def test_outside_root_nested_paths_and_other_repositories_are_ignored(self):
        api = self.github({'valid': "model_registry['example'] = build"})
        items = [
            {'path': path} for path in [
                'other/models/example/__init__.py',
                'brainscore_vision/models/../__init__.py',
                'brainscore_vision/models/one/nested/__init__.py',
                'brainscore_vision/models/example/metadata.yaml',
            ]
        ] + [{'path': 'brainscore_vision/models/elsewhere/__init__.py',
              'repository': {'full_name': 'other/vision'}}]
        api.cached_request.side_effect = [
            {'incomplete_results': False, 'total_count': len(items), 'items': items},
            {'object': {'sha': self.head}},
        ]
        self.assertIsNone(discover_model_folder(api, self.config, 'example')[0])
        api.file.assert_not_called()

    def test_stale_search_file_is_skipped_but_permission_errors_require_fallback(self):
        for status, expected in [(404, 'one'), (403, None)]:
            cache.clear()
            api = self.github({'gone': '', 'one': "model_registry['example'] = build"})
            api.file.side_effect = [ProposalError('Cannot read', status), ("model_registry['example'] = build", 'blob')]
            self.assertEqual(discover_model_folder(api, self.config, 'example')[0], expected)

    def test_search_errors_use_manual_fallback_without_exposing_api_details(self):
        api = Mock()
        api.cached_request.side_effect = ProposalError('private detail', 403)
        folder, message = discover_model_folder(api, self.config, 'example')
        self.assertIsNone(folder)
        self.assertIn('temporarily unavailable', message)
        self.assertNotIn('private detail', message)

    def test_cached_destination_is_scoped_to_repository_branch_root_and_identifier(self):
        api = self.github({'folder': "model_registry['example'] = build"})
        self.assertEqual(discover_model_folder(api, self.config, 'example')[0], 'folder')
        unused = Mock()
        self.assertEqual(discover_model_folder(unused, self.config, 'example')[0], 'folder')
        unused.cached_request.assert_not_called()
        for key, value in [('repository', 'brain-score/language'), ('branch', 'main'),
                           ('model_root', 'brainscore_language/models')]:
            config = dict(self.config, **{key: value})
            changed = Mock()
            changed.cached_request.side_effect = ProposalError('Not indexed')
            self.assertIsNone(discover_model_folder(changed, config, 'example')[0])
            changed.cached_request.assert_called_once()

    def test_language_search_uses_configured_repository_root_and_branch(self):
        self.config = {'repository': 'brain-score/language', 'branch': 'main',
                       'model_root': 'brainscore_language/models'}
        api = self.github({'gpt': "model_registry['gpt-id'] = build"})
        self.assertEqual(discover_model_folder(api, self.config, 'gpt-id'), ('gpt', ''))
        self.assertIn('brain-score%2Flanguage', api.cached_request.call_args_list[0].args[0])
        self.assertIn('/heads/main', api.cached_request.call_args.args[0])

    def test_plugin_code_is_parsed_without_execution(self):
        code = 'raise RuntimeError("do not execute")\nmodel_registry["example"] = build()'
        self.assertEqual(registered_identifiers(code), {'example'})
        with self.assertRaises(ProposalError):
            registered_identifiers('invalid python here')

    def test_slow_search_falls_back_before_reading_more_candidates(self):
        api = self.github({'one': "model_registry['example'] = build"})
        with patch('benchmarks.model_metadata.proposal_source.time.monotonic', side_effect=[0, 21]):
            self.assertIsNone(discover_model_folder(api, self.config, 'example')[0])
        api.file.assert_not_called()
