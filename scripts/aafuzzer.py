#!/usr/bin/env python3

import os
import time

from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup


# https://gist.github.com/thepeoplesbourgeois/66c2eeecc5b264efd41471ca5e354b1a
allEvenListeners = '''
async function getExtShadowRoot() {
  let shadowHost;
  await (shadowHost = driver.findElement(By.css(CSS_SHADOW_HOST)));
  return driver.executeScript("return arguments[0].shadowRoot", shadowHost);
}

async function findShadowDomElement(shadowDomElement) {
  let shadowRoot;
  let element;
  await (shadowRoot = getExtShadowRoot());
  await shadowRoot.then(async (result) => {
    await (element = result.findElement(By.css(shadowDomElement)));
  });
  
  return element;
}

function allEventListeners(){
  const eventNames = Object.keys(window).filter(key => /^(on|mouse)/.test(key))
  //const eventNames = Object.keys(document).filter(key => /^on/.test(key))
  //const drawer = document.getElementsByClassName("pf-c-page__drawer")
  //const eventNames = Object.keys(drawer).filter(key => /^on/.test(key))
  
  return [...document.querySelectorAll('*'), document].flatMap((node) => eventNames
    .filter(event => node[event])
    .map(event => {
       console.log(node, event)
       return {
         node,
         event,
         listener: (typeof node[event] === 'function') ? node[event].toString() : node[event]
       }
    })
  )
}

console.table(allEventListeners())
console.log(getExtShadowRoot())
'''


class AAFuzzer:
    def __init__(self, screenshot_path='screenshots'):
        self.username = os.environ.get('RHN_USERNAME')
        self.password = os.environ.get('RHN_PASSWORD')
        self.driver = None
        self.screenshot_path = screenshot_path
        if not os.path.isdir(self.screenshot_path):
            os.makedirs(self.screenshot_path)
    
    def go_to_homepage(self):
        self.driver.get('https://prod.foo.redhat.com:1337/beta/ansible/automation-analytics/clusters')

    def do_login(self):
        #input id=username
        username_field = self.driver.find_element_by_id("username")
        username_field.send_keys(self.username)
        #button id=login-show-step2
        next_button = self.driver.find_element_by_id("login-show-step2")
        next_button.click()
        time.sleep(3)

        # input id=password
        password_field = self.driver.find_element_by_id("password")
        password_field.send_keys(self.password)

        # input id=kc-login
        login_button = self.driver.find_element_by_id('kc-login')
        login_button.click()
    
    def get_navbar_links(self):
        # nav class="pf-c-nav pf-m-dark" aria-label="Insights Global Navigation"
        # xpath: /html/body/div/aside/nav
        topnav = self.driver.find_element_by_xpath('/html/body/div/aside/nav')
        subnavs = topnav.find_elements_by_tag_name('ul')

        links = []
        for subnav in subnavs:
            apps = subnav.find_elements_by_tag_name('li')
            for app in apps:
                thisclass = app.get_attribute('class')
                print(thisclass)

                hrefs = app.find_elements_by_tag_name('a')
                for href in hrefs:
                    thisurl = href.get_attribute('href')
                    print(thisurl)
                    links.append([thisurl, href])

        navdict = {}
        for link in links:
            print(link)
            #parent = link[1].parent
            parsed = urlparse(link[0])
            navdict[parsed.path] = link[0]
            #import epdb; epdb.st()

        #import epdb; epdb.st()
        return navdict


    def enumerate_page(self, pageurl, pagename):
        # https://stackoverflow.com/a/16544813
        # getEventListeners(domElement)

        print(pageurl)

        self.driver.get(pageurl)
        time.sleep(3)
        self.driver.execute_script(allEvenListeners)
        #data = self.driver.get_log('browser')
        
        # pfc-page__drawer
        #.pf-c-page__drawer

        self.driver.save_screenshot("screenshot_CURRENT_PAGE.png")

        #if 'org' in pageurl:
        #    import epdb; epdb.st()
        sname = "screenshot_%s.png" % pagename.replace('/', '__SLASH__')
        sname = os.path.join(self.screenshot_path, sname)
        print('writing %s ...' % sname)
        self.driver.save_screenshot(sname)


    def run(self):
        # dnf install chromedriver ...
        #self.driver = webdriver.Chrome('/usr/bin/chromedriver')
        #import epdb; epdb.st()

        firefox_profile = webdriver.FirefoxProfile()
        firefox_profile.accept_untrusted_certs = True
        firefox_options = webdriver.FirefoxOptions()
        firefox_options.set_headless()

        geckodriver = os.path.join(os.getcwd(), 'geckodriver')
        self.driver = webdriver.Firefox(firefox_options=firefox_options, firefox_profile=firefox_profile)
        # firefox only ...
        self.driver.maximize_window()
        #for x in range(0, 4):
        #    self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.CONTROL, Keys.SUBTRACT)
        
        #self.driver.get('https://google.com')
        #import epdb; epdb.st()

        self.go_to_homepage()
        time.sleep(3)
        self.do_login()
        time.sleep(5)

        self.driver.save_screenshot("screenshot1.png")

        original_size = self.driver.get_window_size()
        required_width = self.driver.execute_script('return document.body.parentNode.scrollWidth')
        required_height = self.driver.execute_script('return document.body.parentNode.scrollHeight')
        self.driver.set_window_size(required_width, required_height)
        self.driver.set_window_size(1920, 2000)

        '''
        // To zoom out 3 times
        for(int i=0; i<3; i++){
            driver.findElement(By.tagName("html")).sendKeys(Keys.chord(Keys.CONTROL,Keys.SUBTRACT));
        }
        '''

        #for x in range(0, 4):
        #    self.driver.find_element(by.By('html')).send_keys(Keys.CONTROL, Keys.SUBTRACT)

        self.driver.save_screenshot("screenshot2.png")
        navbar_links = self.get_navbar_links()
        keys = sorted(list(navbar_links.keys()))
        for key in keys:
            if 'automation-analytics' in key:
                #self.driver.get(navbar_links[key])
                #if 'org' not in key:
                #    continue
                self.enumerate_page(navbar_links[key], key)
                #time.sleep(3)
        
        #import epdb; epdb.st()

if __name__ == "__main__":
    fuzzer = AAFuzzer()
    fuzzer.run()
