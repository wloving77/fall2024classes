import json
import requests
import pandas as pd
import os
from dotenv import load_dotenv


class contrans:

    def __init__(self):
        load_dotenv("../.env")
        self.congress_key = os.getenv("CONGRESS_API_KEY")
        self.news_key = os.getenv("NEWS_API_KEY")

    def get_votes(self):
        url = "https://voteview.com/static/data/out/votes/H118_votes.csv"
        votes = pd.read_csv(url)
        return votes
    
    def get_ideology(self):
        url = "https://voteview.com/static/data/out/members/H118_members.csv"
        members = pd.read_csv(url)
        return members

    def get_useragent(self):
        url = "https://httpbin.org/user-agent"
        r = requests.get(url)
        useragent = json.loads(r.text)['user-agent']
        return useragent
        
    def make_headers(self, email='wfl9zy@virginia.edu'):
        useragent = self.get_useragent()
        headers = {
            'User-Agent': useragent, 
            'From': email
        }
        return headers
    
    def get_bioguideIDs(self):
        params = {'api_key': self.congress_key, 'limit': 1, 'offset': 0}
        headers = self.make_headers()
        root = "https://api.congress.gov/v3/"   
        endpoint = "/member"
        r = requests.get(root + endpoint
                         ,params=params
                         ,headers=headers)
        
        bioguides = json.loads(r.text)
        total_records = bioguides['pagination']['count']

        j=0
        bio_df = pd.DataFrame()
        while j < total_records: 
            params['limit'] = 250
            params['offset'] = j
            r = requests.get(root + endpoint, params=params, headers=headers)
            records = pd.json_normalize((r.json()['members']))
            bio_df = pd.concat([bio_df, records], ignore_index=True)
            j = j + 250

        return bio_df


    def get_bioguide(self, first_name, last_name, state=None, district=None):
        
        members = self.get_bioguideIDs() # to be stored in PostgreSQL 

        # Create first and last names field
        members['last_names'] = members['name'].str.replace(",","").str.lower().str.strip().str.split().str[0]
        members['first_names'] = members['name'].str.replace(",","").str.lower().str.strip().str.split().str[1]

        members = members[(members['first_names'] == first_name) & (members['last_names'] == last_name)].copy()
        
        if state is not None:
            members = members[members['state'] == state].copy()

        if district is not None:
            members = members[members['district'] == district].copy()

        return members
    
    def get_sponsored_legislation(self, bioguideid):
        root = "https://api.congress.gov/v3/"   
        endpoint = f'/member/{bioguideid}/sponsored-legislation'
        headers = self.make_headers()
        params = {"api_key":self.congress_key, "limit": 1}

        r = requests.get(root + endpoint,
                         params=params,
                         headers=headers)

        total_records = r.json()['pagination']['count']        
        
        j=0
        sl_df = pd.DataFrame()
        while j < total_records: 
            params['limit'] = 250
            params['offset'] = j
            r = requests.get(root + endpoint, params=params, headers=headers)
            records = pd.json_normalize((r.json()['sponsoredLegislation']))
            sl_df = pd.concat([sl_df, records], ignore_index=True)
            j = j + 250
        
        return sl_df


    # NEWS API:


    def search_news(self, query):
        params = {"apiKey":self.news_key, "q":query}
        headers = self.make_headers()
        root_url = "https://newsapi.org/v2/everything"

        r = requests.get(root_url, params=params, headers=headers)

        if(r.status_code==200):
            return r.json()
        else:
            return "Error Processing Request"
        

        

