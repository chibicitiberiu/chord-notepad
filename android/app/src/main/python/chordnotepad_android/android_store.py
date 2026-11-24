"""The session's DocumentStore over Kotlin's SafDocumentStore.

Kotlin's ``DocumentStoreBridge`` (``bridge/BridgeContract.kt``) does the
Storage Access Framework I/O and keeps the recent list;
``session.callback_store.CallbackDocumentStore`` gives it the shape of
``session.documents.DocumentStore``. What is Android's here is how a failure
is read: it arrives as a Java ``DocumentStoreException`` whose message
(``getMessage()``) is user-facing, and Kotlin's ``RenameUnsupportedException``
(a provider that can't rename) means ``RenameNotSupported``. Java exceptions
are told apart by their simple class name, which Chaquopy exposes through
``getClass()``.
"""

from chordnotepad.session.callback_store import CallbackDocumentStore

#: Kotlin's exception for a provider without rename support (simple class name).
RENAME_UNSUPPORTED = "RenameUnsupportedException"


def _message(exc: BaseException) -> str:
    """The user-facing message of a Java exception (or a Python one)."""
    get_message = getattr(exc, "getMessage", None)
    if callable(get_message):
        try:
            message = get_message()
        except Exception:
            message = None
        if message:
            return str(message)
    return str(exc) or type(exc).__name__


def _java_name(exc: BaseException) -> str:
    """The simple class name of a Java exception (Chaquopy), else the Python one."""
    get_class = getattr(exc, "getClass", None)
    if callable(get_class):
        try:
            return str(get_class().getSimpleName())
        except Exception:
            pass
    return type(exc).__name__


class AndroidDocumentStore(CallbackDocumentStore):
    """:class:`session.documents.DocumentStore` backed by Kotlin's store."""

    def message_of(self, exc: BaseException) -> str:
        return _message(exc)

    def is_rename_unsupported(self, exc: BaseException) -> bool:
        return _java_name(exc) == RENAME_UNSUPPORTED or super().is_rename_unsupported(exc)
