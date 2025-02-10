# pip install requests PyPDF2 pyTelegramBotAPI pdf2image Pillow fpdf arabic-reshaper python-bidi

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
from PIL import Image
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display

# Initialize bot with your token
bot = telebot.TeleBot('7354040523:AAEv0KorMBV6r09fpQGFpxwK2FVbeokta_Q')

# Create temporary directory if it doesn't exist
if not os.path.exists('temp'):
    os.makedirs('temp')

def log_message(message, level="INFO"):
    """Log message with timestamp and level"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

# ----------------------------------------------------
# 1. Global Safe Polling: Restart polling if an error occurs.
# ----------------------------------------------------
def safe_polling():
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            log_message(f"Polling error: {str(e)}", level="ERROR")
            time.sleep(5)  # Wait a bit before restarting

# ----------------------------------------------------
# 2. Safe Execution Decorator: Wrap functions so they log errors and continue.
# ----------------------------------------------------
def safe_execution(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log_message(f"Error in {func.__name__}: {e}", level="ERROR")
    return wrapper

# ---------------------------
# Existing Functions for PDF processing
# ---------------------------
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

            log_message("Converting batch to images")
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
            except Exception as e:
                log_message(f"Error updating progress: {e}", level="ERROR")

    except Exception as e:
        log_message(f"Error in PDF processing: {str(e)}", "ERROR")
        bot.send_message(chat_id, f"Error processing PDF: {str(e)}")

@bot.message_handler(commands=['process_url'])
@safe_execution
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
                    except Exception as e:
                        log_message(f"Error updating download progress: {e}", level="ERROR")

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
@safe_execution
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
@safe_execution
def send_welcome(message):
    log_message(f"New user started bot: {message.from_user.id}")
    welcome_text = """
🔥 PDF Tools Bot – Your Ultimate PDF Assistant!🔥  

📌 Features:

📂 Convert PDF to Images:
✅ Upload PDFs (Max: 20MB)📤  
✅ Use /process_url for larger files 🌐

🖼️ Convert Images to PDF:  
1️⃣ Start with /start_create_pdf 🏁  
2️⃣ Send images 📸 & optionally specify page numbers 🔢  
3️⃣ Finish with /done to get your PDF 🎉  
4️⃣ Cancel anytime with /cancel_create_pdf ❌  

📝 Convert Text to PDF:
1️⃣ Begin with /start_text_pdf ✍️  
2️⃣ Send your text messages (multiple messages allowed) 💬  
3️⃣ Type /done_text_pdf to generate your PDF 📜  
4️⃣ Cancel with /cancel_text_pdf ❌  


💡 ommands:
/start | /help | /process_url | /start_create_pdf | /done | /cancel_create_pdf  
/start_text_pdf | /done_text_pdf | /cancel_text_pdf  

Enjoy seamless PDF management! 🚀
"""
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
@safe_execution
def send_help(message):
    log_message(f"Help command requested by user {message.from_user.id}")
    help_text = """
🔥 PDF Tools Bot – Your Ultimate PDF Assistant!🔥  

📌 Features:

📂 Convert PDF to Images:
✅ Upload PDFs (Max: 20MB)📤  
✅ Use /process_url for larger files 🌐

🖼️ Convert Images to PDF:  
1️⃣ Start with /start_create_pdf 🏁  
2️⃣ Send images 📸 & optionally specify page numbers 🔢  
3️⃣ Finish with /done to get your PDF 🎉  
4️⃣ Cancel anytime with /cancel_create_pdf ❌  

📝 Convert Text to PDF:
1️⃣ Begin with /start_text_pdf ✍️  
2️⃣ Send your text messages (multiple messages allowed) 💬  
3️⃣ Type /done_text_pdf to generate your PDF 📜  
4️⃣ Cancel with /cancel_text_pdf ❌  


💡 ommands:
/start | /help | /process_url | /start_create_pdf | /done | /cancel_create_pdf  
/start_text_pdf | /done_text_pdf | /cancel_text_pdf  

