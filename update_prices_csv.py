import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException
from pydantic import BaseModel, field_validator, ValidationError

from file_manager import modify_price, modify_unit, reset_last_update
import multiprocessing
import multiprocessing.synchronize
from datetime import datetime, date
import re
import logging


csv_lock = multiprocessing.Lock()


# Pydantic model to check if ingredients data is correct
class Ingredient(BaseModel):
    name: str
    price: float
    unit: str
    shop: str
    last_update: date


    @field_validator('price')
    def validate_price(cls, price):
        if price <= 0:
            raise ValueError("Price must be positive")
        else:
            price = round(price, 2)
            return price

    @field_validator('last_update')
    def validate_last_update(cls, value):
        # Check if the date is in 'dd/mm' format
        try:
            date_str = value.strftime('%d/%m')
            return value
        except ValueError:
            raise ValueError(f"Invalid 'last_update' format: {date_str}. Use 'dd/mm'.")


def update_aldi_price(*ingredients):
    # This function searches for the ingredient on the Aldi webpage and returns its current price

    with webdriver.Chrome() as driver:## this page doesnt work in headless mode
        url = "https://www.aldi.co.uk/"
        driver.get(url)
        wait = WebDriverWait(driver, 10)

        for index, ingredient in enumerate(ingredients):
            try:
                if index == 0:
                    # if the T&C popup appears click accept
                    accept = wait.until(
                        EC.presence_of_element_located((By.ID, "onetrust-accept-btn-handler"))
                    )
                    accept.click()

                    # Adjust the search-bar toggle to look for groceries
                    wait.until(EC.invisibility_of_element_located((By.ID, 'onetrust-group-container')))
                    search_toggle = wait.until(
                        EC.element_to_be_clickable((By.CLASS_NAME, 'dropdown-search'))
                                               )
                    search_toggle.click()
                    groceries = driver.find_element(By.ID, "groceries")
                    groceries.click()

                    # search for the specified ingredient in the search bar
                    search_bar = driver.find_element(By.ID, "typeahead")
                    search_bar.send_keys(ingredient)
                    search_bar.send_keys(Keys.ENTER)

                    # Switch to the newly opened tab (assuming it's the last one in the list)
                    all_handles = driver.window_handles
                    new_tab_handle = all_handles[-1]
                    driver.switch_to.window(new_tab_handle)

                elif index >= 1:
                    search_bar = driver.find_element(By.ID, "search-input")
                    search_bar.send_keys(ingredient)
                    search_bar.send_keys(Keys.ENTER)

                # navigate to the correct webpage for the ingredient
                ingredient_page_link = wait.until(
                    EC.presence_of_element_located((By.XPATH, f"//a[contains(text(), '{ingredient.title()}')]"))
                )
                ingredient_page_link.click()

                # locate the price per unit
                element = wait.until(EC.visibility_of_element_located(
                    (By.XPATH, "//small[@property='price' and @data-qa='product-price']//span"))
                                     )
                unit_price = element.text

                # scrape the correct price and unit
                if "each" in unit_price:
                    price, unit = unit_price.split(" ")[0], "whole"
                    price = price.replace("£", "")

                elif "per kg" in unit_price:
                    price, unit = unit_price.split(" per ")
                    price = price.replace("£", "")

                elif "ml" in unit_price:
                    price = unit_price.split(" per ")[0].replace("£", "")
                    price = float(price) * 10   ## as aldi gives price per 100ml
                    unit = "l"

                elif "g" in unit_price:
                    price = unit_price.split(" per ")[0].replace("£", "")
                    price = float(price) * 10   ## as aldi gives price per 100g
                    unit = "kg"
                else:
                    print(f"{ingredient} has unaccounted for unit, check aldi webpage.")

                price = round(float(price), 2)

                # validate the ingredient with pydantic validator
                ingredient = Ingredient(name=ingredient, price=price, unit=unit)

                # write the unit and price back to csv and reset the 'last update' column to today
                with csv_lock:
                    modify_unit(ingredient, unit)
                    modify_price(ingredient, price)
                    reset_last_update(ingredient)
                    print(f"{ingredient} updated!")

            except NoSuchElementException:
                logging.error(f"Aldi: {ingredient} not found on webpage")
            except TimeoutException:
                logging.error(f"Aldi: timed out for {ingredient}")
            except ElementNotInteractableException:
                logging.error(f'Aldi: {ingredient} was not interactable')
            except ValueError as e:
                logging.error(f'Aldi: check value for {ingredient}; {e}')


