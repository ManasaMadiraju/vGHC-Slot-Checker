from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from dotenv import load_dotenv
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import schedule
from colorama import Fore, Style, init
from datetime import datetime

# Initialize colorama
init(autoreset=True)

# Load environment variables
load_dotenv()

# URLs
login_url = "https://gracehoppercelebration.com/flow/anitab/vcf25/exhcatalog/login"
main_url = "https://gracehoppercelebration.com/flow/anitab/vcf25/exhcatalog/page/ghc25sponsorcatalog"

# Credentials
username_str = os.getenv("GHC_EMAIL")
password_str = os.getenv("GHC_PASSWORD")

# Email notification setup
sender_email = os.getenv("SENDER_EMAIL")
sender_password = os.getenv("SENDER_PASSWORD")
notify_email = os.getenv("NOTIFY_EMAIL")

# File to track already-notified companies (daily)
notified_file = "notified_companies.txt"

def load_notified_companies():
    if os.path.exists(notified_file):
        with open(notified_file, "r") as f:
            lines = f.read().splitlines()
            if lines:
                saved_date = lines[0].strip()
                today = datetime.now().strftime("%Y-%m-%d")
                if saved_date == today:
                    return set(lines[1:]), saved_date
    return set(), datetime.now().strftime("%Y-%m-%d")

def save_notified_companies(companies, today):
    with open(notified_file, "w") as f:
        f.write(today + "\n")  # first line = date
        for company in companies:
            f.write(company + "\n")

# Load notified list at startup
already_notified, saved_date = load_notified_companies()


def send_email(enabled_companies):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"🔔 GHC Company Meeting Request Status - {timestamp}"
    body = f"Enabled companies as of {timestamp}:\n\n" + "\n".join(enabled_companies)

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = notify_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, notify_email, msg.as_string())
        print(f"{Fore.GREEN}📧 Email sent successfully!{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}❌ Failed to send email: {e}{Style.RESET_ALL}")


def is_request_meeting_enabled(driver, wait):
    try:
        btn = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a[data-analytics-name='request-meeting'][data-test='rf-button']")
            )
        )
    except Exception:
        return False

    disabled_attr = btn.get_attribute("disabled")
    aria_disabled = (btn.get_attribute("aria-disabled") or "").lower()
    class_attr = (btn.get_attribute("class") or "").lower()

    has_no_meetings_text = False
    try:
        driver.find_element(By.XPATH, "//p[contains(., 'No available meetings')]")
        has_no_meetings_text = True
    except Exception:
        pass

    if disabled_attr is not None:
        return False
    if aria_disabled in ("true", "1"):
        return False
    if "disabled" in class_attr:
        return False
    if has_no_meetings_text:
        return False

    return btn.is_enabled()


def wait_for_catalog(wait):
    wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, "div.rf-tile-wrapper.exhibitor-tile")
    ))


def check_companies():
    global already_notified, saved_date

    today = datetime.now().strftime("%Y-%m-%d")
    if today != saved_date:
        # reset daily
        already_notified = set()
        saved_date = today
        save_notified_companies(already_notified, today)
        print(f"{Fore.BLUE}🔄 Reset notified companies for {today}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}🚀 Running company check...{Style.RESET_ALL}")

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20)

    driver.get(login_url)

    # Accept cookies
    try:
        cookie_accept = driver.find_element(By.CSS_SELECTOR, ".cc-btn")
        cookie_accept.click()
        print("🍪 Cookie consent accepted")
    except Exception:
        print("🍪 No cookie banner found")

    # Login
    try:
        username_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        password_input = driver.find_element(By.NAME, "password")
        username_input.send_keys(username_str)
        password_input.send_keys(password_str)

        login_button = driver.find_element(By.CSS_SELECTOR, "button#login-button")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", login_button)
        time.sleep(0.4)
        driver.execute_script("arguments[0].click();", login_button)

        print("✅ Login attempted")
        time.sleep(4)
    except Exception as e:
        print(f"{Fore.RED}❌ Login failed: {e}{Style.RESET_ALL}")
        driver.quit()
        return

    # Navigate to catalog
    driver.get(main_url)
    try:
        wait_for_catalog(wait)
    except Exception:
        print(f"{Fore.RED}❌ Catalog did not load.{Style.RESET_ALL}")
        driver.quit()
        return

    # Scroll
    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(4):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.6)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        driver.execute_script("window.scrollTo(0, 0);")
    except Exception:
        pass

    enabled_companies = []

    idx = 0
    while True:
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, "div.rf-tile-wrapper.exhibitor-tile")
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to read cards: {e}{Style.RESET_ALL}")
            break

        if idx >= len(cards):
            break

        card = cards[idx]

        try:
            company_name = card.find_element(By.CSS_SELECTOR, "div.rf-tile-body h4").text.strip()
            if not company_name:
                company_name = "Unknown Company"
        except Exception:
            company_name = "Unknown Company"

        # Open booth
        try:
            view_btn = card.find_element(By.CSS_SELECTOR, "a[role='link'][data-test='rf-button']")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", view_btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", view_btn)
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Could not open booth for {company_name}: {e}{Style.RESET_ALL}")
            idx += 1
            continue

        # Check meeting button
        try:
            wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a[data-analytics-name='request-meeting'][data-test='rf-button'], h1")
            ))
            enabled = is_request_meeting_enabled(driver, wait)
            if enabled:
                result = f"✅ ENABLED: {company_name}"
                enabled_companies.append(result)
                print(f"{Fore.GREEN}{result}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}❌ DISABLED: {company_name}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Could not determine status for {company_name}: {e}{Style.RESET_ALL}")

        # Back to catalog
        try:
            driver.back()
            wait_for_catalog(wait)
        except Exception:
            try:
                back_link = driver.find_element(By.XPATH, "//a[contains(., 'View All Partners')]")
                driver.execute_script("arguments[0].click();", back_link)
                wait_for_catalog(wait)
            except Exception:
                print(f"{Fore.RED}❌ Could not return to catalog after {company_name}.{Style.RESET_ALL}")
                break

        idx += 1

    driver.quit()

    # ✅ Only send if new companies today
    new_enabled = [c for c in enabled_companies if c not in already_notified]

    if new_enabled:
        print(f"\n{Fore.MAGENTA}📨 Sending email with NEW enabled companies...{Style.RESET_ALL}")
        send_email(new_enabled)
        already_notified.update(new_enabled)
        save_notified_companies(already_notified, today)
    else:
        print(f"{Fore.YELLOW}📭 No NEW enabled companies found today. No email sent.{Style.RESET_ALL}")


# Run immediately once
check_companies()

# Schedule to run once daily at 9 AM (you can change time)
schedule.every().day.at("09:00").do(check_companies)

while True:
    schedule.run_pending()
    time.sleep(60)
