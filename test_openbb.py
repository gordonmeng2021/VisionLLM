from openbb import obb
# obb.news.world(provider='fmp',fmp_api_key='Ofxmp6rl0uvRujfr34G3qWk2usLBkk34')
# obb.news.world(limit=100, provider='intrinio')
# Get news on the specified dates.
# obb.news.world(start_date='2025-09-17', end_date='2025-09-17', provider='intrinio')
# # Display the headlines of the news.
# obb.news.world(display=headline, provider='benzinga')
# # Get news by topics.
# obb.news.world(topics=finance, provider='benzinga')
# # Get news by source using 'tingo' as provider.
# obb.news.world(provider='tiingo', source=bloomberg)
# # Filter aticles by term using 'biztoc' as provider.
# obb.news.world(provider='biztoc', term=apple)

#!/usr/bin/env python
try:
    # For Python 3.0 and later
    from urllib.request import urlopen
except ImportError:
    # Fall back to Python 2's urllib2
    pass
import certifi
import json

def get_jsonparsed_data(url):
    response = urlopen(url, cafile=certifi.where())
    data = response.read().decode("utf-8")
    return json.loads(data)

url = ("https://financialmodelingprep.com/stable/news/general-latest?page=0&limit=20&apikey=Ofxmp6rl0uvRujfr34G3qWk2usLBkk34")
print(get_jsonparsed_data(url))
