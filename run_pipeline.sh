#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p logs

# Check for required files
if [[ ! -f "config.ini" ]]; then
  echo "ERROR: config.ini is missing. Please ensure it's in the current directory."
  exit 1
fi

if [[ ! -f "requirements.txt" ]]; then
  echo "ERROR: requirements.txt is missing. Please ensure it's in the current directory."
  exit 1
fi

# Step 1: Install dependencies
echo "Installing dependencies..."
python3 -m pip install -r requirements.txt > logs/install.log 2>&1
if [[ $? -ne 0 ]]; then
  echo "ERROR: Failed to install dependencies. Check logs/install.log for details."
  exit 1
fi
echo "Dependencies installed successfully."

# Step 2: Test MySQL connection
echo "Checking MySQL connection..."
mysql -u root -pBharadwaj@mysql007 -h 192.168.0.7 -e "SHOW DATABASES;" > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
  echo "ERROR: Unable to connect to MySQL. Please ensure MySQL is running and accessible."
  exit 1
fi
echo "MySQL connection verified."

# Step 3: Run crawl_all_articles.py
echo "Running crawl_all_articles.py to crawl articles..."
python3 crawl_all_articles.py > logs/crawl_all_articles.log 2>&1
if [[ $? -ne 0 ]]; then
  echo "ERROR: crawl_all_articles.py failed. Check logs/crawl_all_articles.log for details."
  exit 1
fi
echo "crawl_all_articles.py completed successfully."

# Step 4: Run milvus_insert.py
echo "Running milvus_insert.py to insert embeddings into Milvus..."
python3 milvus_insert.py > logs/milvus_insert.log 2>&1
if [[ $? -ne 0 ]]; then
  echo "ERROR: milvus_insert.py failed. Check logs/milvus_insert.log for details."
  exit 1
fi
echo "milvus_insert.py completed successfully."

# Step 5: Run milvus_search.py
echo "Running milvus_search.py to query articles..."
python3 milvus_search.py
if [[ $? -ne 0 ]]; then
  echo "ERROR: milvus_search.py encountered an error."
  exit 1
fi
echo "Pipeline completed successfully!"
