import mysql.connector
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from datetime import datetime
from sklearn.feature_extraction.text import CountVectorizer
import configparser


def configure_driver():
    """
    Configure the Selenium WebDriver using the chromedriver path from config.ini.
    """
    config = configparser.ConfigParser()
    config.read("config.ini")
    chromedriver_path = config["selenium"]["chromedriver_path"]

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-software-rasterizer")  # Suppress WebGL warnings
    service = Service(chromedriver_path)
    return webdriver.Chrome(service=service, options=options)


def create_database_and_tables():
    """
    Create the database and tables if they do not exist.
    """
    config = configparser.ConfigParser()
    config.read("config.ini")
    connection = mysql.connector.connect(
        host=config["mysql"]["host"],
        user=config["mysql"]["user"],
        password=config["mysql"]["password"],
    )
    cursor = connection.cursor()

    # Create database if it doesn't exist
    cursor.execute("CREATE DATABASE IF NOT EXISTS oncology_data")

    # Connect to the new database
    connection.database = config["mysql"]["database"]

    # Create `articles` table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            author VARCHAR(255),
            publication_date DATE,
            abstract TEXT
        )
    """)

    # Create `article_summaries` table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS article_summaries (
            id INT AUTO_INCREMENT PRIMARY KEY,
            article_id INT,
            summary TEXT,
            keywords TEXT,
            FOREIGN KEY (article_id) REFERENCES articles(id)
        )
    """)

    cursor.close()
    connection.close()


def connect_to_db():
    """
    Connect to the MySQL database using credentials from config.ini.
    Returns both the connection and cursor objects.
    """
    config = configparser.ConfigParser()
    config.read("config.ini")

    connection = mysql.connector.connect(
        host=config["mysql"]["host"],
        user=config["mysql"]["user"],
        password=config["mysql"]["password"],
        database=config["mysql"]["database"]
    )
    cursor = connection.cursor()
    return connection, cursor


def insert_article(cursor, title, authors, publication_date, summary):
    """
    Insert an article into the 'articles' table and return its ID.
    """
    query = """
    INSERT INTO articles (title, author, publication_date, abstract)
    VALUES (%s, %s, %s, %s)
    """
    cursor.execute(query, (title, authors, publication_date, summary))
    return cursor.lastrowid


def insert_summary(cursor, article_id, summary, keywords):
    """
    Insert the summary and keywords into the 'article_summaries' table.
    """
    query = """
    INSERT INTO article_summaries (article_id, summary, keywords)
    VALUES (%s, %s, %s)
    """
    cursor.execute(query, (article_id, summary, keywords))


def generate_keywords(summary):
    """
    Generate keywords from the summary using CountVectorizer.
    """
    vectorizer = CountVectorizer(max_features=5, stop_words="english")
    keywords = vectorizer.fit([summary]).get_feature_names_out() if summary else []
    return ", ".join(keywords)


def wait_for_metadata(driver):
    """
    Wait until the metadata section is fully loaded.
    """
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "c-card__body"))
        )
    except Exception as e:
        print("DEBUG: Metadata elements did not load within the timeout.")


def extract_dates_with_xpath(driver):
    """
    Extract publication dates using a hardcoded XPath.
    """
    date_xpath = "//time[@class='c-meta__item c-meta__item--block-at-lg']"
    date_elements = driver.find_elements(By.XPATH, date_xpath)
    dates = [elem.get_attribute("datetime") for elem in date_elements if elem.get_attribute("datetime")]
    print(f"DEBUG: Found {len(dates)} dates via XPath.")
    return dates


def parse_articles_and_store(soup, dates, cursor, seen_titles):
    """
    Parse articles from the page source and store them in the database.
    """
    articles = soup.find_all("div", class_="c-card__body")
    print(f"DEBUG: Found {len(articles)} articles.")

    for i, article in enumerate(articles):
        try:
            title_tag = article.find("a", class_="c-card__link u-link-inherit")
            title = title_tag.get_text(strip=True) if title_tag else "No title available"

            if title in seen_titles:
                print(f"DEBUG: Skipping duplicate article: {title}")
                continue
            seen_titles.add(title)

            author_list = article.find("ul", class_="c-author-list")
            authors = ", ".join(
                [author.get_text(strip=True) for author in author_list.find_all("span", itemprop="name")]
            ) if author_list else "No authors available"

            summary_div = article.find("div", {"data-test": "article-description"})
            summary = summary_div.find("p").get_text(strip=True) if summary_div and summary_div.find("p") else "No summary available"

            publication_date = dates[i] if i < len(dates) else None

            article_id = insert_article(cursor, title, authors, publication_date, summary)
            print(f"Inserted article with ID: {article_id} - {title}")

            keywords = generate_keywords(summary)
            insert_summary(cursor, article_id, summary, keywords)

        except Exception as e:
            print(f"Error processing article {i + 1}: {e}")


def test_selenium_page_and_store():
    """
    Main function to fetch articles, parse metadata, and store results.
    """
    config = configparser.ConfigParser()
    config.read("config.ini")
    max_pages = int(config["general"]["max_pages_to_crawl"])

    base_url = "https://www.nature.com/search"
    create_database_and_tables()
    driver = configure_driver()
    connection, cursor = connect_to_db()
    seen_titles = set()

    try:
        for page in range(1, max_pages + 1):
            print(f"Fetching page {page}...")
            url = f"{base_url}?subject=oncology&article_type=protocols,research,reviews"
            if page > 1:
                url += f"&page={page}"

            driver.get(url)
            wait_for_metadata(driver)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            dates = extract_dates_with_xpath(driver)

            parse_articles_and_store(soup, dates, cursor, seen_titles)

        connection.commit()
    except Exception as e:
        print(f"Error during processing: {e}")
    finally:
        driver.quit()
        cursor.close()
        connection.close()


if __name__ == "__main__":
    test_selenium_page_and_store()
