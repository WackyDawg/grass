from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    WebDriverException,
    NoSuchElementException,
    ElementNotInteractableException,
)
from webdriver_manager.chrome import ChromeDriverManager
import time
import requests
import hashlib
import os
import re
from flask import Flask, jsonify

# Constants
EXTENSION_ID = "ilehaonighjijnmpnagapkhpcdbhclfg"
CRX_URL_TEMPLATE = (
    "https://clients2.google.com/service/update2/crx?"
    "response=redirect&prodversion=98.0.4758.102&acceptformat=crx2,crx3&x=id%3D~~~~%26uc"
)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"

# Environment variables or default credentials
USER = os.getenv("GRASS_USER", "your-email@example.com")
PASSW = os.getenv("GRASS_PASS", "your-password")
ALLOW_DEBUG = os.getenv("ALLOW_DEBUG", "True").lower() == "true"

# Flask App
app = Flask(__name__)

def download_extension(extension_id):
    """Downloads a Chrome extension given its ID."""
    url = CRX_URL_TEMPLATE.replace("~~~~", extension_id)
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, stream=True, headers=headers)
    if response.status_code == 200:
        with open("grass.crx", "wb") as file:
            for chunk in response.iter_content(chunk_size=128):
                file.write(chunk)
        if ALLOW_DEBUG:
            print(f"Extension downloaded successfully: {extension_id}")
    else:
        raise Exception(f"Failed to download extension. Status Code: {response.status_code}")

def generate_error_report(driver, description=""):
    """Generates a debug report with a screenshot and console logs."""
    if not ALLOW_DEBUG:
        return
    print(f"Generating error report: {description}")
    try:
        driver.save_screenshot("error.png")
        logs = driver.get_log("browser")
        with open("error.log", "w") as f:
            for log in logs:
                f.write(f"{log}\n")
    except Exception as e:
        print(f"Failed to generate error report: {e}")

def initialize_webdriver():
    """Initializes the Chrome WebDriver with the required settings."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_extension("grass.crx")

    try:
        return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    except WebDriverException as e:
        print(f"Error initializing WebDriver: {e}")
        exit(1)

def login(driver, user, password):
    """Logs in to the Grass app."""
    print("Navigating to Grass app...")
    driver.get("https://app.getgrass.io/")

    for _ in range(15):  # Retry for up to 15 seconds
        try:
            email_input = driver.find_element(By.XPATH, '//input[@type="email"]')
            password_input = driver.find_element(By.XPATH, '//input[@type="password"]')
            login_button = driver.find_element(By.XPATH, '//button[@type="submit"]')

            email_input.send_keys(user)
            password_input.send_keys(password)
            login_button.click()
            print("Login form submitted.")
            return
        except NoSuchElementException:
            print("Waiting for login form to load...")
            time.sleep(1)

    raise Exception("Failed to load login form within the timeout period.")

def wait_for_dashboard(driver):
    """Waits until the dashboard loads after login."""
    print("Waiting for dashboard...")
    for _ in range(30):  # Retry for up to 30 seconds
        try:
            driver.find_element(By.XPATH, '//*[contains(text(), "Dashboard")]')
            print("Dashboard loaded successfully.")
            return
        except NoSuchElementException:
            time.sleep(1)
    raise Exception("Failed to load dashboard within the timeout period.")

@app.route("/")
def fetch_status():
    """API endpoint to fetch the current status of the Grass app."""
    try:
        network_quality = driver.find_element(By.XPATH, '//*[contains(text(), "Network quality")]').text
        network_quality = re.findall(r'\d+', network_quality)[0]
    except Exception as e:
        network_quality = "Unavailable"
        print(f"Error fetching network quality: {e}")

    try:
        token_element = driver.find_element(By.XPATH, '//*[@alt="token"]/following-sibling::div')
        epoch_earnings = token_element.text
    except Exception as e:
        epoch_earnings = "Unavailable"
        print(f"Error fetching earnings: {e}")

    try:
        badges = driver.find_elements(By.XPATH, '//*[contains(@class, "chakra-badge")]')
        connected = any("Connected" in badge.text for badge in badges)
    except Exception as e:
        connected = False
        print(f"Error fetching connection status: {e}")

    return jsonify({
        "connected": connected,
        "network_quality": network_quality,
        "epoch_earnings": epoch_earnings,
    })

# Main execution
if __name__ == "__main__":
    print("Downloading Chrome extension...")
    download_extension(EXTENSION_ID)
    print("Extension downloaded. Initializing WebDriver...")

    driver = initialize_webdriver()
    try:
        login(driver, USER, PASSW)
        wait_for_dashboard(driver)
        print("Logged in and dashboard loaded. Starting API...")
        app.run(host="0.0.0.0", port=80, debug=False)
    except Exception as e:
        print(f"Error during execution: {e}")
        generate_error_report(driver, str(e))
    finally:
        driver.quit()
        print("Driver closed.")
