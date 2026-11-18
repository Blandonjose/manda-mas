// Put narration clips on a silent video without re-encoding the picture.
// usage: swift mux.swift silent.mp4 out.mp4 clip1.aiff START1 [clip2.aiff START2 ...]   (START in seconds)
import AVFoundation

let a = CommandLine.arguments
let video = AVURLAsset(url: URL(fileURLWithPath: a[1]))
let out = URL(fileURLWithPath: a[2])
try? FileManager.default.removeItem(at: out)
let comp = AVMutableComposition()
let total = video.duration
let vSrc = video.tracks(withMediaType: .video)[0]
let vDst = comp.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid)!
try! vDst.insertTimeRange(CMTimeRange(start: .zero, duration: total), of: vSrc, at: .zero)
let aDst = comp.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)!
var i = 3
while i + 1 < a.count {
    let clip = AVURLAsset(url: URL(fileURLWithPath: a[i]))
    let start = CMTime(seconds: Double(a[i + 1])!, preferredTimescale: 600)
    var dur = clip.duration
    if CMTimeAdd(start, dur) > total { dur = CMTimeSubtract(total, start) }  // never run past the picture
    if dur > .zero, let src = clip.tracks(withMediaType: .audio).first {
        try! aDst.insertTimeRange(CMTimeRange(start: .zero, duration: dur), of: src, at: start)
    }
    i += 2
}
// HighestQuality transcodes the AIFF narration to an MP4-compatible audio
// stream. Passthrough cannot mux uncompressed AIFF audio into an MP4.
let export = AVAssetExportSession(asset: comp, presetName: AVAssetExportPresetHighestQuality)!
export.outputURL = out
export.outputFileType = .mp4
export.shouldOptimizeForNetworkUse = true  // moov first ("faststart"), safer for uploads
let done = DispatchSemaphore(value: 0)
export.exportAsynchronously { done.signal() }
done.wait()
if export.status != .completed {
    FileHandle.standardError.write("mux failed: \(String(describing: export.error))\n".data(using: .utf8)!)
    exit(1)
}
