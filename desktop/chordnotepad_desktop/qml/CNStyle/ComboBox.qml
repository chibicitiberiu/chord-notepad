pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Templates as T
import CNTheme

// Raised neutral field with a chevron; the list pops up as a menu surface.
T.ComboBox {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight, implicitContentHeight + topPadding + bottomPadding)
    leftPadding: Theme.padX
    rightPadding: Theme.px(7)
    hoverEnabled: true
    font: Theme.font
    readonly property real windowHeight: Window.height     // for the popup's height

    delegate: T.ItemDelegate {
        id: row
        required property var model
        required property var modelData
        required property int index
        width: ListView.view.width
        implicitHeight: Theme.menuItemHeight
        leftPadding: Theme.padX; rightPadding: Theme.padX
        hoverEnabled: true
        highlighted: control.highlightedIndex === index
        contentItem: SText {
            text: control.textRole ? row.modelData[control.textRole] : row.modelData
            font: control.currentIndex === row.index ? Theme.fontMedium : Theme.font
            color: Theme.text
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            x: Theme.gap1; width: parent.width - 2 * Theme.gap1
            radius: Theme.radiusSmall
            color: row.highlighted ? Theme.selectedRow : "transparent"
        }
    }
    indicator: ChevronIcon {
        x: control.width - width - Theme.gap2
        y: (control.height - height) / 2
        color: control.enabled ? Theme.icon : Theme.disabled
    }
    contentItem: T.TextField {
        text: control.editable ? control.editText : control.displayText
        enabled: control.editable
        autoScroll: control.editable
        readOnly: control.down
        validator: control.validator
        font: control.font
        color: control.enabled ? Theme.text : Theme.disabled
        selectionColor: Theme.selection
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        implicitWidth: Theme.px(34)
        implicitHeight: Theme.controlHeight
        radius: Theme.radius
        color: control.down ? Theme.controlPressed : control.hovered ? Theme.controlHover : Theme.control
        border.width: Theme.hairline
        border.color: control.activeFocus || control.down ? Theme.accent : Theme.borderStrong
        FocusRing { visible: control.visualFocus }
    }
    popup: T.Popup {
        y: control.height + Theme.gap1
        width: Math.max(control.width, Theme.px(40))
        height: Math.min(contentItem.implicitHeight + 2 * Theme.gap1, control.windowHeight - Theme.px(10))
        padding: Theme.gap1
        popupType: T.Popup.Item
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.delegateModel
            currentIndex: control.highlightedIndex
            highlightMoveDuration: 0
            T.ScrollBar.vertical: ScrollBar { }
        }
        background: PopupBackground { }
    }
}
