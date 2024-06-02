import csv
import json
import multiprocessing.synchronize
import re
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException
import multiprocessing
import logging


# TODO: organise these functions into classes ??


logging.basicConfig(filename='error_logs.txt', level=logging.INFO)
csv_lock = multiprocessing.Lock()


        # INGREDIENTS LIST

def view_ingredient(ingredient):
    # This function prints all related information about an ingredient from the csv file

    df = pd.read_csv('price_list.csv')
    ingredients_list = df['ingredient'].values

    if ingredient in ingredients_list:
        print(df.loc[df['ingredient'] == ingredient])
    else:
        print('Ingredient not found in database.')


def add_ingredient(ingredient):
    # This function adds an ingredient to the price_list CSV file

    # Get row info
    price = round(float(input("Price: ")), 2)
    unit = input("Unit: ").strip().lower()
    divisible = input("Divisible ('True' or 'False'): ").title()
    divisible = divisible == 'True'
    shop = input("Shop: ").strip().lower()

    # create row with info, append to df and write back to csv file
    row = [ingredient, price, unit, divisible, shop]
    df = pd.read_csv('price_list.csv')
    row_df = pd.DataFrame([row], columns=df.columns)    ## need [] around 'row' as DataFrame() expects iterable
    df = pd.concat([df, row_df], ignore_index=True)     ## ignoring the index reassigns a new index for the new dataframe, otherwise it will keep its old index
    df.to_csv('price_list.csv', index=False)       ## index=False makes sure we do not write the index back to the CSV file

    # sort the file after adding
    print(f"{ingredient} added!")
    alphabetize_price_list()


def modify_unit(ingredient, unit):
    # This function changes the unit value of an ingredient in the csv file

    with csv_lock:
        df = pd.read_csv('price_list.csv', index_col='ingredient')
        df.at[ingredient, 'unit'] = unit
        df.to_csv('price_list.csv')


def modify_price(ingredient, price):
    # This function allows changes the price of an ingredient in the csv file

    with csv_lock:
        df = pd.read_csv('price_list.csv', index_col='ingredient')
        df.at[ingredient, 'price'] = price
        df.to_csv('price_list.csv')


def reset_last_update(ingredient):
    # This function resets the 'last_update' column to today's date

    with csv_lock:
        today_date = datetime.now().date().strftime("%d/%m")
        df = pd.read_csv('price_list.csv', index_col='ingredient')
        df.at[ingredient, 'last_update'] = today_date
        df.to_csv('price_list.csv')


def alphabetize_price_list():
    # This function sorts the csv file into alphabetical order

    with open('price_list.csv', "r") as csv_file:
        csv_reader = csv.DictReader(csv_file)
        sorted_price_list = sorted(csv_reader, key=lambda x: x['ingredient'])

    with open('price_list.csv', "w") as csv_file:
        fieldnames = sorted_price_list[0].keys()
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(sorted_price_list)


def get_unit(ingredient):
    # This function returns the unit measure of an ingredient from the csv_file
    csv_file = pd.read_csv('price_list.csv', index_col='ingredient')
    return csv_file.loc[ingredient, 'unit']


def get_price(ingredient):
    # This function returns the price of an ingredient from the csv_file
    csv_file = pd.read_csv('price_list.csv', index_col='ingredient')
    return csv_file.loc[ingredient, 'price']


def get_shop(ingredient):
    # This function returns the shop where we buy a specific ingredient from the csv_file
    csv_file = pd.read_csv('price_list.csv', index_col='ingredient')
    return csv_file.loc[ingredient, 'shop']



        # RECIPES LIST

def view_recipe():
    with open("recipes.json", "r") as json_file:
        recipes = json.load(json_file)

    recipe_name = input("Name of Recipe: ").strip().lower()
    if recipe_name in recipes:
        print(recipes[recipe_name])
    else:
        print("Recipe not found in database")


