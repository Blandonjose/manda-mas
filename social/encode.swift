// Turns a list of PNG frames into an H.264 MP4 (no ffmpeg needed; uses macOS AVFoundation).
// usage: swift encode.swift manifest.txt out.mp4
// manifest lines: "<png path>\t<seconds>". Each image crossfades into the next, and the whole video
// zooms in very slowly so it doesn't look like a static slideshow.
import AVFoundation
import CoreGraphics
import ImageIO

let args = CommandLine.arguments
let lines = try! String(contentsOfFile: args[1], encoding: .utf8).split(separator: "\n")
let scenes: [(CGImage, Double)] = lines.map { line in
    let parts = line.split(separator: "\t")
    let url = URL(fileURLWithPath: String(parts[0])) as CFURL
    let src = CGImageSourceCreateWithURL(url, nil)!
    return (CGImageSourceCreateImageAtIndex(src, 0, nil)!, Double(parts[1])!)
}
let W = 1080, H = 1920, fps = 30.0, fade = 0.35
let total = scenes.reduce(0) { $0 + $1.1 }
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
    draw(ctx, scenes[i].0, alpha: 1, zoom: zoom)
    let left = start + scenes[i].1 - t  // fade into the next image during this scene's last `fade` seconds
    if i < scenes.count - 1 && left < fade { draw(ctx, scenes[i + 1].0, alpha: CGFloat(1 - left / fade), zoom: zoom) }
    CVPixelBufferUnlockBaseAddress(pb!, [])
    adaptor.append(pb!, withPresentationTime: CMTime(value: CMTimeValue(f), timescale: CMTimeScale(fps)))
}
input.markAsFinished()
let done = DispatchSemaphore(value: 0)
writer.finishWriting { done.signal() }
done.wait()
print(writer.status == .completed ? "wrote \(args[2]) (\(String(format: "%.1f", total))s)" : "failed: \(String(describing: writer.error))")
