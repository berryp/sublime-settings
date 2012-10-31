import httplib
import json
import os
import sublime
import sublime_plugin


# class Questionnaire(object):

#     def __init__(name, settings):
#         self.settings = settings
#         self.name = name
#         self.path = '/questionnaires/%s/' % self.name

#         conn = httplib.HTTPConnection(self.settings.get('service_url'), 80)
#         conn.request('GET', self.path)
#         response = conn.getresponse()
#         data = response.read()

#         document = json.loads(data)
#         self.archived = document['body']['archived']
#         self.active_version = document['body']['active_version'].split('/')[-2]
#         self.panel = document['body']['panel'].split('/')[-2]


def request(host, path, port=80, method='GET', data=None):
    conn = httplib.HTTPConnection(host, port)
    conn.request(method, path.format(**vars()))
    response = conn.getresponse()
    data = response.read()
    return response.status, response.reason, data


class QuestionnaireManager():

    def get_versions(self, questionnaire_path):
        path = '/{questionnaire_path}versions/'.format(**vars())
        status, reason, data = request(self.settings.get('service_url'), path)

        document = json.loads(data)

        versions = [int(e.split('/')[-2]) for e in document['entities']]

        # Reverse the list so the most resent is at the top when presented
        # to the user.
        return list(reversed(versions))

    def list_questionnaires(self, term):
        path = '/questionnaires/like/{term}/'.format(**vars())
        status, reason, data = request(self.settings.get('service_url'), path)

        document = json.loads(data)

        self.questionnaires = []
        for entity in document['entities']:
            parts = entity.replace('http://', '').split('/')
            path = '/'.join(parts[1:])
            questionnaire = {
                'name': parts[-2],
                'path': path,
                'versions': self.get_versions(path),
            }

            self.questionnaires.append(questionnaire)

        self.window.show_quick_panel([q['name'] for q in self.questionnaires],
                self.on_questionnaire_select_done)

    def open_questionnaire(self):
        path = '/{questionnaire_path}versions/{version}/'.format(
            questionnaire_path=self.questionnaire['path'],
            version=self.version)
        status, reason, data = request(self.settings.get('service_url'), path)

        file_path = os.path.join(self.settings.get('document_path'),
                self.questionnaire['name'] + '.qsl')

        with open(file_path, 'w') as file:
            file.write(data)

        self.window.open_file(file_path)


class OpenQuestionnaireCommand(sublime_plugin.WindowCommand,
        QuestionnaireManager):

    def run(self):
        self.settings = sublime.load_settings('%s.sublime-settings' % __name__)

        # Show the user input window for capturing the search term.
        self.window.show_input_panel('Search term', '',
            self.on_input_done, self.on_input_change, self.on_input_cancel)

    def on_input_done(self, input):
        self.list_questionnaires(input)

    def on_input_change(self, input):
        pass

    def on_input_cancel(self):
        pass

    def on_questionnaire_select_done(self, picked):
        self.questionnaire = self.questionnaires[picked]

        versions = ['Version %s' % v for v in self.questionnaire['versions']]
        self.window.show_quick_panel(versions,
                self.on_version_select_done)

    def on_version_select_done(self, picked):
        self.version = self.questionnaire['versions'][picked]
        self.open_questionnaire()
