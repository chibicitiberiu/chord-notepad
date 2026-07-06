"""Tests for the headless capo-directive insertion service."""

import pytest

from services.capo_insert import insert_capo_directive


class TestInsertAtTop:
    def test_none_selection_inserts_at_top(self):
        text = "C  Am  F  G\nsome lyrics\n"
        out, offset = insert_capo_directive(text, 3, None)
        assert out == "{capo: 3}\nC  Am  F  G\nsome lyrics\n"
        assert offset == 0

    def test_offset_points_at_brace(self):
        text = "hello world\n"
        out, offset = insert_capo_directive(text, 2, None)
        assert out[offset] == '{'
        assert out[offset:offset + len("{capo: 2}")] == "{capo: 2}"


class TestInsertAtLineStart:
    def test_mid_document_offset_lands_at_line_start(self):
        text = "line one\nline two\nline three\n"
        # Offset pointing mid-way into "line two".
        sel = text.index("line two") + 4  # inside the word, not at its start
        out, offset = insert_capo_directive(text, 5, sel)
        assert out == "line one\n{capo: 5}\nline two\nline three\n"
        # Offset is the start of the line that contained the selection.
        assert offset == text.index("line two")
        assert out[offset] == '{'

    def test_offset_at_line_start_stays_there(self):
        text = "aaa\nbbb\nccc\n"
        sel = text.index("bbb")  # exactly at start of line
        out, offset = insert_capo_directive(text, 1, sel)
        assert out == "aaa\n{capo: 1}\nbbb\nccc\n"
        assert offset == sel

    def test_surrounding_lines_preserved_exactly(self):
        text = "first\nsecond\nthird\nfourth\n"
        sel = text.index("third") + 2
        out, offset = insert_capo_directive(text, 4, sel)
        # Everything before and after the inserted line is byte-for-byte intact.
        assert out[:offset] == text[:offset]
        assert out[offset:] == "{capo: 4}\n" + text[offset:]
        assert out.count("first") == 1
        assert out.count("fourth") == 1

    def test_offset_on_first_line_inserts_at_top(self):
        text = "alpha\nbeta\n"
        sel = 3  # inside "alpha"
        out, offset = insert_capo_directive(text, 7, sel)
        assert out == "{capo: 7}\nalpha\nbeta\n"
        assert offset == 0


class TestValuePolicy:
    def test_zero_capo_is_inserted(self):
        out, offset = insert_capo_directive("x\n", 0, None)
        assert out == "{capo: 0}\nx\n"

    def test_negative_capo_inserted_verbatim(self):
        out, offset = insert_capo_directive("x\n", -2, None)
        assert out == "{capo: -2}\nx\n"


class TestEdgeCases:
    def test_empty_document(self):
        out, offset = insert_capo_directive("", 2, None)
        assert out == "{capo: 2}\n"
        assert offset == 0

    def test_empty_document_with_selection_zero(self):
        out, offset = insert_capo_directive("", 5, 0)
        assert out == "{capo: 5}\n"
        assert offset == 0

    def test_document_without_trailing_newline(self):
        text = "one\ntwo"  # no trailing newline
        sel = text.index("two") + 1
        out, offset = insert_capo_directive(text, 3, sel)
        assert out == "one\n{capo: 3}\ntwo"
        assert offset == text.index("two")

    def test_selection_past_end_clamps_to_last_line(self):
        text = "only line"  # no newline at all
        out, offset = insert_capo_directive(text, 1, 999)
        assert out == "{capo: 1}\nonly line"
        assert offset == 0


class TestDialogModuleSmoke:
    def test_capo_dialog_importable(self):
        from ui.dialogs.capo_dialog import CapoDialog
        assert CapoDialog is not None
        assert hasattr(CapoDialog, '_on_ok')
        assert hasattr(CapoDialog, '_on_cancel')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
