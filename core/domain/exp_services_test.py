# coding: utf-8
#
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = 'Sean Lip'

import datetime
import os
import StringIO
import zipfile

from core.domain import exp_domain
from core.domain import exp_services
from core.domain import fs_domain
from core.domain import param_domain
from core.domain import rights_manager
from core.domain import rule_domain
from core.domain import stats_services
from core.platform import models
(base_models, exp_models) = models.Registry.import_models([
    models.NAMES.base_model, models.NAMES.exploration
])
import feconf
import test_utils
import utils


class ExplorationServicesUnitTests(test_utils.GenericTestBase):
    """Test the exploration services module."""

    def setUp(self):
        """Creates dummy users."""
        super(ExplorationServicesUnitTests, self).setUp()

        self.owner_id = 'owner@example.com'
        self.editor_id = 'editor@example.com'
        self.viewer_id = 'viewer@example.com'


class ExplorationQueriesUnitTests(ExplorationServicesUnitTests):
    """Tests query methods."""

    def test_get_all_explorations(self):
        """Test get_all_explorations()."""

        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', 'A exploration_id'))
        self.assertItemsEqual(
            [e.id for e in exp_services.get_all_explorations()],
            [exploration.id]
        )

        exploration2 = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'New title', 'A category',
                'New exploration_id'))
        self.assertItemsEqual(
            [e.id for e in exp_services.get_all_explorations()],
            [exploration.id, exploration2.id]
        )

    def test_get_public_explorations(self):
        EXP_ID = 'A exploration_id'
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', EXP_ID))
        self.assertEqual(exp_services.get_public_explorations(), [])

        rights_manager.publish_exploration(self.owner_id, EXP_ID)

        self.assertEqual(
            [e.id for e in exp_services.get_public_explorations()],
            [exploration.id]
        )

    def test_get_viewable_explorations(self):
        EXP_ID = 'A exploration_id'
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', EXP_ID))
        rights_manager.assign_role(
            self.owner_id, EXP_ID, self.editor_id, rights_manager.ROLE_EDITOR)
        exp_services.save_exploration(self.owner_id, exploration)

        def get_viewable_ids(user_id):
            return [
                e.id for e in exp_services.get_viewable_explorations(user_id)
            ]

        self.assertEqual(get_viewable_ids(self.owner_id), [exploration.id])
        self.assertEqual(get_viewable_ids(self.viewer_id), [])
        self.assertEqual(get_viewable_ids(None), [])

        # Set the exploration's status to published.
        rights_manager.publish_exploration(self.owner_id, EXP_ID)

        self.assertEqual(get_viewable_ids(self.owner_id), [exploration.id])
        self.assertEqual(
            get_viewable_ids(self.viewer_id), [exploration.id])
        self.assertEqual(get_viewable_ids(None), [exploration.id])

    def test_get_editable_explorations(self):
        EXP_ID = 'A exploration_id'
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', EXP_ID))
        rights_manager.assign_role(
            self.owner_id, EXP_ID, self.editor_id, rights_manager.ROLE_EDITOR)
        exp_services.save_exploration(self.owner_id, exploration)

        def get_editable_ids(user_id):
            return [
                e.id for e in exp_services.get_editable_explorations(user_id)
            ]

        self.assertEqual(get_editable_ids(self.owner_id), [exploration.id])
        self.assertEqual(get_editable_ids(self.viewer_id), [])
        self.assertEqual(get_editable_ids(None), [])

        rights_manager.publish_exploration(self.owner_id, EXP_ID)

        self.assertEqual(get_editable_ids(self.owner_id), [exploration.id])
        self.assertEqual(get_editable_ids(self.viewer_id), [])
        self.assertEqual(get_editable_ids(None), [])

    def test_count_explorations(self):
        """Test count_explorations()."""

        self.assertEqual(exp_services.count_explorations(), 0)

        exp_services.create_new(
            self.owner_id, 'A title', 'A category', 'A exploration_id')
        self.assertEqual(exp_services.count_explorations(), 1)

        exp_services.create_new(
            self.owner_id, 'A new title', 'A category', 'A new exploration_id')
        self.assertEqual(exp_services.count_explorations(), 2)


