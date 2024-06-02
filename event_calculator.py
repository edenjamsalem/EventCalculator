import pandas as pd
import json
import math
from file_manager import get_unit, get_price, get_shop
from pydantic import BaseModel, validator
from datetime import date


# Pydantic model to check if ingredients data is correct
class Ingredient(BaseModel):
    name: str
    price: int
    unit: str
    shop: str
    last_update: date


def get_event_details():
    # This function asks the user to input the guest count, recipes, and event type

    guest_count = int(input("Number of Guests: ").strip())
    recipes_list = input("List of dishes served: ").lower().split(', ')
    event_type = input("Type of event (buffet, dinner, canape, etc): ").lower()
    return guest_count, recipes_list, event_type


def estimate_recipe_quantities(recipes_list, event_type, guest_count):
    # This function estimates the quantity of each recipe in the json file that is needed for the given guest count

    recipe_count_columns = ["Recipe", "Multiple"]
    recipe_count = pd.DataFrame(columns=recipe_count_columns)

    for recipe in recipes_list:
        with open('recipes.json', "r") as json_file:
            recipes = json.load(json_file)

            portion_size = float(recipes[recipe]['portions'][event_type])
            recipe_multiplier = round(guest_count * 2 / portion_size) / 2

            new_row = pd.DataFrame([[recipe, recipe_multiplier]], columns=recipe_count_columns)
            recipe_count = pd.concat([recipe_count, new_row], ignore_index=True)

    print("\nEstimated recipe quantities:\n")
    print(recipe_count)
    return recipe_count


def get_user_changes(recipe_count):
    # This function allows the user to change any of the estimated recipe multipliers to fit with the event
    # This way we can exercise our better judgment for how much we think a party will require

    while True:
        user_changes = input(
            "If yes, enter in format: 'recipe: new_quantity', ... \nIf no, enter: 'no'\n").strip().lower()
        if user_changes == "no":
            break
        else:
            try:
                changes = user_changes.split(", ")
                for change in changes:
                    recipe_to_change, new_multiple = change.split(": ")
                    recipe_count.loc[recipe_count['Recipe'] == recipe_to_change, 'Multiple'] = float(new_multiple)
                break
            except ValueError:
                print(f"Invalid input. Please use correct format: 'recipe: new_quantity', ...")

    print(recipe_count)
    return recipe_count


def format_shopping_list(shopping_list, recipes_list):
    # This function formats the shopping list

    # Here we group any like ingredients and sum their quantities
    shopping_list = shopping_list.groupby('ingredient').agg(
        {'quantity': 'sum', 'unit': 'first', 'shop': 'first', 'recipe': lambda x: x.tolist()}).reset_index()

    # here we check if an ingredient is used in all recipes, and print "all recipes" if so
    # this just prints a nicer visual format
    for index, row in shopping_list.iterrows():
        if len(row['recipe']) == len(recipes_list):
            shopping_list.loc[index, 'recipe'] = '[all recipes]'

    # here we check if the quantity of an ingredient is divisible, if not, we round up to the nearest integer
    # this is because we cannot buy, for example, half a bottle of oil
    for index, row in shopping_list.iterrows():
        if row['unit'] == "kg":
            shopping_list.loc[index, 'quantity'] = round(row['quantity'], 1)
        else:
            shopping_list.loc[index, 'quantity'] = math.ceil(row['quantity'])

    # here we create a prices column, and calculate the cost of each ingredient needed for the event
    prices = []
    for index, row in shopping_list.iterrows():
        ingredient = row['ingredient']
        quantity = row['quantity']
        unit_price = get_price(ingredient)
        prices.append(round(quantity * unit_price, 2))

    shopping_list['price'] = prices

    # here we adjust the order of the columns to be more logical and sort the row by which shop we need to buy them
    column_order = ['shop', 'ingredient', 'quantity', 'unit', 'price', 'recipe']
    shopping_list = shopping_list[column_order]
    shopping_list = shopping_list.sort_values(by='shop', ignore_index=True)

    return shopping_list


def calculate_shopping_list(recipes_list, recipe_count):
    # This function creates a shopping list for the list of recipes given for an event

    shopping_list_columns = ['ingredient', 'quantity', 'unit', 'shop', 'recipe']
    shopping_list = pd.DataFrame(columns=shopping_list_columns)

    for recipe in recipes_list:
        with open('recipes.json', "r") as json_file:
            recipes = json.load(json_file)
            recipe_ingredients = recipes[recipe]['ingredients']
            recipe_multiple = recipe_count.loc[recipe_count['Recipe'] == recipe, 'Multiple'].values[0]

            for ingredient, recipe_quantity in recipe_ingredients.items():
                event_quantity = recipe_quantity * recipe_multiple
                unit = get_unit(ingredient)
                shop = get_shop(ingredient)

                new_row = pd.DataFrame({
                    'ingredient': [ingredient],
                    'quantity': [event_quantity],
                    'unit': [unit],
                    'shop': [shop],
                    'recipe': [recipe]
                }, columns=shopping_list_columns)
                shopping_list = pd.concat([shopping_list, new_row], ignore_index=True)

    return shopping_list


def calculate_total_cost(shopping_list):
    # This function calculates the total cost of the event from the shopping list df
    total_cost = round(shopping_list['price'].sum(), 2)
    return total_cost


def main():
    guest_count, recipes_list, event_type = get_event_details()
    recipe_count = estimate_recipe_quantities(recipes_list, event_type, guest_count)
    recipe_count = get_user_changes(recipe_count)

    shopping_list = calculate_shopping_list(recipes_list, recipe_count)
    shopping_list = format_shopping_list(shopping_list, recipes_list)

    # here we make sure that the df is not compressed when printed on the screen
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    print(shopping_list.to_string(max_colwidth=100))

    total_cost = calculate_total_cost(shopping_list)
    print(f'\nTotal cost: {total_cost}')


if __name__ == '__main__':
    main()

# hummus, schug, moroccan carrots, matbucha


# TODO: find out how to remove the decimal place for whole number quantities

# TODO: code defensively against errors

# TODO: create a program to test this code

# TODO: load all our recipes into the files and adjust price info and portion sizing


