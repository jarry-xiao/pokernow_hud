import pandas as pd
from IPython.display import display
import matplotlib.pyplot as plt
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 100)
pd.options.mode.chained_assignment = None 
pd.options.display.width = 0
import os
import datetime
from IPython.core.display import display, HTML
import configparser

cfg = configparser.ConfigParser()
cfg.read("config.ini")
log_dir = cfg["PATHS"]["log_dir"]
img_dir = cfg["PATHS"]["image_dir"]
graph_dir = cfg["PATHS"]["pnl_graph_dir"]

REPLACE = list(cfg._sections["REPLACE"].items())
aliases = cfg._sections["ALIASES"]

game_logs = []
for fname in os.listdir(log_dir):
    path = os.path.join(log_dir, fname)
    t = datetime.datetime.fromtimestamp(os.path.getmtime(path))
    if t.year < 2021:
        continue
    df = pd.read_csv(path)
    df["session"] = fname.split(".")[0].split("_")[-1]
    game_logs.append(df)
    
game = pd.concat(game_logs)
game = game.sort_values(["at", "order"]).reset_index(drop=True)
game["at"] = pd.to_datetime(game["at"])
game = game[~game.entry.str.contains("WARNING")]
game.entry = game.entry.str.lower()
game.entry = game.entry.str.replace('"', "")
for source, target in REPLACE:
    game.entry = game.entry.str.lower().str.replace(source, target)
game["hand_id"] = None
is_starting_hand = game.entry.str.startswith("-- starting")
starting_hands = game.loc[is_starting_hand, "entry"]
i = starting_hands.str.split(" ", expand=True)[3].str[1:].astype(int)
game.loc[is_starting_hand, "hand_id"] = i
game.hand_id = game.hand_id.ffill()
game["street"] = None
is_pre = game.entry.str.startswith("-- starting hand")
is_flop = game.entry.str.startswith("flop")
is_turn = game.entry.str.startswith("turn")
is_river = game.entry.str.startswith("river")
is_ending = game.entry.str.startswith("-- ending hand")
game.loc[is_pre, "street"] = "pre"
game.loc[is_flop, "street"] = "flop" 
game.loc[is_turn, "street"] = "turn" 
game.loc[is_river, "street"] = "river"
game.loc[is_ending, "street"] = "" 
game.street = game.street.ffill()
street_ids = {
    "pre": 0,
    "flop": 1,
    "turn": 2,
    "river": 3,
}
game["street_id"] = game.street.map(street_ids)


NUMBER_REGEX = r'(\s[0-9]+[\.]?[0-9]*(\s|$))'
has_player_info = game.entry.str.contains(" @ ")
player_subset = game.loc[has_player_info]
parsed_entry = player_subset.entry.str.split(" @ ", expand=True)
names = parsed_entry[0].str.split(expand=True).ffill(axis=1)
game.loc[has_player_info, "player"] = names[names.shape[1] - 1].str.lower()
game.loc[has_player_info, "player_id"] = parsed_entry[1].str.split(expand=True)[0]
result = game
result["folded"] = result.entry.str.endswith("folds")
result["showdown"] = result.entry.str.contains("collected") & result.entry.str.contains("with")
result["uncalled"] = result.entry.str.contains("uncalled")
result["betting"] = 0 
is_bet = result.entry.str.contains(r"bets|posts|raises|calls")
is_payoff = result.entry.str.contains(r"collected")
result["all_in"] = result.entry.str.contains("all in")
result["bet"] = -result.entry.str.extract(NUMBER_REGEX)[0].str.strip().astype(float).round(2)
result.loc[result.folded, "bet"] = 0
result.loc[is_payoff, "bet"] *= -1
result.loc[result.uncalled, "bet"] *= -1
result.loc[is_payoff, "street"] = "result"
result.loc[result.uncalled, "street"] = "uncalled"
missed_sb = result.entry.str.contains("missing small blind")
missed_bb = result.entry.str.contains("missing big blind")
result.loc[missed_sb, "street"] = "missed_sb"
result.loc[missed_sb, "street"] = "missed_bb"
result.bet.update(result.loc[result.street == "result"].groupby(["session", "hand_id", "player"]).bet.cumsum())
result = result.merge(result.groupby(["session", "hand_id"]).showdown.any().reset_index(), on=["session", "hand_id"], suffixes=["_raw", ""])

aliases_map = dict(zip(result.player.dropna().str.lower().unique(), result.player.dropna().str.lower().unique()))
aliases_map.update(aliases)
print(aliases_map)


result["player"] = result["player"].map(aliases_map)
result["date"] = result["at"].dt.strftime("%Y-%m-%d")
pots = (
    result
    .query("bet <= 0")
    .groupby(["session", "hand_id", "street_id", "player"]).bet.last()
    .groupby(["session", "hand_id", "street_id"]).sum()
    .groupby(["session", "hand_id"]).cumsum().bfill().ffill()
    .rename("pot")
    .reset_index()
)
result = result.merge(pots, how="left", on=["session", "hand_id", "street_id"])
result["pot"] *= -1


hands = result.query("bet == bet and bet != 0 and hand_id == hand_id and street != ''")
betting_action = hands.drop_duplicates(["player", "session", "hand_id", "street"], keep="last").round(2)
bugs = betting_action.groupby(["session", "hand_id"]).bet.sum().round(2).reset_index().query("bet != 0")
# If this DataFrame is empty, the accounting is probably correct
print("Accounting Errors:")
if bugs.shape[0] == 0:
    print("No obvious accounting bugs found")
    print()
