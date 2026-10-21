# DocSummarizer Telegram Bot

A powerful Telegram bot that summarizes documents, processes audio/video content, and supports multiple languages.

## Features

- 📚 Document summarization (PDF, DOCX, TXT)
- 🌐 Multi-language support (English, Russian, Uzbek)
- 🎤 Audio transcription
- 🎥 Video processing
- ⚙️ User settings management
- 🔄 Real-time processing


## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
GOOGLE_API_KEY=your_google_api_key
```

3. Run the bot:
```bash
python src/core/main.py
```

## Configuration

The bot uses several environment variables for configuration:
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_KEY`: Supabase API key
- `GOOGLE_API_KEY`: Google API key for Gemini model

## Features in Detail

### Document Processing
- Supports PDF, DOCX, and TXT files
- Extracts text and generates summaries
- Handles large documents with chunking

### Audio/Video Processing
- Transcribes audio files to text
- Processes video files to extract audio and text
- Supports multiple audio/video formats

### Language Support
- English (🇬🇧)
- Russian (🇷🇺)
- Uzbek (🇺🇿)

### User Management
- Language preferences
- User activity tracking
- Settings management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 