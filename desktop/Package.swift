// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "TrinetraDesktop",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(
            name: "TrinetraApp",
            targets: ["TrinetraApp"]
        )
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "TrinetraApp",
            dependencies: [],
            path: "Sources/TrinetraApp",
            resources: [
                .process("Resources")
            ]
        ),
        .testTarget(
            name: "TrinetraAppTests",
            dependencies: ["TrinetraApp"],
            path: "Tests/TrinetraAppTests"
        )
    ]
)
