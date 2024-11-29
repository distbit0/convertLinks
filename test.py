import requests

# Define the URL
url = 'https://x.com/i/api/graphql/MJuDXJXZ8bB--c9Ujhy-0g/SearchTimeline'

# Define the query parameters
params = {
    'variables': '{"rawQuery":"conversation_id:1862299845710757980 min_faves:2","count":20,"querySource":"typed_query","product":"Latest"}',
    'features': '{"profile_label_improvements_pcf_account_label_enabled":false,"rweb_tipjar_consumption_enabled":true,"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"rweb_video_timestamps_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_enhance_cards_enabled":false}'
}

# Define the headers
headers = {
    'accept': '*/*',
    'accept-language': 'en-GB,en;q=0.5',
    'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
    'cache-control': 'no-cache',
    'content-type': 'application/json',
    'cookie': 'night_mode=2; kdt=t6sedN40s0EY4C7bvgrJExfxYB5eyxeJLmoQ2v9Q; dnt=1; d_prefs=MjoxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw; lang=en; guest_id=v1%3A173278321753001926; auth_token=30086fdc8e8d3dc6d1d02dc2ed7e929f042a7c94; ct0=ae7892fcdd5d77a23f9beae29bc8ed2212c790900ea3374bd18f7fff4c66869588eab0dec08df6a2aa5137c9644d820bf91f0890fd7b4da3d0a92c12d937262e5f5126f8786fb90b35a4cd4703313f71; twid=u%3D1043842619946627072; att=1-P4YHrZ4F5dSK8jMNv0JBKOhOnAX2L1qAEqT9urAK; guest_id_ads=v1%3A173278321753001926; guest_id_marketing=v1%3A173278321753001926; personalization_id="v1_r0b5l0vhGrk1FqgOOJLRFg=="; external_referer=padhuUp37zihGDM6YyBmzmoi5sb8ERvkS0wlDqCOris%3D|0|8e8t2xd8A2w%3D',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://x.com/search?q=conversation_id%3A1862299845710757980+min_faves%3A2&src=typed_query&f=live',
    'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'sec-gpc': '1',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'x-client-transaction-id': '1RbofayWfT13G6AWlkkJ9BjIurNitJYb46nfI5Vz7E/5eX3o/Xvpik7JJWohk3hliH8gLNcpDMvc/EG7fziNcdcAWxVs1g',
    'x-client-uuid': 'd8c95e47-29a5-4548-9cd4-b4a0db7afd05',
    'x-csrf-token': 'ae7892fcdd5d77a23f9beae29bc8ed2212c790900ea3374bd18f7fff4c66869588eab0dec08df6a2aa5137c9644d820bf91f0890fd7b4da3d0a92c12d937262e5f5126f8786fb90b35a4cd4703313f71',
    'x-twitter-active-user': 'yes',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-client-language': 'en'
}

# Make the GET request
response = requests.get(url, params=params, headers=headers)

# Print the response
print(response.status_code)
print(response.json())  # If the response is JSON