class ExplorationParametersUnitTests(ExplorationServicesUnitTests):
    """Test methods relating to exploration parameters."""

    def test_get_init_params(self):
        """Test the get_init_params() method."""
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', 'eid'))

        independent_pc = param_domain.ParamChange(
            'a', 'Copier', {'value': 'firstValue', 'parse_with_jinja': False})
        dependent_pc = param_domain.ParamChange(
            'b', 'Copier', {'value': '{{a}}', 'parse_with_jinja': True})

        exploration.param_specs = {
            'a': param_domain.ParamSpec('UnicodeString'),
            'b': param_domain.ParamSpec('UnicodeString'),
        }
        exploration.param_changes = [independent_pc, dependent_pc]
        exp_services.save_exploration('committer_id', exploration)

        new_params = exp_services.get_init_params('eid')
        self.assertEqual(new_params, {'a': 'firstValue', 'b': 'firstValue'})

        exploration.param_changes = [dependent_pc, independent_pc]
        exp_services.save_exploration('committer_id', exploration)

        # Jinja string evaluation fails gracefully on dependencies that do not
        # exist.
        new_params = exp_services.get_init_params('eid')
        self.assertEqual(new_params, {'a': 'firstValue', 'b': ''})

    def test_update_with_state_params(self):
        """Test the update_with_state_params() method."""
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', 'eid'))

        independent_pc = param_domain.ParamChange(
            'a', 'Copier', {'value': 'firstValue', 'parse_with_jinja': False})
        dependent_pc = param_domain.ParamChange(
            'b', 'Copier', {'value': '{{a}}', 'parse_with_jinja': True})

        exploration.param_specs = {
            'a': param_domain.ParamSpec('UnicodeString'),
            'b': param_domain.ParamSpec('UnicodeString'),
        }
        exploration.init_state.param_changes = [independent_pc, dependent_pc]
        exp_services.save_exploration('committer_id', exploration)

        reader_params = {}
        new_params = exp_services.update_with_state_params(
            'eid', exploration.init_state_name, reader_params)
        self.assertEqual(new_params, {'a': 'firstValue', 'b': 'firstValue'})
        self.assertEqual(reader_params, {})

        exploration.init_state.param_changes = [dependent_pc]
        exp_services.save_exploration('committer_id', exploration)

        reader_params = {'a': 'secondValue'}
        new_params = exp_services.update_with_state_params(
            'eid', exploration.init_state_name, reader_params)
        self.assertEqual(new_params, {'a': 'secondValue', 'b': 'secondValue'})
        self.assertEqual(reader_params, {'a': 'secondValue'})

        # Jinja string evaluation fails gracefully on dependencies that do not
        # exist.
        reader_params = {}
        new_params = exp_services.update_with_state_params(
            'eid', exploration.init_state_name, reader_params)
        self.assertEqual(new_params, {'b': ''})
        self.assertEqual(reader_params, {})


class ExplorationCreateAndDeleteUnitTests(ExplorationServicesUnitTests):
    """Test creation and deletion methods."""

    def test_create_from_yaml(self):
        """Test the create_from_yaml() method."""
        EXP_ID = 'An exploration_id'
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', EXP_ID))
        exploration.add_states(['New state'])
        self.assertEqual(len(exploration.states), 2)
        exp_services.save_exploration(self.owner_id, exploration)

        yaml_content = exp_services.export_to_yaml(EXP_ID)
        exploration2 = exp_services.get_exploration_by_id(
            exp_services.create_from_yaml(
                yaml_content, self.owner_id, 'Title', 'Category'))
        self.assertEqual(len(exploration2.states), 2)
        yaml_content_2 = exp_services.export_to_yaml(exploration2.id)
        self.assertEqual(yaml_content_2, yaml_content)

        self.assertEqual(exp_services.count_explorations(), 2)

        with self.assertRaises(Exception):
            exp_services.create_from_yaml(
                'No_initial_state_name', self.owner_id, 'Title', 'category')

        with self.assertRaises(Exception):
            exp_services.create_from_yaml(
                'Invalid\ninit_state_name:\nMore stuff',
                self.owner_id, 'Title', 'category')

        with self.assertRaises(Exception):
            exp_services.create_from_yaml(
                'State1:\n(\nInvalid yaml', self.owner_id, 'Title', 'category')

        # Check that no new exploration was created.
        self.assertEqual(exp_services.count_explorations(), 2)

    def test_creation_and_retrieval_of_explorations(self):
        """Test the create_new() and get() methods."""
        with self.assertRaisesRegexp(Exception, 'Entity .* not found'):
            exp_services.get_exploration_by_id('fake_eid')

        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', 'A exploration_id'))
        retrieved_exploration = exp_services.get_exploration_by_id(
            'A exploration_id')
        self.assertEqual(exploration.id, retrieved_exploration.id)
        self.assertEqual(exploration.title, retrieved_exploration.title)

        with self.assertRaises(Exception):
            exp_services.get_exploration_by_id('fake_exploration')

    def test_soft_deletion_of_explorations(self):
        """Test that soft deletion of explorations works correctly."""
        # TODO(sll): Add tests for deletion of states and version snapshots.

        EXP_ID = 'eid'
        exp_services.create_new(self.owner_id, 'A title', 'A category', EXP_ID)

        exp_services.delete_exploration(self.owner_id, EXP_ID)
        with self.assertRaises(Exception):
            exp_services.get_exploration_by_id(EXP_ID)

        # The deleted exploration does not show up in any queries.
        self.assertEqual(exp_services.get_all_explorations(), [])

        # But the models still exist in the backend.
        self.assertIn(
            EXP_ID,
            [exp.id for exp in exp_models.ExplorationModel.get_all(
                include_deleted_entities=True)]
        )

    def test_hard_deletion_of_explorations(self):
        """Test that hard deletion of explorations works correctly."""
        EXP_ID = 'eid'
        exp_services.create_new(self.owner_id, 'A title', 'A category', EXP_ID)

        exp_services.delete_exploration(
            self.owner_id, EXP_ID, force_deletion=True)
        with self.assertRaises(Exception):
            exp_services.get_exploration_by_id(EXP_ID)

        # The deleted exploration does not show up in any queries.
        self.assertEqual(exp_services.get_all_explorations(), [])

        # The exploration model has been purged from the backend.
        self.assertNotIn(
            EXP_ID,
            [exp.id for exp in exp_models.ExplorationModel.get_all(
                include_deleted_entities=True)]
        )

    def test_clone_exploration(self):
        """Test cloning an exploration with assets."""
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', 'An exploration_id'))
        exploration.add_states(['New state'])
        exp_services.save_exploration(self.owner_id, exploration)

        with open(os.path.join(feconf.TESTS_DATA_DIR, 'img.png')) as f:
            raw_image = f.read()
        fs = fs_domain.AbstractFileSystem(
            fs_domain.ExplorationFileSystem(exploration.id))
        fs.put('abc.png', raw_image)

        new_eid = exp_services.clone_exploration(self.owner_id, exploration.id)
        new_fs = fs_domain.AbstractFileSystem(
            fs_domain.ExplorationFileSystem(new_eid))
        new_exploration = exp_services.get_exploration_by_id(new_eid)

        self.assertEqual(new_exploration.title, 'Copy of A title')
        self.assertEqual(new_exploration.category, 'A category')
        self.assertEqual(new_fs.get('abc.png'), raw_image)

    def test_create_new_exploration_error_cases(self):
        with self.assertRaisesRegexp(Exception, 'has no title'):
            exp_services.create_new(self.owner_id, '', '')
        with self.assertRaisesRegexp(Exception, 'has no category'):
            exp_services.create_new(self.owner_id, 'title', '')
        exp_services.create_new(self.owner_id, 'title', 'category')

    def test_save_and_retrieve_exploration(self):
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', 'An exploration_id'))
        exploration.param_specs = {
            'theParameter': param_domain.ParamSpec('Int')}

        # Put and retrieve the exploration.
        exp_services.save_exploration('A user id', exploration)

        retrieved_exploration = exp_services.get_exploration_by_id(
            'An exploration_id')
        self.assertEqual(retrieved_exploration.title, 'A title')
        self.assertEqual(retrieved_exploration.category, 'A category')
        self.assertEqual(len(retrieved_exploration.states), 1)
        self.assertEqual(len(retrieved_exploration.param_specs), 1)
        self.assertEqual(
            retrieved_exploration.param_specs.keys()[0], 'theParameter')


