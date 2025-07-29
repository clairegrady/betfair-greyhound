import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests # Still useful for urljoin

# --- Main Configuration ---
# The URL for the greyhound meetings.
URL = "https://www.racingandsports.com.au/form-guide/greyhound/runners/2025-07-28"

def setup_driver():
    """Sets up the Selenium Chrome WebDriver."""
    print("Setting up Chrome WebDriver...")
    # webdriver-manager will automatically download and manage the correct driver
    service = ChromeService(ChromeDriverManager().install())
    
    # Set Chrome options to run in "headless" mode (no visible browser window)
    # You can comment out the next two lines to watch the browser work.
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    
    driver = webdriver.Chrome(service=service, options=options)
    print("WebDriver setup complete.")
    return driver

def scrape_data(driver, url):
    """Navigates to the URL and scrapes the race data."""
    print(f"Fetching data from: {url}")
    try:
        driver.get(url)
        # Wait for the main meeting container to be present on the page.
        # This ensures the JavaScript has loaded the content.
        # Increase the timeout (in seconds) if the site is slow.
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "meeting"))
        )
        print("Successfully fetched the page and found meeting content.")
        
        # Get the page source after JavaScript has loaded
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        
    except Exception as e:
        print(f"Error fetching the main URL with Selenium: {e}")
        driver.quit()
        return None

    all_runners_data = []

    # --- Parsing logic remains the same ---
    meeting_blocks = soup.find_all('div', class_='meeting')

    if not meeting_blocks:
        print("Could not find any meeting blocks. The page structure may have changed.")
        return []

    for meeting_block in meeting_blocks:
        meeting_header = meeting_block.find('div', class_='meeting-header')
        meeting_name_element = meeting_header.find('h2') if meeting_header else None
        meeting_name = meeting_name_element.get_text(strip=True) if meeting_name_element else "Unknown Meeting"
        
        print(f"\nProcessing Meeting: {meeting_name}")

        race_containers = meeting_block.find_all('div', class_='race')
        
        if not race_containers:
            print(f"  - No race containers found for {meeting_name}.")
            continue

        for race in race_containers:
            race_title_element = race.find('h4')
            race_title = race_title_element.get_text(strip=True).replace('\n', ' ').strip() if race_title_element else "Unknown Race"

            runners_table = race.find('table', class_='form-guide-table')
            if not runners_table:
                continue

            for runner_row in runners_table.find('tbody').find_all('tr'):
                is_scratched = 'scratched' in runner_row.get('class', [])
                cells = runner_row.find_all('td')

                if len(cells) > 5:
                    try:
                        dog_name_anchor = cells[1].find('a')
                        trainer_anchor = cells[3].find('a')
                        price_span = cells[4].find('span', class_='price-fixed')

                        runner_details = {
                            'meeting': meeting_name,
                            'race': race_title,
                            'status': 'Scratched' if is_scratched else 'Active',
                            'box': cells[0].get_text(strip=True),
                            'name': dog_name_anchor.get_text(strip=True) if dog_name_anchor else 'N/A',
                            'dog_url': requests.compat.urljoin(URL, dog_name_anchor['href']) if dog_name_anchor and dog_name_anchor.has_attr('href') else 'N/A',
                            'form': cells[2].get_text(strip=True),
                            'trainer': trainer_anchor.get_text(strip=True) if trainer_anchor else 'N/A',
                            'fixed_win_price': price_span.get_text(strip=True) if price_span else 'N/A'
                        }
                        all_runners_data.append(runner_details)
                    except (AttributeError, IndexError, TypeError) as e:
                        print(f"    - Could not parse a row in {race_title}. Skipping. Error: {e}")
    
    return all_runners_data

def save_to_csv(data):
    """Saves the provided data list to a CSV file."""
    if not data:
        print("No data was scraped, CSV file will not be created.")
        return

    output_filename = 'all_greyhound_data.csv'
    output_keys = data[0].keys()
    
    try:
        with open(output_filename, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=output_keys)
            dict_writer.writeheader()
            dict_writer.writerows(data)
        print(f"\nSuccessfully saved all data to {output_filename}")
    except IOError as e:
        print(f"Error writing to CSV file: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    driver = setup_driver()
    scraped_data = scrape_data(driver, URL)
    
    # Always close the browser
    print("Closing WebDriver.")
    driver.quit()
    
    print(f"\n--------------------------------------------------")
    if scraped_data:
        print(f"Scraping complete. Found data for {len(scraped_data)} runners.")
    else:
        print("Scraping finished with no data.")
    print(f"--------------------------------------------------")
    
    save_to_csv(scraped_data)
