#!/bin/bash

# Save the current directory
CURRENT_DIR=$(pwd)

# Navigate to the desired directory
cd "/home/azzar/Downloads/project/Linux Scripting/DoH-Switcher/" || exit

# Run the Python script in the background
sudo -E python app.py &

# Wait briefly to ensure the server starts
sleep 2

# Open the default web browser to the application's URL
xdg-open "http://127.0.0.1:5003" &

# Return to the original directory
cd "$CURRENT_DIR"