class LoadingAndDeletionOfDemosTest(ExplorationServicesUnitTests):

    TAGS = [test_utils.TestTags.SLOW_TEST]

    def test_loading_and_validation_and_deletion_of_demo_explorations(self):
        """Test loading, validation and deletion of the demo explorations."""
        self.assertEqual(exp_services.count_explorations(), 0)

        for ind in range(len(feconf.DEMO_EXPLORATIONS)):
            start_time = datetime.datetime.utcnow()

            exp_id = str(ind)
            exp_services.load_demo(exp_id)
            exploration = exp_services.get_exploration_by_id(exp_id)
            exploration.validate(strict=True)

            duration = datetime.datetime.utcnow() - start_time
            processing_time = duration.seconds + duration.microseconds / 1E6
            print 'Loaded and validated exploration %s (%.2f seconds)' % (
                exploration.title, processing_time)

        self.assertEqual(
            exp_services.count_explorations(), len(feconf.DEMO_EXPLORATIONS))

        self.assertEqual(
            exp_services.get_exploration_by_id('4').title, u'¡Hola!')
        self.assertEqual(
            exp_services.get_exploration_by_id('9').title,
            u'Project Euler Problem 1')

        for ind in range(len(feconf.DEMO_EXPLORATIONS)):
            exp_services.delete_demo(str(ind))
        self.assertEqual(exp_services.count_explorations(), 0)


