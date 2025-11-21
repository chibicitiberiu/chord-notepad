# Chord Detection - Quick Reference Guide

## TL;DR - Best Regex Pattern

Use this pattern for most applications:

```regex
\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b
```

**What it matches:**
- C, D, E, F, G, A, B (major chords)
- Cm, Dm, etc. (minor chords)
- C7, Cmaj7, C9, C11, C13 (seventh and extended chords)
- Csus2, Csus4 (suspended chords)
- Cadd9 (added note chords)
- C#m7, Dbmaj7 (with accidentals)
- Cm7b5, C7#9 (with alterations)

**What it avoids:**
- "am", "are", "and" (common English words)
- Single letters alone without chord quality

---

## Chord Types Covered

| Type | Examples | Pattern Match |
|------|----------|---------------|
| Major | C, D, E | ✓ |
| Minor | Cm, Dm, Em | ✓ |
| Dominant 7 | C7, D7, G7 | ✓ |
| Major 7 | Cmaj7, Dmaj7 | ✓ |
| Minor 7 | Cm7, Dm7 | ✓ |
| Half-diminished | Cm7b5, Dm7b5 | ✓ |
| Diminished | Cdim, Ddim | ✓ |
| Augmented | Caug, Daug | ✓ |
| Suspended | Csus2, Csus4 | ✓ |
| Added 9 | Cadd9, Dadd9 | ✓ |
| Extended | C9, C11, C13 | ✓ |
| Sharp/Flat | C#, Db, C#m, Dbmaj7 | ✓ |
| Alterations | C7b9, C7#11, C7alt | ✓ |

---

## Language-Specific Code Snippets

### JavaScript
```javascript
const chords = text.match(/\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/g) || [];
```

### Python
```python
import re
chords = re.findall(r'\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b', text)
```

### PHP
```php
preg_match_all('/\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/', $text, $matches);
$chords = $matches[0] ?? [];
```

### Java
```java
Pattern pattern = Pattern.compile("\\b(?!am\\b|are\\b|and\\b|add\\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\\d)?(?:[b#]\\d+)*)\\b");
Matcher matcher = pattern.matcher(text);
```

---

## European Notation (Solfege)

If you need to detect European notation (Do, Re, Mi, Fa, Sol, La, Si):

```regex
\b((?:Do|Re|Mi|Fa|Sol|La|Si)(?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b
```

---

## Slash Chords (with Bass Notes)

For chords with explicit bass notes (C/G, Dm/F):

```regex
\b([A-G](?:[#b])?(?:m(?:aj)?(?:\d+)?|min|maj7|maj9|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)?)\s*/\s*([A-G](?:[#b])?)\b
```

**Captures:**
- Group 1: Main chord
- Group 2: Bass note

---

## Chord Analysis Helper

### Extract Components

**Root note:** First letter (A-G)
```javascript
const root = chord.charAt(0);  // "C" from "Cm7"
```

**Accidental:** # or b after root
```javascript
const accidental = chord.match(/^[A-G]([#b])/)?.[1];  // "#" from "C#m7"
```

**Quality:** Everything after root and accidental
```javascript
const quality = chord.replace(/^[A-G][#b]?/, '');  // "m7" from "C#m7"
```

### Validate Chord

```javascript
function isChord(text) {
  return /\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/.test(text);
}
```

---

## Common False Positives and How to Avoid Them

| Word | Issue | Solution |
|------|-------|----------|
| "am" | Verb | Negative lookahead: `(?!am\b)` |
| "are" | Verb | Negative lookahead: `(?!are\b)` |
| "and" | Conjunction | Negative lookahead: `(?!and\b)` |
| "add" | Verb | Require digit: `add\d` |
| "A" | Article | Require chord marker or lookahead |
| "do" / "Do" | Verb / European chord | Check context or capitalization |

---

## Testing Your Pattern

### Online Tools
- https://regex101.com/ (PCRE, JavaScript, Python, Go)
- https://regexper.com/ (Visualizes regex structure)
- https://www.regexpal.com/ (Quick testing)

### Test Cases to Try

```
Input: "Play C major, then F, and finish with G7."
Expected: C, F, G7

Input: "I am playing the Am7 chord."
Expected: Am7

Input: "Add some spice with Cadd9."
Expected: Cadd9

Input: "The progression: C - F - G - C"
Expected: C, F, G, C

Input: "European: Do, Dom, Domaj7"
Expected: (if using European pattern) Do, Dom, Domaj7
```

