# pip install requests PyPDF2 pyTelegramBotAPI pdf2image

import os
import math
import telebot
from pdf2image import convert_from_path
import time
from PyPDF2 import PdfReader, PdfWriter
import threading
import requests
from urllib.parse import urlparse
import re
from datetime import datetime

# Initialize bot with your token
bot = telebot.TeleBot('BOT_TOKEN')

# Create temporary directory if it doesn't exist
if not os.path.exists('temp'):
    os.makedirs('temp')

def log_message(message, level="INFO"):
    """Log message with timestamp and level"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def is_valid_pdf_url(url):
    """Check if URL points to a PDF file"""
    try:
        log_message(f"Validating URL: {url}")
        response = requests.head(url, allow_redirects=True)
        content_type = response.headers.get('content-type', '').lower()
        is_valid = 'application/pdf' in content_type or url.lower().endswith('.pdf')
        log_message(f"URL validation result: {is_valid}")
        return is_valid
    except Exception as e:
        log_message(f"URL validation error: {str(e)}", "ERROR")
        return False

def download_file_in_chunks(url, destination):
    """Download a file in chunks with progress tracking"""
    log_message(f"Starting download from: {url}")
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    block_size = 8192
    downloaded = 0

    log_message(f"Total file size: {total_size/(1024*1024):.2f}MB")

    with open(destination, 'wb') as file:
        for data in response.iter_content(block_size):
            downloaded += len(data)
            file.write(data)
            if downloaded % (5 * 1024 * 1024) == 0:  # Log every 5MB
                log_message(f"Downloaded: {downloaded/(1024*1024):.2f}MB")
            yield downloaded, total_size

    log_message("Download completed")

def process_pdf_in_batches(pdf_path, chat_id, status_message_id, batch_size=5):
    """Process PDF pages in small batches"""
    try:
        log_message(f"Starting PDF processing: {pdf_path}")
        pdf = PdfReader(pdf_path)
        total_pages = len(pdf.pages)
        log_message(f"Total pages in PDF: {total_pages}")

        for batch_start in range(0, total_pages, batch_size):
            batch_end = min(batch_start + batch_size, total_pages)
            log_message(f"Processing batch: pages {batch_start+1} to {batch_end}")

            # Create temporary PDF for this batch
            pdf_writer = PdfWriter()
            for page_num in range(batch_start, batch_end):
                pdf_writer.add_page(pdf.pages[page_num])

            batch_pdf_path = f"{pdf_path}_batch_{batch_start}.pdf"
            with open(batch_pdf_path, 'wb') as output_file:
                pdf_writer.write(output_file)

            log_message(f"Converting batch to images")
            images = convert_from_path(batch_pdf_path)
            for i, image in enumerate(images):
                page_num = batch_start + i
                image_path = f'temp/page_{page_num}.jpg'
                image.save(image_path, 'JPEG')

                log_message(f"Sending page {page_num + 1}")
                with open(image_path, 'rb') as photo:
                    bot.send_photo(chat_id, photo, caption=f'Page {page_num + 1} of {total_pages}')

                os.remove(image_path)
                log_message(f"Deleted temporary image: {image_path}")

            os.remove(batch_pdf_path)
            log_message(f"Deleted batch PDF: {batch_pdf_path}")

            progress = min(100, int((batch_end / total_pages) * 100))
            try:
                bot.edit_message_text(
                    f"Processing: {progress}% complete ({batch_end}/{total_pages} pages)",
                    chat_id,
                    status_message_id
                )
            except:
                pass

    except Exception as e:
        log_message(f"Error in PDF processing: {str(e)}", "ERROR")
        bot.send_message(chat_id, f"Error processing PDF: {str(e)}")
        raise e

@bot.message_handler(commands=['process_url'])
def handle_url_command(message):
    try:
        log_message(f"Received URL command from user {message.from_user.id}")
        url = message.text.split(' ', 1)[1].strip()
        process_url(message, url)
    except IndexError:
        log_message(f"Invalid URL command format from user {message.from_user.id}", "WARNING")
        bot.reply_to(message, "Please provide a URL after the /process_url command.\nExample: /process_url https://example.com/file.pdf")

def process_url(message, url):
    """Process PDF from URL"""
    try:
        log_message(f"Processing URL request from user {message.from_user.id}: {url}")

        if not is_valid_pdf_url(url):
            log_message("Invalid PDF URL", "WARNING")
            bot.reply_to(message, "The URL must point to a valid PDF file.")
            return

        status_message = bot.reply_to(message, "Starting download...")
        log_message("Download started")

        timestamp = str(int(time.time()))
        pdf_path = f'temp/document_{timestamp}.pdf'

        try:
            for downloaded, total_size in download_file_in_chunks(url, pdf_path):
                progress = (downloaded / total_size * 100) if total_size else 0
                if progress % 10 == 0:  # Update every 10%
                    try:
                        bot.edit_message_text(
                            f"Downloading: {progress:.1f}% ({downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB)",
                            message.chat.id,
                            status_message.message_id
                        )
                    except:
                        pass

            log_message("Download completed, starting PDF processing")
            bot.edit_message_text(
                "Download complete. Processing PDF...",
                message.chat.id,
                status_message.message_id
            )
            process_pdf_in_batches(pdf_path, message.chat.id, status_message.message_id)

        except Exception as e:
            log_message(f"Error during processing: {str(e)}", "ERROR")
            bot.edit_message_text(
                f"Error processing file: {str(e)}",
                message.chat.id,
                status_message.message_id
            )
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                log_message(f"Cleaned up temporary file: {pdf_path}")

    except Exception as e:
        log_message(f"General error: {str(e)}", "ERROR")
        bot.reply_to(message, f"An error occurred: {str(e)}")

@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    try:
        log_message(f"Received document from user {message.from_user.id}")

        if not message.document.file_name.endswith('.pdf'):
            log_message("Non-PDF file received", "WARNING")
            bot.reply_to(message, "Please send a PDF file.")
            return

        file_size_mb = message.document.file_size / (1024 * 1024)
        log_message(f"File size: {file_size_mb:.2f}MB")

        if message.document.file_size > 20 * 1024 * 1024:
            log_message("File too large for direct upload", "WARNING")
            bot.reply_to(message, 
                "This file is larger than 20MB. Please upload it to a file hosting service "
                "and send me the direct download link using the /process_url command.\n\n"
                "Example: /process_url https://example.com/file.pdf")
            return

        status_message = bot.reply_to(message, "Processing PDF...")
        log_message("Downloading file from Telegram")
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        timestamp = str(int(time.time()))
        pdf_path = f'temp/document_{timestamp}.pdf'

        with open(pdf_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        log_message("File downloaded successfully")

        process_pdf_in_batches(pdf_path, message.chat.id, status_message.message_id)

        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            log_message("Cleaned up temporary files")

        bot.edit_message_text(
            "All pages have been sent!",
            message.chat.id,
            status_message.message_id
        )
        log_message("Processing completed successfully")

    except Exception as e:
        log_message(f"Error in handle_pdf: {str(e)}", "ERROR")
        bot.reply_to(message, f"An error occurred: {str(e)}")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    log_message(f"New user started bot: {message.from_user.id}")
    welcome_text = """
    Welcome! I can convert PDF files to images.

    You can either:
    1. Send a PDF file directly (up to 20MB)
    2. For larger files, use the /process_url command with a direct download link

    Example: /process_url https://example.com/file.pdf

    Type /help for more information.
    """
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def send_help(message):
    log_message(f"Help command requested by user {message.from_user.id}")
    help_text = """
    This bot converts PDF files to images.

    Two ways to use:
    1. Direct upload:
       - Send a PDF file up to 20MB
       - Wait for processing

    2. URL processing (for larger files):
       - Upload your PDF to a file hosting service
       - Use /process_url command with the direct download link
       Example: /process_url https://example.com/file.pdf

    Notes:
    - Large PDFs may take longer to process
    - All files are automatically deleted after processing

    Commands:
    /start - Start the bot
    /help - Show this help message
    /process_url - Process PDF from URL
    """
    bot.reply_to(message, help_text)

log_message("Bot started and ready to process PDFs")
print("\n" + "="*50)
print("Bot is running...")
print("Press Ctrl+C to stop")
print("="*50 + "\n")

# Start the bot
bot.polling()
