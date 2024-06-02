import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException
import re
from bs4 import BeautifulSoup
import multiprocessing
import time
from datetime import datetime
import logging
import json

df = pd.read_csv("price_list.csv")
df.drop('divisible', axis=1, inplace=True)
df.to_csv('price_list.csv', index=False)

