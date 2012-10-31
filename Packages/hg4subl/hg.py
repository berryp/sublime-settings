import os
import re
import sys
import sublime
import sublime_plugin
import threading
import subprocess
import functools
def main_thread(callback, *args, **kwargs):
    # sublime.set_timeout gets used to send things onto the main thread
    # most sublime.[something] calls need to be on the main thread
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)

def open_url(url):
    sublime.active_window().run_command('open_url', {"url": url})

def get_hg(view=None):
    if view == None:
        view = sublime.active_window().active_view()
    return view.settings().get("hg4subl_hg", "hg")

def hg_root(directory):
    while directory:
        if os.path.exists(os.path.join(directory, '.hg')):
            return directory
        parent = os.path.realpath(os.path.join(directory, os.path.pardir))
        if parent == directory:
            # /.. == /
            return False
        directory = parent
    return False

def _make_text_safeish(text, fallback_encoding):
    # The unicode decode here is because sublime converts to unicode inside insert in such a way
    # that unknown characters will cause errors, which is distinctly non-ideal...
    # and there's no way to tell what's coming out of hg in output. So...
    try:
        unitext = text.decode('utf-8')
    except UnicodeDecodeError:
        unitext = text.decode(fallback_encoding)
    return unitext

class CommandThread(threading.Thread):
    def __init__(self, command, on_done, working_dir = "", fallback_encoding = ""):
        threading.Thread.__init__(self)
        self.command = command
        self.on_done = on_done
        self.working_dir = working_dir
        self.fallback_encoding = fallback_encoding

    def run(self):
        try:
            # Per http://bugs.python.org/issue8557 shell=True is required to get
            # $PATH on Windows. Yay portable code.
            shell = os.name == 'nt'
            if self.working_dir != "":
                os.chdir(self.working_dir)
            output = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=shell).communicate()[0]
            # if sublime's python gets bumped to 2.7 we can just do:
            # output = subprocess.check_output(self.command)
            main_thread(self.on_done, _make_text_safeish(output, self.fallback_encoding))
        except subprocess.CalledProcessError, e:
            main_thread(self.on_done, e.returncode)

class HgCommand:
    def run_command(self, command, callback = None, show_status = True, filter_empty_args = True, **kwargs):
        if filter_empty_args:
            command = [arg for arg in command if arg]
        if 'working_dir' not in kwargs:
            kwargs['working_dir'] = self.get_file_location()
        if 'fallback_encoding' not in kwargs and self.view.settings().get('fallback_encoding'):
            kwargs['fallback_encoding'] = self.view.settings().get('fallback_encoding').rpartition('(')[2].rpartition(')')[0]

        thread = CommandThread(command, callback or self.generic_done, **kwargs)
        thread.start()

        if show_status:
            message = kwargs.get('status_message', False) or ' '.join(command)
            sublime.status_message(message)

    def generic_done(self, result):
        if not result.strip():
            return
        self.panel(result)

    def _output_to_view(self, output_file, output, clear = False, syntax = "Packages/Diff/Diff.tmLanguage"):
        output_file.set_syntax_file(syntax)
        edit = output_file.begin_edit()
        if clear:
            region = sublime.Region(0, self.output_view.size())
            output_file.erase(edit, region)
        output_file.insert(edit, 0, output)
        output_file.end_edit(edit)

    def scratch(self, output, title = False, **kwargs):
        scratch_file = self.window.new_file()
        if title:
            scratch_file.set_name(title)
        scratch_file.set_scratch(True)
        self._output_to_view(scratch_file, output, **kwargs)
        scratch_file.set_read_only(True)
        return scratch_file

    def panel(self, output, **kwargs):
        if not hasattr(self, 'output_view'):
            self.output_view = self.window.get_output_panel("hg")
        self.output_view.set_read_only(False)
        self._output_to_view(self.output_view, output, clear = True, **kwargs)
        self.output_view.set_read_only(True)
        self.window.run_command("show_panel", {"panel": "output.hg"})

    def get_file_name(self):
        return os.path.basename(self.view.file_name())
    def get_file_location(self):
        return os.path.dirname(self.view.file_name())

