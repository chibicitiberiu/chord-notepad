"""The shared application layer that both the Tk UI and the mobile UIs sit on.

Everything in this package is Tk-free and must import on Android (see
``docs/architecture/session.md``). The guard test in
``tests/test_core_import_guard.py`` enforces that.
"""
