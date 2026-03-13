"""Team name normalization mapping.

Maps openfootball European competition names to Football-Data.co.uk domestic
league names. The domestic name is the canonical form used throughout the project.

Teams that only appear in European data (not in top-5 domestic leagues) are
mapped to a canonical short form for consistency.
"""

# European name -> Domestic/canonical name
# Only includes names that differ; identical names need no mapping.
TEAM_NAME_MAP: dict[str, str] = {
    # England
    "Arsenal FC": "Arsenal",
    "Aston Villa FC": "Aston Villa",
    "Brighton & Hove Albion": "Brighton",
    "Chelsea FC": "Chelsea",
    "Leicester City": "Leicester",
    "Liverpool FC": "Liverpool",
    "Manchester City": "Man City",
    "Manchester City FC": "Man City",
    "Manchester United": "Man United",
    "Manchester United FC": "Man United",
    "Newcastle United FC": "Newcastle",
    "Tottenham Hotspur": "Tottenham",
    "Tottenham Hotspur FC": "Tottenham",
    "West Ham United": "West Ham",
    "West Ham United FC": "West Ham",
    # Spain
    "Athletic Club": "Ath Bilbao",
    "Atlético Madrid": "Ath Madrid",
    "Club Atlético de Madrid": "Ath Madrid",
    "FC Barcelona": "Barcelona",
    "Girona FC": "Girona",
    "Granada CF": "Granada",
    "Málaga CF": "Malaga",
    "Real Betis": "Betis",
    "Real Madrid CF": "Real Madrid",
    "Real Sociedad": "Sociedad",
    "Real Sociedad de Fútbol": "Sociedad",
    "Sevilla FC": "Sevilla",
    "Valencia CF": "Valencia",
    "Villarreal CF": "Villarreal",
    # Germany
    "1. FC Heidenheim 1846": "Heidenheim",
    "1. FC Köln": "FC Koln",
    "1. FC Union Berlin": "Union Berlin",
    "1899 Hoffenheim": "Hoffenheim",
    "Bayer 04 Leverkusen": "Leverkusen",
    "Bayer Leverkusen": "Leverkusen",
    "Bayern München": "Bayern Munich",
    "FC Bayern München": "Bayern Munich",
    "Bor. Mönchengladbach": "M'gladbach",
    "Borussia Dortmund": "Dortmund",
    "Eintracht Frankfurt": "Ein Frankfurt",
    "FC Schalke 04": "Schalke 04",
    "SC Freiburg": "Freiburg",
    "VfB Stuttgart": "Stuttgart",
    "VfL Wolfsburg": "Wolfsburg",
    "RB Leipzig": "RB Leipzig",
    # Italy
    "AC Milan": "Milan",
    "ACF Fiorentina": "Fiorentina",
    "AS Roma": "Roma",
    "Atalanta BC": "Atalanta",
    "Bologna FC 1909": "Bologna",
    "FC Internazionale Milano": "Inter",
    "Juventus FC": "Juventus",
    "Juventus": "Juventus",
    "Lazio Roma": "Lazio",
    "SS Lazio": "Lazio",
    "SSC Napoli": "Napoli",
    "US Salernitana 1919": "Salernitana",
    # France
    "AS Monaco": "Monaco",
    "AS Monaco FC": "Monaco",
    "FC Nantes": "Nantes",
    "Lille OSC": "Lille",
    "Montpellier HSC": "Montpellier",
    "OGC Nice": "Nice",
    "Olympique Lyonnais": "Lyon",
    "Olympique Marseille": "Marseille",
    "Olympique de Marseille": "Marseille",
    "Paris Saint-Germain": "Paris SG",
    "Paris Saint-Germain FC": "Paris SG",
    "RC Lens": "Lens",
    "Racing Club de Lens": "Lens",
    "Stade Brestois 29": "Brest",
    "Stade Rennais": "Rennes",
    "Toulouse FC": "Toulouse",
    # Non-top-5 teams (canonical short forms for European-only teams)
    "AFC Ajax": "Ajax",
    "BSC Young Boys": "Young Boys",
    "Club Brugge KV": "Club Brugge",
    "FC Porto": "Porto",
    "FC Red Bull Salzburg": "RB Salzburg",
    "RB Salzburg": "RB Salzburg",
    "FK Crvena Zvezda": "Crvena Zvezda",
    "FK Shakhtar Donetsk": "Shakhtar Donetsk",
    "GNK Dinamo Zagreb": "Dinamo Zagreb",
    "PFC Ludogorets Razgrad": "Ludogorets",
    "PSV Eindhoven": "PSV",
    "SL Benfica": "Benfica",
    "Sport Lisboa e Benfica": "Benfica",
    "Sporting Clube de Portugal": "Sporting CP",
    "Sporting CP": "Sporting CP",
    "Sporting Braga": "Braga",
    "AC Sparta Praha": "Sparta Praha",
    "Slavia Praha": "Slavia Praha",
    "ŠK Slovan Bratislava": "Slovan Bratislava",
    "SK Sturm Graz": "Sturm Graz",
    "Celtic FC": "Celtic",
    "Rangers FC": "Rangers",
    "Feyenoord Rotterdam": "Feyenoord",
    "RSC Anderlecht": "Anderlecht",
    "Ferencvárosi TC": "Ferencvaros",
    "Viktoria Plzeň": "Viktoria Plzen",
    "IF Elfsborg": "Elfsborg",
    "FK Bodø/Glimt": "Bodo/Glimt",
    "Malmö FF": "Malmo",
    "FC Midtjylland": "Midtjylland",
    "Stade Brestois": "Brest",
    "Qarabağ FK": "Qarabag",
    "FC Twente": "Twente",
    "AZ Alkmaar": "AZ",
    "Union Saint-Gilloise": "Union SG",
    "Dinamo Kiev": "Dynamo Kyiv",
    "AS Roma": "Roma",
    "Galatasaray": "Galatasaray",
    "Fenerbahçe": "Fenerbahce",
    "Beşiktaş": "Besiktas",
    "PAOK Saloniki": "PAOK",
    "Olympiakos Piraeus": "Olympiakos",
    "FC Basel 1893": "Basel",
    "FC Zürich": "Zurich",
    "FCSB": "FCSB",
    "FK RFS": "RFS",
    "Shamrock Rovers": "Shamrock Rovers",
    "Djurgårdens IF": "Djurgarden",
    "NŠ Mura": "Mura",
}


def normalize_team_name(name: str) -> str:
    """Normalize a team name to canonical form.

    Args:
        name: Raw team name from any data source.

    Returns:
        Canonical team name.
    """
    return TEAM_NAME_MAP.get(name, name)
