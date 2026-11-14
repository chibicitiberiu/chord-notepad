import QtQuick
import QtQuick.Templates as T
import CNTheme

// Menus are drawn in-window (Popup.Item): identical on Linux and Windows.
// On macOS the real app keeps the native global menu bar (pitfall 21).
// A Menu has no Repeater: build dynamic items (recent files, voicings) with
// createObject() and addItem()/insertItem() (pitfall 7).
T.Menu {
    onOpened: Theme.bumpLayout()     // re-snap the text inside
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight, implicitContentHeight + topPadding + bottomPadding)
    margins: 0
    padding: Theme.gap1
    overlap: Theme.gap1
    popupType: T.Popup.Item
    font: Theme.font
    delegate: MenuItem { }
    contentItem: ListView {
        implicitHeight: contentHeight
        implicitWidth: {
            var w = Theme.px(48)
            for (var i = 0; i < count; ++i) {
                var it = itemAtIndex(i)
                if (it) w = Math.max(w, it.implicitWidth)
            }
            return w
        }
        model: control.contentModel
        interactive: Window.window ? contentHeight + control.topPadding + control.bottomPadding > control.height : false
        clip: true
        currentIndex: control.currentIndex
        ScrollIndicator.vertical: ScrollIndicator { }
    }
    background: PopupBackground { implicitWidth: Theme.px(48); implicitHeight: Theme.px(8) }
}
