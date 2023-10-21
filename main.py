""" Main Module """
import chardet
import logging
import os
import subprocess
import mimetypes
import gi
gi.require_version('Gtk', '3.0')
# pylint: disable=import-error
from gi.repository import Gio, Gtk
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.item.ExtensionSmallResultItem import ExtensionSmallResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.OpenAction import OpenAction
from ulauncher.api.shared.action.RunScriptAction import RunScriptAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction

LOGGING = logging.getLogger(__name__)

FILE_SEARCH_ALL = 'ALL'

FILE_SEARCH_DIRECTORY = 'DIR'

FILE_SEARCH_FILE = 'FILE'


class FileSearchExtension(Extension):
    """ Main Extension Class  """

    def __init__(self):
        """ Initializes the extension """
        super(FileSearchExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())

    def search(self, query, file_type=None):
        """ Try with the default fd or the previously successful command """
        bin_name = 'fd'
        try:
            subprocess.check_call([bin_name])
        except OSError:
            bin_name = "fdfind" if bin_name == "fd" else "fd"

        """ Searches for Files using fd command """
        cmd = [
            'timeout', '5s', 'ionice', '-c', '3', bin_name, '--threads', '1',
            #'--hidden'
        ]
        
        # 是否显示隐藏的文件或目录
        if self.preferences['show_hidden'] == 'true':
            cmd.append('--hidden')
        
        if file_type == FILE_SEARCH_FILE:
            cmd.append('-t')
            cmd.append('f')
        elif file_type == FILE_SEARCH_DIRECTORY:
            cmd.append('-t')
            cmd.append('d')
        
        # 多个基目录
        for path in self.preferences['base_dir'].split(';'):
            cmd.append('--search-path')
            cmd.append(path)
        #cmd.append(self.preferences['base_dir'])
        #cmd.append('-Fa')
        
        # 多个关键词，就一层层筛选
        # 遍历关键词
        for index, kw in enumerate(query.split(' ')):
            if index != 0:
                cmd.append('| grep')
            cmd.append(kw)
            
            
        # 把生成的命令输出到日志
        self.logger.info(' '.join(cmd))
        
        # 执行搜索的命令
        # subprocess.run 如果命令是数组，就不能使用管道符。所以我把命令转称字符串了，同时Shell=True打开
        process = subprocess.run(' '.join(cmd), stdout=subprocess.PIPE, encoding='utf-8',shell=True)
        out = process.stdout
        if process.returncode != 0:
            self.logger.error(process.returncode)
        
        files = out.split('\n')
        files = list([_f for _f in files if _f])  # remove empty lines

        result = []
        #get folder icon outside loop, so it only happens once
        file = Gio.File.new_for_path("/")
        folder_info = file.query_info('standard::icon', 0, Gio.Cancellable())
        folder_icon = folder_info.get_icon().get_names()[0]
        icon_theme = Gtk.IconTheme.get_default()
        icon_folder = icon_theme.lookup_icon(folder_icon, 128, 0)
        if icon_folder:
            folder_icon = icon_folder.get_filename()
        else:
            folder_icon = "images/folder.png"

        # pylint: disable=C0103
        for f in files[:15]:
            filename = os.path.splitext(f)
            if os.path.isdir(f):
                icon = folder_icon
            else:
                #type_, encoding = mimetypes.guess_type(f.decode('utf-8'))
                type_, encoding = mimetypes.guess_type(f)

                if type_:
                    file_icon = Gio.content_type_get_icon(type_)
                    file_info = icon_theme.choose_icon(file_icon.get_names(), 128, 0)
                    if file_info:
                        icon = file_info.get_filename()
                    else:
                        icon = "images/file.png"
                else:
                    icon = "images/file.png"

            result.append({'path': f, 'name': f, 'icon': icon})

        return result

    def get_open_in_terminal_script(self, path):
        """ Returns the script based on the type of terminal """
        terminal_emulator = self.preferences['terminal_emulator']

        # some terminals might work differently. This is already prepared for that.
        if terminal_emulator in [
                'gnome-terminal', 'terminator', 'tilix', 'xfce-terminal'
        ]:
            return RunScriptAction(terminal_emulator,
                                   ['--working-directory', path])

        return DoNothingAction()


class KeywordQueryEventListener(EventListener):
    """ Listener that handles the user input """

    # pylint: disable=unused-argument,no-self-use
    def on_event(self, event, extension):
        """ Handles the event """
        items = []

        query = event.get_argument()

        if not query or len(query) < 2:
            return RenderResultListAction([
                ExtensionResultItem(
                    icon='images/icon.png',
                    name='Keep typing your search criteria ...',
                    on_enter=DoNothingAction())
            ])

        keyword = event.get_keyword()
        # Find the keyword id using the keyword (since the keyword can be changed by users)
        for kw_id, kw in list(extension.preferences.items()):
            if kw == keyword:
                keyword_id = kw_id

        file_type = FILE_SEARCH_ALL
        if keyword_id == "ff_kw":
            file_type = FILE_SEARCH_FILE
        elif keyword_id == "fd_kw":
            file_type = FILE_SEARCH_DIRECTORY
        
        results = extension.search(query.strip(), file_type)

        if not results:
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='No Results found matching %s' %
                                    query,
                                    on_enter=HideWindowAction())
            ])

        items = []
        for result in results[:15]:
            items.append(
                ExtensionSmallResultItem(
                    icon=result['icon'],
                    #name=result['path'].decode("utf-8"),
                    name=result['path'],
                    #on_enter=OpenAction(result['path'].decode("utf-8")),
                    on_enter=OpenAction(result['path']),
                    on_alt_enter=extension.get_open_in_terminal_script(
                        #result['path'].decode("utf-8"))))
                        result['path'])))

        return RenderResultListAction(items)


if __name__ == '__main__':
    FileSearchExtension().run()