def alphabetize_recipes_list():
    # This function alphabetizes the recipes list in the JSON file

    with open("recipes.json", "r") as json_file:
        recipes = json.load(json_file)
        sorted_recipes = {recipe: recipes[recipe] for recipe in sorted(recipes)}  ## iterates over sorted recipe names and adds them as keys in a new dict, with their old values

    with open("recipes.json", "w") as json_file:
        json.dump(sorted_recipes, json_file, indent=4)
    print("Recipes alphabetized!")


def add_recipe():
    # This function adds a recipe to the 'recipes' json file

    # get name of the recipe and list of ingredients with quantities, stored as a nested dict
    with open("recipes.json", "r") as json_file:
        recipes = json.load(json_file)

    recipe_name = input("Name of Recipe: ").lower()
    if recipe_name in recipes:
        print("A recipe with that name already exists.")
    else:
        ingredients_dict = {}
        portions_dict = {}

        # get ingredients and quantities
        print("Enter the recipe's ingredients with their relevant quantities (type 'done' when finished)")
        while True:
            ingredient = input("Ingredient: ").lower().strip()
            if ingredient == 'done':
                break
            quantity = float(input("Quantity: "))

            ingredients_dict[ingredient] = quantity  ## key = ingredient, value = quantity of ingredient

        # get portion-sizes for different event-type
        print("Enter event types and relevant portion sizes (type 'done' when finished)")
        while True:
            event_type = input("Event Type: ").lower().strip()
            if event_type == 'done':
                break
            portion = int(input("Portion: ").strip())
            portions_dict[event_type] = portion

        # nest dicts and load to json file
        recipe = {recipe_name: {'ingredients': ingredients_dict, 'portions': portions_dict}}
        recipes.update(recipe)
        with open("recipes.json", "w") as json_file:
            json.dump(recipes, json_file, indent=4)

        # sort list so new recipe is in alphabetical order
        alphabetize_recipes_list()
        print(f"{recipe_name} added to database!")
        return recipe_name




        # BOTH DATABASES


def match_recipe_with_csv(recipe):
    # This function makes sure that any ingredient in a recipe is included in the price_list csv

    with open("recipes.json", "r") as json_file:
        recipes = json.load(json_file)

    # creates an ingredients' list from the recipe file
    recipe_ingredients = []
    for ingredient, quantity in recipes[recipe]['ingredients'].items():
        recipe_ingredients.append(ingredient)

    # check to see if each ingredient is in the csv_file, if it's not then add it to a missing_ingredients list
    df = pd.read_csv('price_list.csv')
    missing_ingredients = []
    ingredients_list = df['ingredient'].values
    for ingredient in recipe_ingredients:
        if ingredient not in ingredients_list:
            missing_ingredients.append(ingredient)

    # if there are any missing ingredients, print what's missing and prompt the user to add them to the file
    if len(missing_ingredients) > 0:
        print(f"The following ingredients in '{recipe}' do not exist in the price_list database")
        print(missing_ingredients)
        print("Would you like to \nA: add them to the file now \nB: add them later")
        while True:
            choice = input(" ").strip().upper()
            if choice == 'A':
                for ingredient in missing_ingredients:
                    print(ingredient)
                    add_ingredient(ingredient)
                alphabetize_price_list()
                break
            elif choice == 'B':
                break
            else:
                print("Invalid Input. Enter 'A' or 'B' only")


def match_entire_database():
    # the following function checks if every ingredient in every recipe exists in the json file
    with open("recipes.json", "r") as json_file:
        recipes = json.load(json_file)
        for recipe, recipe_details in recipes.items():
            match_recipe_with_csv(recipe)


def calculate_recipe_cost(recipe_to_calculate):
    with open("recipes.json", "r") as json_file:
        recipes = json.load(json_file)
        for recipe in recipes:
            if recipe == recipe_to_calculate:
                ingredients = recipes[recipe]['ingredients']

                total_cost = 0
                for ingredient, quantity in ingredients.items():
                    total_cost += get_price(ingredient) * quantity

                return round(total_cost, 2)


if __name__ == '__main__':
    while True:
        add_recipe()

