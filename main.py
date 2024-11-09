import discord
import aiohttp
import logging
from discord.ext import commands, tasks
from flask import Flask
import threading
import socket
import os
from datetime import datetime, timedelta
import pytz

# Set up logging
logging.basicConfig(level=logging.INFO)

TOKEN = os.environ['discordtoken']
CHANNEL_ID = 1304802520677355673
URL = 'https://qa-u16-tor6.netsapiens.com/server-versions.html'

# Create an instance of the bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Create a Flask web server
app = Flask(__name__)

# Function to fetch text from a URL
async def fetch_text_from_url():
    async with aiohttp.ClientSession() as session:
        async with session.get(URL) as response:
            # Check if the request was successful
            if response.status == 200:
                # Fetch the text (you can customize this depending on the response format)
                html_content = await response.text()
                return html_content  # Keep the HTML formatting intact
            else:
                logging.error(f"Failed to fetch the URL, status code: {response.status}")
                return None

# Function to send large content in multiple messages, preserving source formatting
async def send_large_content(channel, content):
    # Calculate the maximum chunk size to account for code block formatting (6 characters)
    max_chunk_size = 2000 - 6  # 6 characters for the "```" and newlines
    chunks = [content[i:i + max_chunk_size] for i in range(0, len(content), max_chunk_size)]
    
    for chunk in chunks:
        # Send the chunk as a code block with "```" for preformatted text
        # This will preserve source formatting, such as HTML or any other raw text
        await channel.send(f"```{chunk}```")
        logging.info("Sent chunk to channel")

# Function to calculate the next occurrence of 6:30 PM UTC or 6:30 AM UTC
def get_next_time_in_utc():
    # Get the current time in UTC
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    
    # IST is UTC +5:30, so 12 AM IST = 6:30 PM UTC (previous day)
    # and 12 PM IST = 6:30 AM UTC (same day).
    
    # Set up target times
    target_times_utc = [
        utc_now.replace(hour=18, minute=30, second=0, microsecond=0),  # 6:30 PM UTC (previous day of 12 AM IST)
        utc_now.replace(hour=6, minute=30, second=0, microsecond=0),   # 6:30 AM UTC (same day of 12 PM IST)
    ]
    
    # If the current time is past 6:30 PM, schedule it for tomorrow's 6:30 PM UTC
    if utc_now > target_times_utc[0]:
        target_times_utc[0] += timedelta(days=1)
    # If the current time is past 6:30 AM, schedule it for tomorrow's 6:30 AM UTC
    if utc_now > target_times_utc[1]:
        target_times_utc[1] += timedelta(days=1)

    return target_times_utc

# Task that will run every day at 12 AM IST and 12 PM IST (converted to 6:30 PM UTC and 6:30 AM UTC)
@tasks.loop(hours=24)
async def copy_text_to_channel():
    # Get the next scheduled time in UTC
    next_run_times = get_next_time_in_utc()
    
    # Calculate the time difference until the next run
    now = datetime.utcnow().replace(tzinfo=pytz.utc)
    delay = (next_run_times[0] - now).total_seconds()  # Next 6:30 PM UTC
    
    if delay <= 0:
        delay = (next_run_times[1] - now).total_seconds()  # Next 6:30 AM UTC

    # Wait until the calculated time
    await asyncio.sleep(delay)

    # Fetch text and send it to the Discord channel
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        logging.error(f"Channel with ID {CHANNEL_ID} not found.")
        return

    text = await fetch_text_from_url()
    if text:
        await send_large_content(channel, text)
        logging.info(f"Sent text to channel {CHANNEL_ID}")
    else:
        logging.error(f"Failed to fetch text from the URL")

# Event when the bot starts
@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user}")
    # Start the task when the bot is ready
    copy_text_to_channel.start()

# Flask route to keep the web server alive
@app.route('/')
def index():
    return "Bot is running", 200

# Function to get the public URL of the Flask server
def get_flask_url():
    port = 8080  # Port is set to 8080
    try:
        # Get the local IP address (this will work for local and external access)
        local_ip = socket.gethostbyname(socket.gethostname())
        return f'http://{local_ip}:{port}/'
    except Exception as e:
        logging.error(f"Error determining public URL: {e}")
        # Default to localhost if we can't find the local IP
        return f'http://localhost:{port}/'

# Function to run the Flask app in a separate thread
def run_flask():
    port = 8080  # Port is set to 8080
    try:
        logging.info("Starting Flask app...")
        # Start the Flask app
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logging.error(f"Error starting Flask server: {e}")

# Run the bot and Flask app in parallel
def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    # Get the URL and print it
    flask_url = get_flask_url()
    logging.info(f"Flask app is running at: {flask_url}")
    
    # Start Flask in a separate thread to keep it running alongside the bot
    threading.Thread(target=run_flask).start()

    # Start the Discord bot
    run_bot()
