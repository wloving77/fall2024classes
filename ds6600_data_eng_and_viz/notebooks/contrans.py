import json
import requests
import pandas as pd
import os
from dotenv import load_dotenv
import BeautifulSoup


class contrans:

    def __init__(self):
        load_dotenv("../.env")
        self.mypassword = os.getenv("PASSWORD")
        self.congress_key = os.getenv("CONGRESS_API_KEY")
        self.news_key = os.getenv("NEWS_API_KEY")
        self.us_state_to_abbrev = {
                        "Alabama": "AL","Alaska": "AK","Arizona": "AZ","Arkansas": "AR",
                        "California": "CA","Colorado": "CO","Connecticut": "CT","Delaware": "DE",
                        "Florida": "FL","Georgia": "GA","Hawaii": "HI",
                        "Idaho": "ID","Illinois": "IL","Indiana": "IN","Iowa": "IA",
                        "Kansas": "KS","Kentucky": "KY","Louisiana": "LA",
                        "Maine": "ME","Maryland": "MD","Massachusetts": "MA",
                        "Michigan": "MI","Minnesota": "MN","Mississippi": "MS",
                        "Missouri": "MO","Montana": "MT","Nebraska": "NE",
                        "Nevada": "NV","New Hampshire": "NH","New Jersey": "NJ",
                        "New Mexico": "NM","New York": "NY","North Carolina": "NC",
                        "North Dakota": "ND","Ohio": "OH","Oklahoma": "OK",
                        "Oregon": "OR","Pennsylvania": "PA","Rhode Island": "RI",
                        "South Carolina": "SC","South Dakota": "SD","Tennessee": "TN",
                        "Texas": "TX","Utah": "UT","Vermont": "VT",
                        "Virginia": "VA","Washington": "WA","West Virginia": "WV",
                        "Wisconsin": "WI","Wyoming": "WY","District of Columbia": "DC",
                        "American Samoa": "AS","Guam": "GU","Northern Mariana Islands": "MP",
                        "Puerto Rico": "PR","United States Minor Outlying Islands": "UM",
                        "Virgin Islands": "VI"
                        }

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


    def get_bioguide(self, name, state=None, district=None):
        
        members = self.get_bioguideIDs() # replace with SQL query

        members['name'] = members['name'].str.lower().str.strip()
        name = name.lower().strip()

        tokeep = [name in x for x in members['name']]
        members = members[tokeep]

        if state is not None:
                members = members.query('state == @state')

        if district is not None:
                members = members.query('district == @district')
        
        return members.reset_index(drop=True)

    def get_sponsoredlegislation(self, bioguideid):

            params = {'api_key': self.congresskey,
                        'limit': 1} 
            headers = self.make_headers()
            root = 'https://api.congress.gov/v3'
            endpoint = f'/member/{bioguideid}/sponsored-legislation'
            r = requests.get(root + endpoint,
                                params=params,
                                headers=headers)
            totalrecords = r.json()['pagination']['count']
            
            params['limit'] = 250
            j = 0
            bills_list = []
            while j < totalrecords:
                    params['offset'] = j
                    r = requests.get(root + endpoint,
                                        params=params,
                                        headers=headers)
                    records = r.json()['sponsoredLegislation']
                    bills_list = bills_list + records
                    j = j + 250

            return bills_list
            
    def make_cand_table(self, members):
            # members is output of get_terms()
            replace_map = {'Republican': 'R','Democratic': 'D','Independent': 'I'}
            members['partyletter'] = members['partyName'].replace(replace_map)
            members['state'] = members['state'].replace(self.us_state_to_abbrev)
            members['district'] = members['district'].fillna(0)
            members['district'] = members['district'].astype('int').astype('str')
            members['district'] = ['0' + x if len(x) == 1 else x for x in members['district']]
            members['district'] = [x.replace('00', 'S') for x in members['district']]
            members['DistIDRunFor'] = members['state']+members['district']
            members['lastname']= [x.split(',')[0] for x in members['name']]
            members['firstname']= [x.split(',')[1] for x in members['name']]
            members['name2'] = [ y.strip() + ' (' + z.strip() + ')' 
                            for y, z in 
                            zip(members['lastname'], members['partyletter'])]
            
            cands = pd.read_csv('data/CampaignFin22/cands22.txt', quotechar="|", header=None)
            cands.columns = ['Cycle', 'FECCandID', 'CID','FirstLastP',
                            'Party','DistIDRunFor','DistIDCurr',
                            'CurrCand','CycleCand','CRPICO','RecipCode','NoPacs']
            cands['DistIDRunFor'] = [x.replace('S0', 'S') for x in cands['DistIDRunFor']]
            cands['DistIDRunFor'] = [x.replace('S1', 'S') for x in cands['DistIDRunFor']]
            cands['DistIDRunFor'] = [x.replace('S2', 'S') for x in cands['DistIDRunFor']]
            cands['name2'] = [' '.join(x.split(' ')[-2:]) for x in cands['FirstLastP']]
            cands = cands[['CID', 'name2', 'DistIDRunFor']].drop_duplicates(subset=['name2', 'DistIDRunFor'])
            crosswalk = pd.merge(members, cands, 
                    left_on=['name2', 'DistIDRunFor'],
                    right_on=['name2', 'DistIDRunFor'],
                    how = 'left')
            return crosswalk

    def terms_df(self, members):
            termsDF = pd.DataFrame()
            for index, row in members.iterrows():
                    bioguide_id = row['bioguideId']
                    terms = row['terms.item']
                    df = pd.DataFrame.from_records(terms)
                    df['bioguideId'] = bioguide_id
                    termsDF = pd.concat([termsDF, df])
            members = members.drop('terms.item', axis=1)
            return termsDF, members

    ### Methods for building the 3NF relational DB tables

    def make_members_df(self, members, ideology):
            members_df = pd.merge(members, ideology, 
                                    left_on='bioguideId', 
                                    right_on='bioguide_id',
                                    how='left')
            return members_df

    def make_terms_df(self):
            return self

    def make_votes_df(self):
            return self

    def make_agreement_df(self):
            return self

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


    def make_cand_table(self): 
        return -1
        

        

