import requests
import json
import urllib.parse

headers = {
    'accept': '*/*',
    'accept-language': 'en-GB,en;q=0.9',
    'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
    'cache-control': 'no-cache',
    'content-type': 'application/json',
    'cookie': 'night_mode=2; guest_id=v1%3A172314358710917801; kdt=t6sedN40s0EY4C7bvgrJExfxYB5eyxeJLmoQ2v9Q; auth_token=59f1a68914c50886c4b1e875b9495b6ccd7096e4; ct0=591bbda4074599ea12adfff025946a0c0508f94abeab0406db084dad9216e81b73701cf646b65d562b1b959bf549c7a4dbe5a6f3060c3b00d42932427640d85731f47567e5f5b60c89833be1b58f0749; twid=u%3D1043842619946627072; dnt=1; d_prefs=MjoxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw; lang=en',
    'pragma': 'no-cache',
    'referer': 'https://x.com/search?q=conversation_id%3A1861105589847285835&src=typed_query&f=live',
    'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'sec-gpc': '1',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'x-client-transaction-id': 'T5RxZDxf+pbiHhrGOCIRKJT+8EJ2k95xx/XX/wUoDuQ1e5WpLyMh+7QbGfKdusnaWP7Yt03A+6G4oi/Xxg1T/olN01MOTA',
    'x-client-uuid': 'd8c95e47-29a5-4548-9cd4-b4a0db7afd05',
    'x-csrf-token': '591bbda4074599ea12adfff025946a0c0508f94abeab0406db084dad9216e81b73701cf646b65d562b1b959bf549c7a4dbe5a6f3060c3b00d42932427640d85731f47567e5f5b60c89833be1b58f0749',
    'x-twitter-active-user': 'yes',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-client-language': 'en'
}
def get_tweet_by_id(tweet_id):
    """
    Make Twitter API request and return tweet object matching the given tweet ID.
    
    Args:
        tweet_id (str): The ID of the tweet to find
        
    Returns:
        dict: The matching tweet object, or None if not found
    """
    # API endpoint and parameters
    base_url = "https://x.com/i/api/graphql/nBS-WpgA6ZG0CyNHD517JQ/TweetDetail"
    
    # Request parameters
    variables = {
        "focalTweetId": tweet_id,
        "with_rux_injections": False,
        "rankingMode": "Relevance",
        "includePromotedContent": True,
        "withCommunity": True,
        "withQuickPromoteEligibilityTweetFields": True,
        "withBirdwatchNotes": True,
        "withVoice": True
    }
    
    features = {
        "rweb_tipjar_consumption_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "rweb_video_timestamps_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_enhance_cards_enabled": False
    }
    
    field_toggles = {
        "withArticleRichContentState": True,
        "withArticlePlainText": False,
        "withGrokAnalyze": False,
        "withDisallowedReplyControls": False
    }

    # URL parameters
    params = {
        'variables': json.dumps(variables),
        'features': json.dumps(features),
        'fieldToggles': json.dumps(field_toggles)
    }
    
    try:
        # Make the request
        response = requests.get(base_url, params=params, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
        response_data = response.json()

        # Get the entries from the response
        try:
            entries = response_data['data']['threaded_conversation_with_injections_v2']['instructions'][0]['entries']
        except (KeyError, IndexError):
            return None

        # Helper function to extract tweet from different response structures
        def get_tweet_result(content):
            if not content.get('itemContent'):
                return None
            
            tweet_results = content['itemContent'].get('tweet_results', {})
            if not tweet_results:
                return None
                
            result = tweet_results.get('result')
            if not result:
                return None
                
            # Handle both direct tweets and tweets with visibility results
            if result['__typename'] == 'TweetWithVisibilityResults':
                return result.get('tweet')
            return result if result['__typename'] == 'Tweet' else None

        # Iterate through entries to find matching tweet
        for entry in entries:
            if 'content' in entry:
                # Handle single tweets
                if entry['content']['entryType'] == 'TimelineTimelineItem':
                    tweet = get_tweet_result(entry['content'])
                    if tweet and tweet.get('rest_id') == tweet_id:
                        return tweet
                        
                # Handle conversation threads
                elif entry['content']['entryType'] == 'TimelineTimelineModule':
                    for item in entry['content'].get('items', []):
                        if 'item' in item:
                            tweet = get_tweet_result(item['item'])
                            if tweet and tweet.get('rest_id') == tweet_id:
                                return tweet

        return None

    except requests.RequestException as e:
        print(f"Error making request: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None
    
    
if __name__ == "__main__":
    print(get_tweet_by_id("1861969747228659882"))