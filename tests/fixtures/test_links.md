# Test Links for E2E Testing

## Single YouTube Videos

### Educational Content
- [CrashCourse AI #1: Introduction](https://www.youtube.com/watch?v=GvYYFloV0aA)
- [CrashCourse AI #2: Supervised Learning](https://www.youtube.com/watch?v=4qVRBYAdLAo)
- [How Games Do Destruction](https://www.youtube.com/watch?v=BrIeT9JBR6I)

### Short Test Videos
- [Rick Astley - Never Gonna Give You Up](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

## YouTube Playlists

- [CrashCourse AI - Full Series](https://www.youtube.com/playlist?list=PL8dPuuaLjXtO65LeD2p4_Sb5XQ51par_b)

## Web Pages

### Documentation Sites
- [Pydantic AI - Home](https://ai.pydantic.dev/)
- [Pydantic AI - Installation](https://ai.pydantic.dev/install/)
- [Pydantic AI - Models](https://ai.pydantic.dev/models/)
- [Pydantic AI - Examples](https://ai.pydantic.dev/examples/)

### Technical Articles
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Anthropic Claude Documentation](https://docs.anthropic.com/)

## Test Files (Local)

### Audio Files
- `test_audio.wav` - Sample audio for transcription testing

### Video Files
- `How_Games_Do_Destruction.mp4` - Sample video for transcription/download testing

### Document Files
- `Dylan_Isaac_Resume_AI.pdf` - PDF document for conversion testing

## Crawl Test URLs

### Small Sites (for site crawler)
- Start: https://ai.pydantic.dev/
- Max depth: 2
- Expected pages: ~20-30

## Selector Test URLs

### Pages with specific selectors
- https://ai.pydantic.dev/ (selector: `article.main`)
- https://github.com/jlowin/fastmcp (selector: `article`)
- https://docs.anthropic.com/ (selector: `.docs-content`)