class ExportUnitTests(ExplorationServicesUnitTests):
    """Test export methods for explorations and states."""

    SAMPLE_YAML_CONTENT = (
"""default_skin: conversation_v1
init_state_name: (untitled state)
param_changes: []
param_specs: {}
schema_version: 2
states:
  (untitled state):
    content:
    - type: text
      value: ''
    param_changes: []
    widget:
      customization_args: {}
      handlers:
      - name: submit
        rule_specs:
        - definition:
            rule_type: default
          dest: (untitled state)
          feedback: []
          param_changes: []
      sticky: false
      widget_id: TextInput
  New state:
    content:
    - type: text
      value: ''
    param_changes: []
    widget:
      customization_args: {}
      handlers:
      - name: submit
        rule_specs:
        - definition:
            rule_type: default
          dest: New state
          feedback: []
          param_changes: []
      sticky: false
      widget_id: TextInput
""")

    def test_export_to_yaml(self):
        """Test the export_to_yaml() method."""
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', 'An exploration_id'))
        exploration.add_states(['New state'])
        exp_services.save_exploration(self.owner_id, exploration)

        yaml_content = exp_services.export_to_yaml(exploration.id)
        self.assertEqual(yaml_content, self.SAMPLE_YAML_CONTENT)

    def test_export_to_zip_file(self):
        """Test the export_to_zip_file() method."""
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category', 'An exploration_id'))
        exploration.add_states(['New state'])
        exp_services.save_exploration(self.owner_id, exploration)

        zip_file_output = exp_services.export_to_zip_file(exploration.id)
        zf = zipfile.ZipFile(StringIO.StringIO(zip_file_output))

        self.assertEqual(zf.namelist(), ['A title.yaml'])
        self.assertEqual(
            zf.open('A title.yaml').read(), self.SAMPLE_YAML_CONTENT)

    def test_export_to_zip_file_with_assets(self):
        """Test exporting an exploration with assets to a zip file."""
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category',
                'A different exploration_id'))
        exploration.add_states(['New state'])
        exp_services.save_exploration(self.owner_id, exploration)

        with open(os.path.join(feconf.TESTS_DATA_DIR, 'img.png')) as f:
            raw_image = f.read()
        fs = fs_domain.AbstractFileSystem(
            fs_domain.ExplorationFileSystem(exploration.id))
        fs.put('abc.png', raw_image)

        zip_file_output = exp_services.export_to_zip_file(exploration.id)
        zf = zipfile.ZipFile(StringIO.StringIO(zip_file_output))

        self.assertEqual(zf.namelist(), ['A title.yaml', 'assets/abc.png'])
        self.assertEqual(
            zf.open('A title.yaml').read(), self.SAMPLE_YAML_CONTENT)
        self.assertEqual(zf.open('assets/abc.png').read(), raw_image)

    def test_export_state_to_dict(self):
        """Test exporting a state to a dict."""
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.owner_id, 'A title', 'A category',
                'A different exploration_id'))
        exploration.add_states(['New state'])
        exp_services.save_exploration(self.owner_id, exploration)

        state_dict = exploration.states['New state'].to_dict()
        expected_dict = {
            'content': [{
                'type': 'text',
                'value': u''
            }],
            'param_changes': [],
            'widget': {
                'widget_id': u'TextInput',
                'customization_args': {},
                'sticky': False,
                'handlers': [{
                    'name': u'submit',
                    'rule_specs': [{
                        'definition': {
                            u'rule_type': u'default'
                        },
                        'dest': 'New state',
                        'feedback': [],
                        'param_changes': [],

                    }]
                }]
            },
        }
        self.assertEqual(expected_dict, state_dict)


class MigrationUnitTests(ExplorationServicesUnitTests):
    """Test migration methods for yaml content."""

    YAML_CONTENT_V1 = (
"""default_skin: conversation_v1
param_changes: []
param_specs: {}
schema_version: 1
states:
- content:
  - type: text
    value: ''
  name: (untitled state)
  param_changes: []
  widget:
    customization_args: {}
    handlers:
    - name: submit
      rule_specs:
      - definition:
          rule_type: default
        dest: (untitled state)
        feedback: []
        param_changes: []
    sticky: false
    widget_id: TextInput
- content:
  - type: text
    value: ''
  name: New state
  param_changes: []
  widget:
    customization_args: {}
    handlers:
    - name: submit
      rule_specs:
      - definition:
          rule_type: default
        dest: New state
        feedback: []
        param_changes: []
    sticky: false
    widget_id: TextInput
""")

    YAML_CONTENT_V2 = (
"""default_skin: conversation_v1
init_state_name: (untitled state)
param_changes: []
param_specs: {}
schema_version: 2
states:
  (untitled state):
    content:
    - type: text
      value: ''
    param_changes: []
    widget:
      customization_args: {}
      handlers:
      - name: submit
        rule_specs:
        - definition:
            rule_type: default
          dest: (untitled state)
          feedback: []
          param_changes: []
      sticky: false
      widget_id: TextInput
  New state:
    content:
    - type: text
      value: ''
    param_changes: []
    widget:
      customization_args: {}
      handlers:
      - name: submit
        rule_specs:
        - definition:
            rule_type: default
          dest: New state
          feedback: []
          param_changes: []
      sticky: false
      widget_id: TextInput
""")

    def test_load_from_v1(self):
        """Test direct loading from a v1 yaml file."""
        exp_services.create_from_yaml(
            self.YAML_CONTENT_V1, self.owner_id, 'A title', 'A category',
            'eid')
        v2_yaml = exp_services.export_to_yaml('eid')
        self.assertEqual(v2_yaml, self.YAML_CONTENT_V2)

    def test_load_from_v2(self):
        """Test direct loading from a v2 yaml file."""
        exp_services.create_from_yaml(
            self.YAML_CONTENT_V2, self.owner_id, 'A title', 'A category',
            'eid')
        v2_yaml = exp_services.export_to_yaml('eid')
        self.assertEqual(v2_yaml, self.YAML_CONTENT_V2)


