import json
import requests
from dotenv import load_dotenv
import pandas as pd
import os

class contrans:

    def __init__(self):
        load_dotenv("../.env")
        self.congress_key = os.getenv("CONGRESS_API_KEY")

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
            
        

