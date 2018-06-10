# Built-in Imports
import os
import requests
import subprocess
import tempfile
import testtools
import zipfile

# Cloudify Imports
from cloudify.test_utils import workflow_test


URL = 'https://github.com/cloudify-examples/' \
      'cloudify-environment-setup/archive/latest.zip'
YAML_NAME = 'azure.yaml'
blueprint_directory = tempfile.mkdtemp()
blueprint_zip_path = os.path.join(blueprint_directory, 'blueprint.zip')
blueprint_path = os.path.join(
    blueprint_directory,
    'cloudify-environment-setup-latest', YAML_NAME)


class TestAzure(testtools.TestCase):

    def create_blueprint():
        r = requests.get(URL)
        with open(blueprint_zip_path, 'wb') as outfile:
            outfile.write(r.content)
        zip_ref = zipfile.ZipFile(blueprint_zip_path, 'r')
        zip_ref.extractall(blueprint_directory)
        zip_ref.close()
        return blueprint_path

    def create_inputs():
        try:
            return {
                'password': 'admin',
                'location': 'westus',
                'resource_prefix': 'ecosystem',
                'resource_suffix': os.environ['CIRCLE_BUILD_NUM'],
                'subscription_id': os.environ['AZURE_SUB_ID'],
                'tenant_id': os.environ['AZURE_TEN_ID'],
                'client_id': os.environ['AZURE_CLI_ID'],
                'client_secret': os.environ['AZURE_CLI_SE'],
            }
        except KeyError:
            raise

    def resources_to_copy():
        blueprint_resource_list = [
            (os.path.join(
               blueprint_directory,
               'cloudify-environment-setup-latest/imports/'
               'manager-configuration.yaml'),
             'imports/'),
            (os.path.join(
                blueprint_directory,
                'cloudify-environment-setup-latest/scripts/manager/tasks.py'),
             'scripts/manager/')
        ]
        return blueprint_resource_list

    @workflow_test(blueprint_path=create_blueprint(),
                   resources_to_copy=resources_to_copy(),
                   inputs=create_inputs())
    def test_lifecycle_install(self, cfy_local, *_):
        try:
            cfy_local.execute(
                'install',
                task_retries=45,
                task_retry_interval=10)
            instances = cfy_local.storage.get_node_instances()
            # Login to Azure
            login_command = 'az login -u {0} -p {1}'.format(
                os.environ['TESTUSEREMAIL'],
                os.environ['AZURE_CLI_SE'])
            login = subprocess.Popen(
                login_command.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            login.communicate()
            del login
            # Verify resources
            for instance in instances:
                show_command = 'az resource list --name {0}'.format(
                    instance.runtime_properties['name'])
                show = subprocess.Popen(
                    show_command.split(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
                show.communicate()
                self.assertEqual(show.returncode, 0)
                del show
        finally:
            cfy_local.execute(
                'uninstall',
                parameters={'ignore_failure': True},
                allow_custom_parameters=True,
                task_retries=100,
                task_retry_interval=15)