class StateServicesUnitTests(ExplorationServicesUnitTests):
    """Test methods operating on states."""

    DEFAULT_RULESPEC_STR = exp_domain.DEFAULT_RULESPEC_STR
    SUBMIT_HANDLER = 'submit'

    def test_get_unresolved_answers(self):
        self.assertEquals(
            exp_services.get_unresolved_answers_for_default_rule(
                'eid', 'sid'), {})

        stats_services.EventHandler.record_answer_submitted(
            'eid', 'sid', self.SUBMIT_HANDLER, self.DEFAULT_RULESPEC_STR, 'a1')
        self.assertEquals(
            exp_services.get_unresolved_answers_for_default_rule(
                'eid', 'sid'), {'a1': 1})

        stats_services.EventHandler.record_answer_submitted(
            'eid', 'sid', self.SUBMIT_HANDLER, self.DEFAULT_RULESPEC_STR, 'a1')
        self.assertEquals(
            exp_services.get_unresolved_answers_for_default_rule(
                'eid', 'sid'), {'a1': 2})

        stats_services.EventHandler.resolve_answers_for_default_rule(
            'eid', 'sid', self.SUBMIT_HANDLER, ['a1'])
        self.assertEquals(
            exp_services.get_unresolved_answers_for_default_rule(
                'eid', 'sid'), {})

    def test_delete_state(self):
        """Test deletion of states."""
        USER_ID = 'fake@user.com'
        EXP_ID = 'A exploration_id'
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(USER_ID, 'A title', 'A category', EXP_ID))
        exploration.add_states(['first state'])
        exp_services.save_exploration('fake@user.com', exploration)

        exploration = exp_services.get_exploration_by_id(EXP_ID)
        with self.assertRaisesRegexp(
                ValueError, 'Cannot delete initial state'):
            exp_services.delete_state(
                USER_ID, EXP_ID, exploration.init_state_name)

        exploration.add_states(['second state'])
        exp_services.save_exploration('fake@user.com', exploration)

        exploration = exp_services.get_exploration_by_id(EXP_ID)
        exp_services.delete_state(USER_ID, EXP_ID, 'second state')

        with self.assertRaisesRegexp(ValueError, 'Invalid state name'):
            exp_services.delete_state(USER_ID, EXP_ID, 'fake state')

    def test_state_operations(self):
        """Test adding, updating and checking existence of states."""
        USER_ID = 'fake@user.com'
        EXP_ID = 'A exploration_id'

        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(USER_ID, 'A title', 'A category', EXP_ID))
        with self.assertRaises(KeyError):
            exploration.states['invalid_state_name']

        exploration = exp_services.get_exploration_by_id(EXP_ID)
        self.assertEqual(len(exploration.states), 1)

        default_state_name = exploration.init_state_name
        exploration.rename_state(default_state_name, 'Renamed state')
        exp_services.save_exploration(USER_ID, exploration)

        exploration = exp_services.get_exploration_by_id(EXP_ID)
        self.assertEqual(len(exploration.states), 1)
        self.assertEqual(exploration.init_state_name, 'Renamed state')

        # Add a new state.
        exploration.add_states(['State 2'])
        exp_services.save_exploration(USER_ID, exploration)

        exploration = exp_services.get_exploration_by_id(EXP_ID)
        self.assertEqual(len(exploration.states), 2)

        # It is OK to rename a state to the same name.
        exploration.rename_state('State 2', 'State 2')
        exp_services.save_exploration(USER_ID, exploration)

        # But it is not OK to add or rename a state using a name that already
        # exists.
        with self.assertRaisesRegexp(ValueError, 'Duplicate state name'):
            exploration.add_states(['State 2'])
        with self.assertRaisesRegexp(ValueError, 'Duplicate state name'):
            exploration.rename_state('State 2', 'Renamed state')

        # And it is not OK to rename a state to the END_DEST.
        with self.assertRaisesRegexp(
                utils.ValidationError, 'Invalid state name'):
            exploration.rename_state('State 2', feconf.END_DEST)

        # The exploration now has exactly two states.
        exploration = exp_services.get_exploration_by_id(EXP_ID)
        self.assertNotIn(default_state_name, exploration.states)
        self.assertIn('Renamed state', exploration.states)
        self.assertIn('State 2', exploration.states)