---

## Decision Tree: Which Pattern to Use?

```
Do you need to detect chords?
├─ Yes, American notation only
│  ├─ Should avoid false positives? → Use Pattern 2 (with negative lookahead)
│  └─ Speed is critical? → Use Pattern 1 (basic)
├─ Yes, European notation (Do, Re, Mi)?
│  └─ Use European pattern
├─ Yes, both American and European?
│  └─ Use combined pattern
├─ Yes, slash chords (C/G)?
│  └─ Use slash chord pattern
└─ Yes, strict validation needed?
   └─ Use Pattern 7 (with lookbehind/lookahead)
```

---

## Integration Checklist

- [ ] Choose appropriate regex pattern for your use case
- [ ] Test pattern with sample data from your application
- [ ] Add pattern to your codebase as a constant/variable
- [ ] Implement detection function in your language
- [ ] Add error handling for edge cases
- [ ] Test with chord progressions from your data
- [ ] Optimize performance if detecting in large texts
- [ ] Document pattern and rationale for your team

---

## Common Patterns Summary

| Use Case | Pattern |
|----------|---------|
| Basic American | `\b([A-G]...)` |
| With false positive protection | `\b(?!am\b|are\b|and\b|add\b)([A-G]...)` |
| European notation | `\b((?:Do\|Re\|Mi...)` |
| Slash chords | `\bChord\s*/\s*Bass\b` |
| Chord progressions | Multiple chords with separators |

---

## Example Use Cases

### Music Lesson Tool
Detect and highlight chords in song lyrics for teaching.
```javascript
// User pastes lyrics, pattern finds all chords
// Highlight each chord for interactive learning
```

### Chord Progression Analyzer
Extract and analyze chord sequences.
```javascript
// Input: "C - F - G - C"
// Output: Analyze progression, suggest variations
```

### Lyric Sync Editor
Automatically detect chords in uploaded lyrics.
```javascript
// Paste lyrics with chords, auto-format and validate
```

### Guitar Tab Generator
Verify chord symbols in tabs.
```javascript
// Validate each chord before generating tabs
```

### Music Transcription App
Convert audio transcription labels to chord symbols.
```javascript
// Recognize chord symbols in transcription
// Validate and standardize notation
```

---

## Performance Tips

1. **Pre-compile patterns** (don't create them in loops)
2. **Use word boundaries** (`\b`) for efficiency
3. **Cache results** if processing same text multiple times
4. **Use non-capturing groups** `(?:...)` instead of `(...)`
5. **Consider lazy quantifiers** for large texts

---

## Reference: All Chord Quality Markers

**Minor indicators:**
- m, min, minor

**Major indicators:**
- maj, maj7, maj9, maj11, maj13

**Dominant:**
- 7 (default is dominant 7)

**Extensions:**
- 9, 11, 13 (with or without 7)

**Suspended:**
- sus, sus2, sus4

**Diminished/Augmented:**
- dim, aug

**Added notes:**
- add2, add4, add6, add9, add11, add13

**Alterations:**
- b (flat any interval)
- # (sharp any interval)
- Examples: b5, #11, b9, #9

---

## Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Pattern matches "am" or "are" | Add negative lookahead: `(?!am\b\|are\b)` |
| Pattern doesn't match C#m7 | Add accidental support: `[#b]?` |
| Pattern matches partial words | Use word boundaries: `\b...\b` |
| Slash chords not detected | Use slash chord pattern with `/` |
| Performance slow on long text | Reduce lookahead complexity, cache results |
| Missing some valid chords | Check chord quality list, expand pattern |

---

## Resources

**Music Theory:**
- Wikipedia Chord: https://en.wikipedia.org/wiki/Chord_(music)
- Music Notation: https://en.wikipedia.org/wiki/Musical_notation
- Solfege: https://en.wikipedia.org/wiki/Solf%C3%A8ge

**Regex Help:**
- Regex101: https://regex101.com/
- MDN Regex: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions
- RegexOne Tutorial: https://regexone.com/

**Music Databases:**
- HookTheory: https://www.hooktheory.com/ (Chord progressions)
- Chordify: https://chordify.net/ (Extract chords from videos)

