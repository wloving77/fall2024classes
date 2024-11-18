import json
import requests
import pandas as pd
import os
from dotenv import load_dotenv
import psycopg
import pymongo
from bson.json_util import dumps, loads
from sqlalchemy import create_engine
from bs4 import BeautifulSoup
import plotly.express as px


class contrans_helper:

    def __init__(self):
        load_dotenv("../.env")
        self.congress_key = os.getenv("CONGRESS_API_KEY")
        self.news_key = os.getenv("NEWS_API_KEY")
        self.postgres_user = os.getenv("POSTGRES_USER")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD")
        self.MONGO_INITDB_ROOT_USERNAME = os.getenv("MONGO_INITDB_ROOT_USERNAME")
        self.MONGO_INITDB_ROOT_PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
        self.us_state_to_abbrev = {
            "Alabama": "AL",
            "Alaska": "AK",
            "Arizona": "AZ",
            "Arkansas": "AR",
            "California": "CA",
            "Colorado": "CO",
            "Connecticut": "CT",
            "Delaware": "DE",
            "Florida": "FL",
            "Georgia": "GA",
            "Hawaii": "HI",
            "Idaho": "ID",
            "Illinois": "IL",
            "Indiana": "IN",
            "Iowa": "IA",
            "Kansas": "KS",
            "Kentucky": "KY",
            "Louisiana": "LA",
            "Maine": "ME",
            "Maryland": "MD",
            "Massachusetts": "MA",
            "Michigan": "MI",
            "Minnesota": "MN",
            "Mississippi": "MS",
            "Missouri": "MO",
            "Montana": "MT",
            "Nebraska": "NE",
            "Nevada": "NV",
            "New Hampshire": "NH",
            "New Jersey": "NJ",
            "New Mexico": "NM",
            "New York": "NY",
            "North Carolina": "NC",
            "North Dakota": "ND",
            "Ohio": "OH",
            "Oklahoma": "OK",
            "Oregon": "OR",
            "Pennsylvania": "PA",
            "Rhode Island": "RI",
            "South Carolina": "SC",
            "South Dakota": "SD",
            "Tennessee": "TN",
            "Texas": "TX",
            "Utah": "UT",
            "Vermont": "VT",
            "Virginia": "VA",
            "Washington": "WA",
            "West Virginia": "WV",
            "Wisconsin": "WI",
            "Wyoming": "WY",
            "District of Columbia": "DC",
            "American Samoa": "AS",
            "Guam": "GU",
            "Northern Mariana Islands": "MP",
            "Puerto Rico": "PR",
            "United States Minor Outlying Islands": "UM",
            "Virgin Islands": "VI",
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
        useragent = json.loads(r.text)["user-agent"]
        return useragent

    def make_headers(self, email="wfl9zy@virginia.edu"):
        useragent = self.get_useragent()
        headers = {"User-Agent": useragent, "From": email}
        return headers

    def get_bioguideIDs(self):
        params = {"api_key": self.congress_key, "limit": 1, "offset": 0}
        headers = self.make_headers()
        root = "https://api.congress.gov/v3/"
        endpoint = "/member"
        r = requests.get(root + endpoint, params=params, headers=headers)

        bioguides = json.loads(r.text)
        total_records = bioguides["pagination"]["count"]

        j = 0
        bio_df = pd.DataFrame()
        while j < total_records:
            params["limit"] = 250
            params["offset"] = j
            r = requests.get(root + endpoint, params=params, headers=headers)
            records = pd.json_normalize((r.json()["members"]))
            bio_df = pd.concat([bio_df, records], ignore_index=True)
            j = j + 250

        return bio_df

    def get_bioguide(self, name, state=None, district=None):

        members = self.get_bioguideIDs()  # replace with SQL query

        members["name"] = members["name"].str.lower().str.strip()
        name = name.lower().strip()

        tokeep = [name in x for x in members["name"]]
        members = members[tokeep]

        if state is not None:
            members = members.query("state == @state")

        if district is not None:
            members = members.query("district == @district")

        return members.reset_index(drop=True)

    def get_sponsoredlegislation(self, bioguideid):

        params = {"api_key": self.congress_key, "limit": 1}
        headers = self.make_headers()
        root = "https://api.congress.gov/v3"
        endpoint = f"/member/{bioguideid}/sponsored-legislation"
        r = requests.get(root + endpoint, params=params, headers=headers)
        totalrecords = r.json()["pagination"]["count"]

        params["limit"] = 250
        j = 0
        bills_list = []
        while j < totalrecords:
            params["offset"] = j
            r = requests.get(root + endpoint, params=params, headers=headers)
            records = r.json()["sponsoredLegislation"]
            bills_list = bills_list + records
            j = j + 250

        return bills_list

    def get_billdata(self, billurl):
        r = requests.get(billurl, params={"api_key": self.congress_key})
        bill_json = json.loads(r.text)
        texturl = bill_json["bill"]["textVersions"]["url"]
        r = requests.get(texturl, params={"api_key": self.congress_key})
        toscrape = json.loads(r.text)["textVersions"][0]["formats"][0]["url"]
        r = requests.get(toscrape)
        mysoup = BeautifulSoup(r.text, "html.parser")
        billtext = mysoup.text
        bill_json["bill"]["bill_text"] = billtext
        return bill_json

    def make_cand_table(self, members):
        # members is output of get_terms()
        replace_map = {"Republican": "R", "Democratic": "D", "Independent": "I"}
        members["partyletter"] = members["partyName"].replace(replace_map)
        members["state"] = members["state"].replace(self.us_state_to_abbrev)
        members["district"] = members["district"].fillna(0)
        members["district"] = members["district"].astype("int").astype("str")
        members["district"] = [
            "0" + x if len(x) == 1 else x for x in members["district"]
        ]
        members["district"] = [x.replace("00", "S") for x in members["district"]]
        members["DistIDRunFor"] = members["state"] + members["district"]
        members["lastname"] = [x.split(",")[0] for x in members["name"]]
        members["firstname"] = [x.split(",")[1] for x in members["name"]]
        members["name2"] = [
            y.strip() + " (" + z.strip() + ")"
            for y, z in zip(members["lastname"], members["partyletter"])
        ]

        cands = pd.read_csv("../data/cands22.txt", quotechar="|", header=None)
        cands.columns = [
            "Cycle",
            "FECCandID",
            "CID",
            "FirstLastP",
            "Party",
            "DistIDRunFor",
            "DistIDCurr",
            "CurrCand",
            "CycleCand",
            "CRPICO",
            "RecipCode",
            "NoPacs",
        ]
        cands["DistIDRunFor"] = [x.replace("S0", "S") for x in cands["DistIDRunFor"]]
        cands["DistIDRunFor"] = [x.replace("S1", "S") for x in cands["DistIDRunFor"]]
        cands["DistIDRunFor"] = [x.replace("S2", "S") for x in cands["DistIDRunFor"]]
        cands["name2"] = [" ".join(x.split(" ")[-2:]) for x in cands["FirstLastP"]]
        cands = cands[["CID", "name2", "DistIDRunFor"]].drop_duplicates(
            subset=["name2", "DistIDRunFor"]
        )
        crosswalk = pd.merge(
            members,
            cands,
            left_on=["name2", "DistIDRunFor"],
            right_on=["name2", "DistIDRunFor"],
            how="left",
        )
        return crosswalk

    def terms_df(self, members):
        termsDF = pd.DataFrame()
        for index, row in members.iterrows():
            bioguide_id = row["bioguideId"]
            terms = row["terms.item"]
            df = pd.DataFrame.from_records(terms)
            df["bioguideId"] = bioguide_id
            termsDF = pd.concat([termsDF, df])
        members = members.drop("terms.item", axis=1)
        return termsDF, members

    # DB Functions:
    def connect_to_postgres(
        self, user, password, host="localhost", port="5432", create_contrans=False
    ):
        dbserver = psycopg.connect(user=user, password=password, host=host, port=port)
        dbserver.autocommit = True
        if create_contrans:
            cursor = dbserver.cursor()
            cursor.execute("DROP DATABASE IF EXISTS contrans")
            cursor.execute("CREATE DATABASE contrans")
        engine = create_engine(
            f"postgresql+psycopg://{user}:{password}@{host}:{port}/contrans"
        )
        return dbserver, engine

    def connect_to_mongo(self, from_scratch=False):
        myclient = pymongo.MongoClient(
            f"mongodb://{self.MONGO_INITDB_ROOT_USERNAME}:{self.MONGO_INITDB_ROOT_PASSWORD}@localhost:27017/"
        )
        mongo_contrans = myclient["contrans"]
        collist = mongo_contrans.list_collection_names()
        if from_scratch and "bills" in collist:
            mongo_contrans.bills.drop()
        return mongo_contrans["bills"]

    def upload_one_member_to_mongo(self, mongo_bills, bioguide):
        bill_list = self.get_sponsoredlegislation(bioguide)
        bill_list_with_text = [self.get_billdata(x["url"]) for x in bill_list]
        mongo_bills.insert_many(bill_list_with_text)

    def upload_many_members_to_mongo(self, mongo_bills, members):
        i = 1
        for m in members:
            status = f"Now uploading bills from {m} to MongoDB: legislator {i} of {len(members)}"
            print(status)
            try:
                self.upload_one_member_to_mongo(mongo_bills, m)
            except:
                print(f"Failed to upload {m}")
            i += 1

    def query_mongo(self, collection, rows, columns):
        cursor = collection.find(rows, columns)
        result_dumps = dumps(cursor)
        result_loads = loads(result_dumps)
        result_df = pd.DataFrame.from_records(result_loads)
        return result_df

    def query_mongo_searchengine(
        self, collection, keytosearch, searchterms, columns={}
    ):

        collection.create_index([(keytosearch, "text")])

        cursor = collection.find(
            {"$text": {"$search": searchterms, "$caseSensitive": False}}, columns
        )
        result_dumps = dumps(cursor)
        result_loads = loads(result_dumps)
        result_df = pd.DataFrame.from_records(result_loads)
        return result_df

    ### Methods for building the 3NF relational DB tables
    def make_members_df(self, members, ideology, engine):
        """
        members should be the output of get_bioguideIDs(),
        with terms removed by get_terms(),
        augmented with contributions by make_cand_table().
        ideology should be the output of get_ideology().
        """
        members_df = pd.merge(
            members, ideology, left_on="bioguideId", right_on="bioguide_id", how="left"
        )
        # dbserver, engine = self.connect_to_postgres(self.POSTGRES_PASSWORD)
        members_df.columns = members_df.columns.str.lower()
        members_df.columns = members_df.columns.str.replace(".", "_")
        members_df.to_sql(
            "members", con=engine, index=False, chunksize=1000, if_exists="replace"
        )

    def make_terms_df(self, terms, engine):
        terms.columns = terms.columns.str.lower()
        terms.to_sql(
            "terms", con=engine, index=False, chunksize=1000, if_exists="replace"
        )

    def make_votes_df(self, votes, engine):
        votes.columns = votes.columns.str.lower()
        votes.to_sql(
            "votes", con=engine, index=False, chunksize=1000, if_exists="replace"
        )

    def make_agreement_df(self):
        return self

    # NEWS API:

    def search_news(self, query):
        params = {"apiKey": self.news_key, "q": query}
        headers = self.make_headers()
        root_url = "https://newsapi.org/v2/everything"

        r = requests.get(root_url, params=params, headers=headers)

        if r.status_code == 200:
            return r.json()
        else:
            return "Error Processing Request"

    def dbml_helper(self, data):
        dt = data.dtypes.reset_index().rename({0: "dtype"}, axis=1)
        replace_map = {"object": "varchar", "int64": "int", "float64": "float"}
        dt["dtype"] = dt["dtype"].replace(replace_map)
        return dt.to_string(index=False, header=False)

    def make_agreement_df(self, bioguide_id, engine):
        myquery = f"""
            SELECT icpsr
            FROM members m
            WHERE bioguideid = {bioguide_id}
            """
        icpsr = int(pd.read_sql_query(myquery, con=engine)["icpsr"][0])
        myquery = f"""
            SELECT m.name, m.partyname, m.state, m.district, v.agree
            FROM members m
            INNER JOIN (
            SELECT
                    a.icpsr AS icpsr1,
                    b.icpsr AS icpsr2,
                    AVG(CAST((a.cast_code = b.cast_code) AS INT)) AS agree
                    FROM votes a
            INNER JOIN votes b
                    ON a.rollnumber = b.rollnumber
                    AND a.chamber = b.chamber
            WHERE a.icpsr={icpsr} AND b.icpsr!={icpsr}
            GROUP BY icpsr1, icpsr2
            ORDER BY agree DESC
            ) v
            ON CAST(m.icpsr AS INT) = v.icpsr2
            WHERE m.icpsr IS NOT NULL
            ORDER BY v.agree DESC
            """
        df = pd.read_sql_query(myquery, con=engine)
        return df.head(10), df.tail(10)

    def plot_ideology(self, bioguide_id):
        server, engine = self.connect_to_postgres(self.postgrespassword)
        myquery = """
                    SELECT bioguideid, district, name, partyname, state, nominate_dim1
                    FROM members
                    """
        ideo = pd.read_sql_query(myquery, con=engine)
        member_ideo = ideo.query(f"bioguideid == {bioguide_id}").reset_index(drop=True)
        fig = px.histogram(
            ideo,
            x="nominate_dim1",
            nbins=60,
            title="Distribution of Nominate Dim1",
            color="partyname",
        )
        fig.update_xaxes(title_text="Left-Right Ideology")
        fig.update_layout(title_x=0.5)
        fig.update_layout(
            title_text="How Liberal or Conservative Is this Person?", title_x=0.5
        )
        fig.update_layout(legend_title_text="Party")
        fig.update_xaxes(
            tickvals=[-0.5, 0, 0.5], ticktext=["Liberal", "Centrist", "Conservative"]
        )
        fig.add_vline(x=0, line_width=1, line_color="black")
        fig.add_vline(
            x=member_ideo.iloc[0]["nominate_dim1"],
            line_width=3,
            line_dash="dash",
            line_color="red",
        )
        fig.update_layout(hovermode="closest")
        fig.add_annotation(
            text=f"{member_ideo.iloc[0]['name']} ({member_ideo.iloc[0]['state']}-{member_ideo.iloc[0]['district']})",
            xref="x",
            yref="paper",
            x=member_ideo.iloc[0]["nominate_dim1"],
            y=1.05,
            showarrow=False,
            font=dict(size=12, color="red"),
        )
        return fig
