import mock
import os
import unittest
import click
from click import testing
from skipper import cli
from skipper import config


REGISTRY = 'registry.io:5000'
IMAGE = 'image'
TAG = '1234567'
FQDN_IMAGE = REGISTRY + '/' + IMAGE + ':' + TAG

BUILD_CONTAINER_IMAGE = 'build-container-image'
BUILD_CONTAINER_TAG = 'build-container-tag'
BUILD_CONTAINER_FQDN_IMAGE = REGISTRY + '/' + BUILD_CONTAINER_IMAGE + ':' + BUILD_CONTAINER_TAG

ENV = ["KEY1=VAL1", "KEY2=VAL2"]

SKIPPER_CONF_BUILD_CONTAINER_IMAGE = 'skipper-conf-build-container-image'
SKIPPER_CONF_BUILD_CONTAINER_TAG = 'skipper-conf-build-container-tag'
SKIPPER_CONF_BUILD_CONTAINER_FQDN_IMAGE = REGISTRY + '/' + SKIPPER_CONF_BUILD_CONTAINER_IMAGE + ':' + SKIPPER_CONF_BUILD_CONTAINER_TAG
SKIPPER_CONF_MAKEFILE = 'Makefile.skipper'
SKIPPER_CONF = {
    'registry': REGISTRY,
    'build-container-image': SKIPPER_CONF_BUILD_CONTAINER_IMAGE,
    'build-container-tag': SKIPPER_CONF_BUILD_CONTAINER_TAG,
    'make': {
        'makefile': SKIPPER_CONF_MAKEFILE,
    }
}
CONFIG_ENV = {
    "KEY2": "NOT_VAL2",
    "KEY3": "VAL3",
    "KEY4": "$VAL4",
    "KEY5": "$$VAL5"
}
CONFIG_ENV_EVALUATION = {
    "KEY2": "NOT_VAL2",
    "KEY3": "VAL3",
    "KEY4": "val4-evaluation",
    "KEY5": "$VAL5"
}
SKIPPER_CONF_WITH_ENV = {
    'registry': REGISTRY,
    'build-container-image': SKIPPER_CONF_BUILD_CONTAINER_IMAGE,
    'build-container-tag': SKIPPER_CONF_BUILD_CONTAINER_TAG,
    'make': {
        'makefile': SKIPPER_CONF_MAKEFILE,
    },
    'env': CONFIG_ENV
}


