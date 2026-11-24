import XCTest

@testable import ChordNotepadKit

/// Android's OffsetMapperTest.kt, case for case.
final class OffsetMapperTests: XCTestCase {
    func testAsciiAndBMPTextMapOneToOne() {
        let text = "Am  C/G  Ré  漢字\nG7"
        let m = OffsetMapper(text)
        XCTAssertTrue(m.isIdentity)
        XCTAssertEqual(text.utf16.count, m.codePointLength)
        for i in 0...text.utf16.count {
            XCTAssertEqual(i, m.toUTF16(i))
            XCTAssertEqual(i, m.toCodePoint(i))
        }
    }

    func testEmojiTakesTwoUTF16UnitsButOneCodePoint() {
        let text = "a😀b"  // a(0) 😀(1,2) b(3)
        let m = OffsetMapper(text)
        XCTAssertFalse(m.isIdentity)
        XCTAssertEqual(4, m.utf16Length)
        XCTAssertEqual(3, m.codePointLength)
        XCTAssertEqual([0, 1, 3, 4], (0...3).map(m.toUTF16))
        XCTAssertEqual([0, 1, 1, 2, 3], (0...4).map(m.toCodePoint))
    }

    func testAUTF16OffsetInsideAPairMapsToThePairsCodePoint() {
        let m = OffsetMapper("😀😀")
        XCTAssertEqual(0, m.toCodePoint(1))
        XCTAssertEqual(1, m.toCodePoint(3))
    }

    func testFlagsAndZWJSequencesAreSeveralCodePoints() {
        let text = "🇷🇴 👩‍👩‍👧 C"  // flag = 2 pairs; family = 3 pairs + 2 ZWJ
        let m = OffsetMapper(text)
        XCTAssertEqual(text.unicodeScalars.count, m.codePointLength)
        let utf16 = Array(text.utf16)
        let cOffset = utf16.firstIndex(of: UInt16(UInt8(ascii: "C")))!
        XCTAssertEqual(cOffset, m.toUTF16(m.toCodePoint(cOffset)))
        XCTAssertEqual(codePointCount(utf16, upTo: cOffset), m.toCodePoint(cOffset))
    }

    func testLoneSurrogatesCountAsOneCodePointEachLikeJavaAndPython() {
        // "x\uD83Dy\uDE00z": a high and a low that aren't a pair. A Swift
        // String can't hold them, NSString (and so a text view) can.
        let units: [UInt16] = [0x78, 0xD83D, 0x79, 0xDE00, 0x7A]
        let m = OffsetMapper(utf16: units)
        XCTAssertTrue(m.isIdentity)
        XCTAssertEqual(codePointCount(units, upTo: units.count), m.codePointLength)
    }

    func testOutOfRangeOffsetsAreClamped() {
        let m = OffsetMapper("a😀")
        XCTAssertEqual(0, m.toUTF16(-5))
        XCTAssertEqual(3, m.toUTF16(99))
        XCTAssertEqual(0, m.toCodePoint(-1))
        XCTAssertEqual(2, m.toCodePoint(99))
    }

    func testEmptyText() {
        let m = OffsetMapper("")
        XCTAssertEqual(0, m.toUTF16(0))
        XCTAssertEqual(0, m.toCodePoint(0))
    }

    func testMatchesAReferenceCountOnRandomTextWithSurrogatePairs() {
        var rnd = SplitMix64(seed: 42)
        for _ in 0..<300 {
            let text = randomText(&rnd, length: Int(rnd.next() % 60))
            let m = OffsetMapper(text)
            let scalars = Array(text.unicodeScalars)
            XCTAssertEqual(scalars.count, m.codePointLength)
            var u = 0
            for cp in 0...scalars.count {
                XCTAssertEqual(u, m.toUTF16(cp), "toUTF16(\(cp)) in \"\(text)\"")
                XCTAssertEqual(cp, m.toCodePoint(u), "toCodePoint(\(u)) in \"\(text)\"")
                if cp < scalars.count { u += scalars[cp].utf16.count }
            }
        }
    }
}

/// Code points in `units[0..<end]`, counting a lone surrogate as one (Java's
/// `codePointCount`).
private func codePointCount(_ units: [UInt16], upTo end: Int) -> Int {
    var count = 0
    var i = 0
    while i < end {
        if i + 1 < end, units[i] & 0xFC00 == 0xD800, units[i + 1] & 0xFC00 == 0xDC00 {
            i += 2
        } else {
            i += 1
        }
        count += 1
    }
    return count
}

/// A small seeded generator, so the random cases are the same on every run.
struct SplitMix64: RandomNumberGenerator {
    private var state: UInt64

    init(seed: UInt64) {
        state = seed
    }

    mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }
}

/// Mixed ASCII, BMP and supplementary characters.
private func randomText(_ rnd: inout SplitMix64, length: Int) -> String {
    var text = String.UnicodeScalarView()
    for _ in 0..<length {
        switch rnd.next() % 10 {
        case 0, 1: text.append(Unicode.Scalar(0x1F600 + UInt32(rnd.next() % 0x40))!)  // emoji
        case 2: text.append(Unicode.Scalar(0x1D11E)!)  // musical symbol G clef
        case 3: text.append("é")
        case 4: text.append("\n")
        default: text.append(Unicode.Scalar(UInt8(ascii: "a") + UInt8(rnd.next() % 26)))
        }
    }
    return String(text)
}
