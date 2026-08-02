#!/usr/bin/env python3
"""
Selenium Setup Script
=====================
Installs Selenium and ChromeDriver automatically
"""

import os
import platform
import subprocess
import sys

def install_selenium():
    """Install selenium package"""
    print("📦 Installing Selenium...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium==4.16.0"])
        print("✅ Selenium installed successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to install Selenium: {e}")
        return False

def install_chromedriver():
    """Install ChromeDriver using webdriver-manager"""
    print("\n📦 Installing webdriver-manager (auto-downloads ChromeDriver)...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "webdriver-manager"])
        print("✅ webdriver-manager installed successfully!")
        
        # Test if it works
        print("\n🧪 Testing ChromeDriver setup...")
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
        driver.quit()
        
        print("✅ ChromeDriver is working!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n⚠️ webdriver-manager failed. You may need to:")
        print("   1. Install Chrome browser if not installed")
        print("   2. Download ChromeDriver manually from:")
        print("      https://chromedriver.chromium.org/")
        print("   3. Add ChromeDriver to system PATH")
        return False

def check_chrome_installed():
    """Check if Chrome browser is installed"""
    print("\n🔍 Checking if Chrome is installed...")
    
    system = platform.system()
    
    if system == "Windows":
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for path in chrome_paths:
            if os.path.exists(path):
                print(f"✅ Chrome found at: {path}")
                return True
    
    elif system == "Linux":
        try:
            result = subprocess.run(["which", "google-chrome"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Chrome found at: {result.stdout.strip()}")
                return True
        except:
            pass
    
    print("⚠️ Chrome browser not detected!")
    print("   Please install Chrome from: https://www.google.com/chrome/")
    return False

def main():
    print("=" * 80)
    print("🚀 SELENIUM SETUP FOR ELAACH.COM CRAWLER")
    print("=" * 80)
    
    # Check Chrome
    chrome_installed = check_chrome_installed()
    
    if not chrome_installed:
        print("\n❌ Cannot proceed without Chrome browser.")
        print("   Install Chrome first, then run this script again.")
        return
    
    # Install Selenium
    if not install_selenium():
        print("\n❌ Setup failed at Selenium installation.")
        return
    
    # Install ChromeDriver
    if not install_chromedriver():
        print("\n⚠️ ChromeDriver installation had issues.")
        print("   You may need to install it manually.")
    
    print("\n" + "=" * 80)
    print("✅ SETUP COMPLETE!")
    print("=" * 80)
    print("\nYou can now run the elaach crawler:")
    print("  python elaach_crawler.py")
    print()

if __name__ == "__main__":
    main()
