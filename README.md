
# 📄 PDFusion Documentation

## Overview
PDFusion is a versatile Telegram bot that makes PDF handling easier through a simple interface. It offers multiple PDF-related features including PDF to image conversion, image to PDF creation, and text to PDF conversion.

## Features

### 📂 PDF to Image Conversion
- Accept PDF files directly (up to 20MB)
- Process PDF files from URLs (any size)
- Convert PDF pages to high-quality images
- Send converted images in real-time
- Process large PDFs in batches for efficient handling

### 🖼️ Image to PDF Creation
- Convert multiple images into a single PDF document
- Optional page ordering functionality
- Simple interactive workflow
- Session-based approach for better organization

### 📝 Text to PDF Creation
- Convert text messages to formatted PDF files
- Support for both English and Persian text
- Right-to-left text handling for Arabic/Persian script
- Multi-message support for longer documents

## Technical Implementation

### Core Components
1. **Error Handling System**
   - Safe polling mechanism to maintain bot uptime
   - Decorator pattern for function-level error management

2. **PDF Processing Engine**
   - Batch processing to handle large documents
   - Chunked downloading for better user experience
   - Progress updates during processing

3. **Session Management**
   - Stateful conversations for multi-step operations
   - Clean cancellation capabilities

4. **File Management**
   - Automatic temporary file cleanup
   - Organized file naming conventions

## Command List

| Command | Description |
|---------|-------------|
| `/start` | Initiates the bot and displays welcome message |
| `/help` | Shows complete usage instructions |
| `/process_url` | Processes a PDF from a URL |
| `/start_create_pdf` | Begins image-to-PDF creation session |
| `/done` | Finalizes image-to-PDF creation |
| `/cancel_create_pdf` | Cancels image-to-PDF session |
| `/start_text_pdf` | Begins text-to-PDF creation session |
| `/done_text_pdf` | Finalizes text-to-PDF creation |
| `/cancel_text_pdf` | Cancels text-to-PDF session |


## Dependencies
- `telebot`: Telegram Bot API interface
- `PyPDF2`: PDF manipulation
- `pdf2image`: PDF to image conversion
- `requests`: HTTP requests for URL handling
- `PIL/Pillow`: Image processing
- `fpdf`: PDF creation
- `arabic-reshaper` & `python-bidi`: RTL text support

## Implementation Highlights
- Asynchronous processing for better performance
- Comprehensive logging system
- User-friendly error messages
- Progress reporting during long operations
- Stateful conversation handling
- Automatic resource cleanup
