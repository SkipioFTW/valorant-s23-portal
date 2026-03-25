FROM python:3.9-slim

WORKDIR /app

# Install git and system dependencies
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY . .

# Copy shared scripts (needed for scraper)
# Note: In production build, we need to make sure the context includes the root
# For now, we assume this Dockerfile is run with the repo root as context
# or we copy the specific needed files if they are outside this dir.
# Since this files IS inside bots/discord_bot, we will likely need to adjust the COPY
# during deployment or copy the 'scripts' folder into this folder.
# FOR NOW: We will assume the bot references `scripts` from the root if mounted,
# or we need to copy them.
# BETTER APPROACH for contained bot: Copy the needed scraper file INTO the bot dir
# during build or import it.

CMD ["python", "main.py"]