class UpdateStateTests(ExplorationServicesUnitTests):
    """Test updating a single state."""

    def setUp(self):
        super(UpdateStateTests, self).setUp()
        self.EXP_ID = 'A exploration_id'

        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                'fake@user.com', 'A title', 'A category', self.EXP_ID))

        self.init_state_name = exploration.init_state_name

        self.param_changes = [{
            'customization_args': {
                'list_of_values': ['1', '2'], 'parse_with_jinja': False
            },
            'name': 'myParam',
            'generator_id': 'RandomSelector',
            '$$hashKey': '018'
        }]

        self.widget_handlers = {
            'submit': [{
                'description': 'is equal to {{x|NonnegativeInt}}',
                'definition': {
                    'rule_type': 'atomic',
                    'name': 'Equals',
                    'inputs': {'x': 0},
                    'subject': 'answer'
                },
                'dest': self.init_state_name,
                'feedback': ['Try again'],
                '$$hashKey': '03L'
            }, {
                'description': feconf.DEFAULT_RULE_NAME,
                'definition': {
                    'rule_type': rule_domain.DEFAULT_RULE_TYPE
                },
                'dest': self.init_state_name,
                'feedback': ['Incorrect', '<b>Wrong answer</b>'],
                '$$hashKey': '059'
            }]}

    def test_update_param_changes(self):
        """Test updating of param_changes."""
        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        exploration.param_specs = {'myParam': param_domain.ParamSpec('Int')}
        exp_services.save_exploration('fake@user.com', exploration)
        exp_services.update_exploration(
            'fake@user.com', self.EXP_ID, None, None, None, None, {
                self.init_state_name: {
                    'param_changes': self.param_changes
                }
            }, None)

        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        param_changes = exploration.init_state.param_changes[0]
        self.assertEqual(param_changes._name, 'myParam')
        self.assertEqual(param_changes._generator_id, 'RandomSelector')
        self.assertEqual(
            param_changes._customization_args,
            {'list_of_values': ['1', '2'], 'parse_with_jinja': False})

    def test_update_invalid_param_changes(self):
        """Check that updates cannot be made to non-existent parameters."""
        with self.assertRaisesRegexp(
                utils.ValidationError,
                r'The parameter myParam .* does not exist .*'):
            exp_services.update_exploration(
                'fake@user.com', self.EXP_ID, None, None, None, None, {
                    self.init_state_name: {
                        'param_changes': self.param_changes
                    }
                }, None)

    def test_update_invalid_generator(self):
        """Test for check that the generator_id in param_changes exists."""
        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        exploration.param_specs = {'myParam': param_domain.ParamSpec('Int')}
        exp_services.save_exploration('fake@user.com', exploration)

        self.param_changes[0]['generator_id'] = 'fake'
        with self.assertRaisesRegexp(
                utils.ValidationError, 'Invalid generator id fake'):
            exp_services.update_exploration(
                'fake@user.com', self.EXP_ID, None, None, None, None, {
                    self.init_state_name: {
                        'param_changes': self.param_changes
                    }
                }, None)

    def test_update_widget_id(self):
        """Test updating of widget_id."""
        exp_services.update_exploration(
            'fake@user.com', self.EXP_ID, None, None, None, None, {
                self.init_state_name: {
                    'widget_id': 'MultipleChoiceInput'
                }
            }, None)

        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        self.assertEqual(
            exploration.init_state.widget.widget_id, 'MultipleChoiceInput')

    def test_update_widget_customization_args(self):
        """Test updating of widget_customization_args."""
        exp_services.update_exploration(
            'fake@user.com', self.EXP_ID, None, None, None, None, {
                self.init_state_name: {
                    'widget_id': 'MultipleChoiceInput',
                    'widget_customization_args': {
                        'choices': {'value': ['Option A', 'Option B']}
                    }
                }
            }, None)

        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        self.assertEqual(
            exploration.init_state.widget.customization_args[
                'choices']['value'], ['Option A', 'Option B'])

    def test_update_widget_sticky(self):
        """Test updating of widget_sticky."""
        exp_services.update_exploration(
            'fake@user.com', self.EXP_ID, None, None, None, None, {
                self.init_state_name: {'widget_sticky': False}
            }, None)

        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        self.assertEqual(exploration.init_state.widget.sticky, False)

        exp_services.update_exploration(
            'fake@user.com', self.EXP_ID, None, None, None, None, {
                self.init_state_name: {'widget_sticky': True}
            }, None)

        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        self.assertEqual(exploration.init_state.widget.sticky, True)

        # widget_sticky is left unchanged if it is not supplied as an argument.

        exp_services.update_exploration(
            'fake@user.com', self.EXP_ID, None, None, None, None,
            {self.init_state_name: {}}, None)

        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        self.assertEqual(exploration.init_state.widget.sticky, True)

    def test_update_widget_sticky_type(self):
        """Test for error if widget_sticky is made non-Boolean."""
        with self.assertRaisesRegexp(
                utils.ValidationError,
                'Expected widget sticky flag to be a boolean, received 3'):
            exp_services.update_exploration(
                'fake@user.com', self.EXP_ID, None, None, None, None, {
                    self.init_state_name: {'widget_sticky': 3}
                }, None)

    def test_update_widget_handlers(self):
        """Test updating of widget_handlers."""

        # We create a second state to use as a rule destination
        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        exploration.add_states(['State 2'])
        exp_services.save_exploration('fake@user.com', exploration)

        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        self.widget_handlers['submit'][1]['dest'] = 'State 2'
        exp_services.update_exploration(
            'fake@user.com', self.EXP_ID, None, None, None, None, {
                self.init_state_name: {
                    'widget_id': 'MultipleChoiceInput',
                    'widget_handlers': self.widget_handlers
                }
            }, None)

        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        rule_specs = exploration.init_state.widget.handlers[0].rule_specs
        self.assertEqual(rule_specs[0].definition, {
            'rule_type': 'atomic',
            'name': 'Equals',
            'inputs': {'x': 0},
            'subject': 'answer'
        })
        self.assertEqual(rule_specs[0].feedback, ['Try again'])
        self.assertEqual(rule_specs[0].dest, self.init_state_name)
        self.assertEqual(rule_specs[1].dest, 'State 2')

    def test_update_state_invalid_state(self):
        """Test that rule destination states cannot be non-existant."""
        self.widget_handlers['submit'][0]['dest'] = 'INVALID'
        with self.assertRaisesRegexp(
                utils.ValidationError,
                'The destination INVALID is not a valid state'):
            exp_services.update_exploration(
                'fake@user.com', self.EXP_ID, None, None, None, None, {
                    self.init_state_name: {
                        'widget_id': 'MultipleChoiceInput',
                        'widget_handlers': self.widget_handlers
                    }
                }, None)

    def test_update_state_missing_keys(self):
        """Test that missing keys in widget_handlers produce an error."""
        del self.widget_handlers['submit'][0]['definition']['inputs']
        with self.assertRaisesRegexp(KeyError, 'inputs'):
            exp_services.update_exploration(
                'fake@user.com', self.EXP_ID, None, None, None, None, {
                    self.init_state_name: {
                        'widget_id': 'NumericInput',
                        'widget_handlers': self.widget_handlers
                    }
                }, None)

    def test_update_state_extra_keys(self):
        """Test that extra keys in rule definitions are detected."""
        self.widget_handlers['submit'][0]['definition']['extra'] = 3
        with self.assertRaisesRegexp(
                utils.ValidationError, 'should conform to schema'):
            exp_services.update_exploration(
                'fake@user.com', self.EXP_ID, None, None, None, None, {
                    self.init_state_name: {
                        'widget_id': 'MultipleChoiceInput',
                        'widget_handlers': self.widget_handlers
                    }
                }, None)

    def test_update_state_extra_default_rule(self):
        """Test that rules other than the last cannot be default."""
        self.widget_handlers['submit'][0]['description'] = (
            feconf.DEFAULT_RULE_NAME)
        with self.assertRaisesRegexp(
                ValueError, 'Invalid ruleset: rules other than the last one '
                            'should not be default rules.'):
            exp_services.update_exploration(
                'fake@user.com', self.EXP_ID, None, None, None, None, {
                    self.init_state_name: {
                        'widget_id': 'MultipleChoiceInput',
                        'widget_handlers': self.widget_handlers
                    }
                }, None)

    def test_update_state_missing_default_rule(self):
        """Test that the last rule must be default."""
        self.widget_handlers['submit'][1]['description'] = 'atomic'
        with self.assertRaisesRegexp(
                ValueError,
                'Invalid ruleset: the last rule should be a default rule'):
            exp_services.update_exploration(
                'fake@user.com', self.EXP_ID, None, None, None, None, {
                    self.init_state_name: {
                        'widget_id': 'MultipleChoiceInput',
                        'widget_handlers': self.widget_handlers
                    }
                }, None)

    def test_update_state_variable_types(self):
        """Test that parameters in rules must have the correct type."""
        self.widget_handlers['submit'][0]['definition']['inputs']['x'] = 'abc'
        with self.assertRaisesRegexp(
                Exception,
                'abc has the wrong type. Please replace it with a '
                'NonnegativeInt.'):
            exp_services.update_exploration(
                'fake@user.com', self.EXP_ID, None, None, None, None, {
                    self.init_state_name: {
                        'widget_id': 'MultipleChoiceInput',
                        'widget_handlers': self.widget_handlers
                    }
                }, None)

    def test_update_content(self):
        """Test updating of content."""
        exp_services.update_exploration(
            'fake@user.com', self.EXP_ID, None, None, None, None, {
                self.init_state_name: {
                    'content': [{
                        'type': 'text',
                        'value': '<b>Test content</b>',
                        '$$hashKey': '014'
                    }]
                }
            }, None)

        exploration = exp_services.get_exploration_by_id(self.EXP_ID)
        self.assertEqual(exploration.init_state.content[0].type, 'text')
        self.assertEqual(
            exploration.init_state.content[0].value, '<b>Test content</b>')

    def test_update_content_missing_key(self):
        """Test that missing keys in content yield an error."""
        with self.assertRaisesRegexp(KeyError, 'type'):
            exp_services.update_exploration(
                'fake@user.com', self.EXP_ID, None, None, None, None, {
                    self.init_state_name: {
                        'content': [{
                            'value': '<b>Test content</b>',
                            '$$hashKey': '014'
                        }]
                    }
                }, None)


