import AppKit

// FitAl 图标候选第二轮:
// C = 圆体前倾 + t 横杠拉出上扬飘带;A = 衬线斜体(杂志感)
// 背景2 = 大圆环切角;背景3 = 极光光带
// 组合:c2 / a3 / c3;橙点全保留

let size: CGFloat = 1024
let brand = NSColor(red: 0x2F / 255.0, green: 0x6B / 255.0, blue: 0x53 / 255.0, alpha: 1)
let brandDeep = NSColor(red: 0x1B / 255.0, green: 0x44 / 255.0, blue: 0x33 / 255.0, alpha: 1)
let brandLight = NSColor(red: 0x3D / 255.0, green: 0x84 / 255.0, blue: 0x66 / 255.0, alpha: 1)
let teal = NSColor(red: 0x2E / 255.0, green: 0x7A / 255.0, blue: 0x74 / 255.0, alpha: 1)
let burn = NSColor(red: 0.87, green: 0.49, blue: 0.23, alpha: 1)

func font(design: NSFontDescriptor.SystemDesign, size s: CGFloat, weight: NSFont.Weight, italic: Bool) -> NSFont {
    let base = NSFont.systemFont(ofSize: s, weight: weight)
    var desc = base.fontDescriptor
    if let d = desc.withDesign(design) { desc = d }
    if italic {
        desc = desc.withSymbolicTraits(.italic)
    }
    return NSFont(descriptor: desc, size: s) ?? base
}

func render(_ name: String, draw: (CGContext) -> Void) {
    let image = NSImage(size: NSSize(width: size, height: size))
    image.lockFocus()
    draw(NSGraphicsContext.current!.cgContext)
    image.unlockFocus()
    guard let tiff = image.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let png = rep.representation(using: .png, properties: [:]) else { fatalError() }
    try! png.write(to: URL(fileURLWithPath: "\(FileManager.default.currentDirectoryPath)/\(name).png"))
    print("written: \(name).png")
}

func baseGradient(_ ctx: CGContext) {
    NSGradient(colors: [brandLight, brand, brandDeep])!
        .draw(in: NSRect(x: 0, y: 0, width: size, height: size), angle: -60)
}

func topGlow(_ x: CGFloat = 0.5) {
    NSGradient(
        starting: NSColor.white.withAlphaComponent(0.12),
        ending: NSColor.white.withAlphaComponent(0)
    )!.draw(
        fromCenter: NSPoint(x: size * x, y: size * 0.94), radius: 0,
        toCenter: NSPoint(x: size * x, y: size * 0.94), radius: size * 0.72,
        options: []
    )
}

// 背景2:大圆环从右下角切进画面
func ringBackground(_ ctx: CGContext) {
    baseGradient(ctx)
    ctx.saveGState()
    ctx.setStrokeColor(brandLight.withAlphaComponent(0.38).cgColor)
    ctx.setLineWidth(116)
    ctx.strokeEllipse(in: CGRect(x: 430, y: -620, width: 1150, height: 1150))
    // 内侧再来一圈更淡的细环,层次
    ctx.setStrokeColor(brandLight.withAlphaComponent(0.18).cgColor)
    ctx.setLineWidth(30)
    ctx.strokeEllipse(in: CGRect(x: 330, y: -720, width: 1350, height: 1350))
    ctx.restoreGState()
    topGlow(0.35)
}

// 背景3:对角极光光带(几团青绿柔光沿对角线铺开)
func auroraBackground(_ ctx: CGContext) {
    baseGradient(ctx)
    func glow(_ color: NSColor, at p: NSPoint, r: CGFloat) {
        NSGradient(starting: color, ending: color.withAlphaComponent(0))!
            .draw(fromCenter: p, radius: 0, toCenter: p, radius: r, options: [])
    }
    glow(teal.withAlphaComponent(0.85), at: NSPoint(x: 170, y: 190), r: 560)
    glow(brandLight.withAlphaComponent(0.75), at: NSPoint(x: 540, y: 480), r: 500)
    glow(teal.withAlphaComponent(0.8), at: NSPoint(x: 900, y: 850), r: 540)
    glow(NSColor(red: 0.45, green: 0.75, blue: 0.62, alpha: 0.35), at: NSPoint(x: 760, y: 700), r: 300)
    topGlow(0.6)
}

struct WordLayout {
    let origin: NSPoint
    let attrs: [NSAttributedString.Key: Any]
    let font: NSFont
    let word: String
    var baseline: CGFloat { origin.y - font.descender }
    var xHeight: CGFloat { font.xHeight }
    var width: CGFloat { (word as NSString).size(withAttributes: attrs).width }

    // ı 的横向中心(扣字间距尾巴)
    var dotCX: CGFloat {
        let kern = (attrs[.kern] as? CGFloat) ?? 0
        let f = ("F" as NSString).size(withAttributes: attrs).width
        let fi = ("Fı" as NSString).size(withAttributes: attrs).width
        return origin.x + f + (fi - f - kern) / 2 - kern / 2
    }
}

