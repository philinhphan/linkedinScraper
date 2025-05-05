import os
import time
import pandas as pd
import logging
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("linkedin_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def save_page_source(driver, filename="page_source.html"):
    """Save the page source to a file for debugging"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    logger.info(f"Page source saved to {filename}")

def linkedin_login(driver, email, password):
    """
    Logs into LinkedIn using the provided driver instance.
    Adjust selectors if LinkedIn changes its login form.
    """
    logger.info("Attempting to log in to LinkedIn")
    driver.get("https://www.linkedin.com/login")
    time.sleep(2)  # wait for page to load
    
    # Enter user email
    try:
        username_field = driver.find_element(By.ID, "username")
        username_field.send_keys(email)
        logger.info("Email entered successfully")
    except NoSuchElementException:
        logger.error("Could not find username field")
        save_page_source(driver, "login_page_error.html")
        raise
    
    # Enter user password
    try:
        password_field = driver.find_element(By.ID, "password")
        password_field.send_keys(password)
        logger.info("Password entered successfully")
    except NoSuchElementException:
        logger.error("Could not find password field")
        save_page_source(driver, "login_page_error.html")
        raise
    
    # Submit the form
    password_field.send_keys(Keys.RETURN)
    logger.info("Login form submitted")
    
    # Wait for login to complete and allow time for security checks
    time.sleep(30)
    
    # Check if login was successful
    if "feed" in driver.current_url or "checkpoint" in driver.current_url:
        logger.info("Login successful")
    else:
        logger.warning(f"Login may have failed. Current URL: {driver.current_url}")
        save_page_source(driver, "login_result_page.html")

def scrape_founder_profile(driver, profile_url):
    logger.info(f"Scraping profile: {profile_url}")
    
    data = {
        "profile_url": profile_url,
        "name": None,
        "headline": None,
        "experiences": [],
        "education": []
    }
    
    try:
        driver.get(profile_url)
        logger.info(f"Navigated to profile URL: {profile_url}")
        
        # Wait for the page to load completely
        time.sleep(8)
        logger.info(f"Current URL after navigation: {driver.current_url}")
        
        # Save the page source for debugging
        save_page_source(driver, "profile_page.html")
        
        # Check if we've been redirected to login page
        if "login" in driver.current_url or "authwall" in driver.current_url:
            logger.error("Redirected to login page. Session may have expired.")
            return data
    except Exception as e:
        logger.error(f"Error navigating to profile: {str(e)}")
        return data

    # -------------- NAME --------------
    try:
        logger.info("Attempting to extract name")
        selectors = [
            "h1.text-heading-xlarge",
            "div.ph5.pb5 h1",
            "h1.sJlATPGtyhrnuKlKqeFAWOzgrMgdvKOBE",
            "h1.inline.t-24"
        ]
        
        for selector in selectors:
            try:
                name_el = driver.find_element(By.CSS_SELECTOR, selector)
                data["name"] = name_el.text.strip()
                logger.info(f"Name extracted: {data['name']} using selector: {selector}")
                break
            except NoSuchElementException:
                continue
        
        if not data["name"]:
            logger.warning("Could not extract name with any of the selectors")
    except Exception as e:
        logger.error(f"Error extracting name: {str(e)}")
    
    # -------------- HEADLINE --------------
    try:
        logger.info("Attempting to extract headline")
        selectors = [
            "div.text-body-medium.break-words",
            "div.text-body-medium",
            "div.ph5.pb5 div.text-body-medium"
        ]
        
        for selector in selectors:
            try:
                headline_el = driver.find_element(By.CSS_SELECTOR, selector)
                data["headline"] = headline_el.text.strip()
                logger.info(f"Headline extracted: {data['headline']} using selector: {selector}")
                break
            except NoSuchElementException:
                continue
        
        if not data["headline"]:
            logger.warning("Could not extract headline with any of the selectors")
    except Exception as e:
        logger.error(f"Error extracting headline: {str(e)}")

    # -------------- EXPERIENCE --------------
    try:
        logger.info("Attempting to extract experience section")
        
        # UPDATED: Find all section elements that might contain experience data
        # First, get all section elements
        all_sections = driver.find_elements(By.CSS_SELECTOR, "section.artdeco-card")
        logger.info(f"Found {len(all_sections)} section elements on the page")
        
        experience_section = None
        
        # Look for the section that contains the experience data
        for i, section in enumerate(all_sections):
            try:
                # Try to find a heading that contains "Experience"
                headers = section.find_elements(By.CSS_SELECTOR, "h2")
                for header in headers:
                    if "Experience" in header.text:
                        experience_section = section
                        logger.info(f"Found experience section with header at index {i}")
                        # Log the full HTML of this section for debugging
                        logger.info(f"Experience section HTML: {section.get_attribute('outerHTML')[:1000]}...")
                        break
                if experience_section:
                    break
            except Exception as e:
                logger.error(f"Error checking section {i} for experience header: {str(e)}")
        
        # If we still haven't found it, try looking for sections that come after the experience anchor
        if not experience_section:
            try:
                # Find the experience anchor div
                exp_anchor = driver.find_element(By.ID, "experience")
                # Get its parent section
                parent_section = driver.execute_script("""
                    var element = arguments[0];
                    while (element && element.tagName !== 'SECTION') {
                        element = element.parentElement;
                    }
                    return element;
                """, exp_anchor)
                
                if parent_section:
                    experience_section = parent_section
                    logger.info("Found experience section by navigating up from anchor")
                    logger.info(f"Experience section HTML: {experience_section.get_attribute('outerHTML')[:1000]}...")
            except Exception as e:
                logger.error(f"Error finding experience section by parent: {str(e)}")
        
        # If we found a section, try to extract experience items
        if experience_section:
            # UPDATED: Try different approaches to find experience items
            experience_items = []
            
            # Approach 1: Look for list items directly
            try:
                items = experience_section.find_elements(By.CSS_SELECTOR, "li.artdeco-list__item")
                if items:
                    experience_items = items
                    logger.info(f"Found {len(items)} experience items using artdeco-list__item")
            except Exception as e:
                logger.error(f"Error finding experience items with artdeco-list__item: {str(e)}")
            
            # Approach 2: Look for items in a ul element
            if not experience_items:
                try:
                    # Find all ul elements in the section
                    ul_elements = experience_section.find_elements(By.CSS_SELECTOR, "ul")
                    if ul_elements:
                        logger.info(f"Found {len(ul_elements)} ul elements in experience section")
                        # Try to get items from the first ul
                        items = ul_elements[0].find_elements(By.CSS_SELECTOR, "li")
                        if items:
                            experience_items = items
                            logger.info(f"Found {len(items)} experience items in first ul")
                except Exception as e:
                    logger.error(f"Error finding experience items in ul: {str(e)}")
            
            # Approach 3: Look for any divs that might contain experience data
            if not experience_items:
                try:
                    # Look for divs that might contain job titles
                    items = experience_section.find_elements(By.CSS_SELECTOR, "div.display-flex.flex-column")
                    if items:
                        experience_items = items
                        logger.info(f"Found {len(items)} potential experience items using display-flex.flex-column")
                except Exception as e:
                    logger.error(f"Error finding experience items with display-flex.flex-column: {str(e)}")
            
            # If we found items, process them
            for i, item in enumerate(experience_items):
                try:
                    logger.info(f"Processing experience item {i+1}")
                    logger.debug(f"Experience item HTML: {item.get_attribute('outerHTML')[:500]}...")
                    
                    experience_data = {}
                    
                    # UPDATED: Try more selectors for job title
                    title_selectors = [
                        "div.mr1.t-bold",
                        "div.align-items-center.mr1.t-bold",
                        "span.t-bold",
                        "span.t-16.t-bold",
                        ".t-bold", # Any element with t-bold class
                        "div.align-items-center" # Try broader selector
                    ]
                    
                    for selector in title_selectors:
                        try:
                            title_elements = item.find_elements(By.CSS_SELECTOR, selector)
                            if title_elements:
                                experience_data["title"] = title_elements[0].text.strip()
                                logger.info(f"Title extracted: {experience_data['title']} using selector: {selector}")
                                break
                        except Exception as e:
                            logger.error(f"Error with title selector {selector}: {str(e)}")
                    
                    if "title" not in experience_data or not experience_data["title"]:
                        # Try a different approach - get all text and parse
                        try:
                            all_text = item.text
                            logger.info(f"Item text content: {all_text}")
                            # Simple heuristic: first line might be the title
                            lines = all_text.split('\n')
                            if lines:
                                experience_data["title"] = lines[0].strip()
                                logger.info(f"Title extracted from text: {experience_data['title']}")
                        except Exception as e:
                            logger.error(f"Error extracting title from text: {str(e)}")
                    
                    # UPDATED: Try more selectors for company
                    company_selectors = [
                        "span.t-14.t-normal",
                        "span.t-14.t-normal.t-black",
                        "span.pv-entity__secondary-title",
                        ".t-14.t-normal" # Any element with these classes
                    ]
                    
                    for selector in company_selectors:
                        try:
                            company_elements = item.find_elements(By.CSS_SELECTOR, selector)
                            if company_elements:
                                company_text = company_elements[0].text.strip()
                                if " · " in company_text:
                                    company_parts = company_text.split(" · ")
                                    experience_data["company"] = company_parts[0]
                                    experience_data["employment_type"] = company_parts[1] if len(company_parts) > 1 else ""
                                else:
                                    experience_data["company"] = company_text
                                    experience_data["employment_type"] = ""
                                
                                logger.info(f"Company extracted: {experience_data.get('company', '')} using selector: {selector}")
                                break
                        except Exception as e:
                            logger.error(f"Error with company selector {selector}: {str(e)}")
                    
                    # If we couldn't extract company, try from the text content
                    if "company" not in experience_data or not experience_data.get("company"):
                        try:
                            all_text = item.text
                            lines = all_text.split('\n')
                            if len(lines) > 1:
                                # Second line might be company info
                                company_text = lines[1].strip()
                                if " · " in company_text:
                                    company_parts = company_text.split(" · ")
                                    experience_data["company"] = company_parts[0]
                                    experience_data["employment_type"] = company_parts[1] if len(company_parts) > 1 else ""
                                else:
                                    experience_data["company"] = company_text
                                    experience_data["employment_type"] = ""
                                logger.info(f"Company extracted from text: {experience_data.get('company', '')}")
                        except Exception as e:
                            logger.error(f"Error extracting company from text: {str(e)}")
                    
                    # UPDATED: Try more selectors for date range
                    date_selectors = [
                        "span.t-14.t-normal.t-black--light",
                        "span.pv-entity__date-range",
                        ".t-14.t-normal.t-black--light" # Any element with these classes
                    ]
                    
                    for selector in date_selectors:
                        try:
                            date_elements = item.find_elements(By.CSS_SELECTOR, selector)
                            if date_elements:
                                experience_data["date_range"] = date_elements[0].text.strip()
                                logger.info(f"Date range extracted: {experience_data['date_range']} using selector: {selector}")
                                break
                        except Exception as e:
                            logger.error(f"Error with date selector {selector}: {str(e)}")
                    
                    # If we couldn't extract date range, try from the text content
                    if "date_range" not in experience_data or not experience_data.get("date_range"):
                        try:
                            all_text = item.text
                            lines = all_text.split('\n')
                            if len(lines) > 2:
                                # Third line might be date info
                                experience_data["date_range"] = lines[2].strip()
                                logger.info(f"Date range extracted from text: {experience_data['date_range']}")
                        except Exception as e:
                            logger.error(f"Error extracting date range from text: {str(e)}")
                    
                    # Add the experience to our list if it has at least some data
                    if any(experience_data.values()):
                        data["experiences"].append(experience_data)
                        logger.info(f"Added experience item {i+1}: {json.dumps(experience_data)}")
                    else:
                        logger.warning(f"Skipping empty experience item {i+1}")
                    
                except Exception as e:
                    logger.error(f"Error processing experience item {i+1}: {str(e)}")
        else:
            logger.warning("Could not find experience section")
    except Exception as e:
        logger.error(f"Error extracting experience section: {str(e)}")

    # -------------- EDUCATION --------------
    try:
        logger.info("Attempting to extract education section")
        
        # UPDATED: Find all section elements that might contain education data
        # First, get all section elements if we haven't already
        if 'all_sections' not in locals():
            all_sections = driver.find_elements(By.CSS_SELECTOR, "section.artdeco-card")
            logger.info(f"Found {len(all_sections)} section elements on the page")
        
        education_section = None
        
        # Look for the section that contains the education data
        for i, section in enumerate(all_sections):
            try:
                # Try to find a heading that contains "Education"
                headers = section.find_elements(By.CSS_SELECTOR, "h2")
                for header in headers:
                    if "Education" in header.text:
                        education_section = section
                        logger.info(f"Found education section with header at index {i}")
                        # Log the full HTML of this section for debugging
                        logger.info(f"Education section HTML: {section.get_attribute('outerHTML')[:1000]}...")
                        break
                if education_section:
                    break
            except Exception as e:
                logger.error(f"Error checking section {i} for education header: {str(e)}")
        
        # If we still haven't found it, try looking for sections that come after the education anchor
        if not education_section:
            try:
                # Find the education anchor div
                edu_anchor = driver.find_element(By.ID, "education")
                # Get its parent section
                parent_section = driver.execute_script("""
                    var element = arguments[0];
                    while (element && element.tagName !== 'SECTION') {
                        element = element.parentElement;
                    }
                    return element;
                """, edu_anchor)
                
                if parent_section:
                    education_section = parent_section
                    logger.info("Found education section by navigating up from anchor")
                    logger.info(f"Education section HTML: {education_section.get_attribute('outerHTML')[:1000]}...")
            except Exception as e:
                logger.error(f"Error finding education section by parent: {str(e)}")
        
        # If we found a section, try to extract education items
        if education_section:
            # UPDATED: Try different approaches to find education items
            education_items = []
            
            # Approach 1: Look for list items directly
            try:
                items = education_section.find_elements(By.CSS_SELECTOR, "li.artdeco-list__item")
                if items:
                    education_items = items
                    logger.info(f"Found {len(items)} education items using artdeco-list__item")
            except Exception as e:
                logger.error(f"Error finding education items with artdeco-list__item: {str(e)}")
            
            # Approach 2: Look for items in a ul element
            if not education_items:
                try:
                    # Find all ul elements in the section
                    ul_elements = education_section.find_elements(By.CSS_SELECTOR, "ul")
                    if ul_elements:
                        logger.info(f"Found {len(ul_elements)} ul elements in education section")
                        # Try to get items from the first ul
                        items = ul_elements[0].find_elements(By.CSS_SELECTOR, "li")
                        if items:
                            education_items = items
                            logger.info(f"Found {len(items)} education items in first ul")
                except Exception as e:
                    logger.error(f"Error finding education items in ul: {str(e)}")
            
            # Approach 3: Look for any divs that might contain education data
            if not education_items:
                try:
                    # Look for divs that might contain school names
                    items = education_section.find_elements(By.CSS_SELECTOR, "div.display-flex.flex-column")
                    if items:
                        education_items = items
                        logger.info(f"Found {len(items)} potential education items using display-flex.flex-column")
                except Exception as e:
                    logger.error(f"Error finding education items with display-flex.flex-column: {str(e)}")
            
            # If we found items, process them
            for i, edu in enumerate(education_items):
                try:
                    logger.info(f"Processing education item {i+1}")
                    logger.debug(f"Education item HTML: {edu.get_attribute('outerHTML')[:500]}...")
                    
                    education_data = {}
                    
                    # UPDATED: Try more selectors for school name
                    school_selectors = [
                        "div.mr1.hoverable-link-text.t-bold",
                        "div.align-items-center.mr1.hoverable-link-text.t-bold",
                        "span.t-bold",
                        "h3.pv-entity__school-name",
                        ".t-bold", # Any element with t-bold class
                        "div.align-items-center" # Try broader selector
                    ]
                    
                    for selector in school_selectors:
                        try:
                            school_elements = edu.find_elements(By.CSS_SELECTOR, selector)
                            if school_elements:
                                education_data["school"] = school_elements[0].text.strip()
                                logger.info(f"School extracted: {education_data['school']} using selector: {selector}")
                                break
                        except Exception as e:
                            logger.error(f"Error with school selector {selector}: {str(e)}")
                    
                    if "school" not in education_data or not education_data["school"]:
                        # Try a different approach - get all text and parse
                        try:
                            all_text = edu.text
                            logger.info(f"Item text content: {all_text}")
                            # Simple heuristic: first line might be the school
                            lines = all_text.split('\n')
                            if lines:
                                education_data["school"] = lines[0].strip()
                                logger.info(f"School extracted from text: {education_data['school']}")
                        except Exception as e:
                            logger.error(f"Error extracting school from text: {str(e)}")
                    
                    # UPDATED: Try more selectors for degree
                    degree_selectors = [
                        "span.t-14.t-normal",
                        "span.pv-entity__secondary-title",
                        "p.pv-entity__degree-name",
                        ".t-14.t-normal" # Any element with these classes
                    ]
                    
                    for selector in degree_selectors:
                        try:
                            degree_elements = edu.find_elements(By.CSS_SELECTOR, selector)
                            if degree_elements:
                                education_data["degree"] = degree_elements[0].text.strip()
                                logger.info(f"Degree extracted: {education_data['degree']} using selector: {selector}")
                                break
                        except Exception as e:
                            logger.error(f"Error with degree selector {selector}: {str(e)}")
                    
                    # If we couldn't extract degree, try from the text content
                    if "degree" not in education_data or not education_data.get("degree"):
                        try:
                            all_text = edu.text
                            lines = all_text.split('\n')
                            if len(lines) > 1:
                                # Second line might be degree info
                                education_data["degree"] = lines[1].strip()
                                logger.info(f"Degree extracted from text: {education_data['degree']}")
                        except Exception as e:
                            logger.error(f"Error extracting degree from text: {str(e)}")
                    
                    # UPDATED: Try more selectors for date range
                    date_selectors = [
                        "span.t-14.t-normal.t-black--light",
                        "p.pv-entity__dates",
                        ".t-14.t-normal.t-black--light" # Any element with these classes
                    ]
                    
                    for selector in date_selectors:
                        try:
                            date_elements = edu.find_elements(By.CSS_SELECTOR, selector)
                            if date_elements:
                                education_data["date_range"] = date_elements[0].text.strip()
                                logger.info(f"Date range extracted: {education_data['date_range']} using selector: {selector}")
                                break
                        except Exception as e:
                            logger.error(f"Error with date selector {selector}: {str(e)}")
                    
                    # If we couldn't extract date range, try from the text content
                    if "date_range" not in education_data or not education_data.get("date_range"):
                        try:
                            all_text = edu.text
                            lines = all_text.split('\n')
                            if len(lines) > 2:
                                # Third line might be date info
                                education_data["date_range"] = lines[2].strip()
                                logger.info(f"Date range extracted from text: {education_data['date_range']}")
                        except Exception as e:
                            logger.error(f"Error extracting date range from text: {str(e)}")
                    
                    # Add the education to our list if it has at least some data
                    if any(education_data.values()):
                        data["education"].append(education_data)
                        logger.info(f"Added education item {i+1}: {json.dumps(education_data)}")
                    else:
                        logger.warning(f"Skipping empty education item {i+1}")
                    
                except Exception as e:
                    logger.error(f"Error processing education item {i+1}: {str(e)}")
        else:
            logger.warning("Could not find education section")
    except Exception as e:
        logger.error(f"Error extracting education section: {str(e)}")

    logger.info(f"Finished scraping profile. Data extracted: {json.dumps(data)}")
    return data


def main():
    logger.info("Starting LinkedIn profile scraper")
    
    try:
        # Load CSV of founder LinkedIn profiles
        try:
            df = pd.read_csv('your_file.csv')
            logger.info(f"Loaded CSV with {len(df)} profiles")
        except Exception as e:
            logger.error(f"Error loading CSV: {str(e)}")
            # Fallback to a single profile for testing
            logger.info("Using fallback profile URL for testing")
            df = pd.DataFrame({'founder_link': ['https://www.linkedin.com/in/akkshay/']})
        
        # Setup Chrome options
        options = Options()
        options.headless = False  # Set to True for headless mode
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-notifications")
        
        # Add user agent to appear more like a regular browser
        options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        
        logger.info("Setting up Chrome driver")
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # 1) Log in to LinkedIn
        linkedin_email = os.getenv("LINKEDIN_EMAIL")
        linkedin_password = os.getenv("LINKEDIN_PASSWORD")
        
        try:
            linkedin_login(driver, linkedin_email, linkedin_password)
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            driver.quit()
            return
        
        # 2) Iterate through each founder profile
        results = []
        for link in df['founder_link']:
            try:
                logger.info(f"Processing profile: {link}")
                profile_data = scrape_founder_profile(driver, link)
                results.append(profile_data)
                
                if profile_data["name"]:
                    logger.info(f"Successfully scraped: {profile_data['name']} | {profile_data['profile_url']}")
                else:
                    logger.warning(f"Scraped profile with no name: {profile_data['profile_url']}")
                
                # Add a delay between requests to avoid rate limiting
                delay = 5 + (5 * (len(results) % 3))  # Varying delay to look more human
                logger.info(f"Waiting {delay} seconds before next profile")
                time.sleep(delay)
            except Exception as e:
                logger.error(f"Error scraping {link}: {str(e)}")
                results.append({
                    "profile_url": link,
                    "name": None,
                    "headline": None,
                    "experiences": [],
                    "education": []
                })
        
        # Close the driver
        driver.quit()
        logger.info("Chrome driver closed")
        
        # Create a DataFrame from the results
        data_for_csv = []
        for item in results:
            data_for_csv.append({
                "profile_url": item["profile_url"],
                "name": item["name"],
                "headline": item["headline"],
                "experiences": json.dumps(item["experiences"]),
                "education": json.dumps(item["education"])
            })
        
        out_df = pd.DataFrame(data_for_csv)
        
        # Save to CSV
        out_df.to_csv("founder_profile_data.csv", index=False)
        logger.info("Scraping completed. Data saved to founder_profile_data.csv")
        
    except Exception as e:
        logger.error(f"An error occurred in the main function: {str(e)}")

if __name__ == "__main__":
    main()










    