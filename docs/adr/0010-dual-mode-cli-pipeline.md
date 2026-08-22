# 0010. Dual-Mode CLI Pipeline: Native Audio Extraction and Offline JSON Compilation

We decided that the CLI interface will expose two operational modes:
1. `analyze <audio>`: Executes native CLI extractors on audio files, providing clear diagnostic hints if dependencies are missing.
2. `build-ir --allin1 <path> --essentia <path>`: Pure offline evidence compilation that generates JAMS and Music IR from existing JSON fixtures without C++ or PyTorch dependencies.
This guarantees 100% testability across CI/CD and developer environments.