class TestCLI(unittest.TestCase):
    def setUp(self):
        self._runner = testing.CliRunner()
        self.global_params = [
            '--registry', REGISTRY,
            '--build-container-image', BUILD_CONTAINER_IMAGE,
            '--build-container-tag', BUILD_CONTAINER_TAG
        ]

    def test_cli_without_params(self):
        result = self._invoke_cli()
        self.assertEqual(result.exit_code, 0)

    def test_cli_help(self):
        result = self._invoke_cli(global_params=['--help'])
        self.assertEqual(result.exit_code, 0)

    def test_subcommand_help(self):
        for subcmd in ('build', 'push', 'make', 'run'):
            result = self._invoke_cli(
                global_params=None,
                subcmd=subcmd,
                subcmd_params=['--help']
            )
            self.assertEqual(result.exit_code, 0)

    def test_subcommand_without_global_params(self):
        subcmd_params_map = {
            'push': [IMAGE],
            'run': ['ls' '-l'],
            'make': ['-f', 'Makefile', 'all'],
        }

        for subcmd, subcmd_params in subcmd_params_map.iteritems():
            result = self._invoke_cli(
                global_params=None,
                subcmd=subcmd,
                subcmd_params=subcmd_params,
            )
            self.assertIsInstance(result.exception, click.BadParameter)
            self.assertEqual(result.exit_code, -1)

    @mock.patch('skipper.runner.run', autospec=True)
    def test_subcommand_without_subcommand_params(self, skipper_runner_run_mock):
        for subcmd in ('build', 'push', 'run', 'make'):
            result = self._invoke_cli(self.global_params, subcmd)
            self.assertNotEqual(result.exit_code, 0)
            self.assertFalse(skipper_runner_run_mock.called)

    @mock.patch('skipper.git.get_hash', autospec=True, return_value='1234567')
    @mock.patch('os.path.exists', autospec=True, return_value=True)
    @mock.patch('skipper.runner.run', autospec=True, return_value=0)
    def test_build_existing_image(self, skipper_runner_run_mock, *args):
        build_params = ['my_image']
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='build',
            subcmd_params=build_params
        )
        expected_command = [
            'docker',
            'build',
            '-f', 'Dockerfile.my_image',
            '-t', 'my_image:1234567',
            '.'
        ]
        skipper_runner_run_mock.assert_called_once_with(expected_command)

    @mock.patch('skipper.git.get_hash', autospec=True, return_value='1234567')
    @mock.patch('os.path.exists', autospec=True, return_value=False)
    @mock.patch('skipper.runner.run', autospec=True)
    def test_build_non_existing_image(self, skipper_runner_run_mock, *args):
        build_params = ['my_image']
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='build',
            subcmd_params=build_params
        )
        self.assertFalse(skipper_runner_run_mock.called)

    @mock.patch('skipper.git.get_hash', autospec=True, return_value='1234567')
    @mock.patch('os.path.exists', autospec=True, return_value=True)
    @mock.patch('skipper.runner.run', autospec=True, return_value=0)
    def test_build_multiple_images(self, skipper_runner_run_mock, *args):
        skipper_runner_run_mock.return_value = 0
        build_params = ['image1', 'image2']
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='build',
            subcmd_params=build_params
        )
        expected_commands = [
            mock.call(['docker', 'build', '-f', 'Dockerfile.image1', '-t', 'image1:1234567', '.']),
            mock.call(['docker', 'build', '-f', 'Dockerfile.image2', '-t', 'image2:1234567', '.']),
        ]
        skipper_runner_run_mock.assert_has_calls(expected_commands)

    @mock.patch('skipper.git.get_hash', autospec=True, return_value='1234567')
    @mock.patch('os.path.exists', autospec=True, return_value=True)
    @mock.patch('skipper.runner.run', autospec=True, return_value=1)
    def test_build_multiple_images_with_error(self, skipper_runner_run_mock, *args):
        build_params = ['image1', 'image2']
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='build',
            subcmd_params=build_params
        )
        expected_command = [
            'docker',
            'build',
            '-f', 'Dockerfile.image1',
            '-t', 'image1:1234567',
            '.'
        ]
        skipper_runner_run_mock.assert_called_once_with(expected_command)

    @mock.patch('skipper.utils.get_images_from_dockerfiles', autospec=True, return_value=['image1', 'image2'])
    @mock.patch('skipper.git.get_hash', autospec=True, return_value='1234567')
    @mock.patch('os.path.exists', autospec=True, return_value=True)
    @mock.patch('skipper.runner.run', autospec=True, return_value=0)
    def test_build_all_images(self, skipper_runner_run_mock, *args):
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='build',
        )
        expected_commands = [
                mock.call(['docker', 'build', '-f', 'Dockerfile.image1', '-t', 'image1:1234567', '.']),
                mock.call(['docker', 'build', '-f', 'Dockerfile.image2', '-t', 'image2:1234567', '.']),
        ]
        skipper_runner_run_mock.assert_has_calls(expected_commands)

    @mock.patch('__builtin__.open', create=True)
    @mock.patch('os.path.exists', autospec=True, return_value=True)
    @mock.patch('yaml.load', autospec=True, return_value=SKIPPER_CONF)
    @mock.patch('skipper.git.get_hash', autospec=True, return_value='1234567')
    @mock.patch('skipper.runner.run', autospec=True, return_value=0)
    def test_build_with_defaults_from_config_file(self, skipper_runner_run_mock, *args):
        build_params = ['my_image']
        self._invoke_cli(
            defaults=config.load_defaults(),
            subcmd='build',
            subcmd_params=build_params
        )
        expected_command = [
            'docker',
            'build',
            '-f', 'Dockerfile.my_image',
            '-t', 'my_image:1234567',
            '.'
        ]
        skipper_runner_run_mock.assert_called_once_with(expected_command)

    @mock.patch('skipper.git.get_hash', autospec=True, return_value='1234567')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_push(self, skipper_runner_run_mock, *args):
        push_params = ['my_image']
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='push',
            subcmd_params=push_params
        )
        expected_commands = [
            mock.call(['docker', 'tag', 'my_image:1234567', 'registry.io:5000/my_image:1234567']),
            mock.call(['docker', 'push', 'registry.io:5000/my_image:1234567']),
            mock.call(['docker', 'rmi', 'registry.io:5000/my_image:1234567']),
        ]
        skipper_runner_run_mock.assert_has_calls(expected_commands)

    @mock.patch('__builtin__.open', create=True)
    @mock.patch('os.path.exists', autospec=True, return_value=True)
    @mock.patch('yaml.load', autospec=True, return_value=SKIPPER_CONF)
    @mock.patch('skipper.git.get_hash', autospec=True, return_value='1234567')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_push_with_defaults_from_config_file(self, skipper_runner_run_mock, *args):
        push_params = ['my_image']
        self._invoke_cli(
            defaults=config.load_defaults(),
            subcmd='push',
            subcmd_params=push_params
        )
        expected_commands = [
            mock.call(['docker', 'tag', 'my_image:1234567', 'registry.io:5000/my_image:1234567']),
            mock.call(['docker', 'push', 'registry.io:5000/my_image:1234567']),
            mock.call(['docker', 'rmi', 'registry.io:5000/my_image:1234567']),
        ]
        skipper_runner_run_mock.assert_has_calls(expected_commands)

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.my_image'])
    @mock.patch('tabulate.tabulate', autospec=True)
    @mock.patch('subprocess.check_output', autospec=True)
    def test_images_with_single_local_results(self, subprocess_check_output_mock, tabulate_mock, *args):
        subprocess_check_output_mock.return_value = '{"name": "my_image", "tag": "1234567"}'
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='images',
            subcmd_params=[]
        )

        expected_command = [
            'docker',
            'images',
            '--format', '{"name": "{{.Repository}}", "tag": "{{.Tag}}"}',
            'my_image'
        ]
        subprocess_check_output_mock.assert_called_once_with(expected_command)
        tabulate_mock.assert_called_once_with([['none', 'my_image', '1234567']], headers=['REGISTRY', 'IMAGE', 'TAG'], tablefmt='grid')

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.image1', 'Dockerfile.image2'])
    @mock.patch('tabulate.tabulate', autospec=True)
    @mock.patch('subprocess.check_output', autospec=True)
    def test_images_with_multiple_local_results(self, subprocess_check_output_mock, tabulate_mock, *args):
        subprocess_check_output_mock.side_effect = [
            '{"name": "image1", "tag": "aaaaaaa"}\n',
            '{"name": "image2", "tag": "bbbbbbb"}\n{"name": "image2", "tag": "ccccccc"}\n',
        ]
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='images',
            subcmd_params=[]
        )

        command_prefix = [
            'docker',
            'images',
            '--format', '{"name": "{{.Repository}}", "tag": "{{.Tag}}"}',
        ]
        expected_check_output_calls = [
            mock.call(command_prefix + ['image1']),
            mock.call(command_prefix + ['image2']),
        ]
        subprocess_check_output_mock.assert_has_calls(expected_check_output_calls)
        expected_table = [
            ['none', 'image1', 'aaaaaaa'],
            ['none', 'image2', 'bbbbbbb'],
            ['none', 'image2', 'ccccccc'],
        ]
        tabulate_mock.assert_called_once_with(expected_table, headers=['REGISTRY', 'IMAGE', 'TAG'], tablefmt='grid')

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.my_image'])
    @mock.patch('tabulate.tabulate', autospec=True)
    @mock.patch('requests.get', autospec=True)
    @mock.patch('subprocess.check_output', autospec=True)
    def test_images_with_all_results(self, subprocess_check_output_mock, requests_get_mock, tabulate_mock, *args):
        subprocess_check_output_mock.return_value = '{"name": "my_image", "tag": "aaaaaaa"}'

        requests_response_mock = None
        with mock.patch('requests.Response', autospec=True) as requests_response_class_mock:
            requests_response_mock = requests_response_class_mock.return_value
            requests_response_mock.json.return_value = {
                'name': 'my_image',
                'tags': ['latest', 'aaaaaaa', 'bbbbbbb']
            }
            requests_get_mock.return_value = requests_response_mock

        self._invoke_cli(
            global_params=self.global_params,
            subcmd='images',
            subcmd_params=['-r']
        )

        expected_command = [
            'docker',
            'images',
            '--format', '{"name": "{{.Repository}}", "tag": "{{.Tag}}"}',
            'my_image',
        ]
        subprocess_check_output_mock.assert_called_once_with(expected_command)

        expected_url = 'https://%(registry)s/v2/my_image/tags/list' % dict(registry=REGISTRY)
        requests_get_mock.assert_called_once_with(
            url=expected_url,
            verify=False
        )

        expected_images_results = [
            ['none', 'my_image', 'aaaaaaa'],
            ['registry.io:5000', 'my_image', 'latest'],
            ['registry.io:5000', 'my_image', 'aaaaaaa'],
            ['registry.io:5000', 'my_image', 'bbbbbbb']
        ]
        tabulate_mock.assert_called_once_with(expected_images_results, headers=['REGISTRY', 'IMAGE', 'TAG'], tablefmt='grid')

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.my_image'])
    @mock.patch('tabulate.tabulate', autospec=True)
    @mock.patch('requests.get', autospec=True)
    @mock.patch('subprocess.check_output', autospec=True, return_value='')
    def test_images_with_remote_results_only(self, subprocess_check_output_mock, requests_get_mock, tabulate_mock, *args):
        requests_response_mock = None
        with mock.patch('requests.Response', autospec=True) as requests_response_class_mock:
            requests_response_mock = requests_response_class_mock.return_value
            requests_response_mock.json.return_value = {
                'name': 'my_image',
                'tags': ['latest', 'aaaaaaa', 'bbbbbbb']
            }
            requests_get_mock.return_value = requests_response_mock

        self._invoke_cli(
            global_params=self.global_params,
            subcmd='images',
            subcmd_params=['-r']
        )

        expected_command = [
            'docker',
            'images',
            '--format', '{"name": "{{.Repository}}", "tag": "{{.Tag}}"}',
            'my_image',
        ]
        subprocess_check_output_mock.assert_called_once_with(expected_command)

        expected_url = 'https://%(registry)s/v2/my_image/tags/list' % dict(registry=REGISTRY)
        requests_get_mock.assert_called_once_with(
            url=expected_url,
            verify=False
        )

        expected_images_results = [
            ['registry.io:5000', 'my_image', 'latest'],
            ['registry.io:5000', 'my_image', 'aaaaaaa'],
            ['registry.io:5000', 'my_image', 'bbbbbbb']
        ]
        tabulate_mock.assert_called_once_with(expected_images_results, headers=['REGISTRY', 'IMAGE', 'TAG'], tablefmt='grid')

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.my_image'])
    @mock.patch('tabulate.tabulate', autospec=True)
    @mock.patch('requests.get', autospec=True)
    @mock.patch('subprocess.check_output', autospec=True, return_value='')
    def test_images_with_missing_remote_results(self, subprocess_check_output_mock, requests_get_mock, tabulate_mock, *args):
        requests_response_mock = None
        with mock.patch('requests.Response', autospec=True) as requests_response_class_mock:
            requests_response_mock = requests_response_class_mock.return_value
            requests_response_mock.ok = False
            requests_response_mock.json.return_value = {
                u'errors': [{u'message': u'repository name not known to registry', u'code': u'NAME_UNKNOWN', u'detail': {u'name': u'my_image'}}]
                }
            requests_get_mock.return_value = requests_response_mock

        self._invoke_cli(
            global_params=self.global_params,
            subcmd='images',
            subcmd_params=['-r']
        )

        expected_command = [
            'docker',
            'images',
            '--format', '{"name": "{{.Repository}}", "tag": "{{.Tag}}"}',
            'my_image',
        ]
        subprocess_check_output_mock.assert_called_once_with(expected_command)

        expected_url = 'https://%(registry)s/v2/my_image/tags/list' % dict(registry=REGISTRY)
        requests_get_mock.assert_called_once_with(
            url=expected_url,
            verify=False
        )

        expected_images_results = []
        tabulate_mock.assert_called_once_with(expected_images_results, headers=['REGISTRY', 'IMAGE', 'TAG'], tablefmt='grid')

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.my_image'])
    @mock.patch('tabulate.tabulate', autospec=True)
    @mock.patch('requests.get', autospec=True)
    @mock.patch('subprocess.check_output', autospec=True)
    def test_images_with_local_result_and_missing_remote_results(self, subprocess_check_output_mock, requests_get_mock, tabulate_mock, *args):
        subprocess_check_output_mock.return_value = '{"name": "my_image", "tag": "aaaaaaa"}'

        requests_response_mock = None
        with mock.patch('requests.Response', autospec=True) as requests_response_class_mock:
            requests_response_mock = requests_response_class_mock.return_value
            requests_response_mock.ok = False
            requests_response_mock.json.return_value = {
                u'errors': [{u'message': u'repository name not known to registry', u'code': u'NAME_UNKNOWN', u'detail': {u'name': u'my_image'}}]
                }
            requests_get_mock.return_value = requests_response_mock

        self._invoke_cli(
            global_params=self.global_params,
            subcmd='images',
            subcmd_params=['-r']
        )

        expected_command = [
            'docker',
            'images',
            '--format', '{"name": "{{.Repository}}", "tag": "{{.Tag}}"}',
            'my_image',
        ]
        subprocess_check_output_mock.assert_called_once_with(expected_command)

        expected_url = 'https://%(registry)s/v2/my_image/tags/list' % dict(registry=REGISTRY)
        requests_get_mock.assert_called_once_with(
            url=expected_url,
            verify=False
        )

        expected_images_results = [
            ['none', 'my_image', 'aaaaaaa'],
        ]

        tabulate_mock.assert_called_once_with(expected_images_results, headers=['REGISTRY', 'IMAGE', 'TAG'], tablefmt='grid')

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.my_image'])
    @mock.patch('tabulate.tabulate', autospec=True)
    @mock.patch('requests.get', autospec=True)
    @mock.patch('subprocess.check_output', autospec=True, return_value='')
    def test_images_with_with_remote_error(self, subprocess_check_output_mock, requests_get_mock, tabulate_mock, *args):
        requests_response_mock = None
        with mock.patch('requests.Response', autospec=True) as requests_response_class_mock:
            requests_response_mock = requests_response_class_mock.return_value
            requests_response_mock.ok = False
            requests_response_mock.json.return_value = {
                u'errors': [{u'message': u'repository name not known to registry', u'code': u'UNKNOWN_ERROR', u'detail': {u'name': u'my_image'}}]
                }
            requests_get_mock.return_value = requests_response_mock

        result = self._invoke_cli(
            global_params=self.global_params,
            subcmd='images',
            subcmd_params=['-r']
        )

        expected_command = [
            'docker',
            'images',
            '--format', '{"name": "{{.Repository}}", "tag": "{{.Tag}}"}',
            'my_image',
        ]
        subprocess_check_output_mock.assert_called_once_with(expected_command)

        expected_url = 'https://%(registry)s/v2/my_image/tags/list' % dict(registry=REGISTRY)
        requests_get_mock.assert_called_once_with(
            url=expected_url,
            verify=False
        )

        self.assertIsInstance(result.exception, click.exceptions.ClickException)

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.my_image'])
    @mock.patch('tabulate.tabulate', autospec=True)
    @mock.patch('subprocess.check_output', autospec=True, return_value='')
    def test_images_without_local_results(self, subprocess_check_output_mock, tabulate_mock, *args):
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='images',
            subcmd_params=[]
        )

        expected_command = [
            'docker',
            'images',
            '--format', '{"name": "{{.Repository}}", "tag": "{{.Tag}}"}',
            'my_image',
        ]
        subprocess_check_output_mock.assert_called_once_with(expected_command)
        tabulate_mock.assert_called_once_with([], headers=['REGISTRY', 'IMAGE', 'TAG'], tablefmt='grid')

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.my_image'])
    @mock.patch('subprocess.check_call', autospec=True)
    def test_rmi_local(self, subprocess_check_call_mock, *args):
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='rmi',
            subcmd_params=['my_image', '1234567']
        )

        expected_command = [
            'docker',
            'rmi',
            'my_image:1234567'
        ]
        subprocess_check_call_mock.assert_called_once_with(expected_command)

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.' + IMAGE])
    @mock.patch('requests.delete', autospec=True)
    @mock.patch('requests.get', autospec=True)
    def test_rmi_remote(self, requests_get_mock, requests_delete_mock, *args):
        requests_get_mock.side_effect = [mock.Mock(headers={'Docker-Content-Digest': 'digest'})]
        requests_delete_mock.side_effect = [mock.Mock(ok=True)]
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='rmi',
            subcmd_params=['-r', IMAGE, TAG]
        )

        url = 'https://%(registry)s/v2/%(image)s/manifests/%(reference)s' % dict(registry=REGISTRY, image=IMAGE, reference=TAG)
        headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
        requests_get_mock.assert_called_once_with(url=url, headers=headers, verify=False)
        url = 'https://%(registry)s/v2/%(image)s/manifests/%(reference)s' % dict(registry=REGISTRY, image=IMAGE, reference='digest')
        requests_delete_mock.assert_called_once_with(url=url, verify=False)

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.' + IMAGE])
    @mock.patch('requests.delete', autospec=True)
    @mock.patch('requests.get', autospec=True)
    def test_rmi_remote_fail(self, requests_get_mock, requests_delete_mock, *args):
        requests_get_mock.side_effect = [mock.Mock(headers={'Docker-Content-Digest': 'digest'})]
        requests_delete_mock.side_effect = [mock.Mock(ok=False)]
        result = self._invoke_cli(
            global_params=self.global_params,
            subcmd='rmi',
            subcmd_params=['-r', IMAGE, TAG]
        )
        self.assertIsInstance(result.exception, Exception)

        url = 'https://%(registry)s/v2/%(image)s/manifests/%(reference)s' % dict(registry=REGISTRY, image=IMAGE, reference=TAG)
        headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
        requests_get_mock.assert_called_once_with(url=url, headers=headers, verify=False)
        url = 'https://%(registry)s/v2/%(image)s/manifests/%(reference)s' % dict(registry=REGISTRY, image=IMAGE, reference='digest')
        requests_delete_mock.assert_called_once_with(url=url, verify=False)

    @mock.patch('glob.glob', autospec=True, return_value=['Dockerfile.' + IMAGE])
    def test_validate_project_image(self, *args):
        result = self._invoke_cli(
            global_params=self.global_params,
            subcmd='rmi',
            subcmd_params=['-r', 'non-project-image', TAG]
        )
        self.assertIsInstance(result.exception, click.BadParameter)

    @mock.patch('subprocess.check_output', autospec=True, return_value='1234567\n')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_run_with_existing_local_build_container(self, skipper_runner_run_mock, *args):
        command = ['ls', '-l']
        run_params = command
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='run',
            subcmd_params=run_params
        )
        expected_image_name = 'build-container-image:build-container-tag'
        skipper_runner_run_mock.assert_called_once_with(command, fqdn_image=expected_image_name, environment=[], interactive=False)

    @mock.patch('subprocess.check_output', autospec=True, return_value='')
    @mock.patch('requests.get', autospec=True)
    @mock.patch('skipper.runner.run', autospec=True)
    def test_run_with_existing_remote_build_container(self, skipper_runner_run_mock, requests_get_mock, *args):
        requests_response_class_mock = mock.MagicMock(spec='requests.Response')
        requests_response_mock = requests_response_class_mock.return_value
        requests_response_mock.json.return_value = {
            'name': 'my_image',
            'tags': ['latest', 'aaaaaaa', 'bbbbbbb', 'build-container-tag']
        }
        requests_get_mock.return_value = requests_response_mock

        command = ['ls', '-l']
        run_params = command
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='run',
            subcmd_params=run_params
        )
        expected_image_name = 'registry.io:5000/build-container-image:build-container-tag'
        skipper_runner_run_mock.assert_called_once_with(command, fqdn_image=expected_image_name, environment=[], interactive=False)

    @mock.patch('subprocess.check_output', autospec=True, return_value='')
    @mock.patch('requests.get', autospec=True)
    @mock.patch('skipper.runner.run', autospec=True)
    def test_run_with_non_existing_build_container(self, skipper_runner_run_mock, requests_get_mock, *args):
        requests_response_class_mock = mock.MagicMock(spec='requests.Response')
        requests_response_mock = requests_response_class_mock.return_value
        requests_response_mock.json.return_value = {
            'name': 'my_image',
            'tags': ['latest', 'aaaaaaa', 'bbbbbbb']
        }

        requests_get_mock.return_value = requests_response_mock
        command = ['ls', '-l']
        run_params = command
        ret = self._invoke_cli(
            global_params=self.global_params,
            subcmd='run',
            subcmd_params=run_params
        )
        self.assertIsInstance(ret.exception, click.exceptions.ClickException)

    @mock.patch('__builtin__.open', create=True)
    @mock.patch('os.path.exists', autospec=True, return_value=True)
    @mock.patch('yaml.load', autospec=True, return_value=SKIPPER_CONF)
    @mock.patch('subprocess.check_output', autospec=True, return_value='1234567\n')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_run_with_defaults_from_config_file(self, skipper_runner_run_mock, *args):
        command = ['ls', '-l']
        run_params = command
        self._invoke_cli(
            defaults=config.load_defaults(),
            subcmd='run',
            subcmd_params=run_params
        )
        expected_fqdn_image = 'skipper-conf-build-container-image:skipper-conf-build-container-tag'
        skipper_runner_run_mock.assert_called_once_with(command, fqdn_image=expected_fqdn_image, environment=[], interactive=False)

    @mock.patch('__builtin__.open', create=True)
    @mock.patch('os.path.exists', autospec=True, return_value=True)
    @mock.patch('yaml.load', autospec=True, return_value=SKIPPER_CONF_WITH_ENV)
    @mock.patch('subprocess.check_output', autospec=True, return_value='1234567\n')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_run_with_defaults_and_env_from_config_file(self, skipper_runner_run_mock, *args):
        command = ['ls', '-l']
        run_params = command
        os.environ['VAL4'] = "val4-evaluation"
        self._invoke_cli(
            defaults=config.load_defaults(),
            subcmd='run',
            subcmd_params=run_params
        )
        env = ["%s=%s" % (key, value) for key, value in CONFIG_ENV_EVALUATION.iteritems()]
        expected_fqdn_image = 'skipper-conf-build-container-image:skipper-conf-build-container-tag'
        skipper_runner_run_mock.assert_called_once_with(command, fqdn_image=expected_fqdn_image, environment=env, interactive=False)

    @mock.patch('__builtin__.open', create=True)
    @mock.patch('os.path.exists', autospec=True, return_value=True)
    @mock.patch('yaml.load', autospec=True, return_value=SKIPPER_CONF_WITH_ENV)
    @mock.patch('subprocess.check_output', autospec=True, return_value='1234567\n')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_run_with_env_overriding_config_file(self, skipper_runner_run_mock, *args):
        os.environ['VAL4'] = "val4-evaluation"
        command = ['ls', '-l']
        run_params = ['-e', ENV[0], '-e', ENV[1]] + command
        self._invoke_cli(
            defaults=config.load_defaults(),
            subcmd='run',
            subcmd_params=run_params
        )
        env = ["%s=%s" % (key, value) for key, value in CONFIG_ENV_EVALUATION.iteritems()] + ENV
        expected_fqdn_image = 'skipper-conf-build-container-image:skipper-conf-build-container-tag'
        skipper_runner_run_mock.assert_called_once_with(command, fqdn_image=expected_fqdn_image, environment=env, interactive=False)

    @mock.patch('subprocess.check_output', autospec=True, return_value='1234567\n')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_run_with_env(self, skipper_runner_run_mock, *args):
        command = ['ls', '-l']
        os.environ['VAL4'] = "val4-evaluation"
        run_params = ['-e', ENV[0], '-e', ENV[1]] + command
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='run',
            subcmd_params=run_params
        )
        expected_fqdn_image = 'build-container-image:build-container-tag'
        skipper_runner_run_mock.assert_called_once_with(command, fqdn_image=expected_fqdn_image, environment=ENV, interactive=False)

    @mock.patch('subprocess.check_output', autospec=True, return_value='1234567\n')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_run_non_interactive(self, skipper_runner_run_mock, *args):
        command = ['ls', '-l']
        run_params = ['--interactive'] + command
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='run',
            subcmd_params=run_params
        )
        expected_fqdn_image = 'build-container-image:build-container-tag'
        skipper_runner_run_mock.assert_called_once_with(command, fqdn_image=expected_fqdn_image, environment=[], interactive=True)

    @mock.patch('subprocess.check_output', autospec=True, return_value='')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_run_without_build_container_tag(self, skipper_runner_run_mock, *args):
        global_params = self.global_params[:-2]
        command = ['ls', '-l']
        run_params = command
        self._invoke_cli(
            global_params=global_params,
            subcmd='run',
            subcmd_params=run_params
        )
        expected_commands = [
            mock.call(['docker', 'build', '-t', 'build-container-image', '-f', 'Dockerfile.build-container-image', '.']),
            mock.call(command, fqdn_image='build-container-image', environment=[], interactive=False),
        ]
        skipper_runner_run_mock.assert_has_calls(expected_commands)

    @mock.patch('subprocess.check_output', autospec=True, return_value='1234567\n')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_make(self, skipper_runner_run_mock, *args):
        makefile = 'Makefile'
        target = 'all'
        make_params = ['-f', makefile, target]
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='make',
            subcmd_params=make_params
        )
        expected_command = ['make', '-f', makefile, target]
        expected_fqdn_image = 'build-container-image:build-container-tag'
        skipper_runner_run_mock.assert_called_once_with(expected_command, fqdn_image=expected_fqdn_image, environment=[], interactive=False)

    @mock.patch('__builtin__.open', create=True)
    @mock.patch('os.path.exists', autospec=True, return_value=True)
    @mock.patch('yaml.load', autospec=True, return_value=SKIPPER_CONF)
    @mock.patch('subprocess.check_output', autospec=True, return_value='1234567\n')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_make_with_defaults_from_config_file(self, skipper_runner_run_mock, *args):
        makefile = 'Makefile'
        target = 'all'
        make_params = ['-f', makefile, target]
        self._invoke_cli(
            defaults=config.load_defaults(),
            subcmd='make',
            subcmd_params=make_params
        )
        expected_command = ['make', '-f', makefile, target]
        expected_fqdn_image = 'skipper-conf-build-container-image:skipper-conf-build-container-tag'
        skipper_runner_run_mock.assert_called_once_with(expected_command, fqdn_image=expected_fqdn_image, environment=[], interactive=False)

    @mock.patch('subprocess.check_output', autospec=True, return_value='')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_make_without_build_container_tag(self, skipper_runner_run_mock, *args):
        global_params = self.global_params[:-2]
        makefile = 'Makefile'
        target = 'all'
        make_params = ['-f', makefile, target]
        self._invoke_cli(
            global_params=global_params,
            subcmd='make',
            subcmd_params=make_params
        )
        expected_commands = [
            mock.call(['docker', 'build', '-t', 'build-container-image', '-f', 'Dockerfile.build-container-image', '.']),
            mock.call(['make'] + make_params, fqdn_image='build-container-image', environment=[], interactive=False),
        ]
        skipper_runner_run_mock.assert_has_calls(expected_commands)

    @mock.patch('subprocess.check_output', autospec=True, return_value='1234567\n')
    @mock.patch('skipper.runner.run', autospec=True)
    def test_shell(self, skipper_runner_run_mock, *args):
        self._invoke_cli(
            global_params=self.global_params,
            subcmd='shell',
        )
        expected_fqdn_image = 'build-container-image:build-container-tag'
        skipper_runner_run_mock.assert_called_once_with(['bash'], fqdn_image=expected_fqdn_image, environment=[], interactive=True)

    def _invoke_cli(self, defaults=None, global_params=None, subcmd=None, subcmd_params=None):
        self.assertFalse(subcmd is None and subcmd_params is not None, 'No sub-command was provided!')

        defaults = defaults or {}

        cli_params = []
        if global_params is not None:
            cli_params += global_params

        if subcmd is not None:
            cli_params += [subcmd]

        if subcmd_params is not None:
            cli_params += subcmd_params

        return self._runner.invoke(cli.cli, cli_params, default_map=defaults, obj={}, standalone_mode=False)
