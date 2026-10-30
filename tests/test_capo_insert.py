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


class TestReplaceExistingCapo:
    """A {capo} between the start and the first chord is replaced (Tibi,
    2026-10-30); otherwise the directive goes at the start."""

    @staticmethod
    def spans(text):
        import re
        return [(m.start(), m.end()) for m in re.finditer(r"\{capo:[^}]*\}", text)]

    def test_capo_before_the_first_chord_is_replaced(self):
        text = "{title: x}\n{capo: 2}\nC  G\n"
        out, offset = insert_capo_directive(
            text, 5, None, capo_spans=self.spans(text), first_chord=text.index("C  G"))
        assert out == "{title: x}\n{capo: 5}\nC  G\n"
        assert offset == text.index("{capo")

    def test_capo_after_the_first_chord_is_left_alone(self):
        text = "C  G\n{capo: 2}\nAm F\n"
        out, offset = insert_capo_directive(
            text, 5, None, capo_spans=self.spans(text), first_chord=0)
        assert out == "{capo: 5}\n" + text
        assert offset == 0

    def test_no_capo_inserts_at_the_very_start(self):
        text = "{key: G}\nG  D\n"
        out, offset = insert_capo_directive(
            text, 3, None, capo_spans=[], first_chord=text.index("G  D"))
        assert out == "{capo: 3}\n" + text

    def test_selection_replaces_a_capo_between_its_start_and_its_first_chord(self):
        text = "C  G\n{capo: 1}\nverse words\n{capo: 4}\nAm F\n"
        sel = text.index("verse")
        out, offset = insert_capo_directive(
            text, 2, sel, capo_spans=self.spans(text), first_chord=text.index("Am F"))
        assert out == "C  G\n{capo: 1}\nverse words\n{capo: 2}\nAm F\n"
        assert offset == text.index("{capo: 4}")

    def test_selection_without_a_capo_inserts_at_its_start(self):
        text = "{capo: 1}\nC  G\nAm F\n"
        sel = text.index("Am F")
        out, offset = insert_capo_directive(
            text, 2, sel, capo_spans=self.spans(text), first_chord=sel)
        assert out == "{capo: 1}\nC  G\n{capo: 2}\nAm F\n"
        assert offset == sel

    def test_without_chords_any_capo_after_the_start_counts(self):
        text = "words\n{capo: 1}\n"
        out, _ = insert_capo_directive(text, 3, None, capo_spans=self.spans(text),
                                       first_chord=None)
        assert out == "words\n{capo: 3}\n"
