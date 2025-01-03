import csv
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection, utility
import mysql.connector
from datetime import datetime, timedelta
import re
import dateparser
from prettytable import PrettyTable
import configparser


def connect_to_milvus():
    """
    Connect to Milvus using credentials from config.ini.
    """
    config = configparser.ConfigParser()
    config.read("config.ini")
    milvus_host = config["milvus"]["host"]
    milvus_port = config["milvus"]["port"]
    collection_name = config["milvus"]["collection_name"]

    connections.connect(host=milvus_host, port=milvus_port)

    if not utility.has_collection(collection_name):
        raise ValueError(f"Collection '{collection_name}' does not exist in Milvus.")

    collection = Collection(collection_name)

    try:
        collection.load()
        print(f"Milvus collection '{collection_name}' loaded into memory.")
    except Exception as e:
        print(f"Failed to load the collection '{collection_name}': {e}")
        raise e

    return collection


def create_index_for_collection():
    """
    Create an index for the Milvus collection if it does not exist.
    """
    config = configparser.ConfigParser()
    config.read("config.ini")
    collection_name = config["milvus"]["collection_name"]

    connections.connect()

    if not utility.has_collection(collection_name):
        raise ValueError(f"Collection '{collection_name}' does not exist in Milvus.")

    collection = Collection(collection_name)

    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "L2",
        "params": {"nlist": 128},
    }

    try:
        # Check if an index already exists
        if collection.has_index():
            print(f"Index already exists for collection '{collection_name}'. Skipping index creation.")
            return

        collection.create_index(field_name="embeddings", index_params=index_params)
        print(f"Index created successfully for collection '{collection_name}'.")
    except Exception as e:
        print(f"Failed to create index: {e}")
        raise e


def connect_to_mysql():
    """
    Connect to the MySQL database using credentials from config.ini.
    """
    config = configparser.ConfigParser()
    config.read("config.ini")

    return mysql.connector.connect(
        host=config["mysql"]["host"],
        user=config["mysql"]["user"],
        password=config["mysql"]["password"],
        database=config["mysql"]["database"]
    )


def parse_date_filter(query):
    """
    Parse date-related queries into a range.
    """
    now = datetime.now()
    date_range = None

    if "last week" in query.lower():
        date_range = (now - timedelta(days=7)).date(), now.date()
    elif "last month" in query.lower():
        date_range = (now - timedelta(days=30)).date(), now.date()
    elif "last" in query.lower() or "past" in query.lower():
        match = re.search(r"(last|past)\s(\d+)\s(days|weeks|months)", query, re.IGNORECASE)
        if match:
            duration = int(match.group(2))
            unit = match.group(3).lower()
            if unit == "days":
                date_range = (now - timedelta(days=duration)).date(), now.date()
            elif unit == "weeks":
                date_range = (now - timedelta(weeks=duration)).date(), now.date()
            elif unit == "months":
                date_range = (now - timedelta(days=30 * duration)).date(), now.date()
    else:
        parsed_date = dateparser.parse(query)
        if parsed_date:
            date_range = parsed_date.date(), now.date()

    return date_range


def fetch_filtered_articles_by_ids(ids, date_range=None):
    """
    Fetch articles from MySQL by IDs and optional date range.
    """
    if not ids:
        print("No article IDs to fetch.")
        return []

    connection = connect_to_mysql()
    cursor = connection.cursor()

    query = """SELECT articles.id, articles.title, articles.author, articles.publication_date, 
               articles.abstract, article_summaries.keywords 
               FROM articles 
               LEFT JOIN article_summaries ON articles.id = article_summaries.article_id 
               WHERE articles.id IN (%s)""" % ",".join(["%s"] * len(ids))
    params = list(ids)

    if date_range:
        query += " AND articles.publication_date BETWEEN %s AND %s"
        params.extend(date_range)

    cursor.execute(query, tuple(params))
    articles = cursor.fetchall()
    cursor.close()
    connection.close()
    return articles


def search_articles(query, nprobe=20, limit=10):
    """
    Search articles in Milvus and filter them based on free-text queries.
    """
    model = SentenceTransformer("all-mpnet-base-v2")
    query_embedding = model.encode([query], normalize_embeddings=True).tolist()

    collection = connect_to_milvus()
    search_params = {"metric_type": "L2", "params": {"nprobe": nprobe}}
    try:
        results = collection.search(
            data=query_embedding,
            anns_field="embeddings",
            param=search_params,
            limit=limit,
        )
        ids = [int(result.id) for result in results[0]]
        print(f"Milvus returned IDs: {ids}")
    except Exception as e:
        print(f"Milvus search error: {e}")
        return []

    date_range = parse_date_filter(query)
    articles = fetch_filtered_articles_by_ids(ids, date_range)

    if not articles:
        print("No matching articles found in MySQL.")
    return articles


def display_results(articles, display_type="all"):
    """
    Display the search results in a user-friendly format.
    """
    if not articles:
        print("No articles to display.")
        return

    print("\n--- Search Results ---\n")

    for article in articles:
        print(f"ID: {article[0]}")
        print(f"Title: {article[1]}")
        print(f"Authors: {article[2] or 'No Authors'}")
        print(f"Date: {article[3] if article[3] else 'No Date'}")
        print(f"Abstract: {(article[4][:100] + '...') if article[4] else 'No Summary Available'}")
        print(f"Keywords: {article[5] or 'No Keywords'}")
        print("-" * 80)


def export_to_csv(articles, filename="results.csv"):
    """
    Export the search results to a CSV file.
    """
    if not articles:
        print("No articles to export.")
        return

    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["ID", "Title", "Authors", "Date", "Abstract", "Keywords"])
        for article in articles:
            writer.writerow([
                article[0],
                article[1],
                article[2] or "No Authors",
                article[3] if article[3] else "No Date",
                article[4] or "No Summary Available",
                article[5] or "No Keywords"
            ])
    print(f"Results exported to {filename}")


if __name__ == "__main__":
    create_index_for_collection()
    query = input("Enter your query: ")
    display_type = input("What would you like to see? (all, titles, keywords): ").strip().lower()
    results = search_articles(query)

    if results:
        display_results(results, display_type)

        export = input("Would you like to export the results to a CSV file? (yes/no): ").strip().lower()
        if export == "yes":
            filename = input("Enter filename (default: results.csv): ").strip() or "results.csv"
            export_to_csv(results, filename)
    else:
        print("No articles found.")
