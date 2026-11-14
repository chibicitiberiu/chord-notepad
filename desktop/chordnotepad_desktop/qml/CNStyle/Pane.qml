import QtQuick
import QtQuick.Templates as T
import CNTheme

T.Pane {
    implicitWidth: Math.max(implicitBackgroundWidth, contentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight, contentHeight + topPadding + bottomPadding)
    padding: Theme.gap3
    font: Theme.font
    background: Rectangle { color: Theme.panel }
}
