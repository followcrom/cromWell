#!/bin/bash

# CromWell - Fitbit Data Sync and Streamlit Launcher
# Usage: Add alias to your ~/.bashrc or ~/.zshrc:
#   alias cromwell='/home/followcrom/projects/cromWell/cromwell.sh'

set -e  # Exit on error

# Color codes for better terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  CromWell - Well up for it!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Navigate to project directory
echo -e "${GREEN}[1/8]${NC} Navigating to cromWell project directory..."
cd /home/followcrom/projects/cromWell
echo -e "      Current directory: $(pwd)"
echo ""

# Activate virtual environment
echo -e "${GREEN}[2/8]${NC} Activating Python virtual environment..."
source cw_venv/bin/activate
echo -e "      Virtual environment activated: ${VIRTUAL_ENV}"
echo ""

# Navigate to data_tools directory
echo -e "${GREEN}[3/8]${NC} Moving to data_tools directory..."
cd data_tools
echo -e "      Current directory: $(pwd)"
echo ""

# Check for new files (dry-run)
echo -e "${GREEN}[4/8]${NC} Checking for new files from S3 (dry-run mode)..."
echo -e "${YELLOW}--------------------------------------${NC}"
SYNC_OUTPUT=$(python sync_from_s3.py --dry-run 2>&1)
echo "$SYNC_OUTPUT"
echo -e "${YELLOW}--------------------------------------${NC}"
echo ""

# Check if already up to date
if echo "$SYNC_OUTPUT" | grep -q "No new files to download - already up to date!"; then
    echo -e "${GREEN}✓ All data is up to date!${NC}"
    echo -e "${BLUE}Do you want to proceed to launch Streamlit anyway?${NC}"
    read -p "Enter [y/N] and press Enter: " -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Exiting. Run 'cromwell' again when you're ready.${NC}"
        exit 0
    fi
    # Skip to cleanup and streamlit launch
    SKIP_UPDATE=true
else
    # Ask user if they want to download new files
    echo -e "${BLUE}Do you want to download new files and update Fitbit data?${NC}"
    read -p "Enter [y/N] and press Enter: " -r
    echo ""
    SKIP_UPDATE=false
fi

if [[ $SKIP_UPDATE == false ]]; then
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}[5/8]${NC} Downloading new files and updating Fitbit data..."
        echo -e "${YELLOW}--------------------------------------${NC}"
        ./update_fitbit_data.sh
        echo -e "${YELLOW}--------------------------------------${NC}"
        echo ""

        # Verify sync status after update
        echo -e "${GREEN}[6/8]${NC} Verifying sync status (checking we're up to date)..."
        echo -e "${YELLOW}--------------------------------------${NC}"
        python sync_from_s3.py --dry-run
        echo -e "${YELLOW}--------------------------------------${NC}"
        echo ""
    else
        echo -e "${YELLOW}Skipping download and update steps.${NC}"
        echo ""
    fi
else
    echo -e "${YELLOW}Skipping download and update steps (already up to date).${NC}"
    echo ""
fi

# Navigate to data directory and clean up
echo -e "${GREEN}[7/8]${NC} Navigating to data directory and cleaning up..."
cd ../data
echo -e "      Current directory: $(pwd)"
echo -e "      Removing json.gz files..."
find . -name "*.json.gz" -type f -delete 2>/dev/null && echo "      Json.gz files deleted." || echo "      No json.gz files found."
echo ""

# Launch Streamlit
echo -e "${GREEN}[8/8]${NC} Launching Streamlit application..."
echo -e "${BLUE}--------------------------------------${NC}"
echo -e "${BLUE}  Starting Streamlit on localhost:8501${NC}"
echo -e "${BLUE}--------------------------------------${NC}"
echo ""

# cd into dashboard directory first
cd ../dashboard

# Start Streamlit in the background
streamlit run app.py &
STREAMLIT_PID=$!

# Wait for Streamlit to be ready (check if port 8501 is listening)
echo -e "${YELLOW}Waiting for Streamlit to start...${NC}"
for i in {1..10}; do
    if nc -z localhost 8501 2>/dev/null || lsof -i:8501 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Streamlit is ready!${NC}"
        break
    fi
    sleep 1
done

# Now open Chrome browser
echo -e "${YELLOW}Opening Chrome browser...${NC}"
# WSL - Windows Chrome (prioritized for your environment)
if [ -f "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" ]; then
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" http://localhost:8501 2>/dev/null &
    echo -e "${GREEN}✓ Chrome launched!${NC}"
elif command -v google-chrome &> /dev/null; then
    google-chrome http://localhost:8501 2>/dev/null &
    echo -e "${GREEN}✓ Chrome launched!${NC}"
elif command -v chromium-browser &> /dev/null; then
    chromium-browser http://localhost:8501 2>/dev/null &
    echo -e "${GREEN}✓ Chromium launched!${NC}"
else
    echo -e "${YELLOW}Chrome not found. Please open http://localhost:8501 in your browser${NC}"
fi

echo ""
echo -e "${GREEN}✓ All done! Streamlit is running.${NC}"
echo -e "${BLUE}Press Ctrl+C to stop the server${NC}"
echo ""

# Keep the script running and wait for Streamlit process
wait $STREAMLIT_PID