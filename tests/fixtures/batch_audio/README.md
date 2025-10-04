# Batch Audio Test Directory

This directory is for testing batch audio transcription.

## Setup Instructions

To populate this directory for batch testing:

```bash
# Copy test audio file multiple times with different names
cd /Users/dylanisaac/Projects/gobbler/tests/fixtures/batch_audio

cp ../test_audio.wav sample_01.wav
cp ../test_audio.wav sample_02.wav
cp ../test_audio.wav sample_03.wav
```

Or create symlinks to save space:

```bash
ln -s ../test_audio.wav sample_01.wav
ln -s ../test_audio.wav sample_02.wav
ln -s ../test_audio.wav sample_03.wav
```

## Usage

```python
# Test batch audio transcription
batch_transcribe_directory(
    input_dir="/Users/dylanisaac/Projects/gobbler/tests/fixtures/batch_audio",
    output_dir="/tmp/batch_audio_output",
    model="small",
    skip_existing=True
)
```

## Expected Files

- `sample_01.wav` - First test audio
- `sample_02.wav` - Second test audio
- `sample_03.wav` - Third test audio
- Additional WAV/MP3/M4A files as needed