def update_yasar_halim_price(*ingredients):
    # This function searches for the ingredient on the Yasir Halim webpage and returns its current price

    with webdriver.Chrome() as driver:    ## headless mode not working
        url = "https://www.yasarhalim.com/"
        driver.get(url)
        wait = WebDriverWait(driver, 10)

        for ingredient in ingredients:
            try:
                # search for the ingredient on yasir halim search bar
                search_bar = wait.until(
                    EC.presence_of_element_located((By.ID, "small-searchterms"))
                                        )
                search_bar.send_keys(ingredient)
                search_bar.send_keys(Keys.ENTER)

                # locate the html script for the ingredient's webpage
                ingredient_page_link = wait.until(
                    EC.presence_of_element_located((By.XPATH, f"//a[contains(text(), '{ingredient.title()}')]"))
                )
                ingredient_page_link.click()
                html_content = driver.page_source

                # scrape the price of ingredient from its webpage
                soup = BeautifulSoup(html_content, "html.parser")
                price_cell = soup.find(class_="product-price")
                price = float(price_cell.get_text().strip().replace("£", ""))

                # scrape the correct unit from webpage
                name = soup.find(class_="product-name")
                name = name.text

                # modify the price and unit depending on the unit
                if "Each" in name:
                    unit = "whole"
                elif "Single" in name:
                    unit = "single"
                elif "Bunch" in name:
                    unit = "bunch"
                elif "Pack" in name:
                    unit = "pack"
                elif "G" in name or "Gr" in name:
                    unit_in_g = re.search(r'\w* (\d{1,3}) ?[Gr]{1,2}', name).groups(1)
                    weight = float(unit_in_g[0])
                    if weight >= 100:
                        price = price * 1000 / weight
                        unit = "kg"
                    else:
                        unit = "pack"
                elif "Kg" in name:
                    unit_in_kg = re.search(r'\w* (\d{1-2}) ?Kg', name)
                    weight = int(unit_in_kg.groups(1))
                    price = price / weight
                    unit = "kg"
                else:
                    print(f"{ingredient} unit unaccounted for, check website")
                    unit = "unknown"

                price = round(price, 2)

                # write the unit and price back to csv and reset the 'last update' column to today
                with csv_lock:
                    modify_unit(ingredient, unit)
                    modify_price(ingredient, price)
                    reset_last_update(ingredient)
                    print(f"{ingredient} updated!")

            # if any exceptions crop up, print which ingredients could not be updated and why
            except NoSuchElementException:
                logging.error(f"Yasar Halim: {ingredient} not found on webpage")
            except TimeoutException:
                logging.error(f"Yasar Halim: timed out for {ingredient}")
            except ElementNotInteractableException:
                logging.error(f'Yasar Halim: {ingredient} was not interactable')
            except ValueError as e:
                logging.error(f'Yasar Halim: check value for {ingredient}; {e}')


def update_waitrose_price(*ingredients):
    with webdriver.Chrome() as driver:    ## headless mode not working
        url = "https://www.waitrose.com/"
        driver.get(url)
        wait = WebDriverWait(driver, 10)

        for ingredient in ingredients:
            try:
                # if the T&C popup appears click accept
                accept = wait.until(
                    EC.presence_of_element_located((By.XPATH, '//span[text()="Allow all"]'))
                )
                accept.click()
                print("1")
                # search for the ingredient in the searchbar
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input.input___XVnxR[placeholder="Search groceries..."]'))
                )
                search_bar = driver.find_element((By.CSS_SELECTOR, 'input.input___XVnxR[placeholder="Search groceries...]'))
                search_bar.send_keys(ingredient)
                search_bar.send_keys(Keys.ENTER)
                print("2")
                # navigate to the correct ingredient webpage
                ingredient_page_link = wait.until(
                    EC.presence_of_element_located((By.LINK_TEXT, f"//a[contains(text(), '{ingredient.title()}')]"))
                )
                ingredient_page_link.click()

                name = wait.until(
                    EC.presence_of_element_located((By.ID, "productName"))
                                  )
                print(name.text)


            except:
                ...


def update_all_prices():
    # This function updates all prices and units in the CSV file
    df = pd.read_csv("price_list.csv")
    aldi_ingredients = []
    yasar_halim_ingredients = []
    today_date = datetime.now().date().strftime("%d/%m")

    # iterate through the csv and if an ingredient has not been updated today, divide ingredients by their shop
    for index, row in df.iterrows():
        ingredient = row['ingredient']

        if row['shop'] == "aldi" and not row['last_update'] == today_date:
            aldi_ingredients.append(ingredient)
        elif row['shop'] == "yasar halim":
            yasar_halim_ingredients.append(ingredient)
        else:
            continue

    # run separate threads for each web browser
    aldi_thread = multiprocessing.Process(target=update_aldi_price, args=(*aldi_ingredients,))
    yasar_halim_thread = multiprocessing.Process(target=update_yasar_halim_price, args=(*yasar_halim_ingredients,))

    aldi_thread.start()
    yasar_halim_thread.start()

    aldi_thread.join()
    yasar_halim_thread.join()


def validate_csv_database():
    df = pd.read_csv("price_list.csv")
    for index, row in df.iterrows():
        name = row['ingredient']
        price = row['price']
        unit = row['unit']
        shop = row['shop']
        last_update = row['last_update']

        try:
            Ingredient(name=name, price=price, unit=unit, shop=shop, last_update=last_update)
            print("All values are valid!")
        except ValueError:
            logging.error(f'Validation Error: "{name}" not valid, check CSV file')


if __name__ == '__main__':
    df = pd.read_csv("price_list.csv")
    aldi_ingredients = []
    today_date = datetime.now().date().strftime("%d/%m")

    for index, row in df.iterrows():
        ingredient = row['ingredient']

        if row['shop'] == "aldi" and not row['last_update'] == today_date:
            aldi_ingredients.append(ingredient)
        for ingredient in aldi_ingredients:
            update_aldi_price(ingredient)