func layoutWord(_ word: String, font: NSFont, kern: CGFloat, dy: CGFloat = -20) -> WordLayout {
    let attrs: [NSAttributedString.Key: Any] = [
        .font: font, .foregroundColor: NSColor.white, .kern: kern,
    ]
    let s = (word as NSString).size(withAttributes: attrs)
    let origin = NSPoint(x: (size - s.width) / 2, y: (size - s.height) / 2 + dy)
    return WordLayout(origin: origin, attrs: attrs, font: font, word: word)
}

func drawDot(_ ctx: CGContext, cx: CGFloat, cy: CGFloat, r: CGFloat) {
    ctx.setFillColor(burn.cgColor)
    ctx.fillEllipse(in: CGRect(x: cx - r, y: cy - r, width: r * 2, height: r * 2))
}

// 字体C:圆体前倾 + 飘带。整块文字做剪切变换,点和飘带在同一空间手绘
func drawWordC(_ ctx: CGContext) {
    let f = font(design: .rounded, size: 400, weight: .heavy, italic: false)
    let layout = layoutWord("Fıt", font: f, kern: 4, dy: -30)
    let shear: CGFloat = 0.10
    let pivotY = layout.baseline

    ctx.saveGState()
    // 绕基线剪切:x' = x + shear*(y-基线),字向右前倾
    ctx.concatenate(CGAffineTransform(1, 0, shear, 1, -shear * pivotY, 0))
    (layout.word as NSString).draw(at: layout.origin, withAttributes: layout.attrs)

    // 底部速度弧线:从字左下方掠过、向右上扬收(经典运动底划)
    let startX = layout.origin.x - 30
    let startY = layout.baseline - 128
    let endX = layout.origin.x + layout.width + 74
    let endY = layout.baseline + 10
    ctx.setStrokeColor(NSColor.white.withAlphaComponent(0.92).cgColor)
    ctx.setLineWidth(34)
    ctx.setLineCap(.round)
    ctx.beginPath()
    ctx.move(to: CGPoint(x: startX, y: startY))
    ctx.addQuadCurve(
        to: CGPoint(x: endX, y: endY),
        control: CGPoint(x: startX + (endX - startX) * 0.62, y: startY - 46)
    )
    ctx.strokePath()

    // 橙点(同一剪切空间里画,视觉上与字同倾;剪切量小,圆的变形可忽略)
    drawDot(ctx, cx: layout.dotCX, cy: layout.baseline + layout.xHeight + 84, r: 52)
    ctx.restoreGState()
}

// 字体A:衬线斜体(杂志感)
func drawWordA(_ ctx: CGContext) {
    let f = font(design: .serif, size: 420, weight: .bold, italic: true)
    let layout = layoutWord("Fıt", font: f, kern: 2, dy: -20)
    (layout.word as NSString).draw(at: layout.origin, withAttributes: layout.attrs)
    // 斜体的点:缩小、抬高、按斜度顺势右移,悬在 ı 正上方不压字
    let dotCY = layout.baseline + layout.xHeight + 128
    let italicShift = (dotCY - layout.baseline) * 0.24
    drawDot(ctx, cx: layout.dotCX + italicShift, cy: dotCY, r: 36)
}

// 前景画进透明图层→扫描实际像素边界→整体贴到画布正中(机器保证居中)
func centeredForeground(_ drawFg: (CGContext) -> Void) -> NSImage {
    let fg = NSImage(size: NSSize(width: size, height: size))
    fg.lockFocus()
    drawFg(NSGraphicsContext.current!.cgContext)
    fg.unlockFocus()

    guard let tiff = fg.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff) else { fatalError() }
    let w = rep.pixelsWide, h = rep.pixelsHigh
    var minX = w, maxX = 0, minY = h, maxY = 0
    for y in 0..<h {
        for x in 0..<w where (rep.colorAt(x: x, y: y)?.alphaComponent ?? 0) > 0.05 {
            if x < minX { minX = x }
            if x > maxX { maxX = x }
            if y < minY { minY = y }
            if y > maxY { maxY = y }
        }
    }
    let scale = CGFloat(w) / size // 视网膜屏 2x 折算回点
    let bboxCX = CGFloat(minX + maxX) / 2 / scale
    let bboxCYTopDown = CGFloat(minY + maxY) / 2 / scale
    let bboxCY = size - bboxCYTopDown // colorAt 的 y 从上往下数,翻回 CG 坐标
    let dx = size / 2 - bboxCX
    let dy = size / 2 - bboxCY

    let out = NSImage(size: NSSize(width: size, height: size))
    out.lockFocus()
    fg.draw(in: NSRect(x: dx, y: dy, width: size, height: size))
    out.unlockFocus()
    return out
}

render("icon_c2") { ctx in
    ringBackground(ctx)
    let fg = centeredForeground { fgCtx in drawWordC(fgCtx) }
    fg.draw(in: NSRect(x: 0, y: 0, width: size, height: size))
}

render("icon_a3") { ctx in
    auroraBackground(ctx)
    drawWordA(ctx)
}

render("icon_c3") { ctx in
    auroraBackground(ctx)
    drawWordC(ctx)
}
