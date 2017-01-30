# -*- coding: utf-8 -*-

# TODO: Figure out how to work around the path workaround :)
# import sys
# print(sys.path)

# Webscraping with selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import TimeoutException

# URL encoding
import urllib

# HTML parsing
from bs4 import BeautifulSoup
import re

# Hooking into run function to close browser
from anki.hooks import wrap
from aqt import mw

# Load parameters
from formation_params import initial_url, searchpath

# Colors
colors = ['42A5F5', '4CAF50', 'F57C00', 'D32F2F', '9E9E9E']
# Timeout for Selenium waits
timeout = 2
# BeautifulSoup parser
parser = 'lxml'

# Start virtual browser in module, so we do not have to load it every time
dcap = dict(DesiredCapabilities.PHANTOMJS)
dcap["phantomjs.page.settings.userAgent"] = \
    "Mozilla/5.0 (X11; Linux x86_64; rv:50.0) Gecko/20100101 Firefox/50.0"
browser = webdriver.PhantomJS(desired_capabilities = dcap)
# browser = webdriver.Firefox()
browser.set_window_size(800, 600)

# Start virtual display
# display = Display(visible=0, size=(800, 600))
# display.start()
# Load page to fix colors
# TODO: Adjust to plugin colors
browser.get(initial_url)
# browser.execute_script("setColorScheme('64B4FF','30B030','F08000','D00020','A1A1A1');")
browser.execute_script("setColorScheme(" + ", ".join(["'" + color + "'" for color in colors]) + ");")
browser.execute_script("fn_saveDictionarySetting('0');")

def my_close(*args, **kwargs):
    global browser
    browser.quit()

mw.onClose = wrap(mw.onClose, my_close)

# Hook into run function to close

def innerHTML(element):
    """ Get HTML code of a soup tag """
    return element.decode_contents(formatter="html")

def has_empty_descendants(tag):
    """ Find empty divs in tag """
    desc = tag.descendants
    empty = True
    for d in desc:
        if d.name or d.string.strip():
            empty = False
            break
    return empty and 'gwt-HTML' in tag.get('class', [])

def strip_tags(soup):
    """ Get rid of tags we don't need """
    for tag in soup.find_all('a'):
        tag.name = "span"
        if tag.get('href'):
            del tag['href']
    
    for img in soup.find_all('img'):
        img.decompose()

    for empty_tag in soup.find_all(has_empty_descendants):
        empty_tag.decompose()

def smarten_punctuation(s):
    """ Replace single dash by endash """
    return re.sub(' - ', ' &ndash; ', s)

def simplify_table(soup):
    """ Throw away table tags and other simplifications """
    for tag in soup.find_all():
        if tag.name in ['table', 'td', 'tr', 'tbody', 'input']:
            tag.unwrap()
        elif tag.name == 'span':
            if tag.string and 'Formation:' in tag.string:
                tag.decompose()
            elif tag.get('style'):
                tag['style'] = re.sub('font-size:\w*1\.75em', 'font-size: 1.2em', tag['style'])
        elif tag.name == 'div':
            if tag.get('hidefocus'):
                tag.unwrap()
            tag['style'] = re.sub('padding:.*?;', '', tag.get('style', ''))
            tag['style'] = re.sub('display:inline;', '', tag.get('style', ''))
            for attr in ['hidefocus', 'role', 'aria-hidden']:
                if tag.get(attr):
                    del tag[attr]
        # tag['style'] = re.sub('font-size:.*?;', '', tag.get('style', ''))

def get_formation(hanzi, tree = False):
    """ Get formation information for hanzi

    Only delivers non-empty string if hanzi is a single character.
    tree determines whether to load the whole formation tree.
    """

    if len(hanzi) > 1:
        return ""

    url = searchpath + urllib.quote(hanzi.encode('utf-8'))
    # print(browser)
    browser.get(url)
    # browser.implicitly_wait(timeout)

    # Get formation string
    try:
        WebDriverWait(browser, timeout).until(
                EC.text_to_be_present_in_element((By.ID, "charDef"), "Formation")
                )
    except TimeoutException:
        return ""

    char_def = browser.find_element_by_id("charDef")
    char_def = BeautifulSoup(char_def.get_attribute('outerHTML'), parser)

    # Get formation from char_def
    form_tag = char_def.find('span', string=re.compile('Formation'))
    form_tag.string = form_tag.string.lstrip(u'»').lstrip()
    siblings = list(form_tag.next_siblings)
    formation_doc = BeautifulSoup('', features = parser)
    formation_doc.append(form_tag)
    for s in siblings:
        formation_doc.append(s)
    strip_tags(formation_doc)
    simplify_table(formation_doc)

    if tree:
        # Get tree
        try:
            WebDriverWait(browser, timeout).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "gwt-Tree"))
                    )
            char_tree = browser.find_element_by_class_name("gwt-Tree")

            # Open up recursively
            scissors_left = True
            while scissors_left:
                scissors = char_tree.find_elements_by_xpath("//img[contains(@src, 'etyPlus')]")
                if not scissors:
                    scissors_left = False
                    break
    
                sc = scissors[0]
                sc.click()
                # print('Wait 1')
                # print(sc.get_attribute('outerHTML'))
                # For some reason, the below doesn't work with PhantomJS
                # WebDriverWait(sc, 10).until(
                #     EC.presence_of_element_located((By.XPATH, ".[contains(@src, 'etyMinus')]"))
                #     )
                # print('Wait 2')
                # print(sc.get_attribute('outerHTML'))
                WebDriverWait(sc, timeout).until(
                        EC.presence_of_element_located((By.XPATH, "./following::div[contains(@class, 'gwt-TreeItem')][1]/descendant::a/following-sibling::span"))
                        )
                # print('Done')
    
            char_tree = BeautifulSoup(char_tree.get_attribute('outerHTML'), parser)
            # browser.quit()
    
            # Strip all links from char_tree
            strip_tags(char_tree)
    
            # # Add encoding information
            # headtag = char_tree.new_tag('head')
            # char_tree.html.append(headtag)
            # metatag = char_tree.new_tag('meta')
            # metatag['charset'] = 'utf-8'
            # headtag.append(metatag)
            simplify_table(char_tree)
            char_tree_str = innerHTML(char_tree.body)
        except TimeoutException:
            char_tree_str = ""
    else:
        char_tree_str = ""
        formation_doc.br.decompose()

    char_def_str = innerHTML(formation_doc)

    return smarten_punctuation(char_def_str + char_tree_str)
