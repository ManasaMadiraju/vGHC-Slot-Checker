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


def send_email(results):
    subject = "🔔 GHC Company Meeting Request Status"
    body = "\n".join(results) if results else "No companies found."

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
    """
    On a booth details page, determine if the 'REQUEST MEETING' button is enabled.
    Returns True/False.
    """
    # Wait for the sidebar/actions area to render
    try:
        btn = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a[data-analytics-name='request-meeting'][data-test='rf-button']")
            )
        )
    except Exception:
        # If there's truly no button, treat as disabled
        return False

    disabled_attr = btn.get_attribute("disabled")
    aria_disabled = (btn.get_attribute("aria-disabled") or "").lower()
    class_attr = (btn.get_attribute("class") or "").lower()

    # Some pages also show the helper text when disabled
    has_no_meetings_text = False
    try:
        driver.find_element(By.XPATH, "//p[contains(., 'No available meetings')]")
        has_no_meetings_text = True
    except Exception:
        pass

    # Consider enabled only if none of the disabled signals are present
    if disabled_attr is not None:
        return False
    if aria_disabled in ("true", "1"):
        return False
    if "disabled" in class_attr:
        return False
    if has_no_meetings_text:
        return False

    # Last resort check; anchors often return True regardless, but keep it
    return btn.is_enabled()


def wait_for_catalog(wait):
    wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, "div.rf-tile-wrapper.exhibitor-tile")
    ))


def check_companies():
    print(f"\n{Fore.CYAN}🚀 Running company check...{Style.RESET_ALL}")

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)

    driver.get(login_url)
    wait = WebDriverWait(driver, 20)

    # Accept cookies if present
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
        # Wait for redirect to complete
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

    # OPTIONAL: scroll to ensure all tiles render
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

    results = []

    # Loop by index and re-query each time (SPA navigation will stale old elements)
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

        # Company name on the tile
        try:
            company_name = card.find_element(By.CSS_SELECTOR, "div.rf-tile-body h4").text.strip()
            if not company_name:
                company_name = "Unknown Company"
        except Exception:
            company_name = "Unknown Company"

        # Click "View Booth"
        try:
            view_btn = card.find_element(By.CSS_SELECTOR, "a[role='link'][data-test='rf-button']")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", view_btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", view_btn)
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Could not open booth for {company_name}: {e}{Style.RESET_ALL}")
            results.append(f"🚫 NO BOOTH: {company_name}")
            idx += 1
            continue

        # Wait for booth details page and evaluate the Request Meeting button
        try:
            # Wait for either the request-meeting button or the booth heading to appear
            wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a[data-analytics-name='request-meeting'][data-test='rf-button'], h1")
            ))
            enabled = is_request_meeting_enabled(driver, wait)
            if enabled:
                result = f"✅ ENABLED: {company_name}"
                print(f"{Fore.GREEN}{result}{Style.RESET_ALL}")
            else:
                result = f"❌ DISABLED: {company_name}"
                print(f"{Fore.RED}{result}{Style.RESET_ALL}")
            results.append(result)
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Could not determine status for {company_name}: {e}{Style.RESET_ALL}")
            results.append(f"❓ UNKNOWN: {company_name}")

        # Go back to catalog (SPA friendly)
        try:
            driver.back()
            wait_for_catalog(wait)
        except Exception:
            # Fallback: try clicking the "View All Partners" link if present
            try:
                back_link = driver.find_element(By.XPATH, "//a[contains(., 'View All Partners')]")
                driver.execute_script("arguments[0].click();", back_link)
                wait_for_catalog(wait)
            except Exception:
                print(f"{Fore.RED}❌ Could not return to catalog after {company_name}.{Style.RESET_ALL}")
                break

        idx += 1

    driver.quit()

    print(f"\n{Fore.MAGENTA}📨 Sending email with statuses...{Style.RESET_ALL}")
    send_email(results)


# Run immediately
check_companies()

# Schedule every 5 minutes
# schedule.every(5).minutes.do(check_companies)

# print(f"\n{Fore.MAGENTA}⏳ Scheduler started... Will check every 5 minutes.{Style.RESET_ALL}")
# while True:
#     schedule.run_pending()
#     time.sleep(60)