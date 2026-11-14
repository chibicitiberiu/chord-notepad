import QtQuick
import QtQuick.Templates as T
import CNTheme

// Dialogs: title, body, then a footer the app builds with DialogFooter
// (one fixed button order everywhere: secondary actions left of the primary,
// the primary last on the right; a destructive choice alone on the far left).
// The footer is our own row, not a DialogButtonBox, which ignores a button's
// `highlighted` (pitfall 26).
T.Dialog {
    onOpened: Theme.bumpLayout()     // re-snap the text inside
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding,
                            implicitHeaderWidth, implicitFooterWidth)
    implicitHeight: Math.max(implicitBackgroundHeight, implicitContentHeight + topPadding + bottomPadding
                             + (implicitHeaderHeight > 0 ? implicitHeaderHeight + spacing : 0)
                             + (implicitFooterHeight > 0 ? implicitFooterHeight + spacing : 0))
    padding: Theme.gap6
    topPadding: Theme.gap1
    bottomPadding: Theme.gap4
    popupType: T.Popup.Item
    font: Theme.font
    background: PopupBackground { color: Theme.popup; radius: Theme.radiusDialog }
    header: SText {
        text: control.title
        visible: control.title
        elide: Text.ElideRight
        font: Theme.fontTitleF
        color: Theme.text
        leftPadding: Theme.gap6; rightPadding: Theme.gap6
        topPadding: Theme.px(5); bottomPadding: Theme.gap2
    }
    T.Overlay.modal: Rectangle { color: Theme.dark ? "#80000000" : "#40000000" }
    T.Overlay.modeless: Rectangle { color: "transparent" }
}
