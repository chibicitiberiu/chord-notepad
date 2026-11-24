import Foundation

/// An sRGB colour with alpha, each channel 0...1: what the chord sheet paints
/// with. The app turns it into a `CGColor`; the kit only does arithmetic.
public struct SheetColor: Sendable, Hashable, CustomStringConvertible {
    public var red: Double
    public var green: Double
    public var blue: Double
    public var alpha: Double

    public init(red: Double, green: Double, blue: Double, alpha: Double = 1) {
        self.red = red
        self.green = green
        self.blue = blue
        self.alpha = alpha
    }

    /// `0xAARRGGBB`, as Android writes its colours (`Color(0xFF3F51B5)`).
    public init(argb: UInt32) {
        self.init(red: Double((argb >> 16) & 0xFF) / 255, green: Double((argb >> 8) & 0xFF) / 255,
                  blue: Double(argb & 0xFF) / 255, alpha: Double((argb >> 24) & 0xFF) / 255)
    }

    /// A Tk colour string (`#rgb`, `#rrggbb` or one of the few names Tk
    /// renderers might use), or nil for none (`""`, unknown names): Android's
    /// `parseTkColor`, the desktop's `parse_tk_color`.
    public init?(tk spec: String?) {
        guard let spec, let first = spec.first else { return nil }
        if first == "#" {
            let hex = spec.dropFirst()
            guard hex.allSatisfy(\.isHexDigit), let value = UInt32(hex, radix: 16) else { return nil }
            switch hex.count {
            case 6:
                self.init(argb: 0xFF00_0000 | value)
            case 3:
                let r = (value >> 8) & 0xF, g = (value >> 4) & 0xF, b = value & 0xF
                self.init(argb: 0xFF00_0000 | (r * 17) << 16 | (g * 17) << 8 | (b * 17))
            default:
                return nil
            }
            return
        }
        switch spec.lowercased() {
        case "black": self.init(argb: 0xFF00_0000)
        case "white": self.init(argb: 0xFFFF_FFFF)
        case "red": self.init(argb: 0xFFFF_0000)
        case "gray", "grey": self.init(argb: 0xFFBE_BEBE)
        default: return nil
        }
    }

    public static let black = SheetColor(red: 0, green: 0, blue: 0)
    public static let white = SheetColor(red: 1, green: 1, blue: 1)

    /// The colour as `0xAARRGGBB`, each channel rounded to 8 bits.
    public var argb: UInt32 {
        func byte(_ v: Double) -> UInt32 { UInt32((min(max(v, 0), 1) * 255).rounded()) }
        return byte(alpha) << 24 | byte(red) << 16 | byte(green) << 8 | byte(blue)
    }

    /// `#rrggbb` (alpha left out), lower case.
    public var hex: String {
        String(format: "#%06x", argb & 0x00FF_FFFF)
    }

    public var description: String {
        alpha >= 1 ? hex : hex + String(format: "@%.3f", alpha)
    }

    /// The same colour with another alpha.
    public func withAlpha(_ alpha: Double) -> SheetColor {
        SheetColor(red: red, green: green, blue: blue, alpha: alpha)
    }

    /// HSL lightness: the mean of the largest and smallest channel.
    public var lightness: Double {
        (max(red, green, blue) + min(red, green, blue)) / 2
    }

    /// Hue (degrees, 0..<360), saturation and lightness, as Android's
    /// `darkVariant` works them out.
    public var hsl: (hue: Double, saturation: Double, lightness: Double) {
        let hi = max(red, green, blue)
        let lo = min(red, green, blue)
        let l = (hi + lo) / 2
        let d = hi - lo
        let s = d == 0 ? 0 : d / (1 - abs(2 * l - 1))
        var h: Double
        if d == 0 {
            h = 0
        } else if hi == red {
            h = 60 * ((green - blue) / d).truncatingRemainder(dividingBy: 6)
        } else if hi == green {
            h = 60 * ((blue - red) / d + 2)
        } else {
            h = 60 * ((red - green) / d + 4)
        }
        if h < 0 { h += 360 }
        return (h, s, l)
    }

    /// The colour of HSL `hue` (degrees), `saturation` and `lightness`
    /// (Compose's `Color.hsl`, Qt's `fromHslF`).
    public init(hue: Double, saturation: Double, lightness: Double, alpha: Double = 1) {
        let c = (1 - abs(2 * lightness - 1)) * saturation
        let hp = (hue.truncatingRemainder(dividingBy: 360) + 360).truncatingRemainder(dividingBy: 360) / 60
        let x = c * (1 - abs(hp.truncatingRemainder(dividingBy: 2) - 1))
        let m = lightness - c / 2
        let (r, g, b): (Double, Double, Double)
        switch hp {
        case ..<1: (r, g, b) = (c, x, 0)
        case ..<2: (r, g, b) = (x, c, 0)
        case ..<3: (r, g, b) = (0, c, x)
        case ..<4: (r, g, b) = (0, x, c)
        case ..<5: (r, g, b) = (x, 0, c)
        default: (r, g, b) = (c, 0, x)
        }
        self.init(red: r + m, green: g + m, blue: b + m, alpha: alpha)
    }
}
