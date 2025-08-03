
import enum
from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import (QApplication, QWidget,QPushButton,QMessageBox,QDesktopWidget,QMainWindow,
                             QVBoxLayout,QHBoxLayout,QGridLayout,QTextEdit,QLabel,QRadioButton,QCheckBox,
                             QLineEdit,QGroupBox,QSplitter,QFileDialog, QScrollArea, QListWidget)
try:
    from .base import Plugin_Base
    from .protocol import Plugin as ProtocolPlugin
    from Combobox import ComboBox
    from i18n import _
    import utils, parameters
    from conn.base import ConnectionStatus
    from widgets import statusBar, PlainTextEdit
    from plugins.graph_widgets import graphWidgets
except ImportError:
    from COMTool import utils, parameters
    from COMTool.i18n import _
    from COMTool.Combobox import ComboBox
    from COMTool.conn.base import  ConnectionStatus
    from COMTool.widgets import statusBar
    from COMTool.plugins.graph_widgets import graphWidgets
    from COMTool.plugins.base import Plugin_Base


class Plugin(ProtocolPlugin):
    '''
        call sequence:
            set vars like hintSignal, hintSignal
            onInit
            onWidget
            onUiInitDone
            onActive
                send
                onReceived
            onDel
    '''
    # vars set by caller
    isConnected = lambda o: False
    send = lambda o,x,y:None          # send(data_bytes=None, file_path=None, callback=lambda ok,msg:None), can call in UI thread directly
    ctrlConn = lambda o,k,v:None      # call ctrl func of connection
    hintSignal = None               # hintSignal.emit(type(error, warning, info), title, msg)
    reloadWindowSignal = None       # reloadWindowSignal.emit(title, msg, callback(close or not)), reload window to load new configs
    configGlobal = {}
    # other vars
    connParent = "main"      # parent id
    connChilds = []          # children ids
    id = "graph"
    name = _("Graph")

    enabled = False          # user enabled this plugin
    active  = False          # using this plugin

    help = '{}<br><br>{}<br><h2>Python</h2><br><pre>{}</pre><p><p>{}<br>{}</p><p>{}</p></p><br><h2>C/C++</h2><br><pre>{}</pre>'.format(
        _("Double click graph item to add a graph widget"), _("line chart plot protocol:"),
'''
from COMTool.plugins import graph_protocol

# For ASCII protocol("binary protocol" not checked)
frame = graph_protocol.plot_pack(name, x, y, binary = False)

# For binary protocol("binary protocol" checked)
frame = graph_protocol.plot_pack(name, x, y, header= b'\\xAA\\xCC\\xEE\\xBB')
''',
        _("Full demo see:"),
        '<a href="https://github.com/Neutree/COMTool/tree/master/tool/send_curve_demo.py">https://github.com/Neutree/COMTool/tree/master/tool/send_curve_demo.py</a>',
        _("Install comtool by <code>pip install comtool</code> first"),
'''

/*******'''+ _('For ASCII protocol("binary protocol" not checked)') + ''' *******/
/**
 * $[line name],[x],[y]&lt;,checksum&gt;\\n
 *   ''' + _('"$" means start of frame, end with "\\n" "," means separator') + ''',
 *   ''' + _('checksum is optional, checksum is sum of all bytes in frame except ",checksum".') + '''
 *   ''' + _('[x] is optional') + '''
 *   ''' + _('e.g.') + '''
 *     "$roll,2.0\\n"
 *     "$roll,1.0,2.0\\n"
 *     "$pitch,1.0,2.0\\r\\n"
 *     "$pitch,1.0,2.0,179\\n" (179 = sum(b"$pitch,1.0,2.0") % 256)
 */
int plot_pack_ascii(uint8_t *buff, int buff_len, const char *name, float x, float y)
{
    snprintf(buff, buff_len, "$%s,%f,%f", name, x, y);
    //snprintf(buff, buff_len, "$%s,%f", name, y);
    // add checksum
    int sum = 0;
    for (int i = 0; i &lt; strlen(buff); i++)
    {
        sum += buff[i];
    }
    snprintf(buff + strlen(buff), buff_len - strlen(buff), ",%d\\n", sum & 0xFF);
    return strlen(buff);
}

uint8_t buff[64];
double x = 1.0, y = 2.0;
int len = plot_pack_ascii(buff, sizeof(buff), "data1", x, y);
send_bytes(buff, len);
/*****************************************************************/


/******* ''' + _('For binary protocol("binary protocol" checked)') + ''' *******/
int plot_pack_binary(uint8_t *buff, int buff_len,
               uint8_t *header, int header_len,
               char *name,
               double x, double y)
{
    uint8_t len = (uint8_t)strlen(name);
    int actual_len = header_len + 1 + len + 8 + 8 + 1;
    assert(actual_len &lt;= buff_len);

    memcpy(buff, header, header_len);
    buff[header_len] = len;
    memcpy(buff + 5, name, len);
    memcpy(buff + 5 + len, &x, 8);
    memcpy(buff + 5 + len + 8, &y, 8);
    int sum = 0;
    for (int i = 0; i &lt; header_len+1+len+8+8; i++)
    {
        sum += buff[i];
    }
    buff[header_len+1+len+8+8] = (uint8_t)(sum & 0xff);
    return header_len+1+len+8+8+1;
}

uint8_t buff[64];
uint8_t header[] = {0xAA, 0xCC, 0xEE, 0xBB};
double x = 1.0, y = 2.0;
int len = plot_pack_binary(buff, sizeof(buff), header, sizeof(header), "data1", x, y);
send_bytes(buff, len);
/*****************************************************************/


''')

    def __init__(self):
        super().__init__()
        if not self.id:
            raise ValueError(f"var id of Plugin {self} should be set")

    def onInit(self, config):
        '''
            init params, DO NOT take too long time in this func
            @config dict type, just change this var's content,
                               when program exit, this config will be auto save to config file
        '''
        super().onInit(config)
        default = {
            "version": 1,
            "graphWidgets": [
                # {
                #     "id": "plot",
                #     "config": {}
                # }
            ]
        }
        for k in default:
            if not k in self.config:
                self.config[k] = default[k]
        self.widgets = []

    def onDel(self):
        pass

    def onWidgetMain(self, parent):
        '''
            main widget, just return a QWidget object
        '''
        widget = QWidget()
        widget.setProperty("class", "scrollbar2")
        layout = QVBoxLayout(widget)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        layout.addWidget(scroll)
        widget2 = QWidget()
        scroll.setWidget(widget2)
        self.widgetsLayout = QVBoxLayout()
        widget2.setLayout(self.widgetsLayout)
        widget.resize(600, 400)
        # load graph widgets
        for item in self.config["graphWidgets"]:
            if not item["id"] in graphWidgets:
                continue
            c = graphWidgets[item["id"]]
            w = c(hintSignal = self.hintSignal, rmCallback = self.rmWidgetFromMain, send=self.sendData, config=item["config"])
            self.widgets.append(w)
            self.widgetsLayout.addWidget(w)
        return widget

    def onWidgetSettings(self, parent):
        '''
            setting widget, just return a QWidget object or None
        '''
        layout = QVBoxLayout()
        setingGroup = QGroupBox(_("Rx Stripts"))
        setingGrouplayout = QGridLayout()
        setingGrouplayout.setContentsMargins(10, 18, 10, 18)
        setingGrouplayout.setVerticalSpacing(10)
        setingGroup.setLayout(setingGrouplayout)
        self.codeItems = ComboBox()
        self.codeItemCustomStr = _("Custom, input name")
        self.codeItemLoadDefaultsStr = _("Load defaults")
        self.codeItems.setEditable(True)
        self.codeWidget = PlainTextEdit()
        self.saveCodeBtn = QPushButton(_("Save"))
        self.saveCodeBtn.setEnabled(False)
        self.deleteCodeBtn = QPushButton(_("Delete"))
        btnLayout = QHBoxLayout()
        btnLayout.addWidget(self.saveCodeBtn)
        btnLayout.addWidget(self.deleteCodeBtn)
        setingGrouplayout.addWidget(self.codeItems,0,0,1,1)
        setingGrouplayout.addWidget(self.codeWidget,1,0,1,1)
        setingGrouplayout.addLayout(btnLayout,2,0,1,1)
        itemList = QListWidget()
        for k,v in graphWidgets.items():
            itemList.addItem(k)
        itemList.setToolTip(_("Double click to add a graph widget"))
        itemList.setCurrentRow(0)
        itemList.itemDoubleClicked.connect(self.addWidgetToMain)
        layout.addWidget(setingGroup)
        layout.addWidget(itemList)
        widget = QWidget()
        widget.setLayout(layout)
        layout.setContentsMargins(0,8,0,8)

        self.saveCodeBtn.clicked.connect(self.saveCode)
        self.deleteCodeBtn.clicked.connect(self.deleteCode)
        self.codeWidget.onSave = self.saveCode

        return widget

    def addWidgetToMain(self, item):
        for k, c in graphWidgets.items():
            if k == item.text():
                config = {
                    "id": c.id,
                    "config": {}
                }
                w = c(hintSignal = self.hintSignal, rmCallback = self.rmWidgetFromMain, send=self.sendData, config=config["config"])
                self.widgets.append(w)
                self.widgetsLayout.addWidget(w)
                self.config["graphWidgets"].append(config)

    def rmWidgetFromMain(self, widget):
        self.widgetsLayout.removeWidget(widget)
        for item in self.config["graphWidgets"]:
            if id(item["config"]) == id(widget.config):
                self.config["graphWidgets"].remove(item)
                break
        widget.deleteLater()
        self.widgets.remove(widget)

    def onWidgetFunctional(self, parent):
        '''
            functional widget, just return a QWidget object or None
        '''
        button = QPushButton(_("Clear count"))
        button.clicked.connect(self.clearCount)
        return button

    def onWidgetStatusBar(self, parent):
        self.statusBar = statusBar(rxTxCount=True)
        return self.statusBar

    def clearCount(self):
        self.statusBar.clear()

    def onReceived(self, data : bytes):
        '''
            call in receive thread, not UI thread
        '''
        self.statusBar.addRx(len(data))
        try:
            data = self.decodeMethod(data)
        except Exception as e:
            self.hintSignal.emit("error", _("Error"), _("Run decode error") + " " + str(e))
            return
        if not data:
            return
        for w in self.widgets:
            w.onData(data)

    def sendData(self, data:bytes):
        '''
            send data, chidren call send will invoke this function
            if you send data in this plugin, you can directly call self.send
        '''
        self.send(data, callback=self.onSent)

    def onSent(self, ok, msg, length, path):
        if ok:
            self.statusBar.addTx(length)
        else:
            self.hintSignal.emit("error", _("Error"), _("Send data failed!") + " " + msg)

    def onKeyPressEvent(self, event):
        for w in self.widgets:
            w.onKeyPressEvent(event)

    def onKeyReleaseEvent(self, event):
        for w in self.widgets:
            w.onKeyReleaseEvent(event)

    def onUiInitDone(self):
        '''
            UI init done, you can update your widget here
            this method runs in UI thread, do not block too long
        '''
        # init decoder and encoder
        for k in self.config["code"]:
            self.codeItems.addItem(k)
        self.codeItems.addItem(self.codeItemCustomStr)
        self.codeItems.addItem(self.codeItemLoadDefaultsStr)
        name = self.config["currCode"]
        idx = self.codeItems.findText(self.config["currCode"])
        if idx < 0:
            idx = 0
            name = "default"
        self.codeItems.setCurrentIndex(idx)
        self.selectCode(name)
        self.codeItems.currentIndexChanged.connect(self.onCodeItemChanged) # add here to avoid self.selectCode trigger
        self.codeWidget.textChanged.connect(self.onCodeChanged)

    def onActive(self):
        '''
            plugin active
        '''
        pass
