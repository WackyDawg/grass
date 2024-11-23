from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, NoSuchDriverException, ElementNotInteractableException
from flask import Flask
import time
import requests
import hashlib
import re
import os
import sys

# Configuration
extension_id = 'ilehaonighjijnmpnagapkhpcdbhclfg'
CRX_URL = "https://clients2.google.com/service/update2/crx?response=redirect&prodversion=98.0.4758.102&acceptformat=crx2,crx3&x=id%3D~~~~%26uc&nacl_arch=x86-64"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
USER = os.getenv('GRASS_USER', 'your_email@example.com')  # Replace with your email
PASSW = os.getenv('GRASS_PASS', 'your_password')          # Replace with your password
ALLOW_DEBUG = os.getenv('ALLOW_DEBUG', 'True').lower() == 'true'

# Validate configuration
if not USER or not PASSW:
    print("Error: Please set GRASS_USER and GRASS_PASS environment variables.")
    sys.exit(1)

if ALLOW_DEBUG:
    print("Debugging is enabled!")

# Helper functions
def download_extension(extension_id):
    """Downloads the Chrome extension as a CRX file."""
    url = CRX_URL.replace("~~~~", extension_id)
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, stream=True, headers=headers)
    with open("extension.crx", "wb") as file:
        for chunk in response.iter_content(chunk_size=128):
            file.write(chunk)
    if ALLOW_DEBUG:
        md5 = hashlib.md5(open("extension.crx", "rb").read()).hexdigest()
        print(f"Extension MD5: {md5}")

def generate_error_report(driver):
    """Generates a debug report with a screenshot and logs."""
    if not ALLOW_DEBUG:
        return
    driver.save_screenshot("error.png")
    logs = driver.get_log("browser")
    with open("error.log", "w") as log_file:
        for log in logs:
            log_file.write(f"{log}\n")
    print("Error report generated!")

# Selenium setup
def initialize_driver():
    """Initializes the Selenium WebDriver."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_extension("extension.crx")
    
    try:
        return webdriver.Chrome(options=options)
    except (WebDriverException, NoSuchDriverException):
        print("Error: Unable to start the WebDriver.")
        sys.exit(1)

# Main workflow
def login_to_site(driver):
    """Logs into the Grass application."""
    driver.get("https://app.getgrass.io/")
    sleep_counter = 0

    # Wait for login form to load
    while True:
        try:
            user_input = driver.find_element(By.NAME, "user")
            password_input = driver.find_element(By.NAME, "password")
            submit_button = driver.find_element(By.XPATH, '//*[@type="submit"]')
            break
        except:
            time.sleep(1)
            sleep_counter += 1
            if sleep_counter > 15:
                print("Error: Login form not loaded.")
                generate_error_report(driver)
                sys.exit(1)

    # Enter login credentials
    try:
        user_input.send_keys(USER)
        password_input.send_keys(PASSW)
        submit_button.click()
    except ElementNotInteractableException:
        print("Error: Unable to interact with login fields.")
        generate_error_report(driver)
        sys.exit(1)

    # Wait for dashboard to load
    sleep_counter = 0
    while True:
        try:
            driver.find_element(By.XPATH, '//*[contains(text(), "Dashboard")]')
            break
        except:
            time.sleep(1)
            sleep_counter += 1
            if sleep_counter > 30:
                print("Error: Login failed.")
                generate_error_report(driver)
                sys.exit(1)

def start_flask_api(driver):
    """Starts a Flask API to interact with the browser session."""
    app = Flask(__name__)

    @app.route("/")
    def get_status():
        try:
            network_quality_element = driver.find_element(By.XPATH, '//*[contains(text(), "Network quality")]')
            network_quality = re.findall(r'\d+', network_quality_element.text)[0]
        except:
            network_quality = "Unavailable"
            print("Warning: Unable to retrieve network quality.")

        try:
            token_element = driver.find_element(By.XPATH, '//*[@alt="token"]/following-sibling::div')
            epoch_earnings = token_element.text
        except:
            epoch_earnings = "Unavailable"
            print("Warning: Unable to retrieve epoch earnings.")

        try:
            badges = driver.find_elements(By.CLASS_NAME, "chakra-badge")
            connected = any("Connected" in badge.text for badge in badges)
        except:
            connected = False
            print("Warning: Unable to determine connection status.")

        return {
            "connected": connected,
            "network_quality": network_quality,
            "epoch_earnings": epoch_earnings,
        }

    app.run(host="0.0.0.0", port=80, debug=False)

# Main execution
if __name__ == "__main__":
    print("Downloading extension...")
    download_extension(extension_id)
    print("Extension downloaded successfully!")

    print("Initializing WebDriver...")
    driver = initialize_driver()
    print("WebDriver initialized!")

    print("Logging in...")
    login_to_site(driver)
    print("Login successful!")

    print("Starting Flask API...")
    start_flask_api(driver)

    print("Exiting...")
    #driver.quit()
