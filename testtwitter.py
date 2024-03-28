from twitter.scraper import Scraper
from twitter.util import *
import pandas as pd

scraper = Scraper(session=init_session())

# example tweet
tweet = scraper.tweets_details([1476988122986647553], limit=500, pbar=False)

# unnest items and filter deleted tweets
items = [y for x in find_key(tweet, "items") for y in x if not find_key(y, "tombstone")]

# index into relevant data points
tweet_results = [x.get("result") for x in find_key(items, "tweet_results")]

print(tweet_results)

# df = (
# pd.json_normalize(tweet_results)
# remove duplicate replies if needed
# .drop_duplicates("rest_id")
# clean up column names for illustrative purposes
# .assign(
#     date=lambda x: pd.to_datetime(x["legacy.created_at"]).dt.strftime(
#         "%Y-%m-%d %H:%M:%S"
#     )
# )
# .assign(root_tweet=lambda x: x["legacy.conversation_id_str"])
# .assign(text=lambda x: x["legacy.full_text"])
# .assign(tweet=lambda x: x["rest_id"])
# .assign(username=lambda x: x["core.user_results.result.legacy.screen_name"])
# sort by newest replies to root_tweet
# .sort_values("date", ascending=False).reset_index(drop=True)
# )
