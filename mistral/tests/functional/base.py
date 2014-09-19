# Copyright 2013 Mirantis, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import time

from tempest import clients
from tempest.common import rest_client
from tempest import config
from tempest import exceptions
import tempest.test

CONF = config.CONF


def get_resource(path):
    main_package = 'mistral/tests'
    dir_path = __file__[0:__file__.find(main_package) + len(main_package) + 1]

    return open(dir_path + path).read()


def find_items(items, **props):
        def _matches(item, **props):
            for prop_name, prop_val in props.iteritems():
                if item[prop_name] != prop_val:
                    return False

            return True

        filtered = filter(lambda item: _matches(item, **props), items)

        if len(filtered) == 1:
            return filtered[0]

        return filtered


class MistralClientBase(rest_client.RestClient):

    _version = None

    def __init__(self, auth_provider):
        super(MistralClientBase, self).__init__(auth_provider)

        if self._version == 1:
            self.service = 'workflow'
        elif self._version == 2:
            self.service = 'workflowv2'
        else:
            msg = ("Invalid parameter 'version'. "
                   "Use version=1 or version=2.")
            raise exceptions.UnprocessableEntity(msg)
        self.endpoint_url = 'publicURL'

    def get_list_obj(self, name):
        resp, body = self.get(name)
        return resp, json.loads(body)

    def delete_obj(self, obj, name):
        return self.delete('{obj}/{name}'.format(obj=obj, name=name))

    def get_object(self, obj, id):
        resp, body = self.get('{obj}/{id}'.format(obj=obj, id=id))
        return resp, json.loads(body)


class MistralClientV1(MistralClientBase):

    _version = 1

    def create_workbook(self, name):
        post_body = '{"name": "%s"}' % name
        resp, body = self.post('workbooks', post_body)
        return resp, json.loads(body)

    def update_workbook(self, name):
        post_body = '{"name": "%s"}' % (name + 'updated')
        resp, body = self.put('workbooks/{name}'.format(name=name),
                              post_body)
        return resp, json.loads(body)

    def get_workbook_definition(self, name):
        headers = {'X-Auth-Token': self.auth_provider.get_token()}
        return self.get('workbooks/{name}/definition'.format(name=name),
                        headers)

    def upload_workbook_definition(self, name):
        headers = {'Content-Type': 'text/plain',
                   'X-Auth-Token': self.auth_provider.get_token()}
        text = get_resource('resources/wb_v1.yaml')

        return self.put('workbooks/{name}/definition'.format(name=name),
                        text, headers)

    def create_execution(self, workbook_name, post_body=None):
        if post_body is None:
            body = {
                "workbook_name": workbook_name,
                "task": 'hello',
                "context": ''
            }
        else:
            body = post_body

        rest, body = self.post('workbooks/{name}/executions'.format(
            name=workbook_name), json.dumps(body))

        return rest, json.loads(body)

    def update_execution(self, execution_id, put_body):
        return self.put('executions/{execution}'.format(
            execution=execution_id), json.dumps(put_body))

    def get_tasks_list(self, workbook_name, execution_id):
        resp, body = self.get(
            '/workbooks/{name}/executions/{execution}/tasks'.format(
                name=workbook_name,
                execution=execution_id))

        return resp, json.loads(body)['tasks']

    def get_task(self, workbook_name, execution_id, task_id):
        resp, body = self.get(
            '/workbooks/{name}/executions/{execution}/tasks/{task}'.format(
                name=workbook_name,
                execution=execution_id,
                task=task_id))

        return resp, json.loads(body)

    def update_task(self, task_id, put_body):
        resp, body = self.put('tasks/{task}'.format(
            task=task_id), json.dumps(put_body))

        return resp, json.loads(body)

    def prepare_workbook(self, name, text):
        headers = {'Content-Type': 'text/plain',
                   'X-Auth-Token': self.auth_provider.get_token()}

        return self.put('workbooks/{name}/definition'.format(name=name),
                        text, headers)

    def create_execution_wait_success(self, workbook_name,
                                      context, task, timeout=180):

        body = {
            "workbook_name": workbook_name,
            "task": task,
            "context": json.dumps(context)
        }

        resp, ex_body = self.create_execution(workbook_name, body)

        start_time = time.time()

        expected_states = ['SUCCESS', 'RUNNING']

        while ex_body['state'] != 'SUCCESS':
            if time.time() - start_time > timeout:
                msg = "Execution exceeds timeout {0} to change state " \
                      "to SUCCESS. Execution: {1}".format(timeout, ex_body)
                raise exceptions.TimeoutException(msg)

            _, ex_body = self.get_object('executions', ex_body['id'])

            if ex_body['state'] not in expected_states:
                msg = "Execution state %s is not in expected " \
                      "states: %s" % (ex_body['state'], expected_states)
                raise exceptions.TempestException(msg)

            time.sleep(2)

        return resp, ex_body

    def get_task_by_name(self, workbook_name, execution_id, name):
        _, tasks = self.get_tasks_list(workbook_name, execution_id)
        for task in tasks:
            if task['name'] == name:
                _, task_body = self.get_task(
                    workbook_name, execution_id, task['id'])

                return task_body


