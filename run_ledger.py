import os
import configparser
import argparse
import json
import datetime
from heapq import heapify, heappush, heappop
from googleapiclient.discovery import build
from IPython.display import display
import pandas as pd

def compute_transactions(ledger):
    assert round(sum(ledger.values()), 2) == 0
    neg = []
    pos = []
    for name, value in ledger.items():
        if value < 0:
            heappush(neg, (value, value, name))
        else:
            heappush(pos, (-value, value, name))
    transactions = []
    while neg and pos:
        _, debt, debtee = heappop(pos)
        _, payment, debtor = heappop(neg)
        unaccounted = round(debt + payment, 2)
        if unaccounted > 0:
            heappush(pos, (-unaccounted, unaccounted, debtee))
        elif unaccounted < 0:
            heappush(neg, (unaccounted, unaccounted, debtor))
        amount = min(debt, -payment)
        transactions.append((debtee, debtor, amount))
    assert len(neg) == 0
    assert len(pos) == 0
    transactions = sorted(transactions)
    return transactions

psr = argparse.ArgumentParser()
psr.add_argument("start", nargs='?', default=None)
psr.add_argument("end", nargs='?', default=None)

cfg = configparser.ConfigParser()
cfg.read("ledger.ini")
API_KEY = cfg["KEYS"]["API_KEY"]
SPREADSHEET_ID = cfg["KEYS"]["SPREADSHEET_ID"]
print(API_KEY)
print(SPREADSHEET_ID)

args = psr.parse_args()

today = datetime.date.today()

last = today - datetime.timedelta(7)
nxt = today

start = args.start if args.start is not None else str(last)
end = args.end if args.end is not None else str(nxt)


service = build('sheets', 'v4', developerKey=API_KEY)
sheet_api = service.spreadsheets()
metadata = (
    sheet_api.get(spreadsheetId=SPREADSHEET_ID)
    .execute()
)

form_responses = metadata["sheets"][0]
name = form_responses["properties"]["title"]
data = (
    sheet_api.values()
    .get(spreadsheetId=SPREADSHEET_ID, range=name)
    .execute()["values"]
)
venmo = pd.DataFrame([row[:2] for row in data], columns=["Name", "Venmo"]).dropna()
venmo.columns = ["Name", "Venmo"]
for col in venmo:
    venmo[col] = venmo[col].str.strip()

ledger_sheet_name = metadata["sheets"][1]["properties"]["title"]
data = (
    sheet_api.values()
    .get(spreadsheetId=SPREADSHEET_ID, range=ledger_sheet_name)
    .execute()["values"]
)
ledger_df = pd.DataFrame([row[:4] for row in data[1:]], columns=data[0])
ledger_df.Name = ledger_df.Name.str.strip()
ledger_df.PnL = ledger_df.PnL.astype(float).round(2)
ledger_df = ledger_df.query("Ignore != '1'")
ledger_df = ledger_df.groupby(["Date", "Name"]).sum().reset_index()
ledger_df["Date"] = pd.to_datetime(ledger_df.Date)

ledger = ledger_df.merge(venmo, on="Name", how="left")

s = pd.to_datetime(start)
e = pd.to_datetime(end)
result = ledger.query("@s <= Date <= @e").groupby(["Name", "Venmo"]).PnL.sum().reset_index()
display(result)
ledger = dict(result[["Name", "PnL"]].values)
txns = compute_transactions(ledger)
payments = pd.DataFrame(txns, columns=["To", "From", "Amount"])
payments = payments.merge(venmo, left_on="From", right_on="Name")
payments = payments.merge(venmo, left_on="To", right_on="Name", suffixes=["", "To"])
payments = payments.sort_values("To")
display(payments)

totals = result[["Name", "PnL", "Venmo"]].sort_values("Name")
print(f"Bills from {start} to {end}")
print(f"(See https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID} for reference)")
print()
print("======")
print()
for _, bill in totals.iterrows():
    sign = bill.PnL > 0
    amount = "${:.2f}".format(abs(bill.PnL))
    if not sign:
        amount = "-" + amount
    print(f"{bill.Name} ({bill.Venmo}): {amount}")
print()
print("Transactions To Settle")
print()
print("======================")
print()
for _, tx in payments.iterrows():
    amount = "${:.2f}".format(abs(tx.Amount))
    print(f"{tx.To} ({tx.VenmoTo}) requests {amount} from {tx.From} ({tx.Venmo})")