else:
    display(bugs)
    print()

def debug(bug_index):
    try:
        b = bugs.loc[bug_index]
        s = b.session
        h = b.hand_id
        display(result.query("session == @s and hand_id == @h"))
        display(betting_action.query("session == @s and hand_id == @h"))
    except:
        pass


print("All sessions/dates recorded")
display(result[["date", "session"]].drop_duplicates())
print()

hands = result.query("bet == bet and bet != 0 and hand_id == hand_id and street != ''")
betting_action = hands.drop_duplicates(["player", "session", "hand_id", "street"], keep="last").round(2)
profits = betting_action.groupby(["session", "hand_id", "player"], as_index=False).agg({"bet": "sum", "at": "last"}).sort_values("at")
pd.pivot_table(profits, index=["session", "hand_id"], columns="player").bet.fillna(0).cumsum().plot(figsize=(20, 10))
plt.xticks([])
plt.title("Total PnL")
plt.savefig(os.path.join(img_dir, "total_pnl.png"))

betting_action["session_date"] = betting_action.session.map(dict(betting_action[["session", "date"]].drop_duplicates("session").values))
profits = betting_action.groupby(["session_date", "player"], as_index=False).agg({"bet": "sum", "at": "last"}).sort_values("at")
profits = pd.pivot_table(profits, index=["session_date"], columns="player").bet.fillna(0)
print("Profit by session (note dates are based on UTC)")
display(profits)
print()
print("Cumulative Profit by session")
display(profits.cumsum())

hands = result.query("bet == bet and bet != 0 and hand_id == hand_id and street != '' and showdown")
betting_action = hands.drop_duplicates(["player", "session", "hand_id", "street"], keep="last").round(2)
profits = betting_action.groupby(["session", "hand_id", "player"], as_index=False).agg({"bet": "sum", "at": "last"}).sort_values("at")
pd.pivot_table(profits, index=["at"], columns="player").bet.fillna(0).cumsum().reset_index().drop("at", axis=1).plot(figsize=(20, 10))
plt.xticks([])
plt.title("Showdown PnL")
plt.savefig(os.path.join(img_dir, "showdown_pnl.png"))

hands = result.query("bet == bet and bet != 0 and hand_id == hand_id and street != '' and not showdown")
betting_action = hands.drop_duplicates(["player", "session", "hand_id", "street"], keep="last").round(2)
profits = betting_action.groupby(["session", "hand_id", "player"], as_index=False).agg({"bet": "sum", "at": "last"}).sort_values("at")
pd.pivot_table(profits, index=["at"], columns="player").bet.fillna(0).cumsum().reset_index().drop("at", axis=1).plot(figsize=(20, 10))
plt.xticks([])
plt.title("Non-Showdown PnL")
plt.savefig(os.path.join(img_dir, "non_showdown_pnl.png"))

for player in result.player.dropna().unique():
    hands = result.query("bet == bet and bet != 0 and hand_id == hand_id and street != ''")
    betting_action = hands.drop_duplicates(["player", "session", "hand_id", "street"], keep="last").round(2)
    profits = betting_action.groupby(["session", "hand_id", "player"], as_index=False).agg({"bet": "sum", "at": "last", "showdown": "last"})
    showdown = pd.pivot_table(profits, index="at", columns="player").showdown[player].astype(float).dropna().sort_index()
    total = pd.pivot_table(profits, index="at", columns="player").bet[player].dropna().sort_index()
    sd = total.copy()
    nsd = total.copy()
    sd.loc[showdown == 0] = None
    sd = sd.reset_index()
    sd[player] = sd[player].fillna(0).cumsum()
    nsd.loc[showdown == 1] = None
    nsd = nsd.reset_index()
    nsd[player] = nsd[player].fillna(0).cumsum()
    total = total.reset_index()
    total[player] = total[player].fillna(0).cumsum()
    a = total.plot(y=player, color="g", figsize=(20, 10), label="Profit")
    sd.plot(y=player, color="b", ax=a, label="Showdown")
    nsd.plot(y=player, color="r", ax=a, label="Non-Showdown")
    plt.xticks([])
    plt.title(f"{player.capitalize()}'s PnL Breakdown")
    plt.savefig(os.path.join(graph_dir, f"{player}_pnl.png"))


def print_big_hands(d):
# d = "2021-02-02"
    big_hands = result.query("date == @d and street == 'result' and bet >= 50")
    for _, row in big_hands.iterrows():
        s = row.session
        h = row.hand_id
        log = result.query("session == @s and hand_id == @h")
        display(log[["entry"]])


def print_preflop_ratios():
    pre = result.query("bet == bet and hand_id == hand_id and street == 'pre'")
    stats = []
    for p, pg in pre.groupby("player"):
        pg = pg[
            ~pg.entry.str.contains("collect") 
            & ~pg.entry.str.contains("uncalled")
            & ~pg.entry.str.contains("blinds")
        ]
        last_action = pg.groupby(["session", "hand_id"]).last()
        total_hands = len(last_action)
        last_action = pg.query("bet != 0").groupby(["session", "hand_id"]).last()

        calls = last_action[last_action.entry.str.contains("calls")]
        raises = last_action[last_action.entry.str.contains("bets|raises", regex=True)]
        data = {"player": p, "PFR": len(raises) / total_hands, "VPIP": (len(calls) + len(raises)) / total_hands}
        stats.append(data)
    stat_df = pd.DataFrame(stats)
    stat_df["PFR/VPIP"] = stat_df.eval("PFR / VPIP")
    display(stat_df.round(2))

