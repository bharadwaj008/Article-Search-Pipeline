# Article-Search-Pipeline
This project is a complete pipeline for crawling, storing, embedding, and querying articles related to oncology. It leverages MySQL for relational storage, Milvus for vector-based search, and Selenium for dynamic web scraping.

## Features
Dynamic Web Crawling:

Scrapes articles related to oncology from Nature.
Extracts titles, authors, abstracts, publication dates, and generates keywords.
Relational Storage:

Stores extracted data in a MySQL database.
Vector-Based Search:

Embeds article titles, abstracts, and summaries using SentenceTransformers.
Stores embeddings in Milvus for efficient similarity search.
Free-Text Querying:

Allows users to search articles using natural language (e.g., "give me articles related to surgery").
Supports additional filters like date ranges.
Export Functionality:

Exports query results to a CSV file for further analysis.

## Requirements

1. Software Dependencies
MySQL (Installed on Windows):
Ensure MySQL is running and accessible from WSL.
Milvus (Docker or Standalone):
Use Docker to start Milvus.
Python (3.8+):
Required for all scripts.


2. Python Libraries
Install the required Python libraries:

bash
Copy code
pip install -r requirements.txt

### Setup Instructions
1. Clone the Repository
bash
Copy code
git clone <repository_url>
cd run_pipeline

2. Configure config.ini
Update config.ini with the correct configurations for MySQL, Milvus, and Selenium:

[mysql]
host = 192.168.0.7
user = root
password = YourMySQLPassword
database = oncology_data

[milvus]
host = localhost
port = 19530
collection_name = article_embeddings

[selenium]
chromedriver_path = /mnt/d/path-to-your-chromedriver/chromedriver
3. Ensure MySQL and Milvus Are Running
MySQL: Start the MySQL service on Windows:
cmd
net start MySQL
Milvus: Start the Milvus container using Docker:
bash
Copy code
docker run -d --name milvus-standalone -p 19530:19530 milvusdb/milvus:v2.2.0
Pipeline Execution
Run the entire pipeline with the shell script:

bash
Copy code
./run_pipeline.sh
Script Details
1. crawl_all_articles.py
Scrapes articles and inserts them into MySQL.
Generates keywords using sklearn.
2. milvus_insert.py
Embeds article data (title, abstract, summary) using SentenceTransformers.
Stores embeddings in Milvus.
3. milvus_search.py
Allows natural language queries to find related articles.
Supports exporting results to a CSV file.
Usage Example
Run the Pipeline:

bash
Copy code
./run_pipeline.sh
Search for Articles:

Enter your query when prompted (e.g., "articles related to surgery").
Choose what to display (all, titles, or keywords).
Optionally export results to a CSV file.
Logs and Debugging
Logs are stored in the logs/ directory for each step:

logs/install.log: Dependency installation.
logs/crawl_all_articles.log: Web crawling.
logs/milvus_insert.log: Embedding insertion.
logs/milvus_search.log: Query execution.
Check these files for troubleshooting.

Contributing
Feel free to open issues or contribute to the project via pull requests.

License
This project is licensed under the MIT License.

