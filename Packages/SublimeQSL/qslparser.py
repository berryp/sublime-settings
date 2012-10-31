import sublime
import sublime_plugin


class QSLParseCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        #panelid = raw_input("Panel ID: ")
        panelid = 2
        print 'Running with Panel ID %s' % panelid