class CommitMessageHandlingTests(test_utils.GenericTestBase):
    """Test the handling of commit messages."""

    def setUp(self):
        super(CommitMessageHandlingTests, self).setUp()
        self.EXP_ID = 'A exploration_id'
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                'fake@user.com', 'A title', 'A category', self.EXP_ID,
                default_dest_is_end_state=True))
        self.init_state_name = exploration.init_state_name

    def test_record_commit_message(self):
        """Check published explorations record commit messages."""
        rights_manager.publish_exploration('fake@user.com', self.EXP_ID)

        exp_services.update_exploration(
            'fake@user.com', self.EXP_ID, None, None, None, None,
            {self.init_state_name: {'widget_sticky': False}},
            'A message')

        self.assertEqual(
            exp_services.get_exploration_snapshots_metadata(
                self.EXP_ID, 1)[0]['commit_message'],
            'A message')

    def test_demand_commit_message(self):
        """Check published explorations demand commit messages"""
        rights_manager.publish_exploration('fake@user.com', self.EXP_ID)

        with self.assertRaisesRegexp(
                ValueError, 'Exploration is public so expected a commit '
                            'message but received none.'):
            exp_services.update_exploration(
                'fake@user.com', self.EXP_ID, None, None, None, None,
                {self.init_state_name: {'widget_sticky': False}}, None)

    def test_unpublished_explorations_can_accept_commit_message(self):
        """Test unpublished explorations can accept optional commit messages"""

        exp_services.update_exploration(
            'fake@user.com', self.EXP_ID, None, None, None, None,
            {self.init_state_name: {'widget_sticky': False}},
            'A message')

        exp_services.update_exploration(
            'fake@user.com', self.EXP_ID, None, None, None, None,
            {self.init_state_name: {'widget_sticky': True}}, None)