class HgTextCommand(HgCommand, sublime_plugin.TextCommand):
    def __init__(self, view):
        sublime_plugin.TextCommand.__init__(self, view)
        if self.view.window():
            self.window = self.view.window()
        elif sublime.active_window():
            self.window = sublime.active_window()


    def is_enabled(self):
        # First, is this actually a file on the file system?
        if self.view.file_name() and len(self.view.file_name()) > 0:
            return hg_root(self.get_file_location())

    def get_window(self):
        return self.view.window() or sublime.active_window()

class HgWindowCommand(HgCommand, sublime_plugin.WindowCommand):
    def __init__(self, window):
        sublime_plugin.WindowCommand.__init__(self, window)
        self.view = self.window.active_view()

class HgAnnotateCommand(HgTextCommand):
    def run(self, edit):
        command = [get_hg(self.view), 'annotate', '-aufdqln']

        selection = self.view.sel()[0] # todo: multi-select support?
        if not selection.empty():
            # just the lines we have a selection on
            begin_line, begin_column = self.view.rowcol(selection.begin())
            end_line, end_column = self.view.rowcol(selection.end())
            lines = str(begin_line) + ',' + str(end_line)
            command.extend(('-L', lines))

        command.append(self.get_file_name())
        self.run_command(command, functools.partial(self.scratch, title = "Hg annotate"))

class HgAnnotateSideCommand(HgWindowCommand):
    def run(self, paths):
        self.run_command([get_hg(self.view), 'annotate', '-aufdqln'] + paths, functools.partial(self.scratch, title = "Hg annotate"))

class HgCustomCommand(HgTextCommand):
    def run(self, edit):
        self.get_window().show_input_panel("Hg", "",
            self.on_done, None, None)

    def on_done(self, command):
        c = command.strip()
        if len(c) == 0:
            sublime.status_message("No command provided")
            return
        c = c.split(" ")
        c.insert(0, get_hg(self.view))
        self.run_command(c, self.cmd_done)

    def cmd_done(self, result):
        self.scratch(result, title = "Hg Custom Command")

class HgPushCommand(HgTextCommand):
    def run(self, edit):
        command = [get_hg(self.view), 'push']
        self.run_command(command)

class HgPullCommand(HgTextCommand):
    def run(self, edit):
        command = [get_hg(self.view), 'pull', '--update', 'default']
        self.run_command(command)

class HgFetchCommand(HgTextCommand):
    def run(self, edit):
        command = [get_hg(self.view), 'fetch','default']
        self.run_command(command)

class HgLogCommand(HgTextCommand):
    def run(self, edit):
        self.run_command([get_hg(self.view), 'log', '-v','--', self.get_file_name()], self.log_done)

    def log_done(self, result):
        self.results = [r.strip().split("\n") for r in result.strip().split('\n\n')]
        self.get_window().show_quick_panel(self.results, self.panel_done)

    def panel_done(self, picked):
        if picked == -1:
            return
        if 0 > picked > len(self.results):
            return
        item = self.results[picked]
        ref = re.search("\w\d+(?=:)", item[0]).group(0)
        # I'm not certain I should have the file name here; it restricts the details to just
        # the current file. Depends on what the user expects... which I'm not sure of.
        self.run_command([get_hg(self.view), 'log', '-v', '-p', '-r', ref, '--', self.get_file_name()], self.details_done)

    def details_done(self, result):
        self.scratch(result, title = "Hg Commit Details")

class HgLogAllCommand(HgLogCommand):
    def get_file_name(self):
        return ''

class HgDiffCommand(HgTextCommand):
    def run(self, edit):
        self.run_command([get_hg(self.view), 'diff', self.get_file_name()], functools.partial(self.scratch, title = "Hg Diff"))

class HgDiffAllCommand(HgDiffCommand):
    def get_file_name(self):
        return ''

class HgDiffSideCommand(HgWindowCommand):
    def run(self, paths):
        self.run_command([get_hg(self.view), 'diff'] + paths, functools.partial(self.scratch, title = "Hg Diff"))

