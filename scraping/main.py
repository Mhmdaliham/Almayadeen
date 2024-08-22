import requests
from bs4 import BeautifulSoup
import json
import os
from typing import List, Optional
from dataclasses import dataclass
import concurrent.futures


@dataclass
class ArticleMetadata:
    post_id: str
    title: str
    url: str
    keywords: List[str]
    thumbnail: str
    video_duration: Optional[str]
    word_count: int
    lang: Optional[str]
    published_time: str
    last_updated: str
    description: Optional[str]
    author: str
    classes: List[str]
    full_text: str


class ArticleScraper:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.current_file_index = 1  # Track the current JSON file index
        self.current_article_count = 0  # Track articles in the current JSON file

    def fetch_sitemaps(self, main_sitemap_url: str) -> List[str]:
        """Fetch monthly sitemap URLs from the main sitemap."""
        print(f"Fetching main sitemap index from: {main_sitemap_url}")
        response = requests.get(main_sitemap_url)
        soup = BeautifulSoup(response.content, 'lxml')
        sitemap_urls = [tag.text for tag in soup.find_all('loc')]
        print(f"Found {len(sitemap_urls)} monthly sitemaps.")
        return sitemap_urls

    def fetch_article_urls(self, sitemap_url: str) -> List[str]:
        """Fetch article URLs from a monthly sitemap."""
        print(f"Fetching sitemap from: {sitemap_url}")
        response = requests.get(sitemap_url)
        soup = BeautifulSoup(response.content, 'lxml')
        article_urls = [tag.text for tag in soup.find_all('loc')]
        print(f"Found {len(article_urls)} articles in the sitemap.")
        return article_urls

    def scrape_article(self, article_url: str) -> Optional[ArticleMetadata]:
        """Scrape an article and return its metadata and content."""
        print(f"Scraping article: {article_url}")
        response = requests.get(article_url)
        soup = BeautifulSoup(response.content, 'lxml')

        # Extract metadata from the specific <script> tag with type text/tawsiyat
        script_tag = soup.find('script', {'type': 'text/tawsiyat'})
        if script_tag:
            try:
                metadata = json.loads(script_tag.string)

                # Convert to proper types and handle defaults
                return ArticleMetadata(
                    post_id=str(metadata.get('postid', 'unknown')),
                    title=str(metadata.get('title', 'unknown')),
                    url=article_url,
                    keywords=self._parse_list(metadata.get('keywords', '')),
                    thumbnail=str(metadata.get('thumbnail', 'unknown')),
                    video_duration=str(metadata.get('video_duration', 'unknown')),
                    word_count=self._parse_int(metadata.get('word_count', 0)),
                    lang=str(metadata.get('lang', 'unknown')),
                    published_time=str(metadata.get('published_time', 'unknown')),
                    last_updated=str(metadata.get('last_updated', 'unknown')),
                    description=str(metadata.get('description', 'unknown')),
                    author=str(metadata.get('author', 'unknown')),
                    classes=self._parse_list(metadata.get('classes', '')),
                    full_text="\n".join([p.get_text() for p in soup.find_all('p')])
                )
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing metadata or converting values in article: {article_url} - {e}")
        return None

    def _parse_list(self, value) -> List[str]:
        """Parse a comma-separated string or list into a list of strings."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(',') if item.strip()]
        elif isinstance(value, list):
            return [str(item).strip() for item in value if item]
        return []

    def _parse_int(self, value) -> int:
        """Convert a value to an integer, defaulting to 0 if conversion fails."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def save_articles(self, articles: List[ArticleMetadata]):
        """Save articles to a JSON file. Create a new file if 1000 articles are reached."""
        os.makedirs(self.output_dir, exist_ok=True)

        # Save articles to a file and increment the file index
        file_name = f"articles_{self.current_file_index:02}.json"
        file_path = os.path.join(self.output_dir, file_name)
        with open(file_path, 'w', encoding='utf-8') as json_file:
            json.dump([article.__dict__ for article in articles], json_file, ensure_ascii=False, indent=4)
        print(f"Saved {len(articles)} articles to {file_path}")

        self.current_file_index += 1
        self.current_article_count = 0  # Reset the article count for the next file

    def process_sitemaps(self, main_sitemap_url: str, article_limit: int):
        """Fetch sitemaps, scrape articles, and save them to JSON files."""
        sitemaps = self.fetch_sitemaps(main_sitemap_url)
        total_articles_scraped = 0
        articles = []

        for sitemap_url in sitemaps:
            if total_articles_scraped >= article_limit:
                print(f"Article limit of {article_limit} reached. Exiting.")
                break

            # Extract year and month from the sitemap URL
            year_month = sitemap_url.split('/')[-1].replace('sitemap-', '').replace('.xml', '').split('-')

            if len(year_month) != 2:
                print(f"Skipping invalid sitemap URL: {sitemap_url}")
                continue

            try:
                year, month = int(year_month[0]), int(year_month[1])
            except ValueError:
                print(f"Error parsing year or month from sitemap URL: {sitemap_url}")
                continue

            print(f"Processing month: {year}-{month:02d}")
            article_urls = self.fetch_article_urls(sitemap_url)

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:  # Using 10 workers
                future_to_article = {executor.submit(self.scrape_article, url): url for url in article_urls}
                for future in concurrent.futures.as_completed(future_to_article):
                    try:
                        article = future.result()
                        if article:
                            articles.append(article)
                            total_articles_scraped += 1
                            self.current_article_count += 1

                            # Save and start a new file if we hit 1000 articles
                            if self.current_article_count == 1000:
                                self.save_articles(articles)
                                articles = []  # Reset articles list for the next file

                            # Stop if we've reached the article limit
                            if total_articles_scraped >= article_limit:
                                print(f"Reached the article limit of {article_limit}.")
                                break
                    except Exception as e:
                        print(f"Error scraping article: {e}")

            if total_articles_scraped >= article_limit:
                break

        # Save any remaining articles if they're less than 1000
        if articles:
            self.save_articles(articles)


# Main execution block
if __name__ == "__main__":
    main_sitemap_url = "https://www.almayadeen.net/sitemaps/all.xml"
    scraper = ArticleScraper(output_dir="scraped_articles")
    scraper.process_sitemaps(main_sitemap_url=main_sitemap_url, article_limit=10000)