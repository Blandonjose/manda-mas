// Turns a list of PNG frames into an H.264 MP4 (no ffmpeg needed; uses macOS AVFoundation).
// usage: swift encode.swift manifest.txt out.mp4
// manifest lines: "<png path>\t<seconds>[\t<background mp4>]". Each image crossfades into the next, and the
// whole video zooms in very slowly so it doesn't look like a static slideshow.
// With a background mp4 (stock footage), that clip plays behind the image (which then has a transparent
// background), cropped to fill the vertical frame and darkened a little so the text stays readable.
// Consecutive lines with the same clip keep playing it; a clip that runs out starts again.
import AVFoundation
import CoreGraphics
import CoreImage
import ImageIO

let args = CommandLine.arguments
let lines = try! String(contentsOfFile: args[1], encoding: .utf8).split(separator: "\n")
let scenes: [(CGImage, Double, String?)] = lines.map { line in
    let parts = line.split(separator: "\t")
    let url = URL(fileURLWithPath: String(parts[0])) as CFURL
    let src = CGImageSourceCreateWithURL(url, nil)!
    return (CGImageSourceCreateImageAtIndex(src, 0, nil)!, Double(parts[1])!, parts.count > 2 ? String(parts[2]) : nil)
}

// Plays one background clip frame by frame (transform applied, so portrait phone clips come out upright).
final class Clip {
    let path: String
    var reader: AVAssetReader!
    var output: AVAssetReaderOutput!
    var last: CGImage?
    var lastTime = -1.0
    var offset = 0.0  // where the current loop started, in clip-local time
    static let ci = CIContext()
    init(_ path: String) { self.path = path; open() }
    func open() {
        let asset = AVURLAsset(url: URL(fileURLWithPath: path))
        reader = try! AVAssetReader(asset: asset)
        let vc = AVVideoComposition(propertiesOf: asset)
        let o = AVAssetReaderVideoCompositionOutput(videoTracks: asset.tracks(withMediaType: .video),
                                                    videoSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
        o.videoComposition = vc
        reader.add(o)
        output = o
        reader.startReading()
    }
    // The frame showing at `t` seconds since this clip started playing.
    func frame(_ t: Double) -> CGImage? {
        while lastTime + offset < t || last == nil {
            guard let s = output.copyNextSampleBuffer(), let pb = CMSampleBufferGetImageBuffer(s) else {
                if last == nil { return nil }  // unreadable clip
                offset += max(lastTime, 0.1)   // loop
                lastTime = -1
                open()
                continue
            }
            lastTime = CMSampleBufferGetPresentationTimeStamp(s).seconds
            last = Clip.ci.createCGImage(CIImage(cvPixelBuffer: pb), from: CIImage(cvPixelBuffer: pb).extent)
        }
        return last
    }
}
var clips: [String: Clip] = [:]
var clipStart: [String: Double] = [:]
let W = 1080, H = 1920, fps = 30.0, fade = 0.35
let total = scenes.reduce(0) { $0 + $1.1 }
var t0 = 0.0
for s in scenes { if let p = s.2, clipStart[p] == nil { clipStart[p] = t0; clips[p] = Clip(p) }; t0 += s.1 }

func drawFill(_ ctx: CGContext, _ img: CGImage, zoom: CGFloat) {  // cover the frame, centered
    let k = max(CGFloat(W) / CGFloat(img.width), CGFloat(H) / CGFloat(img.height)) * zoom
    let w = CGFloat(img.width) * k, h = CGFloat(img.height) * k
    ctx.setAlpha(1)
    ctx.draw(img, in: CGRect(x: (CGFloat(W) - w) / 2, y: (CGFloat(H) - h) / 2, width: w, height: h))
    ctx.setFillColor(CGColor(red: 0.03, green: 0.09, blue: 0.2, alpha: 0.28))
    ctx.fill(CGRect(x: 0, y: 0, width: W, height: H))
}
let out = URL(fileURLWithPath: args[2])
try? FileManager.default.removeItem(at: out)
let writer = try! AVAssetWriter(outputURL: out, fileType: .mp4)
let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
    AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: W, AVVideoHeightKey: H,
    AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 8_000_000, AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel],
])
let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB, kCVPixelBufferWidthKey as String: W, kCVPixelBufferHeightKey as String: H,
])
writer.add(input)
writer.startWriting()
writer.startSession(atSourceTime: .zero)

func draw(_ ctx: CGContext, _ img: CGImage, alpha: CGFloat, zoom: CGFloat) {
    ctx.setAlpha(alpha)
    let w = CGFloat(W) * zoom, h = CGFloat(H) * zoom
    ctx.draw(img, in: CGRect(x: (CGFloat(W) - w) / 2, y: (CGFloat(H) - h) / 2, width: w, height: h))
}

let frames = Int(total * fps)
for f in 0..<frames {
    let t = Double(f) / fps
    var start = 0.0, i = 0
    while i < scenes.count - 1 && t >= start + scenes[i].1 { start += scenes[i].1; i += 1 }
    let zoom = CGFloat(1.0 + 0.05 * t / total)
    while !input.isReadyForMoreMediaData { usleep(2000) }
    var pb: CVPixelBuffer?
    CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &pb)
    CVPixelBufferLockBaseAddress(pb!, [])
    let ctx = CGContext(data: CVPixelBufferGetBaseAddress(pb!), width: W, height: H, bitsPerComponent: 8,
                        bytesPerRow: CVPixelBufferGetBytesPerRow(pb!), space: CGColorSpaceCreateDeviceRGB(),
                        bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue)!
    ctx.interpolationQuality = .high
    if let p = scenes[i].2, let img = clips[p]!.frame(t - clipStart[p]!) {
        drawFill(ctx, img, zoom: zoom)
        draw(ctx, scenes[i].0, alpha: 1, zoom: 1)
    } else {
        draw(ctx, scenes[i].0, alpha: 1, zoom: zoom)
    }
    let left = start + scenes[i].1 - t  // fade into the next image during this scene's last `fade` seconds
    if i < scenes.count - 1 && left < fade {
        let next = scenes[i + 1]
        if let p = next.2, p != scenes[i].2, let img = clips[p]!.frame(0) {  // new clip fades in under the text
            ctx.setAlpha(CGFloat(1 - left / fade)); ctx.beginTransparencyLayer(auxiliaryInfo: nil)
            drawFill(ctx, img, zoom: zoom); ctx.endTransparencyLayer()
        }
        draw(ctx, next.0, alpha: CGFloat(1 - left / fade), zoom: next.2 == nil ? zoom : 1)
    }
    CVPixelBufferUnlockBaseAddress(pb!, [])
    adaptor.append(pb!, withPresentationTime: CMTime(value: CMTimeValue(f), timescale: CMTimeScale(fps)))
}
input.markAsFinished()
let done = DispatchSemaphore(value: 0)
writer.finishWriting { done.signal() }
done.wait()
print(writer.status == .completed ? "wrote \(args[2]) (\(String(format: "%.1f", total))s)" : "failed: \(String(describing: writer.error))")