class ExplorationSnapshotUnitTests(ExplorationServicesUnitTests):
    """Test methods relating to exploration snapshots."""

    def test_get_exploration_snapshots_metadata(self):
        eid = 'exp_id'
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                'committer_id_1', 'A title', 'A category', eid,
                default_dest_is_end_state=True))

        self.assertEqual(
            exp_services.get_exploration_snapshots_metadata(eid, 3), [])

        # Publish the exploration so that version snapshots start getting
        # recorded.
        rights_manager.publish_exploration('committer_id_1', eid)

        exploration = exp_services.get_exploration_by_id(eid)
        exploration.title = 'First title'
        exp_services.save_exploration(
            'committer_id_1', exploration, 'Changed title.')

        snapshots_metadata = exp_services.get_exploration_snapshots_metadata(
            eid, 3)
        self.assertEqual(len(snapshots_metadata), 1)
        self.assertDictContainsSubset({
            'committer_id': 'committer_id_1',
            'commit_message': 'Changed title.',
            'version_number': 1,
        }, snapshots_metadata[0])

        # Using the old version of the exploration should raise an error.
        with self.assertRaisesRegexp(Exception, 'version 0, which is too old'):
            exp_services.save_exploration('committer_id_2', exploration)

        exploration = exp_services.get_exploration_by_id(eid)
        exploration.title = 'New title'
        exp_services.save_exploration('committer_id_2', exploration)
        snapshots_metadata = exp_services.get_exploration_snapshots_metadata(
            eid, 3)
        self.assertEqual(len(snapshots_metadata), 2)
        self.assertDictContainsSubset({
            'committer_id': 'committer_id_2',
            'commit_message': '',
            'version_number': 2,
        }, snapshots_metadata[0])
        self.assertDictContainsSubset({
            'committer_id': 'committer_id_1',
            'commit_message': 'Changed title.',
            'version_number': 1,
        }, snapshots_metadata[1])
        self.assertGreaterEqual(
            snapshots_metadata[0]['created_on'],
            snapshots_metadata[1]['created_on'])

    def test_versioning_with_add_and_delete_states(self):
        eid = 'exp_id'
        exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                'committer_id_1', 'A title', 'A category', eid,
                default_dest_is_end_state=True))

        # Publish the exploration so that version snapshots start getting
        # recorded.
        rights_manager.publish_exploration('committer_id_1', eid)

        # TODO(sll): Reinstate the following when state add/delete operations
        # can be done as part of a larger commit.
        """
        exploration = exp_services.get_exploration_by_id(eid)
        exploration.title = 'First title'
        exp_services.save_exploration(
            'committer_id_1', exploration, 'Changed title.')
        commit_dict_1 = {
            'committer_id': 'committer_id_1',
            'commit_message': 'Changed title.',
            'version_number': 1,
        }
        snapshots_metadata = exp_services.get_exploration_snapshots_metadata(
            eid, 5)
        self.assertEqual(len(snapshots_metadata), 1)

        exploration = exp_services.get_exploration_by_id(eid)
        exploration.add_states(['New state'])
        exp_services.save_exploration(
            'committer_id_2', exploration, 'Added new state')

        commit_dict_2 = {
            'committer_id': 'committer_id_2',
            'commit_message': 'Added new state',
            'version_number': 2,
        }
        snapshots_metadata = exp_services.get_exploration_snapshots_metadata(
            eid, 5)
        self.assertEqual(len(snapshots_metadata), 2)
        self.assertDictContainsSubset(
            commit_dict_2, snapshots_metadata[0])
        self.assertDictContainsSubset(commit_dict_1, snapshots_metadata[1])
        self.assertGreaterEqual(
            snapshots_metadata[0]['created_on'],
            snapshots_metadata[1]['created_on'])

        # Perform an invalid action: delete a state that does not exist. This
        # should not create a new version.
        with self.assertRaisesRegexp(ValueError, 'Invalid state name'):
            exp_services.delete_state(
                'bad_committer', eid, 'invalid_state_name')

        # Now delete the new state.
        exp_services.delete_state('committer_id_3', eid, 'New state')
        commit_dict_3 = {
            'committer_id': 'committer_id_3',
            'commit_message': 'Deleted state: New state',
            'version_number': 3,
        }
        snapshots_metadata = exp_services.get_exploration_snapshots_metadata(
            eid, 5)
        self.assertEqual(len(snapshots_metadata), 3)
        self.assertDictContainsSubset(commit_dict_3, snapshots_metadata[0])
        self.assertDictContainsSubset(commit_dict_2, snapshots_metadata[1])
        self.assertDictContainsSubset(commit_dict_1, snapshots_metadata[2])
        self.assertGreaterEqual(
            snapshots_metadata[0]['created_on'],
            snapshots_metadata[1]['created_on'])
        self.assertGreaterEqual(
            snapshots_metadata[1]['created_on'],
            snapshots_metadata[2]['created_on'])

        # The final exploration should have exactly one state.
        exploration = exp_services.get_exploration_by_id(eid)
        self.assertEqual(len(exploration.states), 1)
        """