Enjoy seamless PDF management! 🚀
"""
    bot.reply_to(message, help_text)

# ---------------------------
# New Code: Image to PDF Creation
# ---------------------------
# Dictionary to keep track of PDF creation sessions for images.
# Key: chat_id, Value: list of image info dictionaries: {'file_id': ..., 'page_number': ...}
pdf_creation_sessions = {}

@bot.message_handler(commands=['start_create_pdf'])
@safe_execution
def start_create_pdf(message):
    chat_id = message.chat.id
    pdf_creation_sessions[chat_id] = []  # start a new session
    bot.send_message(chat_id, "Image-to-PDF session started.\nPlease send me the image you want to add to your PDF.")
    bot.register_next_step_handler(message, process_image_for_pdf)

@safe_execution
def process_image_for_pdf(message):
    chat_id = message.chat.id
    if chat_id not in pdf_creation_sessions:
        return

    # Allow finishing the session by sending '/done'
    if message.content_type == 'text' and message.text.strip() == '/done':
        finish_pdf_creation(message)
        return

    if message.content_type != 'photo':
        msg = bot.send_message(chat_id, "That doesn't look like a photo. Please send an image (or type /done to finish).")
        bot.register_next_step_handler(msg, process_image_for_pdf)
        return

    file_id = message.photo[-1].file_id
    msg = bot.send_message(chat_id, "Enter the page number for this image (or type 'skip' for default order, or /done to finish):")
    bot.register_next_step_handler(msg, process_page_number, file_id)

@safe_execution
def process_page_number(message, file_id):
    chat_id = message.chat.id
    if message.text.strip() == '/done':
        finish_pdf_creation(message)
        return

    text = message.text.strip()
    page_number = None
    if text.lower() != 'skip':
        try:
            page_number = int(text)
        except ValueError:
            bot.send_message(chat_id, "Invalid input for page number. The image will use the default order.")
            page_number = None

    pdf_creation_sessions[chat_id].append({'file_id': file_id, 'page_number': page_number})
    msg = bot.send_message(chat_id, "Image added. Send another image or type /done to finish PDF creation.")
    bot.register_next_step_handler(msg, process_image_for_pdf)

@bot.message_handler(commands=['done'])
@safe_execution
def finish_pdf_creation(message):
    chat_id = message.chat.id
    if chat_id not in pdf_creation_sessions or len(pdf_creation_sessions[chat_id]) == 0:
        bot.reply_to(message, "No images received for PDF creation. Start with /start_create_pdf.")
        return
    bot.send_message(chat_id, "Finishing image-to-PDF creation. Please wait...")
    images_info = pdf_creation_sessions[chat_id]
    images_info_sorted = sorted(images_info, key=lambda info: info['page_number'] if info['page_number'] is not None else float('inf'))
    
    image_list = []
    temp_files = []
    for idx, info in enumerate(images_info_sorted):
        try:
            file_info = bot.get_file(info['file_id'])
            downloaded_file = bot.download_file(file_info.file_path)
            temp_image_path = f"temp/pdf_image_{chat_id}_{idx}.jpg"
            with open(temp_image_path, 'wb') as f:
                f.write(downloaded_file)
            temp_files.append(temp_image_path)
            img = Image.open(temp_image_path).convert('RGB')
            image_list.append(img)
        except Exception as e:
            log_message(f"Error downloading image for PDF: {str(e)}", "ERROR")
            bot.send_message(chat_id, f"Error processing one of the images: {str(e)}")
    
    if len(image_list) == 0:
        bot.send_message(chat_id, "No valid images were received to create a PDF.")
        return

    pdf_path = f"temp/created_pdf_{chat_id}_{int(time.time())}.pdf"
    try:
        first_image = image_list[0]
        if len(image_list) > 1:
            first_image.save(pdf_path, "PDF", resolution=100.0, save_all=True, append_images=image_list[1:])
        else:
            first_image.save(pdf_path, "PDF", resolution=100.0)
        bot.send_document(chat_id, open(pdf_path, 'rb'), caption="Here is your image PDF file.")
        log_message(f"PDF created and sent to user {chat_id}")
    except Exception as e:
        log_message(f"Error creating PDF: {str(e)}", "ERROR")
        bot.send_message(chat_id, f"Error creating PDF: {str(e)}")
    finally:
        for path in temp_files:
            if os.path.exists(path):
                os.remove(path)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        del pdf_creation_sessions[chat_id]

@bot.message_handler(commands=['cancel_create_pdf'])
@safe_execution
def cancel_pdf_creation(message):
    chat_id = message.chat.id
    if chat_id in pdf_creation_sessions:
        del pdf_creation_sessions[chat_id]
        bot.reply_to(message, "Image-to-PDF session cancelled.")
    else:
        bot.reply_to(message, "No active image-to-PDF session found.")

@bot.message_handler(content_types=['photo'])
@safe_execution
def handle_photo_in_general(message):
    chat_id = message.chat.id
    if chat_id not in pdf_creation_sessions:
        bot.reply_to(message, "To create a PDF from images, please start a session with /start_create_pdf.")

# ---------------------------
# New Code: Text to PDF Creation
# ---------------------------
# Dictionary to keep track of text-to-PDF sessions.
# Key: chat_id, Value: list of text strings (each message)
text_pdf_sessions = {}

@bot.message_handler(commands=['start_text_pdf'])
@safe_execution
def start_text_pdf(message):
    chat_id = message.chat.id
    text_pdf_sessions[chat_id] = []  # start a new text session
    bot.send_message(chat_id, "Text-to-PDF session started.\nPlease send me your text (English or Persian). You may send multiple messages. When finished, type /done_text_pdf.")
    bot.register_next_step_handler(message, process_text_for_pdf)

@safe_execution
def process_text_for_pdf(message):
    chat_id = message.chat.id
    if message.text.strip() == '/done_text_pdf':
        finish_text_pdf(message)
        return
    if chat_id not in text_pdf_sessions:
        bot.send_message(chat_id, "No active text session found. Start with /start_text_pdf.")
        return
    text_pdf_sessions[chat_id].append(message.text)
    bot.send_message(chat_id, "Text added. Send more text or type /done_text_pdf to finish.")
    bot.register_next_step_handler(message, process_text_for_pdf)

@bot.message_handler(commands=['done_text_pdf'])
@safe_execution
def finish_text_pdf(message):
    chat_id = message.chat.id
    if chat_id not in text_pdf_sessions or len(text_pdf_sessions[chat_id]) == 0:
        bot.reply_to(message, "No text received for PDF creation. Start with /start_text_pdf.")
        return
    bot.send_message(chat_id, "Finishing text-to-PDF creation. Please wait...")
    text_lines = text_pdf_sessions[chat_id]
    pdf_path = create_text_pdf(text_lines, chat_id)
    bot.send_document(chat_id, open(pdf_path, 'rb'), caption="Here is your text PDF file.")
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    del text_pdf_sessions[chat_id]

@bot.message_handler(commands=['cancel_text_pdf'])
@safe_execution
def cancel_text_pdf(message):
    chat_id = message.chat.id
    if chat_id in text_pdf_sessions:
        del text_pdf_sessions[chat_id]
        bot.reply_to(message, "Text-to-PDF session cancelled.")
    else:
        bot.reply_to(message, "No active text-to-PDF session found.")

def create_text_pdf(text_lines, chat_id):
    """
    Create a PDF from the given list of text lines.
    This function uses Vazir.ttf (which supports both English and Persian).
    Make sure the Vazir.ttf file is in the same directory as the script.
    """
    pdf = FPDF()
    pdf.add_page()
    # Register the Vazir font (ensure Vazir.ttf is available)
    pdf.add_font('Vazir', '', 'Vazir.ttf', uni=True)
    pdf.set_font('Vazir', '', 14)
    
    for line in text_lines:
        # If the line contains Persian characters, reshape and reorder it
        if any('\u0600' <= char <= '\u06FF' for char in line):
            reshaped_text = arabic_reshaper.reshape(line)
            bidi_text = get_display(reshaped_text)
            # Use right alignment for Persian text
            line_to_print = bidi_text
            align = 'R'
        else:
            line_to_print = line
            align = 'L'
        pdf.multi_cell(0, 10, line_to_print, align=align)
        pdf.ln(5)
    
    pdf_path = f"temp/text_pdf_{chat_id}_{int(time.time())}.pdf"
    pdf.output(pdf_path)
    return pdf_path
# ---------------------------
# End of New Code: Text to PDF Creation
# ---------------------------

log_message("Bot started and ready to process PDFs, images, and text")
print("\n" + "="*50)
print("Bot is running...")
print("Press Ctrl+C to stop")
print("="*50 + "\n")

# Remove any active webhook
bot.remove_webhook()

# Start polling in a safe mode so errors don't stop the bot.
safe_polling()
