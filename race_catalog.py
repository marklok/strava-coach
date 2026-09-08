"""Small, reviewable marathon catalog. Dates are populated only after verification."""

RACES = [
    # Nordic countries
    {"id":"copenhagen","name":"Copenhagen Marathon","city":"Copenhagen","country":"Denmark","region":"Nordic","url":"https://copenhagenmarathon.dk/en/"},
    {"id":"hca-odense","name":"HCA Marathon","city":"Odense","country":"Denmark","region":"Nordic","url":"https://hcamarathon.dk/"},
    {"id":"north-sea-beach","name":"North Sea Beach Marathon","city":"Hvide Sande","country":"Denmark","region":"Nordic","url":"https://www.northseabeachmarathon.com/"},
    {"id":"stockholm","name":"adidas Stockholm Marathon","city":"Stockholm","country":"Sweden","region":"Nordic","url":"https://www.stockholmmarathon.se/"},
    {"id":"goteborg","name":"Göteborg Marathon","city":"Gothenburg","country":"Sweden","region":"Nordic","url":"https://goteborgmarathon.se/"},
    {"id":"vaxjo","name":"Växjö Marathon","city":"Växjö","country":"Sweden","region":"Nordic","url":"https://vaxjomarathon.se/"},
    {"id":"helsingborg","name":"Helsingborg Marathon","city":"Helsingborg","country":"Sweden","region":"Nordic","url":"https://helsingborgmarathon.se/"},
    {"id":"oslo","name":"Oslo Marathon","city":"Oslo","country":"Norway","region":"Nordic","url":"https://oslomaraton.no/en/"},
    {"id":"bergen","name":"Bergen City Marathon","city":"Bergen","country":"Norway","region":"Nordic","url":"https://www.bergencitymarathon.no/"},
    {"id":"midnight-sun","name":"Midnight Sun Marathon","city":"Tromsø","country":"Norway","region":"Nordic","url":"https://msm.no/en/midnight-sun-marathon/"},
    {"id":"stavanger","name":"Stavanger Marathon","city":"Stavanger","country":"Norway","region":"Nordic","url":"https://stavangermarathon.no/"},
    {"id":"trondheim","name":"Trondheim Marathon","city":"Trondheim","country":"Norway","region":"Nordic","url":"https://www.trondheimmaraton.no/"},
    {"id":"helsinki-city","name":"Helsinki City Marathon","city":"Helsinki","country":"Finland","region":"Nordic","url":"https://helsinkicityrunningday.fi/en/"},
    {"id":"helsinki","name":"Helsinki Marathon","city":"Helsinki","country":"Finland","region":"Nordic","url":"https://helsinkimarathon.fi/en/"},
    {"id":"paavo-nurmi","name":"Paavo Nurmi Marathon","city":"Turku","country":"Finland","region":"Nordic","url":"https://www.paavonurmimarathon.fi/en/"},
    {"id":"tampere","name":"Tampere Marathon","city":"Tampere","country":"Finland","region":"Nordic","url":"https://tampereenmaratonklubi.com/"},
    {"id":"reykjavik","name":"Reykjavik Marathon","city":"Reykjavík","country":"Iceland","region":"Nordic","url":"https://www.rmi.is/en"},
    {"id":"aland","name":"Åland Marathon","city":"Mariehamn","country":"Finland","region":"Nordic","url":"https://www.alandmarathon.ax/"},
    # Rest of Europe
    {"id":"london","name":"TCS London Marathon","city":"London","country":"United Kingdom","region":"Europe","url":"https://www.tcslondonmarathon.com/"},
    {"id":"berlin","name":"BMW Berlin Marathon","city":"Berlin","country":"Germany","region":"Europe","url":"https://www.bmw-berlin-marathon.com/"},
    {"id":"paris","name":"Schneider Electric Marathon de Paris","city":"Paris","country":"France","region":"Europe","url":"https://www.schneiderelectricparismarathon.com/en"},
    {"id":"amsterdam","name":"TCS Amsterdam Marathon","city":"Amsterdam","country":"Netherlands","region":"Europe","url":"https://www.tcsamsterdammarathon.eu/"},
    {"id":"rotterdam","name":"NN Marathon Rotterdam","city":"Rotterdam","country":"Netherlands","region":"Europe","url":"https://www.nnmarathonrotterdam.org/"},
    {"id":"valencia","name":"Valencia Marathon Trinidad Alfonso","city":"Valencia","country":"Spain","region":"Europe","url":"https://www.valenciaciudaddelrunning.com/en/marathon/"},
    {"id":"barcelona","name":"Zurich Marató Barcelona","city":"Barcelona","country":"Spain","region":"Europe","url":"https://www.zurichmaratobarcelona.es/en/"},
    {"id":"rome","name":"Run Rome The Marathon","city":"Rome","country":"Italy","region":"Europe","url":"https://www.runromethemarathon.com/en/"},
    {"id":"vienna","name":"Vienna City Marathon","city":"Vienna","country":"Austria","region":"Europe","url":"https://www.vienna-marathon.com/"},
    {"id":"frankfurt","name":"Mainova Frankfurt Marathon","city":"Frankfurt","country":"Germany","region":"Europe","url":"https://www.frankfurt-marathon.com/en/"},
    {"id":"hamburg","name":"Haspa Marathon Hamburg","city":"Hamburg","country":"Germany","region":"Europe","url":"https://haspa-marathon-hamburg.de/en/"},
    {"id":"prague","name":"Prague International Marathon","city":"Prague","country":"Czechia","region":"Europe","url":"https://www.runczech.com/en/events/orlen-prague-marathon-2026"},
    {"id":"dublin","name":"Irish Life Dublin Marathon","city":"Dublin","country":"Ireland","region":"Europe","url":"https://irishlifedublinmarathon.ie/"},
    {"id":"athens","name":"Athens Marathon. The Authentic","city":"Athens","country":"Greece","region":"Europe","url":"https://www.athensauthenticmarathon.gr/"},
    # United States
    {"id":"boston","name":"Boston Marathon","city":"Boston","country":"United States","region":"United States","url":"https://www.baa.org/races/boston-marathon"},
    {"id":"new-york","name":"TCS New York City Marathon","city":"New York","country":"United States","region":"United States","url":"https://www.nyrr.org/tcsnycmarathon"},
    {"id":"chicago","name":"Bank of America Chicago Marathon","city":"Chicago","country":"United States","region":"United States","url":"https://www.chicagomarathon.com/"},
    {"id":"marine-corps","name":"Marine Corps Marathon","city":"Arlington","country":"United States","region":"United States","url":"https://www.marinemarathon.com/"},
    {"id":"los-angeles","name":"Los Angeles Marathon","city":"Los Angeles","country":"United States","region":"United States","url":"https://www.mccourtfoundation.org/event/los-angeles-marathon/"},
    {"id":"honolulu","name":"Honolulu Marathon","city":"Honolulu","country":"United States","region":"United States","url":"https://www.honolulumarathon.org/"},
    {"id":"philadelphia","name":"Philadelphia Marathon","city":"Philadelphia","country":"United States","region":"United States","url":"https://www.philadelphiamarathon.com/"},
    {"id":"houston","name":"Chevron Houston Marathon","city":"Houston","country":"United States","region":"United States","url":"https://www.chevronhoustonmarathon.com/"},
]


VERIFIED_DATES = {
    # Copy only dates published by the linked organiser. Never infer the next date.
    "copenhagen": ("2027-05-09", "2026-09-08"),
    "boston": ("2027-04-19", "2026-09-08"),
}


def public_catalog():
    result = []
    for race in RACES:
        next_date, verified_at = VERIFIED_DATES.get(race["id"], (None, None))
        result.append(dict(race, next_date=next_date, verified_at=verified_at))
    return result
