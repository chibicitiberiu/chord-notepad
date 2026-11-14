import QtQuick
import QtQuick.Templates as T
import CNTheme

T.ToolSeparator {
    id: control
    leftPadding: vertical ? Theme.gap2 : 0; rightPadding: vertical ? Theme.gap2 : 0
    topPadding: vertical ? Theme.gap2 : 0; bottomPadding: vertical ? Theme.gap2 : 0
    contentItem: Rectangle {
        implicitWidth: control.vertical ? Theme.hairline : Theme.px(5)
        implicitHeight: control.vertical ? Theme.px(5) : Theme.hairline
        color: Theme.border
    }
}
