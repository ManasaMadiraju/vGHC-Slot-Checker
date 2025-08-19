from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
from dotenv import load_dotenv
import os

# URLs
login_url = "https://gracehoppercelebration.com/flow/anitab/vcf25/exhcatalog/login"  # Update with actual login URL
main_url = "https://gracehoppercelebration.com/flow/anitab/vcf25/exhcatalog/page/ghc25sponsorcatalog"

load_dotenv()  # loads variables from .env file

# Your login credentials
username_str = os.getenv("GHC_EMAIL")
password_str = os.getenv("GHC_PASSWORD")

# Initialize driver
driver = webdriver.Chrome()
driver.get(login_url)
time.sleep(3)

# 1️⃣ Login
username_input = driver.find_element(By.NAME, "email")      # Update with actual element ID or selector
password_input = driver.find_element(By.NAME, "password")   # Update with actual element ID or selector
login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")  # Update if needed

username_input.send_keys(username_str)
password_input.send_keys(password_str)
login_button.click()

# Wait for login to complete and redirect
time.sleep(5)

# 2️⃣ Navigate to main page
driver.get(main_url)
time.sleep(3)

# 3️⃣ Collect company links
company_elements = driver.find_elements(By.CSS_SELECTOR, "div.exhibitor-details-back-to-catalog a")
company_links = [c.get_attribute("href") for c in company_elements]

enabled_companies = []

# 4️⃣ Visit each company page
for link in company_links:
    driver.get(link)
    time.sleep(2)
    
    # Company name
    company_name = driver.find_element(By.CSS_SELECTOR, "div.exhibitor-title").text.strip()
    
    try:
        # Find the request meeting link
        request_meeting = driver.find_element(By.CSS_SELECTOR, "div.exhibitor-request-meeting a")
        
        # Check if disabled attribute exists
        if request_meeting.get_attribute("disabled"):
            print(f"{company_name}: DISABLED")
        else:
            enabled_companies.append(company_name)
            print(f"{company_name}: ENABLED")
            
    except:
        print(f"{company_name}: No Request Meeting option found")

driver.quit()

print("\nCompanies with Request Meeting ENABLED:")
print(enabled_companies)
