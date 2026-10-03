// Native vector rendering of the Pangaea store icon (icon-small.png, icon-large.png).
import AppKit

let root = URL(fileURLWithPath: CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "store")

for size in [80, 144] {
    let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: size,
        pixelsHigh: size,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    )!
    let context = NSGraphicsContext(bitmapImageRep: bitmap)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    let c = context.cgContext

    // Scale 144 coordinate space to target size
    let scale = CGFloat(size) / 144.0
    c.scaleBy(x: scale, y: scale)
    c.translateBy(x: 0, y: 144)
    c.scaleBy(x: 1, y: -1)

    func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1.0) -> CGColor {
        return CGColor(red: r/255.0, green: g/255.0, blue: b/255.0, alpha: a)
    }

    // 1. Dark space background with rounded corners
    let bgRect = CGRect(x: 0, y: 0, width: 144, height: 144)
    let bgPath = CGPath(roundedRect: bgRect, cornerWidth: 28, cornerHeight: 28, transform: nil)
    c.addPath(bgPath)
    c.setFillColor(color(8, 16, 24))
    c.fillPath()

    // 2. Deep-Time "Day Arc" outer ring
    // Center is (72, 72), outer radius 60
    let center = CGPoint(x: 72, y: 72)
    
    // Background track ring
    c.setStrokeColor(color(25, 45, 60, 0.6))
    c.setLineWidth(4.0)
    c.strokeEllipse(in: CGRect(x: 72 - 58, y: 72 - 58, width: 116, height: 116))

    // Colored Mesozoic Era Arcs (Triassic: Amber, Jurassic: Cyan, Cretaceous: Mint)
    // Triassic Arc (135° to 225°)
    c.setLineWidth(4.5)
    c.setLineCap(.round)
    c.setStrokeColor(color(255, 170, 0, 0.95)) // Amber
    let triassic = CGMutablePath()
    triassic.addArc(center: center, radius: 58, startAngle: 2.3, endAngle: 3.8, clockwise: false)
    c.addPath(triassic)
    c.strokePath()

    // Jurassic Arc (225° to 315°)
    c.setStrokeColor(color(0, 255, 255, 0.95)) // Cyan
    let jurassic = CGMutablePath()
    jurassic.addArc(center: center, radius: 58, startAngle: 3.9, endAngle: 5.1, clockwise: false)
    c.addPath(jurassic)
    c.strokePath()

    // Cretaceous Arc (315° to 60°)
    c.setStrokeColor(color(85, 255, 170, 0.95)) // Mint
    let cretaceous = CGMutablePath()
    cretaceous.addArc(center: center, radius: 58, startAngle: 5.2, endAngle: 6.8, clockwise: false)
    c.addPath(cretaceous)
    c.strokePath()

    // Chicxulub Asteroid Impact tick (Red/Rose)
    c.setStrokeColor(color(255, 0, 85, 1.0))
    c.setLineWidth(5.0)
    let impact = CGMutablePath()
    impact.addArc(center: center, radius: 58, startAngle: 0.52, endAngle: 0.60, clockwise: false)
    c.addPath(impact)
    c.strokePath()

    // 3. Central Panthalassa Ocean & Pangaea Globe
    let globeRadius: CGFloat = 44
    let globeRect = CGRect(x: 72 - globeRadius, y: 72 - globeRadius, width: globeRadius * 2, height: globeRadius * 2)
    c.setFillColor(color(10, 36, 42)) // Panthalassa deep teal
    c.fillEllipse(in: globeRect)
    c.setStrokeColor(color(28, 85, 95))
    c.setLineWidth(2.0)
    c.strokeEllipse(in: globeRect)

    // Graticule lines (equator & prime meridian)
    c.setStrokeColor(color(18, 58, 66, 0.8))
    c.setLineWidth(1.0)
    c.move(to: CGPoint(x: 72 - globeRadius, y: 72))
    c.addLine(to: CGPoint(x: 72 + globeRadius, y: 72))
    c.strokePath()
    c.strokeEllipse(in: CGRect(x: 72 - 20, y: 72 - globeRadius, width: 40, height: globeRadius * 2))

    // 4. Stylized Supercontinent Pangaea
    // Single contiguous C-shaped landmass embracing the Tethys Ocean
    c.setFillColor(color(38, 120, 100))
    let pangaea = CGMutablePath()
    // Laurasia / Northern bulk
    pangaea.move(to: CGPoint(x: 52, y: 52))
    pangaea.addCurve(to: CGPoint(x: 82, y: 50), control1: CGPoint(x: 60, y: 44), control2: CGPoint(x: 74, y: 44))
    pangaea.addCurve(to: CGPoint(x: 96, y: 64), control1: CGPoint(x: 90, y: 54), control2: CGPoint(x: 98, y: 58))
    // Tethys bay embayment (inward curve)
    pangaea.addCurve(to: CGPoint(x: 76, y: 74), control1: CGPoint(x: 90, y: 70), control2: CGPoint(x: 82, y: 72))
    // Gondwana / Southern bulk
    pangaea.addCurve(to: CGPoint(x: 92, y: 92), control1: CGPoint(x: 84, y: 80), control2: CGPoint(x: 94, y: 86))
    pangaea.addCurve(to: CGPoint(x: 68, y: 104), control1: CGPoint(x: 88, y: 100), control2: CGPoint(x: 78, y: 106))
    pangaea.addCurve(to: CGPoint(x: 48, y: 86), control1: CGPoint(x: 58, y: 102), control2: CGPoint(x: 46, y: 96))
    // West coast curve back to north
    pangaea.addCurve(to: CGPoint(x: 52, y: 52), control1: CGPoint(x: 46, y: 72), control2: CGPoint(x: 48, y: 60))
    pangaea.closeSubpath()
    c.addPath(pangaea)
    c.fillPath()

    // Inner highland ridge / tectonic spine
    c.setFillColor(color(55, 165, 135))
    let spine = CGMutablePath()
    spine.move(to: CGPoint(x: 58, y: 58))
    spine.addQuadCurve(to: CGPoint(x: 74, y: 60), control: CGPoint(x: 66, y: 54))
    spine.addQuadCurve(to: CGPoint(x: 66, y: 76), control: CGPoint(x: 72, y: 68))
    spine.addQuadCurve(to: CGPoint(x: 60, y: 88), control: CGPoint(x: 64, y: 82))
    spine.addQuadCurve(to: CGPoint(x: 58, y: 58), control: CGPoint(x: 54, y: 74))
    spine.closeSubpath()
    c.addPath(spine)
    c.fillPath()

    // 5. Pulsing Observer Crosshair / Home Reticle (Amber)
    let homeX: CGFloat = 62
    let homeY: CGFloat = 68
    // Outer halo
    c.setFillColor(color(255, 170, 0, 0.25))
    c.fillEllipse(in: CGRect(x: homeX - 7, y: homeY - 7, width: 14, height: 14))
    // Ring
    c.setStrokeColor(color(255, 170, 0, 0.95))
    c.setLineWidth(1.5)
    c.strokeEllipse(in: CGRect(x: homeX - 4.5, y: homeY - 4.5, width: 9, height: 9))
    // Crosshair ticks
    c.move(to: CGPoint(x: homeX - 7, y: homeY)); c.addLine(to: CGPoint(x: homeX - 3, y: homeY)); c.strokePath()
    c.move(to: CGPoint(x: homeX + 3, y: homeY)); c.addLine(to: CGPoint(x: homeX + 7, y: homeY)); c.strokePath()
    c.move(to: CGPoint(x: homeX, y: homeY - 7)); c.addLine(to: CGPoint(x: homeX, y: homeY - 3)); c.strokePath()
    c.move(to: CGPoint(x: homeX, y: homeY + 3)); c.addLine(to: CGPoint(x: homeX, y: homeY + 7)); c.strokePath()
    // Center point
    c.setFillColor(color(255, 255, 255, 1.0))
    c.fillEllipse(in: CGRect(x: homeX - 1.5, y: homeY - 1.5, width: 3, height: 3))

    NSGraphicsContext.restoreGraphicsState()
    let name = size == 80 ? "icon-small.png" : "icon-large.png"
    let outUrl = root.appendingPathComponent(name)
    try bitmap.representation(using: .png, properties: [:])!.write(to: outUrl)
    print("Rendered \(name) at \(size)x\(size)")
}
