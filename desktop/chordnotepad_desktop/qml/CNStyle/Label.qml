import QtQuick
import QtQuick.Templates as T
import CNTheme

T.Label {
    id: lbl
    transform: SnapTranslate { target: lbl }   // whole device pixels (crisp native text at 125%)
    color: enabled ? Theme.text : Theme.disabled
    linkColor: Theme.accent
    font: Theme.font
}