class HgCommitCommand(HgTextCommand):
    def run(self, edit):
        self.get_window().show_input_panel("Message", "", self.on_input, None, None)

    def on_input(self, message):
        if message.strip() == "":
            # Okay, technically an empty commit message is allowed, but I don't want to encourage that sort of thing
            sublime.error_message("No commit message provided")
            return
        self.run_command([get_hg(self.view), 'commit', '-m', message])

class HgStatusCommand(HgTextCommand):
    def run(self, edit):
        self.run_command([get_hg(self.view), 'status',], self.status_done)
    def status_done(self, result):
        self.results = filter(self.status_filter, result.rstrip().split('\n'))
        self.get_window().show_quick_panel(self.results, self.panel_done, sublime.MONOSPACE_FONT)
    def status_filter(self, item):
        # for this class we don't actually care
        return True
    def panel_done(self, picked):
        if picked == -1:
            return
        if 0 > picked > len(self.results):
            return
        picked_file = self.results[picked]
        # first 2 characters are status codes
        picked_file = picked_file[2:]
        self.panel_followup(picked_file)
    def panel_followup(self, picked_file):
        # split out solely so I can override it for laughs
        self.run_command([get_hg(self.view), 'diff', picked_file], self.diff_done, working_dir = hg_root(self.get_file_location()))

    def diff_done(self, result):
        if not result.strip():
            return
        self.scratch(result, title = "Hg Diff")

class HgAddChoiceCommand(HgStatusCommand):
    def status_filter(self, item):
        return not item[1].isspace()
    def panel_followup(self, picked_file):
        self.run_command([get_hg(self.view), 'add', picked_file], working_dir = hg_root(self.get_file_location()))

class HgAdd(HgTextCommand):
    def run(self, edit):
        self.run_command([get_hg(self.view), 'add', self.get_file_name()])

class HgAddSide(HgWindowCommand):
    def run(self, paths):
        self.run_command([get_hg(self.view), 'add'] + paths)

class HgRemove(HgTextCommand):
    def run(self, edit):
        self.run_command([get_hg(self.view), 'remove', '-f', self.get_file_name()])

class HgRemoveSide(HgWindowCommand):
    def run(self, paths):
        self.run_command([get_hg(self.view), 'remove', '-f'] + paths)

class HgShelveCommand(HgTextCommand):
    def run(self, edit):
        self.run_command([get_hg(self.view), 'shelve'])

class HgUnshelveCommand(HgTextCommand):
    def run(self, edit):
        self.run_command([get_hg(self.view), 'unshelve'])

class hgBranchCommand(HgTextCommand):
    def run(self, edit):
        self.run_command([get_hg(self.view), 'branches'], self.branch_done)
    def branch_done(self, result):
        self.results = result.rstrip().split('\n')
        self.get_window().show_quick_panel(self.results, self.panel_done, sublime.MONOSPACE_FONT)
    def panel_done(self, picked):
        if picked == -1:
            return
        if 0 > picked > len(self.results):
            return
        picked_branch = self.results[picked]
        if picked_branch.startswith("*"):
            return
        picked_branch = picked_branch.split()[0]
        picked_branch = picked_branch.strip()

        self.run_command([get_hg(self.view), 'update', picked_branch])

#-----------------------------------------------------------#
# For self updating the plugin. Future I will implement
# auto download and updating.
#-----------------------------------------------------------#

class hg4sublUpdate(HgTextCommand):
    def run(self,edit):
        package_names = os.listdir(sublime.packages_path())
        for path in package_names:
            if path == 'hg4subl':
                hg_update_command = []
                hg4subl_folder = os.path.join(sublime.packages_path(), path)
                #self.run_command(['cd', hg4subl_folder,self.pull_update])
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                args = [get_hg(self.view),"pull", "--update", "default"]
                proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, startupinfo=startupinfo, cwd=hg4subl_folder)
                output = proc.stdout.read()
                returncode = proc.wait()
                if returncode != 0:
                    error = NonCleanExitError(returncode)
                    error.output = output
                    raise error
                self.panel(output)
