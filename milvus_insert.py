from sentence_transformers import SentenceTransformer
from pymilvus import Collection, connections, CollectionSchema, FieldSchema, DataType, utility
import mysql.connector
import numpy as np
import configparser


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


def fetch_article_data():
    """
    Fetch articles and summaries from the MySQL database.
    """
    connection = connect_to_mysql()
    cursor = connection.cursor()
    cursor.execute("SELECT id, title, abstract FROM articles")
    articles = cursor.fetchall()
    cursor.execute("SELECT article_id, summary FROM article_summaries")
    summaries = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.close()
    connection.close()
    return articles, summaries


def connect_to_milvus():
    """
    Connect to Milvus and ensure the collection has the correct schema.
    """
    config = configparser.ConfigParser()
    config.read("config.ini")

    milvus_host = config["milvus"]["host"]
    milvus_port = config["milvus"]["port"]
    collection_name = config["milvus"]["collection_name"]

    connections.connect(host=milvus_host, port=milvus_port)

    # Define schema for the collection with dim=768
    fields = [
        FieldSchema(name="embeddings", dtype=DataType.FLOAT_VECTOR, dim=768, is_primary=False),
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False)
    ]
    schema = CollectionSchema(fields, description="Collection for article embeddings")

    # Check if the collection exists
    if collection_name in utility.list_collections():
        collection = Collection(collection_name)

        # Validate the schema
        existing_fields = collection.schema.fields
        for field in existing_fields:
            if field.name == "embeddings" and field.params["dim"] != 768:
                print(f"Schema mismatch detected for field 'embeddings'. Expected dim=768, got dim={field.params['dim']}.")
                print("Dropping and recreating the collection.")
                
                # Drop and recreate the collection
                utility.drop_collection(collection_name)
                collection = Collection(name=collection_name, schema=schema)
                print(f"Recreated collection: {collection_name}")
                return collection
        
        print(f"Connected to existing collection: {collection_name} with correct schema.")
    else:
        # Create the collection if it does not exist
        collection = Collection(name=collection_name, schema=schema)
        print(f"Created new collection: {collection_name}")

    return collection


def combine_embeddings(title_embedding, abstract_embedding, summary_embedding, weights):
    """
    Combine embeddings from title, abstract, and summary using specified weights.
    """
    return (weights[0] * title_embedding +
            weights[1] * abstract_embedding +
            weights[2] * summary_embedding)


def insert_weighted_embeddings(articles, summaries):
    """
    Generate weighted embeddings for articles and insert them into Milvus.
    """
    model = SentenceTransformer('all-mpnet-base-v2')
    collection = connect_to_milvus()

    embeddings = []
    ids = []

    # Weights for title, abstract, and summary embeddings
    weights = [0.5, 0.3, 0.2]

    for article in articles:
        article_id, title, abstract = article
        summary = summaries.get(article_id, "")

        # Generate embeddings for each field
        title_embedding = model.encode(title, normalize_embeddings=True)
        abstract_embedding = model.encode(abstract, normalize_embeddings=True)
        summary_embedding = model.encode(summary, normalize_embeddings=True)

        # Combine embeddings with weights
        combined_embedding = combine_embeddings(title_embedding, abstract_embedding, summary_embedding, weights)

        embeddings.append(combined_embedding)
        ids.append(article_id)

    # Insert embeddings into the collection
    collection.insert([embeddings, ids])
    print(f"Inserted {len(ids)} articles into Milvus.")


if __name__ == "__main__":
    articles, summaries = fetch_article_data()
    insert_weighted_embeddings(articles, summaries)
