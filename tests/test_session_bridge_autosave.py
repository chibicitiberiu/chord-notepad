"""The bridge saves the config shortly after a settings-changing command."""

from session.bridge import SessionBridge
from session.testing import ManualHost


class FakeSession:
    def __init__(self, fail=False):
        self.saves = 0
        self.fail = fail
        self.bpms = []

    def subscribe(self, cb):
        class Sub:
            def cancel(self):
                pass
        return Sub()

    def set_bpm(self, bpm):
        self.bpms.append(bpm)

    def stop(self):
        pass

    def save_config(self):
        self.saves += 1
        if self.fail:
            raise OSError("disk full")


def make(autosave_s=1.5, **kw):
    host = ManualHost()
    session = FakeSession(**kw)
    return host, session, SessionBridge(host, session, lambda *_: None, autosave_s=autosave_s)


def test_saves_once_after_a_burst_of_changes():
    host, session, bridge = make()
    for bpm in (100, 110, 120):
        bridge.submit("set_bpm", '{"bpm": %d}' % bpm)
        host.run_pending()
        host.advance(1.0)
    assert session.saves == 0  # each change restarted the 1.5 s wait
    host.advance(0.6)
    assert session.saves == 1 and session.bpms == [100, 110, 120]
    host.advance(10)
    assert session.saves == 1


def test_other_commands_do_not_arm_a_save():
    host, session, bridge = make()
    bridge.submit("stop", "{}")
    host.run_pending()
    assert host.pending_timers == 0
    host.advance(10)
    assert session.saves == 0


def test_off_by_default():
    host, session, bridge = make(autosave_s=None)
    bridge.submit("set_bpm", '{"bpm": 90}')
    host.run_pending()
    host.advance(10)
    assert session.saves == 0


def test_close_drops_the_pending_save_and_a_failure_is_survived():
    host, session, bridge = make()
    bridge.submit("set_bpm", '{"bpm": 90}')
    host.run_pending()
    bridge.close()
    host.advance(10)
    assert session.saves == 0

    host, session, bridge = make(fail=True)
    bridge.submit("set_bpm", '{"bpm": 90}')
    host.run_pending()
    host.advance(2)
    assert session.saves == 1
