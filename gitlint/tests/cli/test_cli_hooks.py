# -*- coding: utf-8 -*-

import io
import os

from click.testing import CliRunner

try:
    # python 2.x
    from StringIO import StringIO
except ImportError:
    # python 3.x
    from io import StringIO  # pylint: disable=ungrouped-imports

try:
    # python 2.x
    from mock import patch
except ImportError:
    # python 3.x
    from unittest.mock import patch  # pylint: disable=no-name-in-module, import-error

from gitlint.tests.base import BaseTestCase
from gitlint import cli
from gitlint import hooks
from gitlint import config

from gitlint.utils import DEFAULT_ENCODING


class CLIHookTests(BaseTestCase):
    USAGE_ERROR_CODE = 253
    GIT_CONTEXT_ERROR_CODE = 254
    CONFIG_ERROR_CODE = 255

    def setUp(self):
        super(CLIHookTests, self).setUp()
        self.cli = CliRunner()

        # Patch gitlint.cli.git_version() so that we don't have to patch it separately in every test
        self.git_version_path = patch('gitlint.cli.git_version')
        cli.git_version = self.git_version_path.start()
        cli.git_version.return_value = "git version 1.2.3"

    def tearDown(self):
        self.git_version_path.stop()

    @patch('gitlint.hooks.GitHookInstaller.install_commit_msg_hook')
    @patch('gitlint.hooks.git_hooks_dir', return_value=os.path.join(u"/hür", u"dur"))
    def test_install_hook(self, _, install_hook):
        """ Test for install-hook subcommand """
        result = self.cli.invoke(cli.cli, ["install-hook"])
        expected_path = os.path.join(u"/hür", u"dur", hooks.COMMIT_MSG_HOOK_DST_PATH)
        expected = u"Successfully installed gitlint commit-msg hook in {0}\n".format(expected_path)
        self.assertEqual(result.output, expected)
        self.assertEqual(result.exit_code, 0)
        expected_config = config.LintConfig()
        expected_config.target = os.path.realpath(os.getcwd())
        install_hook.assert_called_once_with(expected_config)

    @patch('gitlint.hooks.GitHookInstaller.install_commit_msg_hook')
    @patch('gitlint.hooks.git_hooks_dir', return_value=os.path.join(u"/hür", u"dur"))
    def test_install_hook_target(self, _, install_hook):
        """  Test for install-hook subcommand with a specific --target option specified """
        # Specified target
        result = self.cli.invoke(cli.cli, ["--target", self.SAMPLES_DIR, "install-hook"])
        expected_path = os.path.join(u"/hür", u"dur", hooks.COMMIT_MSG_HOOK_DST_PATH)
        expected = "Successfully installed gitlint commit-msg hook in %s\n" % expected_path
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, expected)

        expected_config = config.LintConfig()
        expected_config.target = self.SAMPLES_DIR
        install_hook.assert_called_once_with(expected_config)

    @patch('gitlint.hooks.GitHookInstaller.install_commit_msg_hook', side_effect=hooks.GitHookInstallerError(u"tëst"))
    def test_install_hook_negative(self, install_hook):
        """ Negative test for install-hook subcommand """
        result = self.cli.invoke(cli.cli, ["install-hook"])
        self.assertEqual(result.exit_code, self.GIT_CONTEXT_ERROR_CODE)
        self.assertEqual(result.output, u"tëst\n")
        expected_config = config.LintConfig()
        expected_config.target = os.path.realpath(os.getcwd())
        install_hook.assert_called_once_with(expected_config)

    @patch('gitlint.hooks.GitHookInstaller.uninstall_commit_msg_hook')
    @patch('gitlint.hooks.git_hooks_dir', return_value=os.path.join(u"/hür", u"dur"))
    def test_uninstall_hook(self, _, uninstall_hook):
        """ Test for uninstall-hook subcommand """
        result = self.cli.invoke(cli.cli, ["uninstall-hook"])
        expected_path = os.path.join(u"/hür", u"dur", hooks.COMMIT_MSG_HOOK_DST_PATH)
        expected = u"Successfully uninstalled gitlint commit-msg hook from {0}\n".format(expected_path)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, expected)
        expected_config = config.LintConfig()
        expected_config.target = os.path.realpath(os.getcwd())
        uninstall_hook.assert_called_once_with(expected_config)

    @patch('gitlint.hooks.GitHookInstaller.uninstall_commit_msg_hook', side_effect=hooks.GitHookInstallerError(u"tëst"))
    def test_uninstall_hook_negative(self, uninstall_hook):
        """ Negative test for uninstall-hook subcommand """
        result = self.cli.invoke(cli.cli, ["uninstall-hook"])
        self.assertEqual(result.exit_code, self.GIT_CONTEXT_ERROR_CODE)
        self.assertEqual(result.output, u"tëst\n")
        expected_config = config.LintConfig()
        expected_config.target = os.path.realpath(os.getcwd())
        uninstall_hook.assert_called_once_with(expected_config)

    def test_hook_no_tty(self):
        """ Test for run-hook subcommand.
            When no TTY is available (like is the case for this test), the hook will abort after the first check.
        """

        # No need to patch git as we're passing a msg-filename to run-hook, so no git calls are made.
        # Note that this is the case when passing --staged as well, but that's tested as part of the integration tests
        # (=end-to-end scenario).

        # Ideally we'd be able to assert that run-hook internally calls the lint cli command, but couldn't make
        # that work. Have tried many different variatons of mocking and patching without avail. For now, we just
        # check the output which indirectly proves the same thing.

        with self.tempdir() as tmpdir:
            msg_filename = os.path.join(tmpdir, u"hür")
            with io.open(msg_filename, 'w', encoding=DEFAULT_ENCODING) as f:
                f.write(u"WIP: tïtle\n")

            with patch('gitlint.display.stderr', new=StringIO()) as stderr:
                result = self.cli.invoke(cli.cli, ["--msg-filename", msg_filename, "run-hook"])
                self.assertEqual(result.output, self.get_expected('cli/test_cli_hooks/test_hook_no_tty_1_stdout'))
                self.assertEqual(stderr.getvalue(), self.get_expected("cli/test_cli_hooks/test_hook_no_tty_1_stderr"))

                # exit code is 1 because aborted (no stdin available)
                self.assertEqual(result.exit_code, 1)

    @patch('gitlint.cli.shell')
    def test_hook_edit(self, shell):
        """ Test for run-hook subcommand, answering 'e(dit)' after commit-hook """

        set_editors = [None, u"myeditor"]
        expected_editors = [u"vim -n", u"myeditor"]
        commit_messages = [u"WIP: höok edit 1", u"WIP: höok edit 2"]

        for i in range(0, len(set_editors)):
            if set_editors[i]:
                os.environ['EDITOR'] = set_editors[i]

            with self.patch_input(['e', 'e', 'n']):
                with self.tempdir() as tmpdir:
                    msg_filename = os.path.realpath(os.path.join(tmpdir, u"hür"))
                    with io.open(msg_filename, 'w', encoding=DEFAULT_ENCODING) as f:
                        f.write(commit_messages[i] + "\n")

                    with patch('gitlint.display.stderr', new=StringIO()) as stderr:
                        result = self.cli.invoke(cli.cli, ["--msg-filename", msg_filename, "run-hook"])
                        self.assertEqual(result.output, self.get_expected('cli/test_cli_hooks/test_hook_edit_1_stdout',
                                                                          {"commit_msg": commit_messages[i]}))
                        expected = self.get_expected("cli/test_cli_hooks/test_hook_edit_1_stderr",
                                                     {"commit_msg": commit_messages[i]})
                        self.assertEqual(stderr.getvalue(), expected)

                        # exit code = number of violations
                        self.assertEqual(result.exit_code, 2)

                        shell.assert_called_with(expected_editors[i] + " " + msg_filename)
                        self.assert_log_contains(u"DEBUG: gitlint.cli run-hook: editing commit message")
                        self.assert_log_contains(u"DEBUG: gitlint.cli run-hook: {0} {1}".format(expected_editors[i],
                                                                                                msg_filename))

    def test_hook_no(self):
        """ Test for run-hook subcommand, answering 'n(o)' after commit-hook """

        with self.patch_input(['n']):
            with self.tempdir() as tmpdir:
                msg_filename = os.path.join(tmpdir, u"hür")
                with io.open(msg_filename, 'w', encoding=DEFAULT_ENCODING) as f:
                    f.write(u"WIP: höok no\n")

                with patch('gitlint.display.stderr', new=StringIO()) as stderr:
                    result = self.cli.invoke(cli.cli, ["--msg-filename", msg_filename, "run-hook"])
                    self.assertEqual(result.output, self.get_expected('cli/test_cli_hooks/test_hook_no_1_stdout'))
                    self.assertEqual(stderr.getvalue(), self.get_expected("cli/test_cli_hooks/test_hook_no_1_stderr"))

                    # We decided not to keep the commit message: hook returns number of violations (>0)
                    # This will cause git to abort the commit
                    self.assertEqual(result.exit_code, 2)
                    self.assert_log_contains("DEBUG: gitlint.cli run-hook: commit message declined")

    def test_hook_yes(self):
        """ Test for run-hook subcommand, answering 'y(es)' after commit-hook """
        with self.patch_input(['y']):
            with self.tempdir() as tmpdir:
                msg_filename = os.path.join(tmpdir, u"hür")
                with io.open(msg_filename, 'w', encoding=DEFAULT_ENCODING) as f:
                    f.write(u"WIP: höok yes\n")

                with patch('gitlint.display.stderr', new=StringIO()) as stderr:
                    result = self.cli.invoke(cli.cli, ["--msg-filename", msg_filename, "run-hook"])
                    self.assertEqual(result.output, self.get_expected('cli/test_cli_hooks/test_hook_yes_1_stdout'))
                    self.assertEqual(stderr.getvalue(), self.get_expected("cli/test_cli_hooks/test_hook_yes_1_stderr"))

                    # Exit code is 0 because we decide to keep the commit message
                    # This will cause git to keep the commit
                    self.assertEqual(result.exit_code, 0)
                    self.assert_log_contains("DEBUG: gitlint.cli run-hook: commit message accepted")

    @patch('gitlint.cli.get_stdin_data', return_value=u"WIP: Test hook stdin tïtle\n")
    def test_hook_stdin_violations(self, _):
        """ Test for passing stdin data to run-hook, expecting some violations. Equivalent of:
            $ echo "WIP: Test hook stdin tïtle" | gitlint run-hook
        """

        with patch('gitlint.display.stderr', new=StringIO()) as stderr:
            result = self.cli.invoke(cli.cli, ["run-hook"])
            expected_stderr = self.get_expected('cli/test_cli_hooks/test_hook_stdin_violations_1_stderr')
            self.assertEqual(stderr.getvalue(), expected_stderr)
            self.assertEqual(result.output, self.get_expected('cli/test_cli_hooks/test_hook_stdin_violations_1_stdout'))
            # Hook will auto-abort because we're using stdin. Abort = exit code 1
            self.assertEqual(result.exit_code, 1)

    @patch('gitlint.cli.get_stdin_data', return_value=u"Test tïtle\n\nTest bödy that is long enough")
    def test_hook_stdin_no_violations(self, _):
        """ Test for passing stdin data to run-hook, expecting *NO* violations, Equivalent of:
            $ echo -e "Test tïtle\n\nTest bödy that is long enough" | gitlint run-hook
        """

        with patch('gitlint.display.stderr', new=StringIO()) as stderr:
            result = self.cli.invoke(cli.cli, ["run-hook"])
            self.assertEqual(stderr.getvalue(), "")  # no errors = no stderr output
            expected_stdout = self.get_expected('cli/test_cli_hooks/test_hook_stdin_no_violations_1_stdout')
            self.assertEqual(result.output, expected_stdout)
            self.assertEqual(result.exit_code, 0)

    @patch('gitlint.cli.get_stdin_data', return_value=u"WIP: Test hook config tïtle\n")
    def test_hook_config(self, _):
        """ Test that gitlint still respects config when running run-hook, equivalent of:
            $ echo "WIP: Test hook config tïtle" | gitlint -c title-max-length.line-length=5 --ignore B6 run-hook
        """

        with patch('gitlint.display.stderr', new=StringIO()) as stderr:
            result = self.cli.invoke(cli.cli, ["-c", "title-max-length.line-length=5", "--ignore", "B6", "run-hook"])
            self.assertEqual(stderr.getvalue(), self.get_expected('cli/test_cli_hooks/test_hook_config_1_stderr'))
            self.assertEqual(result.output, self.get_expected('cli/test_cli_hooks/test_hook_config_1_stdout'))
            # Hook will auto-abort because we're using stdin. Abort = exit code 1
            self.assertEqual(result.exit_code, 1)

    @patch('gitlint.cli.get_stdin_data', return_value=False)
    @patch('gitlint.git.sh')
    def test_hook_local_commit(self, sh, _):
        """ Test running the hook on the last commit-msg from the local repo, equivalent of:
            $ gitlint run-hook
            and then choosing 'e'
        """
        sh.git.side_effect = [
            "6f29bf81a8322a04071bb794666e48c443a90360",
            u"test åuthor\x00test-email@föo.com\x002016-12-03 15:28:15 +0100\x00åbc\n"
            u"WIP: commït-title\n\ncommït-body",
            u"#",  # git config --get core.commentchar
            u"commit-1-branch-1\ncommit-1-branch-2\n",
            u"file1.txt\npåth/to/file2.txt\n"
        ]

        with self.patch_input(['e']):
            with patch('gitlint.display.stderr', new=StringIO()) as stderr:
                result = self.cli.invoke(cli.cli, ["run-hook"])
                expected = self.get_expected('cli/test_cli_hooks/test_hook_local_commit_1_stderr')
                self.assertEqual(stderr.getvalue(), expected)
                self.assertEqual(result.output, self.get_expected('cli/test_cli_hooks/test_hook_local_commit_1_stdout'))
                # If we can't edit the message, run-hook follows regular gitlint behavior and exit code = # violations
                self.assertEqual(result.exit_code, 2)
