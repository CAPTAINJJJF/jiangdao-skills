#!/usr/bin/env swift

import AppKit
import Foundation
import Vision

func cgImage(from path: String) -> CGImage? {
    guard let image = NSImage(contentsOfFile: path) else { return nil }
    var rect = NSRect(origin: .zero, size: image.size)
    return image.cgImage(forProposedRect: &rect, context: nil, hints: nil)
}

var arguments = Array(CommandLine.arguments.dropFirst())
var outputPath: String?
if arguments.count >= 2, arguments[0] == "--output" {
    outputPath = arguments[1]
    arguments.removeFirst(2)
}
let paths = arguments
guard !paths.isEmpty else {
    FileHandle.standardError.write(Data("usage: ocr-images.swift [--output <file>] <image> [...]\n".utf8))
    exit(2)
}

var output: [String] = []
for path in paths {
    output.append("===IMAGE:\(path)===")
    guard let image = cgImage(from: path) else {
        output.append("[OCR_ERROR] image_unreadable")
        continue
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["zh-Hans", "en-US"]

    do {
        try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
        let observations = (request.results ?? []).sorted { left, right in
            let yDelta = left.boundingBox.midY - right.boundingBox.midY
            if abs(yDelta) > 0.015 { return yDelta > 0 }
            return left.boundingBox.minX < right.boundingBox.minX
        }
        for observation in observations {
            if let text = observation.topCandidates(1).first?.string,
               !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                output.append(text)
            }
        }
    } catch {
        output.append("[OCR_ERROR] \(error.localizedDescription)")
    }
}

let rendered = output.joined(separator: "\n") + "\n"
if let outputPath {
    try rendered.write(toFile: outputPath, atomically: true, encoding: .utf8)
} else {
    print(rendered, terminator: "")
}
