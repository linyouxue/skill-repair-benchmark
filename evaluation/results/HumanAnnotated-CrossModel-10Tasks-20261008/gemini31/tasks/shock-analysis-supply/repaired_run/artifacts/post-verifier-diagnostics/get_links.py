from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('https://www.imf.org/en/Publications/WEO/weo-database/2023/October/download-entire-database')
        
        links = page.eval_on_selector_all('a', '(elements) => elements.map(e => {return {text: e.innerText, href: e.href}})')
        for i, link in enumerate(links):
            if 'xls' in link['href'] or 'xlsx' in link['href'] or 'tsv' in link['href'] or 'csv' in link['href']:
                print(f"Found link: {link['text']} -> {link['href']}")
                
        browser.close()

run()
