# Batch Videos Test Directory

This directory is for testing batch video downloads or transcriptions.

## Setup Instructions

This directory can be used for:

1. **Output directory for batch YouTube downloads**
2. **Source directory for batch video transcription**

### For YouTube Downloads

```python
# Download multiple videos from youtube_urls.txt
with open("../youtube_urls.txt") as f:
    urls = [line.strip() for line in f
            if line.strip() and not line.startswith("#")][:3]  # First 3 videos

for url in urls:
    download_youtube_video(
        video_url=url,
        output_dir="/Users/dylanisaac/Projects/gobbler/tests/fixtures/batch_videos",
        quality="360p"  # Use lower quality for faster testing
    )
```

### For Batch Transcription

After downloading videos, transcribe them:

```python
batch_transcribe_directory(
    input_dir="/Users/dylanisaac/Projects/gobbler/tests/fixtures/batch_videos",
    output_dir="/tmp/batch_video_transcripts",
    model="tiny",  # Use faster model for testing
    skip_existing=True
)
```

## Notes

- Keep video quality low (360p) for faster test execution
- Use "tiny" or "small" Whisper models for batch testing
- Clean up downloaded videos after testing to save space