class MistralClientV2(MistralClientBase):

    _version = 2

    def create_workbook(self, name):
        post_body = '{"name": "%s", "tags": "tag"}' % name
        resp, body = self.post('workbooks', post_body)

        return resp, json.loads(body)

    def update_workbook(self, name):
        post_body = '{"name": "%s", "tags": "tag"}' % (name + 'updated')
        resp, body = self.put('workbooks/{name}'.format(name=name),
                              post_body)

        return resp, json.loads(body)

    def get_workbook_definition(self, name):
        return self.get('workbooks/{name}'.format(name=name))

    def upload_workbook_definition(self, name):
        text = get_resource('resources/wb_v2.yaml')
        post_body = {"name": "%s" % name,
                     "tags": "tag",
                     "definition": "%s" % text}
        resp, body = self.put('workbooks/{name}'.format(name=name),
                              json.dumps(post_body))

        return resp, json.loads(body)

    def create_workflow(self, name):
        text = get_resource('resources/wf_v2.yaml')
        post_body = {"name": "%s" % name,
                     "definition": "%s" % text,
                     "tags": "tag"}
        resp, body = self.post('workflows', json.dumps(post_body))

        return resp, json.loads(body)

    def update_workflow(self, name):
        post_body = '{"name": "%s", "tags": "tag"}' % (name + 'updated')
        resp, body = self.put('workflows/{name}'.format(name=name),
                              post_body)

        return resp, json.loads(body)

    def get_workflow_definition(self, name):
        return self.get('workflows/{name}'.format(name=name))

    def upload_workflow_definition(self, name):
        text = get_resource('resources/wf_v2.yaml')
        post_body = {"name": "%s" % name,
                     "tags": "tag",
                     "definition": "%s" % text}
        resp, body = self.put('workflows/{name}'.format(name=name),
                              json.dumps(post_body))

        return resp, json.loads(body)

    def create_execution(self, wf_name, post_body=None):
        if post_body is None:
            body = '{"workflow_name": "%s"}' % wf_name
        else:
            body = post_body
        rest, body = self.post('executions', body)

        return rest, json.loads(body)

    def update_execution(self, execution_id, put_body):
        return self.put('executions/{execution}'.format(
            execution=execution_id), json.dumps(put_body))

    def update_task(self, task_id, put_body):
        resp, body = self.put('tasks/{task}'.format(
            task=task_id), json.dumps(put_body))

        return resp, json.loads(body)


class TestCase(tempest.test.BaseTestCase):

    @classmethod
    def setUpClass(cls):
        """This method allows to initialize authentication before
        each test case and define parameters of Mistral API Service.
        """
        super(TestCase, cls).setUpClass()

        cls.mgr = clients.Manager()
        if cls._version == 1:
            cls.client = MistralClientV1(cls.mgr.auth_provider)
        if cls._version == 2:
            cls.client = MistralClientV2(cls.mgr.auth_provider)

    def setUp(self):
        super(TestCase, self).setUp()

    def tearDown(self):
        super(TestCase, self).tearDown()

        _, items = self.client.get_list_obj('workbooks')
        for i in items['workbooks']:
            self.client.delete_obj('workbooks', i['name'])


class TestCaseAdvanced(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestCaseAdvanced, cls).setUpClass()

        cls.server_client = cls.mgr.servers_client

        cls.image_ref = CONF.compute.image_ref
        cls.flavor_ref = CONF.compute.flavor_ref

    def setUp(self):
        super(TestCaseAdvanced, self).setUp()

        self.workbook_name = 'test'
        self.client.create_workbook(self.workbook_name)

    def tearDown(self):
        _, items = self.client.get_list_obj('workbooks')
        for i in items['workbooks']:
            self.client.delete_obj('workbooks', i['name'])

        _, executions = self.client.get_list_obj('executions')

        for ex in executions['executions']:
            self.client.delete_obj('executions', '{0}'.format(ex['id']))

        super(TestCaseAdvanced, self).tearDown()