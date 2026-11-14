.pragma library

// Tooltip texts of the Settings window's fields: the help, then Tk's
// "⚠ message" when the field is wrong (voicings_page.py _apply_field_mark:
// "{base}\n\n⚠ {message}"). CNStyle's ToolTip shows styled text, so the
// texts are escaped and their line breaks kept.

function escape(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                       .replace(/\n/g, "<br>")
}

function tip(help, error) {
    var base = help ? String(help) : ""
    var text = error ? (base ? base + "\n\n" : "") + "⚠ " + error : base
    return text ? escape(text) : ""
}
