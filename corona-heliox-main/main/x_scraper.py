try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
import re

def normalize_count(value: str) -> int | None:
    """Convert Twitter-style counts like '236.5K' or '2.3M' to integers."""
    if not value:
        return None
    value = value.strip()
    multiplier = 1
    if value.endswith("K"):
        multiplier = 1_000
        value = value[:-1]
    elif value.endswith("M"):
        multiplier = 1_000_000
        value = value[:-1]
    elif value.endswith("B"):
        multiplier = 1_000_000_000
        value = value[:-1]
    try:
        return int(float(value) * multiplier)
    except ValueError:
        return None


def scrape_twitter_profile(url: str):
    if sync_playwright is None:
        return {"name": None, "handle": None, "description": "Twitter scraper offline or Playwright not installed.", "followers": None}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # set True for headless
        page = browser.new_page()
        page.set_default_timeout(120_000)
        page.set_default_navigation_timeout(120_000)
        page.goto(url)

        profile = {}

        # --- Name ---
        name_xpath = "//div[@data-testid='UserName']//span[normalize-space(text()) != '']"
        page.wait_for_selector(f"xpath={name_xpath}")
        profile["name"] = page.locator(f"xpath={name_xpath}").nth(0).inner_text()

        # --- Handle ---
        handle_xpath = "//div[@data-testid='UserName']//span[contains(text(), '@')]"
        profile["handle"] = page.locator(f"xpath={handle_xpath}").inner_text()

        # --- Description (bio) ---
        desc_xpath = "//div[@data-testid='UserDescription']"
        if page.locator(f"xpath={desc_xpath}").count() > 0:
            profile["description"] = " ".join(page.locator(f"xpath={desc_xpath}//span").all_inner_texts())
        else:
            profile["description"] = None

        # --- Mentions in bio (like @yzilabs) ---
        mentions_xpath = "//div[@data-testid='UserDescription']//a[contains(@href, '/')]"
        profile["mentions"] = [m.inner_text() for m in page.locator(f"xpath={mentions_xpath}").all()]

        # --- External links in bio (TEXT instead of href) ---
        links_xpath = "//div[@data-testid='UserDescription']//a[@href and starts-with(@href,'http')]"
        profile["bio_links"] = [l.inner_text() for l in page.locator(f"xpath={links_xpath}").all()]

        # --- Avatar (profile image) ---
        avatar_xpath = "//div[starts-with(@data-testid,'UserAvatar-Container')]//img"
        if page.locator(f"xpath={avatar_xpath}").count() > 0:
            profile["avatar"] = page.locator(f"xpath={avatar_xpath}").first.get_attribute("src")
        else:
            profile["avatar"] = None

        # --- Location ---
        loc_xpath = "//span[@data-testid='UserLocation']"
        profile["location"] = page.locator(f"xpath={loc_xpath}").inner_text() if page.locator(f"xpath={loc_xpath}").count() > 0 else None

        # --- Website (TEXT instead of href) ---
        url_xpath = "//a[@data-testid='UserUrl']"
        profile["website"] = page.locator(f"xpath={url_xpath}").inner_text() if page.locator(f"xpath={url_xpath}").count() > 0 else None

        # --- Join date ---
        join_xpath = "//span[@data-testid='UserJoinDate']"
        profile["join_date"] = page.locator(f"xpath={join_xpath}").inner_text() if page.locator(f"xpath={join_xpath}").count() > 0 else None

        # --- Following count ---
        following_xpath = "//a[contains(@href,'/following')]//span[not(contains(text(),'Following'))]"
        if page.locator(f"xpath={following_xpath}").count() > 0:
            raw_following = page.locator(f"xpath={following_xpath}").nth(0).inner_text()
            profile["following"] = normalize_count(raw_following)
        else:
            profile["following"] = None

        # --- Followers count ---
        followers_xpath = "//a[contains(@href,'followers')]//span"
        spans = page.locator(f"xpath={followers_xpath}")
        raw_followers = None

        for s in spans.all():
            txt = s.inner_text().strip()
            # Match numbers like "88", "236.5K", "1.2M"
            if re.match(r"^[\d,.]+[KMB]?$", txt):
                raw_followers = txt
                break

        profile["followers_raw"] = raw_followers        # keep the original text like "1.2M"
        profile["followers"] = normalize_count(raw_followers)  # convert to int: 1200000


        # verified_xpath = "//svg[contains(@data-testid,'icon-verified')]"
        # profile["is_verified"] = page.locator(f"xpath={verified_xpath}").count() > 0

        browser.close()
        return profile


def scrape_profile(x_profile: str) :
    try:
        data = scrape_twitter_profile(x_profile)
        return data
    except :
        return None
